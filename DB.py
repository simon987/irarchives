import os
import traceback
from time import sleep

import psycopg2
from psycopg2.errorcodes import UNIQUE_VIOLATION
from gmpy2 import popcount

from common import logger
from img_util import thumb_path


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
                self.cur.execute(query_string, args)
                return self.cur.fetchall()
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
                             "WHERE url = %s", (url,))

        return None if not res else res[0][0]

    def get_hash_from_url(self, url):
        with self.get_conn() as conn:
            res = conn.query("SELECT i.hash from imageurls "
                             "INNER JOIN images i on i.id = imageurls.imageid "
                             "WHERE url = %s", (url,))

        return None if not res else res[0][0]

    def get_similar_images(self, hash, distance=0):
        with self.get_conn() as conn:
            if distance <= 0:
                res = conn.query("SELECT id from images WHERE hash = %s", (hash,))
            else:
                hash = int(hash)
                hashes = conn.query("SELECT id, hash FROM images")
                return [row[0] for row in hashes if popcount(int(row[1]) ^ hash) <= distance]

        return [] if not res else res[0]

    def get_image_from_sha1(self, sha1):
        with self.get_conn() as conn:
            res = conn.query("SELECT id from images "
                             "WHERE sha1=%s", (sha1,))

        return None if not res else res[0][0]

    def insert_imageurl(self, url, imageid, albumid, postid, commentid):
        with self.get_conn() as conn:
            conn.exec("INSERT INTO imageurls (url, imageid, albumid, postid, commentid) "
                      "VALUES (%s,%s,%s,%s,%s)", (url, imageid, albumid, postid, commentid))

    def insert_image(self, imhash, width, height, size, sha1):
        with self.get_conn() as conn:
            res = conn.query("INSERT INTO images (width, height, bytes, hash, sha1) "
                             "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING returning id ",
                             (width, height, size, imhash, sha1))
            # race condition: image was inserted after the existing_by_sha1 check
            if not res:
                res = conn.query("SELECT id FROM images WHERE sha1=%s", (sha1,))

        return None if not res else res[0][0]

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

    # Search

    def build_result_for_images(self, images):
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
                "WHERE imageid = ANY (%s)", #  OR c.postid = imageurls.postid
                (list(images),)
            )

            comments = []
            posts = []

            for row in res:
                if row[3] is not None:
                    # Comment
                    comments.append({
                        "hexid": row[3], "author": row[4], "body": row[5],
                        "ups": row[6], "downs": row[7], "created": row[8],
                        "subreddit": row[9], "permalink": row[10], "postid": row[11],
                        "imageurl": row[0], "width": row[24], "height": row[25],
                        "size": row[26], "sha1": row[27], "albumurl": row[1],
                        "thumb": os.path.join(thumb_path(row[28]), str(row[28]) + ".jpg")
                    })
                else:
                    # Post
                    posts.append({
                        "hexid": row[12], "title": row[13], "url": row[14],
                        "text": row[15], "author": row[16], "permalink": row[17],
                        "subreddit": row[18], "comments": row[19], "ups": row[20],
                        "downs": row[21], "score": row[22], "created": row[23],
                        "imageurl": row[0], "width": row[24], "height": row[25],
                        "size": row[26], "sha1": row[27], "albumurl": row[1],
                        "thumb": os.path.join(thumb_path(row[28]), str(row[28]) + ".jpg")
                    })
            return comments, posts

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
            print(len(res))
        return res

    # Stats

    def get_post_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM posts")[0][0]

    def get_image_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM images")[0][0]

    def get_comment_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM comments")[0][0]

    def get_album_count(self):
        with self.get_conn() as conn:
            return conn.query("SELECT COUNT(*) FROM albums")[0][0]
