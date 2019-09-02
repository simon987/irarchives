import json
import os
import re
from os import path

from flask import Blueprint, Response, request

from DB import DB
from Httpy import Httpy
from common import DBFILE, cache
from img_util import thumb_path, image_from_buffer, get_hash
from util import clean_url, is_user_valid
from video_util import info_from_video_buffer

search_page = Blueprint('search', __name__, template_folder='templates')

AlphaNum = re.compile(r'[\W_]+')
MAX_DISTANCE = 30

MAX_FRAME_COUNT = 30
DEFAULT_FRAME_COUNT = 10

db = DB(DBFILE)


class SearchResults:
    __slots__ = "url", "hits", "error", "result_count"

    def __init__(self, hits, error=None, url=""):
        self.url = url
        self.hits = hits
        self.error = error
        self.result_count = len(hits)

    def json(self):

        return json.dumps({
            "hits": [h.json() for h in self.hits],
            "error": self.error,
            "url": self.url,
            "result_count": self.result_count
        })


def build_results_for_images(images):
    results = db.build_result_for_images(images)

    return SearchResults(results)


@search_page.route("/search")
@cache.cached(timeout=3600 * 24, query_string=True)
def search():
    """ Searches for a single URL, prints results """

    if "d" in request.args:
        try:
            distance = min(int(request.args["d"]), MAX_DISTANCE)
        except:
            distance = 0
    else:
        distance = 0

    if "f" in request.args:
        try:
            frame_count = max(min(int(request.args["f"]), MAX_FRAME_COUNT), 1)
        except:
            frame_count = DEFAULT_FRAME_COUNT
    else:
        frame_count = DEFAULT_FRAME_COUNT

    if "img" in request.args:
        return search_img_url(request.args["img"], distance)

    if "vid" in request.args:
        return search_vid_url(request.args["vid"], distance, frame_count)

    if "album" in request.args:
        return search_album(request.args["album"])

    if "user" in request.args:
        return search_user(request.args["user"])

    # if "reddit" in request.args:
    #     return search_reddit(request.args["reddit"])

    # if "text" in request.args:
    #     return search_text(request.args["text"])

    return Response(json.dumps({'error': "Invalid query"}), mimetype="application/json")


def search_vid_url(query, distance, frame_count):
    if ' ' in query:
        query = query.replace(' ', '%20')

    try:
        video_id = db.get_video_from_url(url=query)

        if not video_id:
            # Download video
            web = Httpy()
            video_buffer = web.download(url=query)
            if not video_buffer:
                raise Exception('unable to download video at %s' % query)

            try:
                frames, info = info_from_video_buffer(video_buffer, os.path.splitext(query)[1][1:])
            except:
                raise Exception("Could not identify video")

            videos = db.get_similar_videos_by_hash(frames, distance, frame_count)

        else:

            hashes = db.get_video_hashes(video_id)
            videos = db.get_similar_videos_by_hash(hashes, distance, frame_count)

        results = SearchResults(db.build_results_for_videos(videos))

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype="application/json")

    return Response(results.json(), mimetype="application/json")


def search_img_url(query, distance):
    if ' ' in query:
        query = query.replace(' ', '%20')

    try:
        hash = db.get_image_hash_from_url(url=query)

        if not hash:
            # Download image
            web = Httpy()
            try:
                image_buffer = web.download(url=query)
            except:
                raise Exception('unable to download image at %s' % query)

            try:
                im = image_from_buffer(image_buffer)
                hash = get_hash(im)
            except:
                raise Exception("Could not identify image")

        images = db.get_similar_images(hash, distance=distance)
        results = build_results_for_images(images)

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype="application/json")

    return Response(results.json(), mimetype="application/json")


# TODO update
def search_reddit(reddit_id):
    """ Match on comment/post id"""
    images = db.get_images_from_reddit_id(reddit_id=reddit_id)
    comments, posts = db.build_result_for_images(images)

    return Response(json.dumps({
        'url': 'reddit:%s' % reddit_id,
        'posts': posts,
        'comments': comments
    }), mimetype="application/json")


def search_user(user):
    """ Returns posts/comments by a reddit user """
    if user.strip() == '' or not is_user_valid(user):
        raise Exception('invalid username')

    images = db.get_images_from_author(author=user)
    results = build_results_for_images(images)

    return Response(results.json(), mimetype="application/json")


def search_album(url):
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

    for (urlid, imageurl, width, height) in image_tuples:
        image = {
            "thumb": path.join(thumb_path(urlid), '%d.jpg' % urlid),
            "url": imageurl,
            "width": width,
            "height": height,
        }
        images.append(image)

    return Response(json.dumps({
        'url': 'cache:%s' % url,
        'images': images
    }), mimetype="application/json")


# TODO update (FULLTEXT please!)
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
