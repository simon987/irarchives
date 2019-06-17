import json

from flask import Blueprint, Response
from common import DBFILE
from ClientDB import DB
from util import load_list

db = DB(DBFILE)
status_page = Blueprint('status', __name__, template_folder='templates')


def get_count(table):
    return db.select("count(*)", table)[0][0]


def count_subs_db():
    return db.select("count(distinct subreddit)", "Posts")[0][0]


def count_subs_txt():
    return len(load_list('subs.txt'))


@status_page.route("/status")
def status():
    return Response(json.dumps({
        'status': {
            'posts': get_count('Posts'),
            'comments': get_count('Comments'),
            'albums': get_count('Albums'),
            'images': get_count('Images'),
            'subreddits': count_subs_txt(),
            'subreddits_pending': count_subs_txt()
        },
    }), mimetype='application/json')
