from flask import Blueprint, render_template, send_from_directory

index_page = Blueprint('index', __name__, template_folder='templates')


@index_page.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@index_page.route("/")
def index():
    return render_template("layout.html")
