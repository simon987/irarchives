import subprocess
from subprocess import CalledProcessError, check_output, TimeoutExpired

from common import logger, HTTP_PROXY


def get_image_urls(url):
    result = set()

    logger.debug('Getting urls from %s ...' % (url,))

    try:
        cmd_res = check_output([
            'gallery-dl', '-g', '-q',
            '--proxy', HTTP_PROXY, '--no-check-certificate',
            '-R' '1', '--http-timeout', '600', url
        ], timeout=60 * 15, stderr=subprocess.DEVNULL).decode()

        for image_url in cmd_res.split('\n'):
            if image_url.strip() != "":
                result.add(image_url)
    except CalledProcessError as e:
        logger.error('Error in get_image_url: %s', (e,))
    except TimeoutExpired as e:
        logger.error('Timeout in get_image_url: %s', (e,))

    logger.debug('Got %d urls from %s' % (len(result), url))

    return result
