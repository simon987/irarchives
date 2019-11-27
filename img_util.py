import hashlib
import os
from io import BytesIO, StringIO

import sys
from PIL import Image
from gallery_dl import job, config
from gallery_dl.job import UrlJob
from imagehash import dhash

from common import logger, HTTP_PROXY, TN_SIZE
from util import thumb_path


class ListUrlJob(UrlJob):
    def __init__(self, url):
        super().__init__(url)
        self.list = []

    def handle_url(self, url, _):
        self.list.append(url)


def get_image_urls(url):
    logger.debug('Getting urls from %s ...' % (url,))

    config.set(["proxy"], HTTP_PROXY)
    config.set(["verify"], False)
    config.set(["retries"], 2)
    config.set(["timeout"], 600)

    j = ListUrlJob(url)
    j.run()

    result = set(j.list)

    logger.debug('Got %d urls from %s' % (len(result), url))

    return result


def image_from_buffer(buf):
    return Image.open(BytesIO(buf))


def create_thumb(im, num):
    """
        Creates a thumbnail for a given image file.
        Saves to 'thumbs' directory, named <num>.jpg
    """

    dirpath = thumb_path(num)

    try:
        os.makedirs(dirpath, exist_ok=True)
    except OSError as e:
        logger.warn("Could not create dir: %s" % (e, ))
        pass

    # Convert to RGB if not already
    if im.mode != "RGB":
        im = im.convert("RGB")
    im.thumbnail((TN_SIZE, TN_SIZE), Image.ANTIALIAS)

    im.save(os.path.join(dirpath, str(num) + ".jpg"), 'JPEG')


def get_sha1(buffer):
    return hashlib.sha1(buffer).hexdigest()


def get_hash(im):
    return sum(1 << i for i, b in enumerate(dhash(im, hash_size=12).hash.flatten()) if b)\
        .to_bytes(18, "big")
