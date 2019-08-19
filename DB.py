import os
import traceback
from time import sleep

import psycopg2
from psycopg2.errorcodes import UNIQUE_VIOLATION

from common import logger, SQL_DEBUG
from img_util import thumb_path
from util import clean_url


class SearchResult:
    __slots__ = "permalink", "subreddit", "created", \
                "author", "item", "ups", "downs", "hexid", "author"

    def __init__(self, permalink, subreddit, created, item, ups, downs, hexid, author):
        self.permalink = permalink
        self.subreddit = subreddit
        self.created = created
        self.item = item
        self.ups = ups
        self.downs = downs
        self.hexid = hexid
        self.author = author

    def json(self):
        raise NotImplementedError


class CommentSearchResult(SearchResult):
    __slots__ = "body", "post_id"

    def __init__(self, body, post_id, permalink, subreddit, created, item,
                 ups, downs, hexid, author):
        super().__init__(permalink, subreddit, created, item,
                         ups, downs, hexid, author)

        self.body = body
        self.post_id = post_id

    def json(self):
        return {
            "body": self.body,
            "post_id": self.post_id,
            "permalink": self.permalink,
            "subreddit": self.subreddit,
            "created": self.created,
            "ups": self.ups,
            "downs": self.downs,
            "hexid": self.hexid,
            "author": self.author,
            "item": self.item.json(),
            "type": "comment",
        }


class PostSearchResult(SearchResult):
    __slots__ = "title", "text", "comments"

    def __init__(self, title, text, comments, permalink, subreddit,
                 created, item, ups, downs, hexid, author):
        super().__init__(permalink, subreddit, created,
                         item, ups, downs, hexid, author)

        self.title = title
        self.text = text
        self.comments = comments

    def json(self):
        return {
            "title": self.title,
            "text": self.text,
            "comments": self.comments,
            "permalink": self.permalink,
            "subreddit": self.subreddit,
            "created": self.created,
            "ups": self.ups,
            "downs": self.downs,
            "hexid": self.hexid,
            "author": self.author,
            "item": self.item.json(),
            "type": "post",
        }


class ImageItem:
    __slots__ = "url", "width", "height", "size", "thumb", "sha1", "album_url"

    def __init__(self, url, width, height, size, thumb, sha1, album_url):
        self.url = url
        self.width = width
        self.height = height
        self.size = size
        self.sha1 = sha1
        self.thumb = thumb
        self.album_url = album_url

    def json(self):
        return {
            "type": "image",
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "size": self.size,
            "sha1": self.sha1,
            "thumb": self.thumb,
            "album_url": self.album_url,
        }


class VideoItem:
    __slots__ = "url", "width", "height", "size", "bitrate", "codec", "format", "sha1", "duration", \
                "frames", "video_id"

    def __init__(self, url, width, height, size, bitrate, codec, format, duration,
                 frames, sha1, video_id):
        self.url = url
        self.width = width
        self.height = height
        self.size = size
        self.bitrate = bitrate
        self.codec = codec
        self.format = format
        self.duration = duration
        self.frames = frames
        self.sha1 = sha1
        self.video_id = video_id

    def json(self):
        return {
            "type": "video",
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "size": self.size,
            "sha1": self.sha1,
            "video_id": self.video_id,
            "bitrate": self.bitrate,
            "codec": self.codec,
            "format": self.format,
            "duration": self.duration,
            "frames": self.frames,
        }


