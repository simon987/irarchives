#!/usr/bin/python

"""
What this script does:
    1. Scans reddit.com subreddits for new posts/comments
    2. Retrieves images from day-old posts/comments
    3. Stores image information (hash, size, etc) in a database
    4. If post/comment contains image/link, stores post/comment info in database
"""
import binascii
import os
import sys
import time
from subprocess import getstatusoutput

import ReddiWrap
from DB import DB
from Httpy import Httpy
from common import logger, DBFILE
from img_util import get_image_urls, create_thumb, image_from_buffer, get_sha1, get_hash, thumb_path
from util import load_list, get_links_from_body, is_image_direct_link, clean_url, \
    should_parse_link, is_video
from video_util import info_from_video_buffer, flatten_video_info

reddit = ReddiWrap.ReddiWrap()

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
        'hash   NUMERIC, \n\t' +
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
        'hash     NUMERIC NOT NULL, \n\t' +
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
        'imageid     INTEGER NOT NULL, \n\t' +
        'albumid   INTEGER, \n\t' +
        'postid    INTEGER, \n\t' +
        'commentid INTEGER, \n\t' +
        'FOREIGN KEY(imageid) REFERENCES images(id), \n\t' +
        'FOREIGN KEY(postid)    REFERENCES posts(id),     \n\t' +
        'FOREIGN KEY(commentid) REFERENCES comments(id),  \n\t' +
        'FOREIGN KEY(albumid)   REFERENCES albums(id)',

}


def exit_if_already_started():
    (status, output) = getstatusoutput('ps aux')
    running_processes = 0
    for line in output.split('\n'):
        if 'python' in line and 'scan.py' in line and '/bin/sh -c' not in line:
            running_processes += 1
    if running_processes > 1:
        logger.error("process is already running, exiting")
        sys.exit(0)


class Scanner:

    def __init__(self):
        self.db = DB(DBFILE, **SCHEMA)
        self.web = Httpy()

    def run(self):
        """
            Main loop of program.
            Infinitely iterates over the list of subreddits
        """
        exit_if_already_started()
        while True:
            for timeframe in ['all', 'month', 'week']:
                subreddits = load_list('subs.txt')
                while subreddits:
                    # Grab all images/comments from sub, remove from list
                    self.parse_subreddit(subreddits.pop(0), timeframe)

    def parse_subreddit(self, subreddit, timeframe):
        """ Parses top 1,000 posts from subreddit within time frame. """

        total_post_count = 0
        current_post_index = 0

        while True:
            query_text = '/r/%s/top?t=%s' % (subreddit, timeframe)
            if total_post_count == 0:
                logger.info('Loading first page of %s' % query_text)
                posts = reddit.get(query_text)

            elif reddit.has_next():
                logger.info('[+] Loading  next page of %s' % query_text)
                posts = reddit.get_next()
            else:
                # No more pages to load
                break

            if posts is None or not posts:
                logger.warning('No posts found')
                return

            total_post_count += len(posts)

            for post in posts:
                current_post_index += 1
                logger.info('[%3d/%3d] Scraping http://redd.it/%s %s' %
                            (current_post_index, total_post_count, post.id, post.url[:50]))

                self.parse_post(post)

    def parse_post(self, post):
        """ Scrapes and indexes a post and it's comments. """
        # Ignore posts less than 24 hours old
        if time.time() - post.created < 60 * 60 * 24:
            logger.debug('Ignoring post (too new)')
            return False

        # Add post to database
        postid_db = self.db.insert_post(post.id, post.title, post.url, post.selftext,
                                        post.author, post.permalink, post.subreddit, post.num_comments,
                                        post.upvotes, post.downvotes, post.score,
                                        int(post.created_utc), post.is_self, post.over_18)

        if postid_db is None:
            logger.debug('Ignoring post (already indexed)')
            return False

        if post.selftext != '':
            urls = get_links_from_body(post.selftext)
            for url in urls:
                self.parse_url(url, postid=postid_db)
        else:
            self.parse_url(post.url, postid=postid_db)

        # Iterate over top-level comments
        if post.num_comments > 0:
            reddit.fetch_comments(post)
            for comment in post.comments:
                self.parse_comment(comment, postid_db)

    def parse_comment(self, comment, postid):
        """
            Parses links from a comment. Populates DB.
            Recursively parses child comments.
        """
        urls = get_links_from_body(comment.body)
        if urls:
            # Only insert comment into DB if it contains a link
            comid_db = self.db.insert_comment(postid, comment.id, comment.author,
                                              comment.body, comment.upvotes, comment.downvotes, comment.created_utc)
            for url in urls:
                self.parse_url(url, postid=postid, commentid=comid_db)
        # Recurse over child comments
        for child in comment.children:
            self.parse_comment(child, postid)

    def parse_url(self, url, postid=None, commentid=None):
        """ Gets image hash(es) from URL, populates database """

        if is_image_direct_link(url):
            self.parse_image(url, postid=postid, commentid=commentid, albumid=None)
            return True

        if is_video(url):
            self.parse_video(url, postid=postid, commentid=commentid)
            return True

        if not should_parse_link(url):
            return

        image_urls = get_image_urls(url)
        url = clean_url(url)

        # We assume that any url that yields more than 1 image is an album
        albumid = None
        if len(image_urls) > 1:
            albumid = self.db.get_or_create_album(url)  # TODO: fix url len thing

        for image_url in image_urls:
            if is_image_direct_link(image_url):
                self.parse_image(image_url, postid, commentid, albumid)
            elif is_video(image_url):
                self.parse_video(image_url, postid, commentid)
        return True

    def parse_image(self, url, postid=None, commentid=None, albumid=None):

        existing_by_url = self.db.get_image_from_url(url)
        if existing_by_url:
            self.db.insert_imageurl(url=url, imageid=existing_by_url, postid=postid, commentid=commentid,
                                    albumid=albumid)
            return

        try:
            image_buffer = self.web.download(url)

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

    def parse_video(self, url, postid=None, commentid=None):

        existing_by_url = self.db.get_video_from_url(url)
        if existing_by_url:
            self.db.insert_videourl(url=url, video_id=existing_by_url, postid=postid, commentid=commentid)
            return

        try:
            video_buffer = self.web.download(url)
        except Exception as e:
            if not str(e).startswith("HTTP"):
                raise e
            logger.error(e)
            return

        sha1 = get_sha1(video_buffer)
        existing_by_sha1 = self.db.get_video_from_sha1(sha1)
        if existing_by_sha1:
            self.db.insert_videourl(url=url, video_id=existing_by_sha1, postid=postid, commentid=commentid)
            return

        frames, info = info_from_video_buffer(video_buffer, url[url.rfind(".") + 1:].replace("gifv", "mp4"))
        if not frames:
            logger.error("no frames todo elaborate")
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
        scanner = Scanner()
        scanner.run()

    except KeyboardInterrupt:
        logger.error('Interrupted (^C)')
