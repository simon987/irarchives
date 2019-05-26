from time import sleep

import requests

DEFAULT_USERAGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:19.0) Gecko/20100101 Firefox/19.0'
DEFAULT_TIMEOUT = 30


class Httpy:
    """
        Easily perform GET and POST requests with web servers.
        Keeps cookies to retain web sessions.
        Includes helpful methods that go beyond GET and POST:
            * get_meta - retrieves meta info about a URL
            * unshorten - returns (some) redirected URLs
    """

    def __init__(self, user_agent=DEFAULT_USERAGENT, timeout=DEFAULT_TIMEOUT):
        self.session = requests.Session()
        self.user_agent = user_agent
        self.session.headers = self.get_headers()
        self.timeout = timeout

    def get(self, url, timeout=DEFAULT_TIMEOUT, raise_exception=False):
        """ GET request """
        result = ''
        try:
            result = self.session.get(url, timeout=timeout, headers=self.get_headers()).text
        except Exception as e:
            if raise_exception:
                raise e
        return result

    def post(self, url, postdata=None, timeout=DEFAULT_TIMEOUT, raise_exception=False):
        """
            Submits a POST request to URL. Posts 'postdata' if
            not None. URL-encodes postdata and strips Unicode chars.
        """
        result = ''

        try:
            result = self.session.post(url, timeout=timeout, data=postdata).text
        except Exception as e:
            if raise_exception:
                raise e
        return result

    def download(self, url, save_as, timeout=DEFAULT_TIMEOUT, raise_exception=False):
        """ Downloads file from URL to save_as path. """
        retries = 3

        while retries > 0:
            try:
                with open(save_as, 'wb') as outfile:
                    r = self.session.get(url, timeout=timeout)
                    if r.status_code == 200:
                        for chunk in r.iter_content(65536):
                            outfile.write(chunk)
                        return True
            except Exception as e:
                retries -= 1
                sleep(5)
        if raise_exception:
            raise e
        return False

    def get_meta(self, url, raise_exception=False, timeout=DEFAULT_TIMEOUT):
        """
            Returns a dict containing info about the URL.
            Such as Content-Type, Content-Length, etc.
        """
        try:
            r = self.session.get(url, timeout=timeout)
            return r.headers
        except Exception as e:
            if raise_exception:
                raise e
        return {}

    def clear_cookies(self):
        self.session = requests.Session()

    def get_headers(self):
        """ Returns default headers for URL requests """
        return {'User-agent': self.user_agent}

    def between(self, source, start, finish):
        """
            Useful when parsing responses from web servers.

            Looks through a given source string for all items between two other strings,
            returns the list of items (or empty list if none are found).

            Example:
                test = 'hello >30< test >20< asdf >>10<< sadf>'
                print between(test, '>', '<')

            would print the list:
                ['30', '20', '>10']
        """
        result = []
        i = source.find(start)
        j = source.find(finish, i + len(start) + 1)

        while i >= 0 and j >= 0:
            i = i + len(start)
            result.append(source[i:j])
            i = source.find(start, j + len(finish))
            j = source.find(finish, i + len(start) + 1)

        return result
