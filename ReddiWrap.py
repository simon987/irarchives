#!/usr/bin/python

"""
Reddit.com API Wrapper (ReddiWrap)

Intuitive middleware between you and reddit.com

(C) 2012 Derv Merkler @ github.com/derv82/reddiwrap

TODO:
    include 'depth' in comments to know how deep into replies we are.
    test all use cases (user about page, /r/none, etc)

    throw exceptions when receiving errors from server (403)

"""

import json
from pprint import pprint

from Httpy import Httpy  # Class for communicating with the web server.


class Post(object):
    """
        Stores information and logic about reddit "post"s.
        A reddit post is a submission that contains either a link or self-text.
        Posts contain child comments.
    """

    def __init__(self):
        self.modhash = ''  # base36 string for communicating with account
        self.id = ''  # base36 id for a post (usually 5 characters)
        self.name = ''  # example: t1_czwe3. t# is content type, the rest is the ID
        self.title = ''  # Title of post
        self.url = ''  # URL to post
        self.author = ''  # Username of author
        self.domain = ''  # Domain posted ot
        self.subreddit = ''  # Subreddit posted to
        self.subreddit_id = ''  # base36 ID for subreddit. E.g. t5_2uehl
        self.permalink = ''  # Link to the post (including comments)
        self.is_self = False  # Self-post
        self.selftext = ''  # Self-post text
        self.selftext_html = ''  # HTML for self-post text
        self.num_comments = ''  # Number of comments
        self.score = 0  # upvotes - downvotes * crazy reddit vote fuzzing constant
        self.upvotes = 0
        self.downvotes = 0
        self.over_18 = False  # NSFW post
        self.hidden = False
        self.saved = False
        self.edited = False
        self.created = 0
        self.created_utc = 0
        self.comments = []  # List of Comment objects that are replies to the Post
        self.has_more_comments = False  # Contains comments that have not been loaded
        self.more_comments = ''  # JSON data containing information about comments to load
        self.num_reports = 0
        self.banned_by = False
        self.approved_by = None
        self.media_embed = {}
        self.media = None
        self.thumbnail = ''
        self.link_flair_text = ''
        self.link_flair_class = ''  # link_flair_css_class": null,
        self.author_flair_text = ''  # "author_flair_css_class": null,
        self.author_flair_class = ''

    def set_using_json_data(self, data):
        """ Sets fields using json data. Assumes all fields in JSON exist. """
        self.id = data['id']
        self.name = data['name']
        self.title = data['title']
        self.url = data['url']
        self.author = data['author']
        self.domain = data['domain']
        self.subreddit = data['subreddit']
        self.subreddit_id = data['subreddit_id']
        self.permalink = data['permalink']
        self.is_self = data['is_self']
        self.selftext = data['selftext']
        self.selftext_html = data['selftext_html']
        self.num_comments = data['num_comments']
        self.score = data['score']
        self.upvotes = data['ups']
        self.downvotes = data['downs']
        self.over_18 = data['over_18']
        self.hidden = data['hidden']
        self.saved = data['saved']
        self.edited = data['edited']
        self.created = data['created']
        self.created_utc = data['created_utc']
        self.num_reports = data['num_reports']
        self.banned_by = data['banned_by']
        self.approved_by = data['approved_by']
        self.media_embed = data['media_embed']
        self.media = data['media']
        self.thumbnail = data['thumbnail']
        self.link_flair_text = data['link_flair_text']
        self.link_flair_class = data['link_flair_css_class']
        self.author_flair_text = data['author_flair_text']
        self.author_flair_class = data['author_flair_css_class']

    def __str__(self):
        """ STRING summary of comment; author and body. """
        return ('"%s" by %s in /r/%s' % (self.title, self.author, self.subreddit)).encode('ascii', 'ignore')

    def __repr__(self):
        return self.__str__()

    def verbose(self):
        """ Returns string containing all fields and their values. Verbose. """
        return pprint(self.__dict__)


