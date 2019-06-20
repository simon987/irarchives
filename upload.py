import base64
import json

from flask import Blueprint, Response, request

from DB import DB
from common import DBFILE
from common import logger
from img_util import get_hash, image_from_buffer

upload_page = Blueprint('upload', __name__, template_folder='templates')
db = DB(DBFILE)


@upload_page.route("/upload", methods=["POST"])
def upload():
    logger.info("Paste upload")

    if "data" in request.form \
            and "fname" in request.form \
            and request.form["fname"] == "image" \
            and "," in request.form["data"]:
        image_buffer = base64.b64decode(request.form["data"][request.form["data"].index(","):])
        image = image_from_buffer(image_buffer)
        image_hash = get_hash(image)

        images = db.get_similar_images(image_hash)
        comments, posts = db.build_result_for_images(images)

        return Response(json.dumps({
            'posts': posts,
            'comments': comments,
            'url': "hash:" + image_hash
        }), mimetype="application/json")

