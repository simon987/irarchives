import json
import re
from os import path

from flask import Blueprint, Response, request
from common import DBFILE
from DB import DB
from Httpy import Httpy
from ImageHash import avhash, thumb_path, image_from_buffer
from util import clean_url, sort_by_ranking, is_user_valid

search_page = Blueprint('search', __name__, template_folder='templates')

AlphaNum = re.compile(r'[\W_]+')

db = DB(DBFILE)
web = Httpy()


@search_page.route("/search")
def search():
    """ Searches for a single URL, prints results """

    if "q" in request.args:
        query = request.args["q"]
        lquery = query.lower()
    else:
        return Response(json.dumps(""))

    # Cache
    if lquery.startswith('cache:'):
        return search_cache(query[len('cache:'):])

    # User
    elif lquery.startswith('user:'):
        return search_user(query[len('user:'):])

    elif 'reddit.com/u/' in lquery:
        return search_user(query[lquery.find('/u/') + 3:])

    elif 'reddit.com/user/' in lquery:
        return search_user(query[lquery.find('/user/') + 6:])

    # Text
    elif lquery.startswith('text:'):
        return search_text(query[len('text:'):])

    # Post
    elif 'reddit.com/r/' in query and '/comments/' in query:
        # Reddit post
        if not query.endswith('.json'):
            query += '.json'
        r = web.get(query)
        if '"url": "' in r:
            query = web.between(r, '"url": "', '"')[0]

    # URL
    if ' ' in query:
        query = query.replace(' ', '%20')
    try:
        query, posts, comments, related, downloaded = get_results_tuple_for_image(query)
    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype="application/json")

    return Response(json.dumps({
        'posts': posts,
        'comments': comments,
        'url': query,
        'related': related
    }), mimetype="application/json")


def search_user(user):
    """ Returns posts/comments by a reddit user """
    if user.strip() == '' or not is_user_valid(user):
        raise Exception('invalid username')

    posts = []
    comments = []
    related = []
    # This search will pull up all posts and comments by the user
    # NOTE It will also grab all comments containing links in the user's posts (!)
    query_text = 'postid IN '
    query_text += '(SELECT DISTINCT id FROM Posts '
    query_text += 'WHERE author LIKE "%s" ' % user
    query_text += 'ORDER BY ups DESC LIMIT 50) '
    query_text += 'OR '
    query_text += 'commentid IN '
    query_text += '(SELECT DISTINCT id FROM Comments '
    query_text += 'WHERE author LIKE "%s" ' % user
    query_text += 'ORDER BY ups DESC LIMIT 50) '
    query_text += 'GROUP BY postid, commentid'  # LIMIT 50'
    # To avoid comments not created by the author, use this query:
    # query_text = 'commentid = 0 AND postid IN (SELECT DISTINCT id FROM Posts WHERE author LIKE "%s" ORDER BY ups DESC LIMIT 50) OR commentid IN (SELECT DISTINCT id FROM Comments WHERE author LIKE "%s" ORDER BY ups DESC LIMIT 50) GROUP BY postid, commentid LIMIT 50' % (user, user)
    images = db.select('urlid, albumid, postid, commentid', 'Images', query_text)
    for (urlid, albumid, postid, commentid) in images:
        # Get image's URL, dimensions & size
        if commentid != 0:
            # Comment
            try:
                comment_dict = build_comment(commentid, urlid, albumid)
                comments.append(comment_dict)
            except:
                pass
        else:
            # Post
            try:
                post_dict = build_post(postid, urlid, albumid)
                posts.append(post_dict)
                related += build_related_comments(postid, urlid, albumid)
            except:
                pass
    posts = sort_by_ranking(posts)
    comments = sort_by_ranking(comments)

    for com in comments:
        for rel in related:
            if rel['hexid'] == com['hexid']:
                related.remove(rel)
                break

    return Response(json.dumps({
        'url': 'user:%s' % user,
        'posts': posts,
        'comments': comments,
        'related': related
    }), mimetype="application/json")


