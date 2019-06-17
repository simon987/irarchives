#!/usr/bin/python

"""
What this script does:
    1. Scans reddit.com subreddits for new posts/comments
    2. Retrieves images from day-old posts/comments
    3. Stores image information (hash, size, etc) in a database
    4. If post/comment contains image/link, stores post/comment info in database
"""

import sys
import time
from itertools import repeat
from multiprocessing.pool import ThreadPool
from os import remove
from subprocess import getstatusoutput

import ReddiWrap
from DB import DB
from Httpy import Httpy
from ImageHash import avhash, create_thumb, image_from_buffer
from common import logger, DBFILE
from img_util import get_image_urls
from util import load_list, get_links_from_body, should_download_image, is_direct_link, clean_url, \
    should_parse_link

reddit = ReddiWrap.ReddiWrap()
web = Httpy()

SCHEMA = {
    'Posts':
        '\n\t' +
        'id        INTEGER PRIMARY KEY, \n\t' +
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
        'is_self   NUMERIC, \n\t' +
        'over_18   NUMERIC',

    'Comments':
        '\n\t' +
        'id      INTEGER PRIMARY KEY, \n\t' +
        'postid  INTEGER, \n\t' +  # Reference to Posts table
        'hexid   TEXT UNIQUE, \n\t' +  # base36 reddit id to comment
        'author  TEXT,    \n\t' +
        'body    TEXT,    \n\t' +
        'ups     INTEGER, \n\t' +
        'downs   INTEGER, \n\t' +
        'created INTEGER, \n\t' +  # Time in UTC
        'FOREIGN KEY(postid) REFERENCES Posts(id)',

    'Hashes':
        '\n\t' +
        'id   INTEGER PRIMARY KEY, \n\t' +
        'hash TEXT UNIQUE',

    'ImageURLs':
        '\n\t' +
        'id      INTEGER PRIMARY KEY, \n\t' +
        'url     TEXT UNIQUE, \n\t' +
        'hashid  INTEGER,     \n\t' +  # Reference to Hashes table
        'width   INTEGER,     \n\t' +
        'height  INTEGER,     \n\t' +
        'bytes   INTEGER,     \n\t' +
        'FOREIGN KEY(hashid) REFERENCES Hashes(id)',

    'Albums':
        '\n\t' +
        'id  INTEGER PRIMARY KEY, \n\t' +
        'url TEXT UNIQUE',

    'Images':
        '\n\t' +
        'urlid     INTEGER, \n\t' +  # Reference to ImageURLs table
        'hashid    INTEGER, \n\t' +  # Reference to Hashes table
        'albumid   INTEGER, \n\t' +  # Reference to Albums table   (0 if none)
        'postid    INTEGER, \n\t' +  # Reference to Posts table
        'commentid INTEGER, \n\t' +  # Reference to Comments table (0 if post)
        'FOREIGN KEY(urlid)     REFERENCES ImageURLs(id), \n\t' +
        'FOREIGN KEY(hashid)    REFERENCES Hashes(id),    \n\t' +
        'FOREIGN KEY(albumid)   REFERENCES Albums(id),    \n\t' +
        'FOREIGN KEY(postid)    REFERENCES Posts(id),     \n\t' +
        'FOREIGN KEY(commentid) REFERENCES Comments(id),  \n\t' +
        'PRIMARY KEY(urlid, postid, commentid)'
    # Prevent a post or comment from having more than two of the same exact image
}
db = DB(DBFILE, **SCHEMA)


def main():
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
                parse_subreddit(subreddits.pop(0), timeframe)


def exit_if_already_started():
    (status, output) = getstatusoutput('ps aux')
    running_processes = 0
    for line in output.split('\n'):
        if 'python' in line and 'scan.py' in line and '/bin/sh -c' not in line:
            running_processes += 1
    if running_processes > 1:
        logger.error("process is already running, exiting")
        sys.exit(0)


def parse_subreddit(subreddit, timeframe):
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

            parse_post(post)


def parse_post(post):
    """ Scrapes and indexes a post and it's comments. """
    # Ignore posts less than 24 hours old
    if time.time() - post.created < 60 * 60 * 24:
        logger.debug('Ignoring post (too new)')
        return False

    # Add post to database
    postid_db = db.insert('Posts',
                          (None,
                           post.id,
                           post.title,
                           post.url,
                           post.selftext,
                           post.author,
                           post.permalink,
                           post.subreddit,
                           post.num_comments,
                           post.upvotes,
                           post.downvotes,
                           post.score,
                           post.created_utc,
                           int(post.is_self),
                           int(post.over_18)))
    # If post already exists, we've already indexed it; skip!
    if postid_db == -1:
        logger.debug('Ignoring post (already indexed)')
        return False
    # Write post to DB so we don't hit it again

    # NOTE: postid_db is the ID of the post in the database; NOT on reddit

    # Check for self-post
    if post.selftext != '':
        urls = get_links_from_body(post.selftext)
        for url in urls:
            parse_url(url, postid=postid_db)
    else:
        # Attempt to retrieve hash(es) from link
        parse_url(post.url, postid=postid_db)

    # Iterate over top-level comments
    if post.num_comments > 0:
        reddit.fetch_comments(post)
        for comment in post.comments:
            parse_comment(comment, postid_db)


