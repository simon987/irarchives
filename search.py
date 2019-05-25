import json
import tempfile
import time
from os import path, close, remove
from threading import Thread
from time import sleep, time

from flask import Blueprint, Response, request

from DB import DB
from Httpy import Httpy
from ImageHash import avhash
from util import clean_url, sort_by_ranking, is_user_valid

search_page = Blueprint('search', __name__, template_folder='templates')

db = DB('reddit.db')
web = Httpy()

MAX_ALBUM_SEARCH_DEPTH = 3  # Number of images to download from album
MAX_ALBUM_SEARCH_TIME = 10  # Max time to search album in seconds
MAX_GOOGLE_SEARCH_TIME = 10  # Max time to spend retrieving & searching google results


@search_page.route("/search")
def search():
    """ Searches for a single URL, prints results """

    if "q" in request.args:
        query = request.args["q"].lower()
    else:
        return Response(json.dumps(""))

    # Cache
    if query.startswith('cache:'):
        return search_cache(query[len('cache:'):])

    # User
    elif query.startswith('user:'):
        return search_user(query[len('user:'):])

    elif 'reddit.com/u/' in query:
        return search_user(query[query.find('/u/') + 3:])

    elif 'reddit.com/user/' in query:
        return search_user(query[query.find('/user/') + 6:])

    # Text
    elif query.startswith('text:'):
        return search_text(query[len('text:'):])

    # Post?
    elif 'reddit.com/r/' in query and '/comments/' in query:
        # Reddit post
        if not query.endswith('.json'):
            query += '.json'
        r = web.get(query)
        if '"url": "' in r:
            query = web.between(r, '"url": "', '"')[0]

    if ' ' in query:
        query = query.replace(' ', '%20')
    try:
        (query, posts, comments, related, downloaded) = \
            get_results_tuple_for_image(query)
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
        'url': 'user:%s' % user,  # 'http://reddit.com/user/%s' % user,
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
            'thumb': 'static/thumbs/%d.jpg' % urlid,
            'url': imageurl
        }
        images.append(image)

    return Response(json.dumps({
        'url': 'cache:%s' % url,
        'images': images
    }), mimetype="application/json")


def search_text(text):
    """ Prints posts/comments containing text in title/body. """
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


GOOGLE_RESULTS = []
GOOGLE_THREAD_COUNT = 0
GOOGLE_THREAD_MAX = 3


def search_google(url):
    """ 
        Searches google reverse image search,
        gets URL of highest-res image,
        searches that.
    """
    # No country redirect
    web.get('http://www.google.com/ncr')
    sleep(0.2)

    time_started = time()
    time_to_stop = time_started + MAX_GOOGLE_SEARCH_TIME
    # Get image results
    u = 'http://images.google.com/searchbyimage?hl=en&safe=off&image_url=%s' % url
    r = web.get(u)
    total_searched = 0
    start = 10
    while True:
        if 'that include matching images' in r:
            chunk = r[r.find('that include matching images'):]
        elif start == 10:
            break
        else:
            chunk = r
        if 'Visually similar images' in chunk:
            chunk = chunk[:chunk.find('Visually similar images')]
        images = web.between(chunk, '/imgres?imgurl=', '&amp;imgref')
        for image in images:
            if time() > time_to_stop:
                break
            splits = image.split('&')
            image = ''
            for split in splits:
                if split.startswith('amp;'):
                    break
                if image != '':
                    image += '&'
                image += split
            # Launch thread
            while GOOGLE_THREAD_COUNT >= GOOGLE_THREAD_MAX:
                sleep(0.1)
            if time() < time_to_stop:
                args = (image, time_to_stop)
                t = Thread(target=handle_google_result, args=args)
                t.start()
            else:
                break

        if time() > time_to_stop:
            break
        if '>Next<' not in r:
            break
        sleep(1)
        r = web.get('%s&start=%s' % (u, start))
        start += 10

    posts = []
    comments = []
    related = []
    # Wait for threads to finish
    while GOOGLE_THREAD_COUNT > 0:
        sleep(0.1)
    # Iterate over results
    for (image_url, image_hash, downloaded) in GOOGLE_RESULTS:
        # hashid = get_hashid_from_hash(image_hash)
        try:
            (t_url, t_posts, t_comments, t_related, t_downloaded) = \
                get_results_tuple_for_hash(image_url, image_hash, downloaded)
        except:
            continue
        total_searched += 1
        merge_results(posts, t_posts)
        merge_results(comments, t_comments)
        merge_results(related, t_related)
    if len(posts) + len(comments) + len(related) == 0:
        return Response({"error": 'no results - searched %d google images' % total_searched})

    return Response(json.dumps({
        'posts': posts,
        'comments': comments,
        'url': 'google:%s' % url,
        'related': related
    }), mimetype="application/json")


