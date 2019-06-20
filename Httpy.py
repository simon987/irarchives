from io import BytesIO

from pycurl import Curl
from urllib3 import disable_warnings

from common import HTTP_PROXY

disable_warnings()

DEFAULT_TIMEOUT = 600


class Httpy:
    """
        Easily perform GET and POST requests with web servers.
        Keeps cookies to retain web sessions.
        Includes helpful methods that go beyond GET and POST:
            * get_meta - retrieves meta info about a URL
            * unshorten - returns (some) redirected URLs
    """

    def __init__(self):
        self.curl = Curl()
        self.curl.setopt(self.curl.SSL_VERIFYPEER, 0)
        self.curl.setopt(self.curl.SSL_VERIFYHOST, 0)
        self.curl.setopt(self.curl.TIMEOUT, DEFAULT_TIMEOUT)
        self.curl.setopt(self.curl.PROXY, HTTP_PROXY)

    def get(self, url):
        """ GET request """
        try:
            body = BytesIO()
            self.curl.setopt(self.curl.WRITEFUNCTION, body.write)
            self.curl.setopt(self.curl.URL, url)
            self.curl.perform()
            r = body.getvalue()
            body.close()
            return r.decode()
        except Exception as e:
            raise e

    def download(self, url):
        """ Downloads file from URL to save_as path. """
        try:
            body = BytesIO()
            self.curl.setopt(self.curl.WRITEFUNCTION, body.write)
            self.curl.setopt(self.curl.URL, url)
            self.curl.perform()
            if self.curl.getinfo(self.curl.HTTP_CODE) != 200:
                raise Exception("HTTP" + str(self.curl.getinfo(self.curl.HTTP_CODE)))

            r = body.getvalue()
            body.close()
            return r
        except Exception as e:
            raise Exception(str(e) + " HTTP" + str(self.curl.getinfo(self.curl.HTTP_CODE)))

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
