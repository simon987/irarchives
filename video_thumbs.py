import json

from flask import Blueprint, Response

from DB import DB
from common import DBFILE, cache

db = DB(DBFILE)
video_thumbs = Blueprint('video_thumbs', __name__, template_folder='templates')


@video_thumbs.route("/video_thumbs/<int:video_id>")
@cache.cached(timeout=600)
def thumbs(video_id):
    return Response(json.dumps({
        'thumbs': db.get_videoframes(video_id),
    }), mimetype='application/json')
