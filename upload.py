import base64
import json

from flask import Blueprint, Response, request

from DB import DB
from common import DBFILE
from common import logger
from img_util import get_hash, image_from_buffer
from search import MAX_DISTANCE

upload_page = Blueprint('upload', __name__, template_folder='templates')
db = DB(DBFILE)


@upload_page.route("/upload", methods=["POST"])
def upload():
    if "data" in request.form \
            and "fname" in request.form \
            and request.form["fname"] == "image" \
            and "," in request.form["data"]:

        if "d" in request.form:
            try:
                distance = min(int(request.form["d"]), MAX_DISTANCE)
            except:
                distance = 0
        else:
            distance = 0
        logger.info("Paste upload with distance %d" % (distance, ))

        image_buffer = base64.b64decode(request.form["data"][request.form["data"].index(","):])
        image = image_from_buffer(image_buffer)
        image_hash = get_hash(image)

        images = db.get_similar_images(image_hash, distance)
        comments, posts = db.build_result_for_images(images)

        return Response(json.dumps({
            'posts': posts,
            'comments': comments,
            'url': "hash:" + str(image_hash)
        }), mimetype="application/json")

