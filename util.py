import re

LINK_RE = re.compile(r'\[.*\]\(([^\)]+)\)')

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



def load_list(filename):
    with open(filename) as f:
        return [x.strip().lower() for x in f.readlines() if x != "\n"]


def save_list(lst, filename):
    """ Saves list to filename """
    with open(filename, 'w') as f:
        for item in lst:
            f.write(item + '\n')


def should_parse_link(url):

    # TODO: Don't parse links pointing to a whole subreddit,
    #   Don't parse links pointing to a whole user
    #   Don't parse links pointing to /message/compose
    #   Don't parse links pointing to instagram/facebook profiles

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
    return url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp', '.webp'))


def is_direct_link(url):
    return _is_ddl_image(url)


def should_download_image(url):
    return _is_ddl_image(url)


def clean_url(url):
    """ Sanitizes URLs for DB input, strips excess chars """
    url = url.replace('"', '%22')
    url = url.replace("'", '%27')
    if '?' in url:
        url = url[:url.find('?')]
    if '#' in url:
        url = url[:url.find('#')]
    return url


def sanitize_url(url, web):
    """
        Retrieves direct link to image based on URL,
        Strips excess data from imgur albums,
        Throws Exception if unable to find direct image.
    """
    url = url.strip()
    if '?' in url:
        url = url[:url.find('?')]
    if '#' in url:
        url = url[:url.find('#')]
    if url == '' or not '.' in url:
        raise Exception('invalid URL')

    if '://' not in url:
        url = 'http://%s' % url  # Fix for what'shisface who forgets to prepend http://

    while url.endswith('/'):
        url = url[:-1]
    if 'imgur.com' in url:
        if '.com/a/' in url:
            # Album
            url = url.replace('http://', '').replace('https://', '')
            while url.endswith('/'):
                url = url[:-1]
            while url.count('/') > 2:
                url = url[:url.rfind('/')]
            if '?' in url:
                url = url[:url.find('?')]
            if '#' in url:
                url = url[:url.find('#')]
            url = 'http://%s' % url  # How the URL will be stored in the DB
            return url

        elif url.lower().endswith('.jpeg') or \
                url.lower().endswith('.jpg') or \
                url.lower().endswith('.png') or \
                url.lower().endswith('.gif'):
            # Direct imgur link, find highest res
            url = imgur_get_highest_res(url, web)
        # Drop out of if statement & parse image
        else:
            # Indirect imgur link (e.g. "imgur.com/abcde")
            r = web.get(url)
            if '"image_src" href="' in r:
                url = web.between(r, '"image_src" href="', '"')[0]
            else:
                raise Exception("unable to find imgur image (404?)")
    elif 'gfycat.com' in url and 'thumbs.gfycat.com' not in url:
        r = web.get(url)
        if "og:image' content='" in r:
            url = web.between(r, "og:image' content='", "'")[-1]
        else:
            raise Exception("unable to find gfycat poster image")
    elif url.lower().endswith('.jpg') or \
            url.lower().endswith('.jpeg') or \
            url.lower().endswith('.png') or \
            url.lower().endswith('.gif'):
        # Direct link to non-imgur image
        pass  # Drop out of if statement & parse image
    else:
        # Not imgur, not a direct link; no way to parse
        raise Exception("unable to parse non-direct, non-imgur link")
    return url


def imgur_get_highest_res(url, web):
    """ Retrieves highest-res imgur image """
    if 'h.' not in url:
        return url
    temp = url.replace('h.', '.')
    m = web.get_meta(temp)
    if 'Content-Type' in m and 'image' in m['Content-Type'].lower() and \
            'Content-Length' in m and m['Content-Length'] != '503':
        return temp
    else:
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
