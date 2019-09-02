from flask import Blueprint, render_template, send_from_directory

from common import SFW, cache

index_page = Blueprint('index', __name__, template_folder='templates')


@index_page.route('/favicon.ico')
@cache.cached(timeout=3600)
def favicon():
    if SFW:
        return send_from_directory('static', 'sfw.png', mimetype='image/png')
    else:
        return send_from_directory('static', 'nsfw.png', mimetype='image/png')


@index_page.route("/")
@cache.cached(timeout=3600)
def index():
    if SFW:
        return render_template("index_sfw.html")
    else:
        return render_template("index_nsfw.html")
