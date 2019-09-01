import binascii
import json
import os
import sys
from queue import Queue
from subprocess import getstatusoutput
from threading import Thread

import pika
from youtube_dl import YoutubeDL

from DB import DB
from Httpy import Httpy
from common import logger, DBFILE
from img_util import get_image_urls, create_thumb, image_from_buffer, get_sha1, get_hash, thumb_path
from reddit import Post, Comment, COMMENT_FIELDS, POST_FIELDS
from util import is_image_direct_link, should_parse_link, is_video, load_list
from video_util import info_from_video_buffer, flatten_video_info

SCHEMA = {
    'Posts':
        '\n\t' +
        'id        SERIAL PRIMARY KEY, \n\t' +
        'hexid     TEXT UNIQUE, \n\t' +  # base36 reddit id to comment
        'title     TEXT,    \n\t' +
        'url       TEXT,    \n\t' +
        'text      TEXT,    \n\t' +  # self-text
        'author    TEXT,    \n\t' +
        'permalink TEXT,    \n\t' +  # /r/Subreddit/comments/id/title
        'subreddit TEXT,    \n\t' +
        'comments  INTEGER, \n\t' +  # Number of comment
        'ups       INTEGER, \n\t' +
        'downs     INTEGER, \n\t' +
        'score     INTEGER, \n\t' +
        'created   INTEGER, \n\t' +  # Time in UTC
        'is_self   BOOLEAN, \n\t' +
        'over_18   BOOLEAN',

    'Comments':
        '\n\t' +
        'id      SERIAL PRIMARY KEY, \n\t' +
        'postid  INTEGER, \n\t' +  # Reference to Posts table
        'hexid   TEXT UNIQUE, \n\t' +  # base36 reddit id to comment
        'author  TEXT,    \n\t' +
        'body    TEXT,    \n\t' +
        'ups     INTEGER, \n\t' +
        'downs   INTEGER, \n\t' +
        'created INTEGER, \n\t' +  # Time in UTC
        'FOREIGN KEY(postid) REFERENCES posts(id)',

    'Images':
        '\n\t' +
        'id  SERIAL PRIMARY KEY, \n\t' +
        'sha1   TEXT UNIQUE, \n\t' +
        'hash   bytea, \n\t' +
        'width   INTEGER,     \n\t' +
        'height  INTEGER,     \n\t' +
        'bytes   INTEGER',

    'videos':
        '\n\t' +
        'id  SERIAL PRIMARY KEY, \n\t' +
        'sha1   TEXT UNIQUE, \n\t' +
        'width   INTEGER,     \n\t' +
        'height  INTEGER,     \n\t' +
        'bitrate  INTEGER,     \n\t' +
        'codec  TEXT,     \n\t' +
        'format  TEXT,     \n\t' +
        'duration  INTEGER,     \n\t' +
        'frames  INTEGER,     \n\t' +
        'bytes   INTEGER',

    'videoframes':
        'id      SERIAL PRIMARY KEY, \n\t' +
        'hash     bytea NOT NULL, \n\t' +
        'videoid     INTEGER NOT NULL, \n\t' +
        'FOREIGN KEY(videoid) REFERENCES videos(id)',

    'videourls':
        '\n\t' +
        'id      SERIAL PRIMARY KEY, \n\t' +
        'url     TEXT, \n\t' +
        'clean_url     TEXT, \n\t' +
        'videoid     INTEGER NOT NULL, \n\t' +
        'postid    INTEGER, \n\t' +
        'commentid INTEGER, \n\t' +
        'FOREIGN KEY(videoid) REFERENCES videos(id), \n\t' +
        'FOREIGN KEY(postid)    REFERENCES posts(id),     \n\t' +
        'FOREIGN KEY(commentid) REFERENCES comments(id)',

    'Albums':
        '\n\t' +
        'id  SERIAL PRIMARY KEY, \n\t' +
        'url TEXT UNIQUE',

    'ImageURLs':
        '\n\t' +
        'id      SERIAL PRIMARY KEY, \n\t' +
        'url     TEXT, \n\t' +
        'clean_url TEXT, \n\t'
        'imageid     INTEGER NOT NULL, \n\t' +
        'albumid   INTEGER, \n\t' +
        'postid    INTEGER, \n\t' +
        'commentid INTEGER, \n\t' +
        'FOREIGN KEY(imageid) REFERENCES images(id), \n\t' +
        'FOREIGN KEY(postid)    REFERENCES posts(id),     \n\t' +
        'FOREIGN KEY(commentid) REFERENCES comments(id),  \n\t' +
        'FOREIGN KEY(albumid)   REFERENCES albums(id)',

}


