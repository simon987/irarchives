#!/usr/bin/python
import os
from io import BytesIO

from PIL import Image

from common import logger


def avhash(im):
    """
        Shrinks image to 16x16 pixels,
        Finds average amongst the pixels,
        Iterates over every pixel, comparing to average.
        1 if above avg, 0 if below.
        Returns resulting integer. (hash of the image 'im')
        Updated to not use ternary operator (not available in python 2.4.x)
    """
    im = im.convert('L').resize((16, 16), Image.ANTIALIAS)
    ttl = 0
    for gd in im.getdata():
        ttl += gd
    avg = ttl / 256
    result = 0
    for i, gd in enumerate(im.getdata()):
        if gd > avg:
            result += (1 << i)
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
    del im


def thumb_path(thumb_id):
    digit1 = str(thumb_id)[0]
    digit2 = str(thumb_id)[1] if thumb_id >= 10 else "0"
    return os.path.join('static/thumbs/', digit1, digit2)
