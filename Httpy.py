from io import BytesIO

from pycurl import Curl
from urllib3 import disable_warnings

from common import HTTP_PROXY, logger

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
        self.curl.setopt(self.curl.FOLLOWLOCATION, True)

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
        retries = 3
        while retries:
            try:
                body = BytesIO()
                self.curl.setopt(self.curl.WRITEFUNCTION, body.write)
                self.curl.setopt(self.curl.URL, url)
                self.curl.perform()
                if self.curl.getinfo(self.curl.HTTP_CODE) != 200:

                    text = body.getvalue()
                    if "404" not in text:
                        raise Exception("HTTP" + str(self.curl.getinfo(self.curl.HTTP_CODE)))
                r = body.getvalue()
                body.close()
                return r
            except Exception as e:
                if str(e).find("transfer closed") > 0 and retries:
                    retries -= 1
                    continue
                raise Exception(str(e) + " HTTP" + str(self.curl.getinfo(self.curl.HTTP_CODE)))
