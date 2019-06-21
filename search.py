import json
import re
from os import path

from flask import Blueprint, Response, request

from DB import DB
from Httpy import Httpy
from common import DBFILE, cache, logger
from img_util import thumb_path, image_from_buffer, get_hash
from util import clean_url, is_user_valid

search_page = Blueprint('search', __name__, template_folder='templates')

AlphaNum = re.compile(r'[\W_]+')
MAX_DISTANCE = 30

db = DB(DBFILE)
web = Httpy()


@search_page.route("/search")
@cache.cached(timeout=3600 * 24, query_string=True)
def search():
    """ Searches for a single URL, prints results """

    if "q" in request.args:
        query = request.args["q"]
        lquery = query.lower()
    else:
        return Response(json.dumps(""))

    if "d" in request.args:
        try:
            distance = min(int(request.args["d"]), MAX_DISTANCE)
        except:
            distance = 0
    else:
        distance = 0

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
        # Reddit post, get its url and do a search_url() with it
        try:
            if not query.endswith('.json'):
                query += '.json'
            r = web.get(query)
            if '"url": "' in r:
                query = web.between(r, '"url": "', '"')[0]
        except Exception as e:
            return Response(json.dumps({'error': str(e)}), mimetype="application/json")

    # URL
    return search_url(query, distance)


def search_url(query, distance):
    if ' ' in query:
        query = query.replace(' ', '%20')

    try:
        hash = db.get_hash_from_url(url=query)

        if not hash:
            # Download image
            image_buffer = web.download(url=query)
            if not image_buffer:
                raise Exception('unable to download image at %s' % query)

            try:
                im = image_from_buffer(image_buffer)
                hash = get_hash(im)
            except:
                raise Exception("Could not identify image")

        images = db.get_similar_images(hash, distance=distance)
        comments, posts = db.build_result_for_images(images)

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype="application/json")

    return Response(json.dumps({
        'posts': posts,
        'comments': comments,
        'url': query
    }), mimetype="application/json")


def search_user(user):
    """ Returns posts/comments by a reddit user """
    if user.strip() == '' or not is_user_valid(user):
        raise Exception('invalid username')

    images = db.get_images_from_author(author=user)
    comments, posts = db.build_result_for_images(images)

    return Response(json.dumps({
        'url': 'user:%s' % user,
        'posts': posts,
        'comments': comments
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
    image_tuples = db.get_images_from_album_url(album_url=url)

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
    images = db.get_images_from_text(text)

    comments, posts = db.build_result_for_images(images)

    return Response(json.dumps({
        'url': 'text:%s' % text,
        'posts': posts,
        'comments': comments
    }), mimetype="application/json")