class Comment(object):
    """
        Stores information and logic about a comment.
        Comments are either direct replies to a Post or replies to other Comments.
    """

    def __init__(self):
        self.modhash = ''  # Modhash included with this comment
        self.id = ''
        self.name = ''
        self.link_id = ''
        self.parent_id = ''
        self.author = ''
        self.body = ''
        self.body_html = ''
        self.subreddit = ''
        self.upvotes = 0
        self.downvotes = 0
        self.score = 0
        self.created = 0
        self.created_utc = 0
        self.edited = False
        self.children = []
        self.has_more_comments = False
        self.more_comments = ''
        self.num_reports = 0
        self.banned_by = ''
        self.approved_by = ''
        self.flair_class = ''
        self.flair_text = ''

    def set_using_json_data(self, data):
        """ Initializes object using JSON data. Assumes fields in JSON exist. """
        self.id = data['id']
        self.name = data['name']
        if data.get('link_id') is not None:
            self.link_id = data['link_id']
        if data.get('parent_id') is not None:
            self.parent_id = data['parent_id']
        self.author = data['author']
        self.body = data['body']
        self.body_html = data['body_html']
        self.subreddit = data['subreddit']
        self.subreddit_id = data['subreddit_id']
        self.upvotes = data['ups']
        self.downvotes = data['downs']
        if data.get('score') is not None:
            self.score = data['score']
        self.created = data['created']
        self.created_utc = data['created_utc']
        self.edited = data['edited']
        self.num_reports = data['num_reports']
        self.banned_by = data['banned_by']
        self.approved_by = data['approved_by']
        self.flair_class = data['author_flair_css_class']
        self.flair_text = data['author_flair_text']

        # Adding other comments / more
        if data.get('replies') is None:
            return
        replies = data['replies']
        if replies == '' or replies.get('data') is None:
            return
        repdata = replies['data']
        if repdata.get('children') is None:
            return
        for child in repdata['children']:
            cdata = child['data']
            ckind = child['kind']
            if ckind == 'more':
                self.has_more_comments = True
                self.more_comments = cdata
                continue
            comment = Comment()
            comment.set_using_json_data(cdata)
            # Recursive call! Parses and stores child comments
            self.children.append(comment)

    def __str__(self):
        """ STRING summary of comment; author and body. """
        return ('%s: "%s"' % (self.author, self.body)).encode('ascii', 'ignore')

    def __repr__(self):
        return self.__str__()

    def verbose(self):
        """ Returns string containing all fields and their values. Verbose. """
        return pprint(self.__dict__)


class Subreddit(object):
    """
        Contains information about a single subreddit.
        Used by get_reddits()
    """

    def __init__(self, json_data):
        self.id = json_data['id']  # 2qh0u
        self.name = json_data['name']  # t5_2qh0u
        self.display_name = json_data['display_name']  # pics
        self.header_img = json_data['header_img']  # .png
        self.title = json_data['title']  # /r/Pics
        self.url = json_data['url']  # /r/pics/
        self.description = json_data['description']  # <text description>
        self.created = json_data['created']  # time since 1/1/1970, local
        self.created_utc = json_data['created_utc']  # time since 1/1/1970, UTC
        self.over18 = json_data['over18']  # false
        self.subscribers = json_data['subscribers']  # 1979507
        self.public_desc = json_data['public_description']  # <brief summary>
        self.header_title = json_data['header_title']  # "Pictures and Images"

    def __repr__(self):
        """ Returns string containing all fields and their values. Verbose. """
        return pprint(self.__dict__)


