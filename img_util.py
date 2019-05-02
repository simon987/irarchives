from subprocess import CalledProcessError, check_output

from common import logger


def get_image_urls(url):

    result = set()

    try:
        cmd_res = check_output(['gallery-dl', '-g', '-q',  url]).decode()
        for image_url in cmd_res.split('\n'):
            if image_url.strip() != "":
                result.add(image_url)
    except CalledProcessError as e:
        logger.error('Error in get_image_url: %s', (e, ))

    logger.debug('Got %d urls from %s' % (len(result), url))

    return result
