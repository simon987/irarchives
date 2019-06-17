import logging
import sys
from logging import FileHandler, StreamHandler

logger = logging.getLogger("default")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s %(levelname)-5s %(message)s')
file_handler = FileHandler("rarchives.log")
file_handler.setFormatter(formatter)
for h in logger.handlers:
    logger.removeHandler(h)
logger.addHandler(file_handler)
logger.addHandler(StreamHandler(sys.stdout))

HTTP_PROXY = "http://localhost:5050"

DBFILE = "reddit.db"