class Message(object):
    """
        Contains information about a single message (PM).
    """

    def __init__(self, json_data):
        self.id = json_data['id']  # base36 ID for comment/message
        self.name = json_data['name']  # t4_c51d3 for message, t1_c52351 for comment reply
        self.author = json_data['author']  # Username of author of message
        self.subject = json_data['subject']  # Subject of message, or "comment reply" if comment
        self.body = json_data['body']  # Text of message
        self.body_html = json_data['body_html']  # Text of message, including HTML markup
        self.new = json_data['new']  # True if message/comment is unread, False otherwise
        self.was_comment = json_data['was_comment']  # True if message is comment, False otherwise
        self.first_message = json_data['first_message']  # None of first message, otherwise ID of first msg
        self.created = json_data['created']  # Time since 1/1/1970, local time
        self.created_utc = json_data['created_utc']  # Time since 1/1/1970, UTC
        self.parent_id = json_data['parent_id']  # base36 ID of parent of message
        self.context = json_data['context']  # Permalink to comment with context, "" if message
        self.dest = json_data['dest']  # Destination username
        self.subreddit = json_data['subreddit']  # Subreddit comment was made in, None if message
        # Messages with no replies have an empty list for 'replies' []
        # Otherwise, the replies contain the actual replied Message object
        self.replies = []
        jreplies = json_data.get('replies')
        if jreplies is not None and isinstance(jreplies, dict):
            jdata = jreplies.get('data')
            if jdata is not None:
                jchildren = jdata.get('children')
                if jchildren is not None and isinstance(jchildren, list):
                    for jreply in jchildren:
                        cdata = jreply.get('data')
                        ckind = jreply.get('kind')
                        if cdata is None:
                            continue
                        # Recursive call
                        msg = Message(cdata)
                        self.replies.append(msg)

    def __repr__(self):
        """ Returns brief summary of message. """
        return '%s sent PM: "%s"' % (self.author, self.body)

    def verbose(self):
        """ Returns string containing all fields and their values. Verbose. """
        return pprint(self.__dict__)


