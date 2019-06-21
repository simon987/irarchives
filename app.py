from flask import Flask

from common import cache
from index import index_page
from search import search_page
from status import status_page
from subreddits import subreddits_page
from upload import upload_page

app = Flask(__name__)
cache.init_app(app)
app.register_blueprint(subreddits_page)
app.register_blueprint(status_page)
app.register_blueprint(index_page)
app.register_blueprint(search_page)
app.register_blueprint(upload_page)

if __name__ == '__main__':
    app.run(port=5010)
