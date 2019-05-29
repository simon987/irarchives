import re

from common import logger

LINK_RE = re.compile(r'\[.*\]\(([^)]+)\)')
SUB_RE = re.compile(r"^(.*)/r/(\w+)"
                    r"($|/|/about/(.*)|/wiki/(.*)|/(top|new|hot|rising|controvertial|gilded)/\?.*|/comments/(.*))"
                    r"($|\?.*$)")
USER_RE = re.compile("^https?://(.*)/(u|user)/(\\w+)($|/)$")

TRUSTED_AUTHORS = [
    '4_pr0n',
    'pervertedbylanguage',
    'WakingLife']
TRUSTED_SUBREDDITS = [
    'AmateurArchives',
    'gonewild',
    'pornID',
    'tipofmypenis',
    'UnrealGirls']
ALLOWED_FILETYPES = (
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


def load_list(filename):
    with open(filename) as f:
        return [x.strip().lower() for x in f.readlines() if x != "\n"]


def save_list(lst, filename):
    """ Saves list to filename """
    with open(filename, 'w') as f:
        for item in lst:
            f.write(item + '\n')


def should_parse_link(url):

    if SUB_RE.match(url):
        logger.debug('Skipping url %s: Subreddit' % url)
        return False

    if USER_RE.match(url):
        logger.debug('Skipping url %s: User' % url)
        return False

    if "message/compose" in url:
        logger.debug('Skipping url %s: PM' % url)
        return False

    if "youtu.be" in url or "youtube.com" in url:
        logger.debug('Skipping url %s: Youtube' % url)
        return False

    if "reddit.com/search?q=" in url or "github.com" in url:
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
    if '?' in url:
        url = url[:url.find('?')]
    return url.lower().endswith(ALLOWED_FILETYPES)


def is_direct_link(url):
    return _is_ddl_image(url)


def should_download_image(url):
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


def sort_by_ranking(objs):
    """ Sorts list of posts/comments based on heuristic. """
    for obj in objs:
        if 'comments' in obj:
            obj['ranking'] = int(obj['comments'])
            obj['ranking'] += int(obj['ups'])
        else:
            obj['ranking'] = int(obj['ups'])
        if 'url' in obj and 'imgur.com/a/' in obj['url'] \
                or 'imageurl' in obj and 'imgur.com/a/' in obj['imageurl']:
            obj['ranking'] += 600
        if obj['author'] in TRUSTED_AUTHORS:
            obj['ranking'] += 500
        if obj['subreddit'] in TRUSTED_SUBREDDITS:
            obj['ranking'] += 400
    return sorted(objs, reverse=True, key=lambda tup: tup['ranking'])