class PgConn:
    def __init__(self, conn, conn_str):
        self.conn = conn
        self.conn_str = conn_str
        self.cur = conn.cursor()

    def __enter__(self):
        return self

    def exec(self, query_string, args=None):
        if args is None:
            args = []
        while True:
            try:
                self.cur.execute(query_string, args)
                break
            except psycopg2.Error as e:
                if e.pgcode == UNIQUE_VIOLATION:
                    break
                traceback.print_stack()
                self._handle_err(e, query_string, args)

    def query(self, query_string, args=None):
        while True:
            try:
                if SQL_DEBUG:
                    logger.debug(query_string)
                    logger.debug("With args " + str(args))

                self.cur.execute(query_string, args)
                res = self.cur.fetchall()

                if SQL_DEBUG:
                    logger.debug("result: " + str(res))

                return res
            except psycopg2.Error as e:
                if e.pgcode == UNIQUE_VIOLATION:
                    break
                self._handle_err(e, query_string, args)

    def _handle_err(self, err, query, args):
        logger.warn("Error during query '%s' with args %s: %s %s (%s)" % (query, args, type(err), err, err.pgcode))
        self.conn = psycopg2.connect(self.conn_str)
        self.cur = self.conn.cursor()
        sleep(0.1)

    def __exit__(self, type, value, traceback):
        try:
            self.conn.commit()
            self.cur.close()
        except:
            pass


