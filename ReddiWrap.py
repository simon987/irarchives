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
from datetime import date  # For converting unix epoch time in seconds to date/time
from pprint import pprint
from time import time  # For getting current... and possibly throttling requests

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


class UserInfo(object):
    """ Contains information about the currently-logged-in reddit user. See user_info() """

    def __init__(self, json_data):
        if json_data.get('error') == 404:
            self.error = 404
        else:
            self.id = json_data['id']
            self.has_mail = json_data['has_mail']  # Boolean, True if user has unread mail.
            self.name = json_data['name']  # String, username
            self.created = json_data['created']  # Time since 1/1/1970 when acct was created
            self.created_utc = json_data['created_utc']  # Same as 'created', but in UTC
            # self.modhash       = json_data['modhash']       # Unique hash for interacting with account
            self.link_karma = json_data['link_karma']  # Integer, total score of submissions
            self.comment_karma = json_data['comment_karma']  # Integer, total score of comments
            self.is_gold = json_data['is_gold']  # Boolean
            self.has_mod_mail = json_data['has_mod_mail']  # Boolean
            self.is_mod = json_data['is_mod']  # Boolean

    def __repr__(self):
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

    def __init__(self, user='', password='', user_agent=None):
        """
            Initializes instance fields, sets user agent.
            Logs into reddit if user and password are given.
        """

        # Default user agent is awesome!
        if user_agent is None:
            user_agent = 'ReddiWrap'

        # Create object we will use to communicate with reddit's servers
        self.web = Httpy(user_agent=user_agent)

        self.modhash = ''  # Hash used to authenticate/interact with user account
        self.last_url = ''  # The last URL retrieved
        self.before = None  # ID pointing to 'previous' page
        self.after = None  # ID pointing to 'next' page
        self.logged_in = False  # Flag to detect if we are logged in or not

        # Sets instance fields, logs in user if needed.
        self.login(user, password)

    ####################
    # LOGGING IN & OUT #
    ####################

    def login(self, user='', password=''):
        """
            Clears cookies/modhash, then logs into reddit if applicable.
            Logs out user if user or password is '' or None

            Returns 0 if login (or logout) is successful,
            Returns 1 if user/pass is invalid,
            Returns 2 if login rate limit is reached,
            Returns -1 if some unknown error is encountered
        """

        self.web.clear_cookies()  # Removes any traces of previous activity
        self.modhash = ''
        self.logged_in = False

        if user == '' or user is None or \
                password == '' or password is None:
            # "Log out"
            self.user = ''
            self.password = ''
            return 0

        self.user = user
        self.password = password

        data = {'user': self.user, 'passwd': self.password, 'api_type': 'json'}

        r = self.web.post('http://www.reddit.com/api/login/%s' % self.user, data)
        if "WRONG_PASSWORD" in r:
            # Invalid password
            return 1
        elif 'RATELIMIT' in r:
            # Rate limit reached.
            return 2
        else:  # if 'redirect' in r:
            js = json.loads(r)
            if js.get('json') is None or js['json'].get('data') is None:
                return -1
            # Correct password.
            self.logged_in = True
            self.modhash = js['json']['data']['modhash']
            return 0
        # Unexpected response.
        return -1

    def logout(self):
        """
            "Logs out": Clears cookies, resets modhash.
        """
        self.switch_user('', '')

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

    ##########
    # VOTING #
    ##########

    def vote(self, post, direction):
        """
            Votes for a post or comment.
            "post" is the Post/Comment object to vote on.
            "direction" is vote type: 1 to upvote, -1 to downvote, 0 to rescind vote.
            Returns True if vote was casted successful, False otherwise.
        """
        if self.modhash == '':
            return False  # Modhash required to vote
        data = {}
        if isinstance(post, Post):
            data['id'] = 't3_%s' % post.id
        else:
            data['id'] = 't1_%s' % post.id
        data['dir'] = str(direction)
        data['uh'] = self.modhash
        response = self.web.post('http://www.reddit.com/api/vote', data)
        # Reddit should respond with '{}' if vote was successful.
        return response == '{}'

    def upvote(self, post):
        return self.vote(post, 1)

    def downvote(self, post):
        return self.vote(post, -1)

    def novote(self, post):
        return self.vote(post, 0)

    ##############
    # COMMENTING #
    ##############

    def get_user_comments(self, user, sort=''):
        """
            Returns list of Comments made by "user".
            "sort" changes the order of comments; use "new", "old" or "top"
            Returns None if unable to retrieve.
        """
        return self.get('/user/%s/comments/' % user)

    def get_user_posts(self, user, sort=''):
        """
            Returns list of Posts made by "user".
            "sort" changes the order of posts; use "new", "old" or "top"
            Returns None if unable to retrieve.
        """
        return self.get('/user/%s/submitted/' % user)

    def reply(self, post, text):
        """
            Reply to given Post, Comment, or Message.
            "post" is the Post, Comment, or Message object to reply to.
            "text" is the text to reply with.

            Returns empty dict {} if unable to reply.
            Otherwise, returns dict containing reply information:
              'content':     javascript for updating layout on main site
                'contentText': Plaintext of reply's body. Probably identical to 'text' parameter
                'contentHTML': HTML-formatted text of reply's body
                'id':          base36 ID of reply  E.g. t1_c58sfuc (Comment) or t4_cqug9 (Message)
                'parent':      base36 ID of parent E.g. t1_c58sfog (Comment) or t4_cpgyw (Message)
            Comments/Posts have additional keys in dict:
                'replies':     List of replies to reply (?) probably empty everytime...
                'link':        base36 ID of post reply was inside of. E.g. t3_vvtts

            TODO Return a new Comment/Message object, containing expected values.
        """
        result = {}
        data = {'uh': self.modhash, 'text': text}

        if isinstance(post, Post):
            data['thing_id'] = 't3_%s' % post.id
        elif isinstance(post, Comment):
            data['parent'] = 't1_%s' % post.id
        elif isinstance(post, Message):
            data['thing_id'] = post.name

        response = self.web.post('http://www.reddit.com/api/comment', data)
        if '".error.USER_REQUIRED"' in response:
            return result
        # Extract appropriate dict out of response
        jres = json.loads(response)
        jquery = jres.get('jquery')
        if jquery is None:
            return result

        for i in range(0, len(jquery)):
            if not isinstance(jquery[i][3], list) or not jquery[i][3]:
                continue
            if not isinstance(jquery[i][3][0], list) or not jquery[i][3][0]:
                continue
            jdict = jquery[i][3][0][0]
            result = jdict.get('data')
            break
        return result

    #############
    # SEARCHING #
    #############

    def search(self, query, subreddit='', sort=''):
        """
            Searches reddit, returns list of results.
            "query" is the text to search for on reddit
            "subreddit" is the subreddit to restrict the search to. Use '' to search all of reddit.
            "sort" is the order of results. Use "new", "top" or "relevance" (default)

            Examples:
                results = reddit.search('girlfriend')
                results = reddit.search('skateboard', subreddit='pics')
                results = reddit.search('birthday', subreddit='pics', sort='new')
            After calling search(), you can call get_next() and get_previous() to navigate.
        """
        url = '/search?q=' + query
        if sort != '':
            url += '&sort=' + sort
        if subreddit != '':
            url = '/r/' + subreddit + url + '&restrict_sr=on'
        return self.get(url)

    ##############
    # NAVIGATING #
    ##############

    """
        Notice that inside of the 'get()' method, we store:
            * the last URL retrieved (self.last_url)
            * the 'before' tag which links to the previous page (self.before)
            * the 'after'  tag which links to the next page     (self.after)
        Because of this, we can load the 'next' or 'previous' pages of some results.
        This will only go to the 'next' or 'previous' page of the LAST PAGE RETRIEVED using get()
        This means get_next() and get_previous() will only be operational AFTER retrieving:
            * subreddits:     .get('/r/subreddit')
            * the main page:  .get('')
            * search results: .search('my face when')
            * user pages:     .get('/user/krispykrackers')
            * ...possibly others?
    """

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

    ###########
    # POSTING #
    ###########

    def post_link(self, title, link, subreddit):
        """
            Submits a new link (URL) to reddit.
            No captcha support! User must have verified email address
            "title" is the title of the submission, "link" is the submission's URL.
            "subreddit" is the NAME of the subreddit to post to, e.g. 'funny' NOT '/r/funny'.
            Returns permalink to post if successful, e.g. 'r/Subreddit/comments/id/title'
            Returns permalink of EXISTING link (with ?already_submitted=true) if the link already exists.
            Returns '' if unable to post (not logged in, unverified email).
        """
        if not self.logged_in:
            return ''
        data = {'uh': self.modhash, 'kind': 'link', 'url': link, 'sr': subreddit, 'title': title, 'r': subreddit,
                'renderstyle': 'html'}
        response = self.web.post('http://www.reddit.com/api/submit', data)
        if "You haven't verified your email address" in response:
            return ''

        if 'already_submitted=true' in response:
            # Link already exists in that subreddit!
            jres = json.loads(response)
            existing_link = jres['jquery'][10][3][0]
            # Return existing link
            return existing_link
        link = self.web.between(response, 'call", ["http://www.reddit.com/', '"]')[0]
        return link

    def post_self(self, title, text, subreddit):
        """
            Submits a new "self-post" (text-based post) reddit.
            "title" is the title of the submission. "text" is the self-text.
            "subreddit" is the NAME of the subreddit to post to, e.g. 'funny' NOT '/r/funny'.
            Returns permalink to post if successful, e.g. 'r/Subreddit/comments/id/title'
            Returns '' if unable to post (not logged in, unverified email)
        """
        data = {'uh': self.modhash, 'title': title, 'kind': 'self', 'thing_id': '', 'text': text, 'sr': subreddit,
                'id': '#newlink', 'r': subreddit, 'renderstyle': 'html'}
        response = self.web.post('http://www.reddit.com/api/submit', data)
        if "You haven't verified your email address" in response:
            return ''
        link = self.web.between(response, 'call", ["http://www.reddit.com/', '"]')[0]
        return link

    ############
    # MESSAGES #
    ############
    def compose(self, recipient, subject, message):
        """
            Sends PM to recipient.
            Returns True if message was sent successfully, False otherwise.
        """
        data = {'id': '#compose-message', 'uh': self.modhash, 'to': recipient, 'text': message, 'subject': subject,
                'thing-id': '', 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/compose', data)
        return 'your message has been delivered' in r

    def mark_message(self, message, mark_as_read=True):
        """ Marks passed message as either 'read' or 'unread' depending on mark_as_read's value """
        data = {'id': message.name, 'uh': self.modhash, 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/read_message', data)
        message.new = not mark_as_read

    ########################
    # USER-RELATED METHODS #
    ########################

    def user_info(self, username=None):
        """
            If username is unset (None), returns UserInfo object for the currently-logged-in user.
            If username is set (String), returns UserInfo object for the given 'username'

            Returns a userinfo with .error = 404 if user page is not found. example:
                uinfo = reddit.user_info('violentacres')
                if uinfo.error == 404: print 'violentacres is still gone!'
                else: print 'Who unbanned him?'

            Returns None object if unable to retrieve data.
        """
        if username is None:
            if not self.logged_in: return None
            url = 'http://reddit.com/api/me.json'
        else:
            url = 'http://reddit.com/user/%s/about.json' % username
        r = self.web.get(url)
        if r == '' or r == '""':
            return None  # Server gave null response.
        try:
            js = json.loads(r)
        except ValueError:
            return None  # If it's not JSON, we can't parse it.
        if js is None:
            return None
        return UserInfo(js.get('data'))

    def save(self, post):
        """ Saves Post to user account. "post" is the actual Post object to save. """
        data = {'id': post.id, 'uh': self.modhash}
        response = self.web.post('http://www.reddit.com/api/save', data)
        return response == '{}'

    def unsave(self, post):
        """ Un-saves Post from user account. "post" is the actual Post object to un-save. """
        data = {'id': post.id, 'uh': self.modhash}
        response = self.web.post('http://www.reddit.com/api/unsave', data)
        return response == '{}'

    def hide(self, post):
        """ Hides Post from user's visibility. "post" is the actual Post object to hide. """
        data = {'id': post.id, 'uh': self.modhash, 'executed': 'hidden'}
        response = self.web.post('http://www.reddit.com/api/hide', data)
        return response == '{}'

    def unhide(self, post):
        """ Un-hides Post from user's visibility. "post" is the actual Post object to un-hide. """
        data = {'id': post.id, 'uh': self.modhash, 'executed': 'unhidden'}
        response = self.web.post('http://www.reddit.com/api/unhide', data)
        return response == '{}'

    def report(self, post):
        """ Reports a post or comment to the mods of the current subreddit. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'executed': 'reported', 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/report', data)
        return r == '{}'

    def share(self, post, from_username, from_email, to_email, message):
        """ Share a post with someone via email. """
        data = {'id': '#sharelink_' + post.name, 'uh': self.modhash, 'r': post.subreddit, 'parent': post.name,
                'message': message, 'replyto': from_email, 'share_to': to_email, 'share_from': from_username,
                'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/share', data)
        return 'your link has been shared' in r

    def mark_nsfw(self, post):
        """ Marks a Post as NSFW. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/marknsfw', data)
        return r == '{}'

    def unmark_nsfw(self, post):
        """ Removes NSFW mark from a Post. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/unmarknsfw', data)
        return r == '{}'

    def subscribe(self, subreddit, unsub=False):
        """ Subscribes (or unsubscribes) user to/from subreddit. """
        data = {'sr': subreddit.name, 'uh': self.modhash, 'r': subreddit.display_name, 'renderstyle': 'html'}
        if not unsub:
            data['action'] = 'sub'
        else:
            data['action'] = 'unsub'
        r = self.web.post('http://www.reddit.com/api/subscribe', data)
        return r == '{}'

    #############
    # MODERATOR #
    #############

    def spam(self, post):
        """ Marks a Post (or Comment) as 'spam'. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/remove', data)
        return r == '{}'

    def approve(self, post):
        """ Un-removes ('approves') a Post or Comment. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/approve', data)
        return r == '{}'

    def remove(self, post):
        """ Removes a Post or Comment from public view. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'spam': 'False', 'renderstyle': 'html'}
        r = self.web.post('http://www.reddit.com/api/remove', data)
        return r == '{}'

    def distinguish(self, post, turn_on=True):
        """ Distinguishes a Post or Comment with moderator flair. """
        data = {'id': post.name, 'uh': self.modhash, 'r': post.subreddit, 'renderstyle': 'html'}
        url = 'http://www.reddit.com/api/distinguish/'
        if turn_on:
            url += 'yes'
        else:
            url += 'no'
        r = self.web.post(url, data)
        return r != ''

    def approved_submitter(self, subreddit, username, add_user=True):
        """
            Add/remove user as an Approved Submitter for a given Subreddit.
            subreddit is a Subreddit object! Must have .name and .display_name
            Must be logged in as a moderator of the Subreddit.
        """
        data = {'id': '#contributor', 'uh': self.modhash, 'r': subreddit.display_name, 'name': username,
                'type': 'contributor', 'action': 'add', 'container': subreddit.name, 'renderstyle': 'html'}
        url = 'http://www.reddit.com/api/'
        if add_user:
            url += 'friend'
        else:
            url += 'unfriend'
        r = self.web.post(url, data)
        return r != ''

    def moderator(self, subreddit, username):
        """
            Add/remove user as a moderator of a given Subreddit
            subreddit is a Subreddit object! Must have .name and .display_name
            Must be logged in as a moderator of the Subreddit.
        """
        data = {'id': '#moderator', 'uh': self.modhash, 'r': subreddit.display_name, 'name': username,
                'type': 'moderator', 'action': 'add', 'container': subreddit.name, 'renderstyle': 'html'}
        url = 'http://www.reddit.com/api/'
        if add_user:
            url += 'friend'
        else:
            url += 'unfriend'
        r = self.web.post(url, data)
        return r != ''

    def time_to_date(self, seconds):
        """ Returns date object based on given seconds. """
        return date.fromtimestamp(seconds)

    def time_since(self, seconds):
        """ Returns time elapsed since current time in human-readable format. """
        delta = time() - seconds
        factors = [
            ('second', 60),
            ('minute', 60),
            ('hour', 24),
            ('day', 365),
            ('year', 10),
            ('decade', 100)
        ]
        current = delta
        for (unit, factor) in factors:
            if current < factor:
                plural = 's'
                if current == 1:
                    plural = ''
                return '%d %s%s' % (current, unit, plural)
            current /= factor
        current /= 365
        plural = 's'
        if current == 1:
            plural = ''
        return '%d %s%s' % (current, 'year', plural)
