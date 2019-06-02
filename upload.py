import base64
import json
import os
import tempfile

from flask import Blueprint, Response, request

from DB import DB
from ImageHash import avhash
from common import logger
from scan import try_remove
from search import get_results_tuple_for_hash

upload_page = Blueprint('upload', __name__, template_folder='templates')
db = DB('reddit.db')


@upload_page.route("/upload", methods=["POST"])
def upload():
    logger.info("Paste upload")

    if "data" in request.form \
            and "fname" in request.form \
            and request.form["fname"] == "image" \
            and "," in request.form["data"]:

        tmphandle, temp_image = tempfile.mkstemp(prefix='uploadimg', suffix='.jpg')
        try:
            with os.fdopen(tmphandle, "wb") as tmpfile:
                tmpfile.write(base64.b64decode(request.form["data"][request.form["data"].index(","):]))

            image_hash = str(avhash(temp_image))
            query, posts, comments, related, downloaded = get_results_for_hash(image_hash)
            return Response(json.dumps({
                'posts': posts,
                'comments': comments,
                'url': query,
                'related': related
            }), mimetype="application/json")

        finally:
            try_remove(temp_image)


def get_results_for_hash(hash):
    hashids = db.select('id', 'Hashes', 'hash = "%s"' % hash)
    url = "hash:" + hash
    if not hashids:
        return url, [], [], [], True
    return get_results_tuple_for_hash(url, hash, True)

