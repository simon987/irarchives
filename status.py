import json

from flask import Blueprint, Response

from DB import DB
from common import DBFILE
from util import load_list

db = DB(DBFILE)
status_page = Blueprint('status', __name__, template_folder='templates')


def count_subs_txt():
    return len(load_list('subs.txt'))


@status_page.route("/status")
def status():
    return Response(json.dumps({
        'status': {
            'posts': db.get_post_count(),
            'comments': db.get_comment_count(),
            'albums': db.get_album_count(),
            'images': db.get_image_count(),
            'subreddits': count_subs_txt()
        },
    }), mimetype='application/json')
