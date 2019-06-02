#!/usr/bin/python
import os
from os import mkdir, sep

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
    if not isinstance(im, Image.Image):
        im = Image.open(im)
    im = im.convert('L').resize((16, 16), Image.ANTIALIAS)
    ttl = 0
    for gd in im.getdata():
        ttl += gd
    avg = ttl / 256
    result = 0
    for i, gd in enumerate(im.getdata()):
        if gd > avg:
            result += (1 << i)
    del im
    return result


def avhash_dict(im):
    """
        Generate hashes for the image, including variations of the image
        * Regular image
        * Mirrored (left-right)
        * Rotated left (90deg)
        * Rotated right (270deg)
    """
    if not isinstance(im, Image.Image):
        im = Image.open(im)
    im = im.resize((16, 16), Image.ANTIALIAS).convert('L')
    ttl = 0
    for gd in im.getdata():
        ttl += gd
    avg = ttl / 256
    result = {}

    # Regular hash
    regular_hash = 0
    for i, gd in enumerate(im.getdata()):
        if gd > avg:
            regular_hash += (1 << i)
    result['hash'] = regular_hash

    # Mirror hash
    mirror_im = im.transpose(Image.FLIP_LEFT_RIGHT)
    mirror_hash = 0
    for i, gd in enumerate(mirror_im.getdata()):
        if gd > avg:
            mirror_hash += (1 << i)
    result['mirror'] = mirror_hash

    # Rotated 90deg hash
    left_im = im.transpose(Image.ROTATE_90)
    left_hash = 0
    for i, gd in enumerate(left_im.getdata()):
        if gd > avg:
            left_hash += (1 << i)
    result['left'] = left_hash

    # Rotated 270deg hash
    right_im = im.transpose(Image.ROTATE_270)
    right_hash = 0
    for i, gd in enumerate(right_im.getdata()):
        if gd > avg:
            right_hash += (1 << i)
    result['right'] = right_hash
    del im
    return result


def dimensions(im):
    """ Returns tuple (Width, Height) for given image. """
    if not isinstance(im, Image.Image):
        im = Image.open(im)
    result = im.size
    del im
    return result


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

    if not isinstance(im, Image.Image):
        im = Image.open(im)
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