class DB:

    def __init__(self, db_file, **schemas):
        """
        Initializes database.
        Attempts to creates tables with schemas if needed.
            * db_file - Name of the database file.
            * schemas - A python dictionary where:
                KEY is the table name,
                VALUE is that table's schema.

        For example:
            db = DB('file.db', {
                'Customer': 'name text, phone int, address text',
                'Order':    'id int primary key, customer_name text, cost real'})
            # This would open the 'file.db' file and create two tables with the respective schemas.
            If the tables already exist, the existing tables remain unaltered.
        """
        self.db_file = db_file
        self.conn = psycopg2.connect(self.db_file)

        # Don't create tables if not supplied.
        if schemas is not None and schemas != {} and schemas:

            # Create table for every schema given.
            for key in schemas:
                self._create_table(key, schemas[key])

    def get_conn(self):
        return PgConn(self.conn, self.db_file)

    def _create_table(self, table_name, schema):
        """Creates new table with schema"""
        with self.get_conn() as conn:
            conn.exec('''CREATE TABLE IF NOT EXISTS %s (%s)''' % (table_name, schema))

    def get_image_from_url(self, url):
        with self.get_conn() as conn:
            res = conn.query("SELECT i.id from imageurls "
                             "INNER JOIN images i on i.id = imageurls.imageid "
                             "WHERE clean_url = %s", (clean_url(url),))

        return None if not res else res[0][0]

    def get_image_hash_from_url(self, url):
        with self.get_conn() as conn:
            res = conn.query("SELECT i.hash from imageurls "
                             "INNER JOIN images i on i.id = imageurls.imageid "
                             "WHERE clean_url = %s", (url,))

        return None if not res else res[0][0]

    def get_similar_images(self, hash, distance=0):
        with self.get_conn() as conn:
            # TODO: LIMIT X
            if distance <= 0:
                res = conn.query("SELECT id from images WHERE hash = %s", (hash,))
            else:
                res = conn.query(
                    "SELECT id FROM images WHERE hash_is_within_distance(hash, %s, %s)",
                    (hash, distance,)
                )

        return [] if not res else [row[0] for row in res]

    def get_similar_videos_by_hash(self, hashes, distance, frame_count):
        with self.get_conn() as conn:
            # TODO: LIMIT X
            if distance == 0:
                res = conn.query(
                    "SELECT videos.id from videoframes "
                    "INNER JOIN videos on videos.id = videoid "
                    "WHERE hash_equ_any(hash, %s) "
                    "GROUP BY videos.id "
                    "HAVING COUNT(videoframes.id) >= %s",
                    (b''.join(hashes), frame_count)
                )
            else:
                res = conn.query(
                    "SELECT videos.id from videoframes "
                    "INNER JOIN videos on videos.id = videoid "
                    "WHERE hash_is_within_distance_any(hash, %s, %s) "
                    "GROUP BY videos.id "
                    "HAVING COUNT(videoframes.id) >= %s",
                    (b''.join(hashes), distance, frame_count)
                )

        return [] if not res else [row[0] for row in res]

    def get_image_from_sha1(self, sha1):
        with self.get_conn() as conn:
            res = conn.query("SELECT id from images "
                             "WHERE sha1=%s", (sha1,))

        return None if not res else res[0][0]

    def insert_imageurl(self, url, imageid, albumid, postid, commentid):
        with self.get_conn() as conn:
            conn.exec("INSERT INTO imageurls (url, clean_url, imageid, albumid, postid, commentid) "
                      "VALUES (%s,%s,%s,%s,%s,%s)", (url, clean_url(url), imageid, albumid, postid, commentid))

    def insert_image(self, imhash, width, height, size, sha1):
        with self.get_conn() as conn:
            res = conn.query("INSERT INTO images (width, height, bytes, hash, sha1) "
                             "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING returning id ",
                             (width, height, size, imhash, sha1))
            # race condition: image was inserted after the existing_by_sha1 check
            if not res:
                res = conn.query("SELECT id FROM images WHERE sha1=%s", (sha1,))

        return None if not res else res[0][0]

    def insert_video(self, sha1, size=0, info={}):
        with self.get_conn() as conn:
            res = conn.query("INSERT INTO videos "
                             "(sha1, width, height, bitrate, codec, format, duration, frames, bytes) "
                             "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING returning id ",
                             (sha1, info["width"], info["height"], info["bitrate"], info["codec"], info["format"],
                              info["duration"], info["frames"], size))
            # race condition: video was inserted after the existing_by_sha1 check
            if not res:
                res = conn.query("SELECT id FROM videos WHERE sha1=%s", (sha1,))

        return None if not res else res[0][0]

    def insert_videourl(self, url, video_id, postid, commentid):
        with self.get_conn() as conn:
            conn.exec("INSERT INTO videourls (url, clean_url, videoid, postid, commentid) "
                      "VALUES (%s,%s,%s,%s,%s)", (url, clean_url(url), video_id, postid, commentid))

    def insert_video_frames(self, video_id, frames):
        with self.get_conn() as conn:
            res = conn.query(
                "INSERT INTO videoframes (hash, videoid) VALUES " +
                ", ".join("(%%s,%d)" % (video_id,) for _ in frames) +
                " RETURNING id",
                list(i for i in frames)
            )

        return None if not res else [r[0] for r in res]

    def get_video_from_url(self, url):
        with self.get_conn() as conn:
            res = conn.query("SELECT v.id from videourls "
                             "INNER JOIN videos v on v.id = videourls.videoid "
                             "WHERE clean_url = %s", (clean_url(url),))

        return None if not res else res[0][0]

    def get_video_from_sha1(self, sha1):
        with self.get_conn() as conn:
            res = conn.query("SELECT id from videos "
                             "WHERE sha1=%s", (sha1,))
        return None if not res else res[0][0]

    def get_videoframes(self, video_id):
        with self.get_conn() as conn:
            res = conn.query("SELECT id from videoframes "
                             "WHERE videoid=%s", (video_id,))
        return None if not res else [r[0] for r in res]

    def get_video_hashes(self, video_id):
        with self.get_conn() as conn:
            res = conn.query("SELECT hash from videoframes "
                             "WHERE videoid=%s", (video_id,))
        return None if not res else [r[0] for r in res]

    def get_or_create_album(self, url):
        with self.get_conn() as conn:
            res = conn.query("INSERT INTO albums (url) VALUES (%s) ON CONFLICT DO NOTHING RETURNING ID", (url,))

            # album already exists..
            if not res:
                res = conn.query("SELECT id FROM albums WHERE url=%s", (url,))

        return None if not res else res[0][0]

    def insert_comment(self, postid, comment_id, comment_author,
                       comment_body, comment_upvotes, comment_downvotes, comment_created_utc):
        with self.get_conn() as conn:
            res = conn.query("INSERT INTO comments (postid, hexid, author, body, ups, downs, created)"
                             " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING ID",
                             (postid, comment_id, comment_author, comment_body, comment_upvotes, comment_downvotes,
                              comment_created_utc))
        return None if not res else res[0][0]

    def insert_post(self, post_id, title, url, selftext,
                    author, permalink, subreddit, num_comments,
                    upvotes, downvotes, score,
                    created_utc, is_self, over_18):

        with self.get_conn() as conn:
            res = conn.query(
                "INSERT INTO posts (hexid, title, url, text, author, permalink,"
                " subreddit, comments, ups, downs, score, created, is_self, over_18)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING ID",
                (post_id, title, url, selftext, author, permalink, subreddit, num_comments,
                 upvotes, downvotes, score, created_utc, is_self, over_18))
        return None if not res else res[0][0]

    def get_postid_from_hexid(self, hexid):
        with self.get_conn() as conn:
            res = conn.query(
                "SELECT id FROM posts WHERE hexid=%s",
                (hexid, ))
        return None if not res else res[0]

    # Search

    def build_result_for_images(self, images):

        results = []

        with self.get_conn() as conn:
            # TODO: order by?
            res = conn.query(
                "SELECT imageurls.url, a.url,"
                "c.postid, c.hexid, c.author, c.body, c.ups, c.downs, c.created,"
                "cp.subreddit, cp.permalink, cp.hexid, "
                "p.hexid, p.title, p.url, p.text, p.author, p.permalink, p.subreddit, p.comments,"
                " p.ups, p.downs, p.score, p.created,"
                "im.width, im.height, im.bytes, im.sha1, imageid "
                "from imageurls "
                "LEFT JOIN albums a on imageurls.albumid = a.id "
                "LEFT JOIN comments c on imageurls.commentid = c.id "
                "   LEFT JOIN posts cp on c.postid = cp.id "
                "LEFT JOIN posts p on imageurls.postid = p.id "
                "LEFT JOIN images im on imageurls.imageid = im.id "
                "WHERE imageid = ANY (%s)",  # OR c.postid = imageurls.postid
                (list(images),)
            )

            for row in res:
                if row[3] is not None:
                    results.append(CommentSearchResult(
                        body=row[5],
                        post_id=row[11],
                        hexid=row[3],
                        author=row[4],
                        ups=row[6],
                        downs=row[7],
                        created=row[8],
                        subreddit=row[9],
                        permalink=row[10],
                        item=ImageItem(
                            url=row[0],
                            width=row[24],
                            height=row[25],
                            size=row[26],
                            thumb=os.path.join(thumb_path(row[28]), str(row[28]) + ".jpg"),
                            sha1=row[27],
                            album_url=row[1]
                        )
                    ))
                else:
                    results.append(PostSearchResult(
                        text=row[15],
                        title=row[13],
                        hexid=row[12],
                        author=row[16],
                        ups=row[20],
                        downs=row[21],
                        created=row[23],
                        subreddit=row[18],
                        permalink=row[17],
                        comments=row[19],
                        item=ImageItem(
                            url=row[0],
                            width=row[24],
                            height=row[25],
                            size=row[26],
                            thumb=os.path.join(thumb_path(row[28]), str(row[28]) + ".jpg"),
                            sha1=row[27],
                            album_url=row[1]
                        )
                    ))
            return results

    def build_results_for_videos(self, videos):

        results = []

        with self.get_conn() as conn:
            # TODO: order by?
            res = conn.query(
                "SELECT videourls.url,"
                "c.postid, c.hexid, c.author, c.body, c.ups, c.downs, c.created,"
                "cp.subreddit, cp.permalink, cp.hexid, "
                "p.hexid, p.title, p.url, p.text, p.author, p.permalink, p.subreddit, p.comments,"
                " p.ups, p.downs, p.score, p.created,"
                "vid.width, vid.height, vid.bytes, vid.sha1, vid.frames, vid.duration, vid.format,"
                " vid.codec, vid.bitrate, videourls.videoid "
                "from videourls "
                "LEFT JOIN comments c on videourls.commentid = c.id "
                "   LEFT JOIN posts cp on c.postid = cp.id "
                "LEFT JOIN posts p on videourls.postid = p.id "
                "LEFT JOIN videos vid on videourls.videoid = vid.id "
                "WHERE videourls.videoid = ANY (%s)",  # OR c.postid = imageurls.postid
                (list(videos),)
            )

            for row in res:
                if row[2] is not None:
                    results.append(CommentSearchResult(
                        body=row[4],
                        post_id=row[10],
                        hexid=row[2],
                        author=row[3],
                        ups=row[5],
                        downs=row[6],
                        created=row[7],
                        subreddit=row[8],
                        permalink=row[9],
                        item=VideoItem(
                            url=row[0],
                            width=row[23],
                            height=row[24],
                            size=row[25],
                            sha1=row[26],
                            frames=row[27],
                            duration=row[28],
                            format=row[29],
                            codec=row[30],
                            bitrate=row[31],
                            video_id=row[32]
                        )
                    ))
                else:
                    results.append(PostSearchResult(
                        text=row[14],
                        title=row[12],
                        hexid=row[11],
                        author=row[15],
                        ups=row[19],
                        downs=row[20],
                        created=row[22],
                        subreddit=row[17],
                        permalink=row[16],
                        comments=row[18],
                        item=VideoItem(
                            url=row[0],
                            width=row[23],
                            height=row[24],
                            size=row[25],
                            sha1=row[26],
                            frames=row[27],
                            duration=row[28],
                            format=row[29],
                            codec=row[30],
                            bitrate=row[31],
                            video_id=row[32]
                        )
                    ))
            return results

    def get_images_from_reddit_id(self, reddit_id):
        with self.get_conn() as conn:
            if len(reddit_id) == 6:
                res = conn.query(
                    "SELECT DISTINCT imageid from imageurls "
                    "LEFT JOIN posts p on imageurls.postid = p.id "
                    "WHERE p.hexid=%s",
                    (reddit_id,)
                )
            elif len(reddit_id) == 7:
                res = conn.query(
                    "SELECT DISTINCT imageid from imageurls "
                    "LEFT JOIN comments c on imageurls.commentid = c.id "
                    "WHERE c.hexid=%s",
                    (reddit_id,)
                )
            else:
                raise Exception("Invalid reddit id")
        return res

    def get_images_from_author(self, author):

        with self.get_conn() as conn:
            res = conn.query(
                "SELECT imageid from imageurls WHERE "
                "postid IN (SELECT id FROM Posts WHERE author LIKE %s ORDER BY ups DESC LIMIT 50) "
                "OR commentid IN (SELECT id FROM Comments WHERE author LIKE %s ORDER BY ups DESC LIMIT 50) ",
                (author, author)
            )
        return res

    def get_images_from_album_url(self, album_url):
        with self.get_conn() as conn:
            res = conn.query(
                "SELECT i.id, u.url from albums "
                "INNER JOIN imageurls u on albums.id = u.albumid "
                "INNER JOIN images i on u.imageid = i.id WHERE albums.url = %s",
                (album_url,)
            )
        return res

    def get_images_from_text(self, text):
        with self.get_conn() as conn:
            text = "%" + text + "%"
            res = conn.query(
                "SELECT DISTINCT(imageid) FROM imageurls "
                "WHERE commentid is NULL AND postid IN "
                "(SELECT id FROM Posts WHERE title LIKE %s or text LIKE %s ORDER BY ups DESC) "
                "OR commentid IN "
                "(SELECT id FROM Comments WHERE body LIKE %s ORDER BY ups DESC) "
                "LIMIT 50",
                (text, text, text)
            )
        return res

    # Stats

    def get_post_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM posts")[0][0]

    def get_image_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM images")[0][0]

    def get_videoframe_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM videoframes")[0][0]

    def get_comment_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM comments")[0][0]

    def get_album_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM albums")[0][0]