class Consumer:

    def __init__(self):
        self.db = DB(DBFILE, **SCHEMA)
        self.web = Httpy()
        self._rabbitmq = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self._rabbitmq_channel = self._rabbitmq.channel()
        self._rabbitmq_channel.exchange_declare(exchange='reddit', exchange_type='topic')
        self._rabbitmq_queue = self._rabbitmq_channel.queue_declare('', exclusive=True)
        self._q = Queue()

    def run(self):
        for sub in load_list("subs.txt"):
            self._rabbitmq_channel.queue_bind(exchange='reddit',
                                              queue=self._rabbitmq_queue.method.queue,
                                              routing_key="*.%s" % sub)

        def msg_callback(ch, method, properties, body):
            self._q.put(body)

        self._rabbitmq_channel.basic_consume(queue=self._rabbitmq_queue.method.queue,
                                             on_message_callback=msg_callback,
                                             auto_ack=True)
        for _ in range(0, 30):
            t = Thread(target=self._message_callback_worker)
            t.start()
        self._rabbitmq_channel.start_consuming()

    def _message_callback(self, body, web):
        j = json.loads(body)

        if "title" in j:
            self.parse_post(Post(*(j[k] for k in POST_FIELDS)), web)
        else:
            self.parse_comment(Comment(*(j[k] for k in COMMENT_FIELDS)), web)

    def _message_callback_worker(self):
        logger.info("Started message callback worker")
        web = Httpy()
        while True:
            try:
                body = self._q.get()
                self._message_callback(body, web)
            except Exception as e:
                logger.error(e)
            finally:
                self._q.task_done()

    def parse_post(self, post, web):
        # Add post to database
        postid_db = self.db.insert_post(post.id, post.title, post.url, post.selftext,
                                        post.author, post.permalink, post.subreddit, post.num_comments,
                                        post.ups, post.downs, post.score,
                                        int(post.created_utc), post.is_self, post.over_18)

        if postid_db is None:
            logger.debug('Ignoring post (already indexed)')
            return False

        for url in post.urls:
            self.parse_url(url, web, postid=postid_db)

    def parse_comment(self, comment, web):

        if comment.urls:
            postid = self.db.get_postid_from_hexid(comment.link_id[3:])
            if not postid:
                return
            comid_db = self.db.insert_comment(postid, comment.id, comment.author,
                                              comment.body, comment.ups, comment.downs, comment.created_utc)
            for url in comment.urls:
                self.parse_url(url, web, postid=postid, commentid=comid_db)

    def parse_url(self, url, web, postid=None, commentid=None):
        """ Gets image hash(es) from URL, populates database """

        if is_image_direct_link(url):
            self.parse_image(url, web, postid=postid, commentid=commentid, albumid=None)
            return True

        if is_video(url):
            self.parse_video(url, web, postid=postid, commentid=commentid)
            return True

        if "v.redd.it" in url:
            logger.debug("Using youtube-dl to get reddit video url")
            ytdl = YoutubeDL()
            info = ytdl.extract_info(url, download=False, process=False)

            best = max(info["formats"], key=lambda x: x["width"] if "width" in x and x["width"] else 0)
            self.parse_video(best["url"], web, postid=postid, commentid=commentid)
            return

        if not should_parse_link(url):
            return

        image_urls = get_image_urls(url)

        # We assume that any url that yields more than 1 image is an album
        albumid = None
        if len(image_urls) > 1:
            albumid = self.db.get_or_create_album(url)  # TODO: fix url len thing

        for image_url in image_urls:
            if is_image_direct_link(image_url):
                self.parse_image(image_url, web, postid=postid, commentid=commentid, albumid=albumid)
            elif is_video(image_url):
                self.parse_video(image_url, web, postid=postid, commentid=commentid)
        return True

    def parse_image(self, url, web, postid=None, commentid=None, albumid=None):
        existing_by_url = self.db.get_image_from_url(url)
        if existing_by_url:
            self.db.insert_imageurl(url=url, imageid=existing_by_url, postid=postid, commentid=commentid,
                                    albumid=albumid)
            return

        try:
            image_buffer = web.download(url)

            sha1 = get_sha1(image_buffer)
            existing_by_sha1 = self.db.get_image_from_sha1(sha1)
            if existing_by_sha1:
                self.db.insert_imageurl(url=url, imageid=existing_by_sha1, postid=postid, commentid=commentid,
                                        albumid=albumid)
                return

            im = image_from_buffer(image_buffer)
            imhash = get_hash(im)
            width, height = im.size
            size = len(image_buffer)

            imageid = self.db.insert_image(imhash, width, height, size, sha1)
            self.db.insert_imageurl(url, imageid=imageid, albumid=albumid, postid=postid, commentid=commentid)
            create_thumb(im, imageid)
            del im
            del image_buffer

            logger.info("(+) Image ID(%s) [%dx%s %dB] #%s" %
                        (
                            imageid, width, height, size,
                            binascii.hexlify(imhash).decode("ascii")
                        ))
        except Exception as e:
            logger.error(e)

    def parse_video(self, url, web, postid=None, commentid=None):
        existing_by_url = self.db.get_video_from_url(url)
        if existing_by_url:
            self.db.insert_videourl(url=url, video_id=existing_by_url, postid=postid, commentid=commentid)
            return

        try:
            video_buffer = web.download(url)

            if not video_buffer:
                raise Exception("Download failed %s" % url)
        except Exception as e:
            logger.error(e)
            return

        sha1 = get_sha1(video_buffer)
        existing_by_sha1 = self.db.get_video_from_sha1(sha1)
        if existing_by_sha1:
            self.db.insert_videourl(url=url, video_id=existing_by_sha1, postid=postid, commentid=commentid)
            return

        frames, info = info_from_video_buffer(video_buffer, url[url.rfind(".") + 1:].replace("gifv", "mp4"))
        if not frames:
            logger.error("No frames " + url)
            return

        info = flatten_video_info(info)

        video_id = self.db.insert_video(sha1, size=len(video_buffer), info=info)
        self.db.insert_videourl(url, video_id, postid, commentid)

        frame_ids = self.db.insert_video_frames(video_id, frames)

        for i, thumb in enumerate(frames.values()):
            dirpath = thumb_path(frame_ids[i], "vid")
            os.makedirs(dirpath, exist_ok=True)
            thumb.save(os.path.join(dirpath, "%d.jpg" % frame_ids[i]))

        logger.info("(+) Video ID(%s) [%dx%s %dB] %d frames" %
                    (video_id, info["width"], info["height"],
                     len(video_buffer), len(frames)))


if __name__ == '__main__':
    try:
        consumer = Consumer()
        consumer.run()

    except KeyboardInterrupt:
        logger.error('Interrupted (^C)')
