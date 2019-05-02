import json

from flask import Blueprint, Response

from util import load_list

subreddits_page = Blueprint('subreddits', __name__, template_folder='templates')


@subreddits_page.route("/subreddits")
def get_subs():
    return Response(json.dumps({'subreddits': load_list('subs.txt')}), mimetype="application/json")
