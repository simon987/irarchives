import logging
import sys
from logging import FileHandler, StreamHandler

from flask_caching import Cache

HTTP_PROXY = "http://localhost:5050"
DBFILE = "dbname=ir user=ir password=ir"
USE_REDIS = True

if USE_REDIS:
    cache = Cache(config={
        "CACHE_TYPE": "redis",
        "CACHE_KEY_PREFIX": "ir",
        "CACHE_REDIS_HOST": "localhost",
        "CACHE_REDIS_PORT": "6379"
    })
else:
    cache = Cache(config={
        "CACHE_TYPE": "simple"
    })


logger = logging.getLogger("default")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s %(levelname)-5s %(message)s')
file_handler = FileHandler("rarchives.log")
file_handler.setFormatter(formatter)
for h in logger.handlers:
    logger.removeHandler(h)
logger.addHandler(file_handler)
logger.addHandler(StreamHandler(sys.stdout))