class ReddiWrap:
    """
        Class for interacting with reddit.com
        Uses reddit's API.
    """

    def __init__(self):
        """
            Initializes instance fields, sets user agent.
            Logs into reddit if user and password are given.
        """

        # Create object we will use to communicate with reddit's servers
        self.web = Httpy()

        self.modhash = ''  # Hash used to authenticate/interact with user account
        self.last_url = ''  # The last URL retrieved
        self.before = None  # ID pointing to 'previous' page
        self.after = None  # ID pointing to 'next' page
        self.logged_in = False  # Flag to detect if we are logged in or not

    ################
    # WEB REQUESTS #
    ################

    @staticmethod
    def fix_url(url):
        """
            'Corrects' a given URL as needed. Ensures URL will function with API properly.

            Ensures:
                * URL begins with http://
                * 'reddit.com' is used instead of 'www.reddit.com'
                * URL contains '.json'
                * URLs that are relative (start with '/') start with 'reddit.com'
        """
        result = url
        if result == '':
            result = '/'

        if result.startswith('/'):
            result = 'http://reddit.com' + result

        if not result.startswith('http://'):
            result = 'http://' + result

        # Get does not like 'www.' for some reason.
        result = result.replace('www.reddit.com', 'reddit.com')

        if '.json' not in result:
            q = result.find('?')
            if q == -1:
                result += '.json'
            else:
                result = result[:q] + '.json' + result[q:]
        return result

    def get(self, url):
        """
            Returns a list of Post and/or Comment and/or Message and/or Subreddit objects.

            Requesting comments will return a list of Comments. Examples:
                * .get('/r/all/comments')
                * .get('/user/godofatheism/comments')
            Requesting front pages and the like (/top) will return lists of Posts. Examples:
                * .get('')
                * .get('/r/all')
                * .get('/user/blackstar9000/submitted')
            Requesting user pages will return lists of Posts AND Comments. Example:
                * .get('/user/violentacrez')
            Requesting "reddits" will return a list of Subreddit objects. Example:
                * .get('/reddits')
            Requesting messages will return a list of Comment and/or Message objects. Examples:
                * .get('/message/inbox')

            Returns None if unable to get data from URL.
            Returns empty list [] if no results are found.

            'url' must be within reddit.com domain.

            This method automatically updates self.modhash so you don't have to.

        """

        # "Fix" URL to ensure it is formatted for reddit queries
        url = self.fix_url(url)

        r = self.web.get(url)  # Get the response

        if r == '' or r == '""' or r == '"{}"':
            return None  # Server gave null response.

        try:
            js = json.loads(r)
        except ValueError:
            # If it's not JSON, we don't want to parse it.
            return None
        except TypeError:
            # Parsing JSON led to a TypeError (probably unpack non-sequence)
            return None

        posts = []
        # If the response json contains a LIST of objects: post (0) & comments (1)
        if isinstance(js, list):
            if len(js) < 2:
                return None
            # Main Post
            data = js[0]['data']
            for child in data.get('children'):
                cdata = child['data']
                post = Post()
                post.modhash = data['modhash']
                post.set_using_json_data(cdata)
                posts.append(post)
            # Comment
            data = js[1]['data']
            for child in data.get('children'):
                cdata = child['data']
                ckind = child['kind']
                if ckind == 'more':
                    post.has_more_comments = True
                    post.more_comments = cdata
                    continue
                comment = Comment()
                comment.set_using_json_data(cdata)
                post.comments.append(comment)

        # Or simply the data object (subreddit page, user page, etc)
        elif isinstance(js, dict):
            data = js.get('data')
            if data is None or data.get('children') is None:
                return posts
            for child in data.get('children'):
                cdata = child['data']
                if child['kind'] == 't3':
                    # Post
                    post = Post()
                    post.modhash = data['modhash']
                    post.set_using_json_data(cdata)
                    posts.append(post)
                elif child['kind'] == 't1':
                    # Comment
                    comment = Comment()
                    comment.modhash = data['modhash']
                    comment.set_using_json_data(cdata)
                    posts.append(comment)
                elif child['kind'] == 't4':
                    # Message/PM (inbox)
                    msg = Message(cdata)
                    posts.append(msg)
                elif child['kind'] == 't5':
                    # Subreddit
                    subr = Subreddit(cdata)
                    posts.append(subr)

        # Set the variables to keep track of the user hash and current page.
        self.modhash = data.get('modhash')
        if '/comments/' not in url:
            # Only set before/after (get_next()/get_prev()) if we
            # loaded something OTHER than a post's comments
            # This allows us to continue to use .get_prev/.get_next
            self.before = data.get('before')
            self.after = data.get('after')
            # Save last URL in case user wants to get_next() or get_previous()
            self.last_url = url

        return posts

    def fetch_comments(self, post, limit=0):
        """
            Retrieves comments for a given Post.
            Sets the comments to the given Post object.
            Can be used to "refresh" comments for a Post.
            "limit" is the number of posts to grab, uses account's preference as default.
        """
        # Retrieve Post
        url = '/r/%s/comments/%s' % (post.subreddit, post.id)
        if limit != 0:
            url += '?limit=%d' % (limit,)
        posts = self.get(url)
        # We only expect 1 result: posts[0]
        if posts is None or len(posts) == 0:
            return
        post.comments = posts[0].comments
        post.num_comments = posts[0].num_comments

    def navigate(self, after=True):
        """
            Helper method, used by get_next() and get_previous().
            Used to retrieve the 'next' (or 'previous') page on reddit.
            If "after" == True, it loads the next page; otherwise, loads the previous
            Returns the same format of information as get():
                * None if unable to retrieve,
                * [] if no results
                * Otherwise, list of relevantPost and/or Comment objects
        """
        if after:
            nav_text = 'after'
            nav_id = self.after
        else:
            nav_text = 'before'
            nav_id = self.before
        if nav_id is None:
            return []  # No previous/next link to navigate with.
        url = self.last_url
        # Strip out after/before params from the previous URL.
        if '?before' in url:
            url = url[:url.find('?before')]
        if '&before' in url:
            url = url[:url.find('&before')]
        if '?after' in url:
            url = url[:url.find('?after')]
        if '&after' in url:
            url = url[:url.find('&after')]

        if '?' in url:
            url += '&%s=%s' % (nav_text, nav_id)
        else:
            url += '?%s=%s' % (nav_text, nav_id)
        url += '&count=25'  # Include "count=#" the navigation to work properly!
        return self.get(url)

    def get_previous(self):
        """
            Go "back" -- that is, retrieve previous 25/50/100 posts. See navigate()
            Returns None if unable to retrieve, or [] if no results are found.
        """
        return self.navigate(after=False)

    def get_next(self):
        """
            Go "next" -- retrieve the next 25/50/100 posts. See navigate()
            Returns None if unable to retrieve, or [] if no results are found.
        """
        return self.navigate(after=True)

    def has_previous(self):
        """ Returns True if there is a 'previous' page, False otherwise.  """
        return self.before is not None

    def has_next(self):
        """ Returns True if there is a 'next' page, False otherwise.  """
        return self.after is not None
