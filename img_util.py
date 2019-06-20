import hashlib
import os
from io import BytesIO, StringIO

import sys
from PIL import Image
from gallery_dl import job
from imagehash import dhash

from common import logger


def get_image_urls(url):
    result = set()

    logger.debug('Getting urls from %s ...' % (url,))

    try:
        sys.stdout = StringIO()

        # TODO: Currently not using proxy, do not use with scan.py !!!
        job.UrlJob(url).run()

        for image_url in sys.stdout.getvalue().split('\n'):
            if image_url.strip() != "":
                result.add(image_url)
        sys.stdout.close()
    except:
        pass
    finally:
        sys.stdout = sys.__stdout__

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
    im.thumbnail((500, 500), Image.ANTIALIAS)

    im.save(os.path.join(dirpath, str(num) + ".jpg"), 'JPEG')


def thumb_path(thumb_id):
    digit1 = str(thumb_id)[0]
    digit2 = str(thumb_id)[1] if thumb_id >= 10 else "0"
    return os.path.join('static/thumbs/', digit1, digit2)


def get_sha1(image_buffer):
    return hashlib.sha1(image_buffer).hexdigest()


def get_hash(im):
    return sum(1 << i for i, b in enumerate(dhash(im, hash_size=12).hash.flatten()) if b)
