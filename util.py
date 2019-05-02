import re

LINK_RE = re.compile(r'\[.*\]\(([^\)]+)\)')


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
    return url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp'))


def is_direct_link(url):
    return _is_ddl_image(url)


def should_download_image(url):
    return _is_ddl_image(url)


def sanitize_url(url):
    """ Sanitizes URLs for DB input, strips excess chars """
    url = url.replace('"', '%22')
    url = url.replace("'", '%27')
    if '?' in url:
        url = url[:url.find('?')]
    if '#' in url:
        url = url[:url.find('#')]
    return url