def parse_comment(comment, postid):
    """
        Parses links from a comment. Populates DB.
        Recursively parses child comments.
    """
    urls = get_links_from_body(comment.body)
    if urls:
        # Only insert comment into DB if it contains a link
        comid_db = db.insert('Comments',
                             (None,
                              postid,
                              comment.id,
                              comment.author,
                              comment.body,
                              comment.upvotes,
                              comment.downvotes,
                              comment.created_utc))
        for url in urls:
            parse_url(url, postid=postid, commentid=comid_db)
    # Recurse over child comments
    for child in comment.children:
        parse_comment(child, postid)


def parse_url(url, postid=0, commentid=0):
    """ Gets image hash(es) from URL, populates database """

    if is_direct_link(url):
        parse_image(url, postid, commentid)
        return True

    if not should_parse_link(url):
        return

    image_urls = get_image_urls(url)
    url = clean_url(url)

    # We assume that any url that yields more than 1 image is an album
    albumid = 0
    if len(image_urls) > 1:
        albumid = get_or_create_album(url)

    if len(image_urls) > 10:
        logger.debug("Using multithreading to download large album")
        pool = ThreadPool(processes=10)
        pool.starmap(func=parse_image,
                     iterable=zip(image_urls, repeat(postid), repeat(commentid), repeat(albumid)))
        pool.close()
    else:
        for image_url in image_urls:
            parse_image(image_url, postid, commentid, albumid)
    return True


def get_or_create_album(url):
    albumid = db.insert('Albums', (None, url))
    if albumid == -1:
        albumids = db.select('id', 'Albums', 'url LIKE "%s"' % url)
        albumid = albumids[0][0]
    return albumid


def parse_image(url, postid=0, commentid=0, albumid=0):
    """
        Downloads & indexes image.
        Populates 'Hashes', 'ImageURLs', and 'Images' tables
    """

    if not should_download_image(url):
        logger.debug('Skipping file %s' % url)
        return

    try:
        (hashid, urlid, downloaded) = get_hashid_and_urlid(url)
    except Exception as e:
        logger.error('Failed to calculate hash for %s\n'
                     'Exception: %s' % (url, str(e)))
        return False
    # 'Images' table is used for linking reddit posts/comments to images
    # If there is no post/comment, don't bother linking
    if postid != 0 or commentid != 0:
        db.insert('Images', (urlid, hashid, albumid, postid, commentid))
    return True


def get_hashid_and_urlid(url):
    """
        Retrieves hash ID ('Hashes' table) and URL ID
        ('ImageURLs' table) for an image at a given URL.
        Populates 'Hashes' and 'ImageURLs' if needed.
        3rd tuple is True if downloading of image was required
    """
    existing = db.select('id, hashid', 'ImageURLs', 'url LIKE "%s"' % clean_url(url))
    if existing:
        urlid = existing[0][0]
        hashid = existing[0][1]
        return hashid, urlid, False

    # Download image
    if url.startswith('//'):
        url = 'http:%s' % url
    logger.debug('Downloading %s ...' % url)
    try:
        image_buffer = web.download(url)
    except Exception as e:
        logger.debug('Failed')
        raise Exception('Unable to download image at %s: %s' % (url, e))

    # Get image hash
    try:
        logger.debug('Hashing ...')
        image = image_from_buffer(image_buffer)
        (width, height) = image.size
        image_hash = str(avhash(image))
    except Exception as e:
        logger.debug('Failed')
        raise e
    logger.debug('Indexing ... ')

    # Insert image hash into Hashes table
    hashid = db.insert('Hashes', (None, image_hash))
    if hashid == -1:
        # Already exists, need to lookup existing hash
        hashids = db.select('id', 'Hashes', 'hash = "%s"' % (image_hash,))
        if not hashids:
            raise Exception('unable to add hash to table, or find hash (wtf?)')
        hashid = hashids[0][0]

    # Image attributes
    try:
        filesize = len(image_buffer)
        url = clean_url(url)
        urlid = db.insert('ImageURLs', (None, url, hashid, width, height, filesize))
        create_thumb(image, urlid)
        logger.debug('Done')
    except Exception as e:
        raise e
    return hashid, urlid, True


def try_remove(filename):
    try:
        remove(filename)
    except Exception as e:
        logger.warn("Could not delete %s: %s" % (filename, str(e)))
        pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.error('Interrupted (^C)')
