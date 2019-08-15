from collections import namedtuple

POST_FIELDS = [
    "author", "created", "created_utc", "downs",
    "id", "is_self", "num_comments", "over_18",
    "score", "selftext", "subreddit", "ups", "title",
    "url", "permalink", "urls"
]
Post = namedtuple("Post", POST_FIELDS)

COMMENT_FIELDS = [
    "author", "body", "created", "created_utc",
    "downs", "id", "permalink", "score", "subreddit",
    "ups", "link_id", "urls"
]
Comment = namedtuple("Comment", COMMENT_FIELDS)