def search_cache(url):
    """
        Prints list of images inside of an album
        The images are stored in the database, so 404'd albums
        can be retrieved via this method (sometimes)
    """
    try:
        url = clean_url(url)
    except Exception as e:
        return Response(json.dumps({"error": str(e)}), mimetype="application/json")
    images = []
    query_text = 'id IN (SELECT urlid FROM Images WHERE albumid IN (SELECT DISTINCT id FROM albums WHERE url LIKE "%s"))' \
                 % (url,)
    image_tuples = db.select('id, url', 'ImageURLs', query_text)
    for (urlid, imageurl) in image_tuples:
        image = {
            'thumb': path.join(thumb_path(urlid), '%d.jpg' % urlid),
            'url': imageurl
        }
        images.append(image)

    return Response(json.dumps({
        'url': 'cache:%s' % url,
        'images': images
    }), mimetype="application/json")


def search_text(text):
    """ Prints posts/comments containing text in title/body. """
    text = AlphaNum.sub('', text)
    posts = []
    comments = []
    related = []
    query_text = 'commentid = 0 AND postid IN (SELECT DISTINCT id FROM Posts WHERE title LIKE "%%%s%%" or text LIKE "%%%s%%" ORDER BY ups DESC LIMIT 50) OR commentid IN (SELECT DISTINCT id FROM Comments WHERE body LIKE "%%%s%%" ORDER BY ups DESC LIMIT 50) GROUP BY postid, commentid LIMIT 50' \
                 % (text, text, text)
    images = db.select('urlid, albumid, postid, commentid', 'Images', query_text)
    for (urlid, albumid, postid, commentid) in images:
        # Get image's URL, dimensions & size
        if commentid != 0:
            # Comment
            try:
                comment_dict = build_comment(commentid, urlid, albumid)
                comments.append(comment_dict)
            except:
                pass
        else:
            # Post
            try:
                post_dict = build_post(postid, urlid, albumid)
                posts.append(post_dict)
                related += build_related_comments(postid, urlid, albumid)
            except:
                pass
    posts = sort_by_ranking(posts)
    comments = sort_by_ranking(comments)
    return Response(json.dumps({
        'url': 'text:%s' % text,
        'posts': posts,
        'comments': comments,
        'related': related
    }), mimetype="application/json")


###################
# Helper methods
def get_results_tuple_for_image(url):
    """ Returns tuple of posts, comments, related for an image """

    try:
        (hashid, downloaded) = get_hashid(url)
        if hashid == -1:  # No hash matches
            return url, [], [], [], downloaded
        image_hashes = db.select('hash', 'Hashes', 'id = %d' % hashid)
        if not image_hashes:
            raise Exception('could not get hash for %s' % url)
        image_hash = image_hashes[0][0]
    except Exception as e:
        raise e

    return get_results_tuple_for_hash(url, image_hash, downloaded)


def get_results_tuple_for_hash(url, image_hash, downloaded):
    posts = []
    comments = []
    related = []  # Comments contaiing links found in posts

    # Get matching hashes in 'Images' table.
    # This shows all of the posts, comments, and albums containing the hash
    query_text = 'hashid IN'
    query_text += ' (SELECT id FROM Hashes WHERE hash = "%s")' % image_hash
    query_text += ' GROUP BY postid, commentid'
    query_text += ' LIMIT 50'
    images = db.select('urlid, albumid, postid, commentid', 'Images', query_text)
    for (urlid, albumid, postid, commentid) in images:
        # Get image's URL, dimensions & size
        if commentid != 0:
            # Comment
            try:
                comment_dict = build_comment(commentid, urlid, albumid)
                if comment_dict['author'] == 'rarchives':
                    continue
                comments.append(comment_dict)
            except:
                pass
        else:
            # Post
            try:
                post_dict = build_post(postid, urlid, albumid)
                posts.append(post_dict)

                for rel in build_related_comments(postid, urlid, albumid):
                    if rel['author'] == 'rarchives':
                        continue
                    related.append(rel)
            except:
                pass

    for com in comments:
        for rel in related:
            if rel['hexid'] == com['hexid']:
                related.remove(rel)
                break

    posts = sort_by_ranking(posts)
    comments = sort_by_ranking(comments)
    return url, posts, comments, related, downloaded