def handle_google_result(url, time_to_stop):
    global GOOGLE_RESULTS, GOOGLE_THREAD_MAX, GOOGLE_THREAD_COUNT
    if time() > time_to_stop:
        return
    GOOGLE_THREAD_COUNT += 1
    url = web.unshorten(url, timeout=3)
    if time() > time_to_stop:
        GOOGLE_THREAD_COUNT -= 1
        return
    m = web.get_meta(url, timeout=3)
    if 'Content-Type' not in m or \
            'image' not in m['Content-Type'].lower() or \
            time() > time_to_stop:
        GOOGLE_THREAD_COUNT -= 1
        return
    try:
        image_hash = get_hash(url, timeout=4)
        GOOGLE_RESULTS.append((url, image_hash, True))
    except Exception:
        GOOGLE_THREAD_COUNT -= 1
    GOOGLE_THREAD_COUNT -= 1


###################
# Helper methods
def get_results_tuple_for_image(url):
    """ Returns tuple of posts, comments, related for an image """

    try:
        (hashid, downloaded) = get_hashid(url)
        if hashid == -1 or hashid == 870075:  # No hash matches
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


def get_hash(url, timeout=10):
    """ 
        Retrieves hash ID ('Hashes' table) for image.
        Returns -1 if the image's hash was not found in the table.
        Does not modify DB! (read only)
    """
    # Download image
    (tmpfile, temp_image) = tempfile.mkstemp(prefix='redditimg', suffix='.jpg')
    close(tmpfile)
    if not web.download(url, temp_image, timeout=timeout):
        raise Exception('unable to download image at %s' % url)

    # Get image hash
    try:
        image_hash = str(avhash(temp_image))
        try:
            remove(temp_image)
        except:
            pass
        return image_hash
    except Exception as e:
        # Failed to get hash, delete image & raise exception
        try:
            remove(temp_image)
        except:
            pass
        raise e


def get_hashid_from_hash(image_hash):
    hashids = db.select('id', 'Hashes', 'hash = "%s"' % image_hash)
    if not hashids:
        return -1
    return hashids[0][0]


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
    (tmpfile, temp_image) = tempfile.mkstemp(prefix='redditimg', suffix='.jpg')
    close(tmpfile)
    if not web.download(url, temp_image, timeout=timeout):
        raise Exception('unable to download image at %s' % url)

    # Get image hash
    try:
        image_hash = str(avhash(temp_image))
        try:
            remove(temp_image)
        except:
            pass
    except Exception as e:
        # Failed to get hash, delete image & raise exception
        try:
            remove(temp_image)
        except:
            pass
        raise e

    hashids = db.select('id', 'Hashes', 'hash = "%s"' % image_hash)
    if not hashids:
        return -1, True
    return hashids[0][0], True


def merge_results(source_list, to_add):
    """ 
        Adds posts/comments from to_add list to source_list
        Ensures source_list is free fo duplicates.
    """
    for target in to_add:
        should_add = True
        # Check for duplicates
        for source in source_list:
            if target['hexid'] == source['hexid']:
                should_add = False
                break
        if should_add:
            source_list.append(target)


###################
# "Builder" methods

def build_post(postid, urlid, albumid):
    """ Builds dict containing attributes about a post """
    item = {'thumb': 'static/thumbs/%d.jpg' % urlid}  # Dict to return
    # Thumbnail
    # if not path.exists(item['thumb']):
    #     item['thumb'] = ''

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
    item = {'thumb': 'static/thumbs/%d.jpg' % urlid}  # Dict to return

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
