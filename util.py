import re

from common import logger
import os

LINK_RE = re.compile(r'\[.*\]\(([^)]+)\)')
SUB_RE = re.compile(r"^(.*)/r/([\w+]+)"
                    r"($|/|/about/(.*)|/wiki/(.*)|/(top|new|hot|rising|controvertial|gilded)/?\?.*|/comments/(.*))"
                    r"($|\?.*$)")
USER_RE = re.compile("^https?://(.*)/(u|user)/(\\w+)($|/)$")

IMAGE_FILETYPES = (
    # :orig for twitter cdn
    '.jpg',
    '.jpg:orig',
    '.jpeg',
    '.jpeg:orig',
    '.png',
    '.png:orig',
    '.gif',
    '.gif:orig',
    '.tiff',
    '.bmp',
    '.webp'
)

# Reminder that .gifv is not a real file type, it should be passed to gallery-dl so it can pull the real
# file url
VIDEO_FILETYPES = (
    ".webm",
    ".mp4",
)


def load_list(filename):
    with open(filename) as f:
        return [x.strip().lower() for x in f.readlines() if x != "\n"]


def should_parse_link(url):

    if "message/compose" in url:
        logger.debug('Skipping url %s: PM' % url)
        return False

    if "youtu.be" in url or "youtube.com" in url:
        logger.debug('Skipping url %s: Youtube' % url)
        return False

    if "reddit.com/search?q=" in url or "github.com" in url or\
            "wikipedia.org" in url or "addons.mozilla.org" in url:
        logger.debug('Skipping url %s: Misc' % url)
        return False

    return True


def get_links_from_body(body):
    """ Returns list of URLs found in body (e.g. selfpost or comment). """
    result = set()

    body = body.replace("\\)", "&#x28;")
    for match in LINK_RE.finditer(body):
        url = match.group(1)
        if should_parse_link(url):
            result.add(url)

    return result


def _is_ddl_image(url):

    if "i.reddituploads.com" in url:
        return True

    if '?' in url:
        url = url[:url.find('?')]
    return url.lower().endswith(IMAGE_FILETYPES)


def is_video(url):

    if '?' in url:
        url = url[:url.find('?')]
    return url.lower().endswith(VIDEO_FILETYPES)


def is_image_direct_link(url):
    return _is_ddl_image(url)


def clean_url(url):
    """ Sanitizes URLs for DB input, strips excess chars """
    url = url.replace('"', '%22')\
        .replace("'", '%27')\
        .replace("'", '%27')\
        .replace('http://', '')\
        .replace('https://', '')

    while url.endswith('/'):
        url = url[:-1]
    if '?' in url:
        url = url[:url.find('?')]
    if '#' in url:
        url = url[:url.find('#')]
    url = 'http://' + url
    return url


def is_user_valid(username):
    """ Checks if username is valid reddit name, assumes lcase/strip """
    allowed = 'abcdefghijklmnopqrstuvwxyz1234567890_-'
    valid = True
    for c in username.lower():
        if c not in allowed:
            valid = False
            break
    return valid


def thumb_path(thumb_id, folder="im"):
    digit1 = str(thumb_id)[0]
    digit2 = str(thumb_id)[1] if thumb_id >= 10 else "0"
    return os.path.join('static/thumbs/', folder, digit1, digit2)