def get_hashid(url, timeout=10):
    """ 
        Retrieves hash ID ('Hashes' table) for image.
        Returns -1 if the image's hash was not found in the table.
        Does not modify DB! (read only)
    """
    cleaned_url = clean_url(url)
    existing = db.select('hashid', 'ImageURLs', 'url LIKE "%s"' % cleaned_url)
    if existing:
        return existing[0][0], False

    # Download image
    image_buffer = web.download(url, timeout=timeout)
    if not image_buffer:
        raise Exception('unable to download image at %s' % url)

    # Get image hash
    try:
        image = image_from_buffer(image_buffer)
        image_hash = str(avhash(image))
    except:
        # Failed to get hash, delete image & raise exception
        raise Exception("Could not identify image")

    hashids = db.select('id', 'Hashes', 'hash = "%s"' % image_hash)
    if not hashids:
        return -1, True
    return hashids[0][0], True


###################
# "Builder" methods
def build_post(postid, urlid, albumid):
    """ Builds dict containing attributes about a post """
    item = {
        'thumb': path.join(thumb_path(urlid), '%d.jpg' % urlid),
    }

    # Get info about post
    (postid,
     item['hexid'],
     item['title'],
     item['url'],
     item['text'],
     item['author'],
     item['permalink'],
     item['subreddit'],
     item['comments'],
     item['ups'],
     item['downs'],
     item['score'],
     item['created'],
     item['is_self'],
     item['over_18']) = db.select('*', 'Posts', 'id = %d' % postid)[0]
    # Get info about image
    (item['imageurl'],
     item['width'],
     item['height'],
     item['size']) \
        = db.select('url, width, height, bytes', 'ImageURLs', 'id = %d' % urlid)[0]
    # Set URL to be the album (if it's an album)
    if albumid != 0:
        item['url'] = db.select("url", "Albums", "id = %d" % albumid)[0][0]
    return item


def build_comment(commentid, urlid, albumid):
    """ Builds dict containing attributes about a comment """
    item = {
        'thumb': path.join(thumb_path(urlid), '%d.jpg' % urlid),
    }

    # Thumbnail
    if not path.exists(item['thumb']):
        item['thumb'] = ''

    # Get info about comment
    (comid,
     postid,
     item['hexid'],
     item['author'],
     item['body'],
     item['ups'],
     item['downs'],
     item['created']) \
        = db.select('*', 'Comments', 'id = %d' % commentid)[0]

    # Get info about post comment is replying to
    (item['subreddit'],
     item['permalink'],
     item['postid']) \
        = db.select('subreddit, permalink, hexid', 'Posts', 'id = %d' % postid)[0]
    # Get info about image
    (item['imageurl'],
     item['width'],
     item['height'],
     item['size']) \
        = db.select('url, width, height, bytes', 'ImageURLs', 'id = %d' % urlid)[0]
    if albumid != 0:
        item['url'] = db.select("url", "Albums", "id = %d" % albumid)[0][0]
    return item


def build_related_comments(postid, urlid, albumid):
    """ Builds dict containing attributes about a comment related to a post"""
    items = []  # List to return
    # return items

    # Get info about post comment is replying to
    (postsubreddit,
     postpermalink,
     posthex) \
        = db.select('subreddit, permalink, hexid', 'Posts', 'id = %d' % postid)[0]

    # Get & iterate over comments
    for (comid,
         postid,
         comhexid,
         comauthor,
         combody,
         comups,
         comdowns,
         comcreated) \
            in db.select('*', 'Comments', 'postid = %d' % postid):
        item = {
            # Post-specific attributes
            'subreddit': postsubreddit,
            'permalink': postpermalink,
            'postid': posthex,
            # Comment-specific attributes
            'hexid': comhexid,
            'author': comauthor,
            'body': combody,
            'ups': comups,
            'downs': comdowns,
            'created': comcreated,
            'thumb': '',
            # Image-specific attributes (irrelevant)
            'imageurl': '',
            'width': 0,
            'height': 0,
            'size': 0
        }
        items.append(item)
    return items
