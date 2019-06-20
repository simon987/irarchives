import json
from collections import namedtuple
from multiprocessing import Process, JoinableQueue as Queue
from queue import Empty

import psycopg2
from pycurl import Curl

from common import DBFILE
from scan import Scanner
from util import get_links_from_body

Post = namedtuple("Post", "id title url selftext author permalink subreddit num_comments"
                          " upvotes downvotes score created_utc is_self over_18")


def work_post(q):
    scanner = Scanner()
    # don't use proxy
    scanner.web.curl = Curl()
    scanner.web.curl.setopt(scanner.web.curl.SSL_VERIFYPEER, 0)
    scanner.web.curl.setopt(scanner.web.curl.SSL_VERIFYHOST, 0)

    done = set()

    conn = psycopg2.connect(DBFILE)
    cur = conn.cursor()
    cur.execute("SELECT hexid from Posts")
    for row in cur.fetchall():
        done.add(row[0])
    conn.close()
    print("Thread initialised")
    while True:
        try:
            post = q.get()
        except Empty:
            break

        try:
            if post.id in done:
                continue
            if post.is_self and post.selftext:
                urls = get_links_from_body(post.selftext)
                if not urls:
                    continue
            elif not post.url:
                continue
            postid_db = scanner.db.insert_post(
                post.id,
                post.title,
                post.url,
                post.selftext,
                post.author,
                post.permalink,
                post.subreddit,
                post.num_comments,
                post.upvotes,
                post.downvotes,
                post.score,
                int(post.created_utc),
                post.is_self,
                post.over_18)

            if post.is_self and post.selftext:
                for url in urls:
                    if should_parse_url(url):
                        scanner.parse_url(url, postid=postid_db)
            elif should_parse_url(post.url):
                scanner.parse_url(post.url, postid=postid_db)

        except Exception as e:
            print(e)
        finally:
            q.task_done()


def should_parse_url(url):
    if "minus.com" in url:
        return False
    if "pornhub.com" in url:
        return False
    if "instagram.com" in url:
        return False
    if "gfycat.com" in url:
        return False
    if "xhamster.com" in url:
        return False
    if "youporn.com" in url:
        return False
    if "tumblr.com" in url:
        return False
    if "blogspot.com" in url:
        return False
    return True


THREADS = 200
threads = []
queue = Queue(THREADS * 16)


def scan_posts():
    for _ in range(0, THREADS):
        t = Process(target=work_post, args=(queue,))
        t.start()
        threads.append(t)
        print("Started thread...")

    with open("posts.ndjson") as f:
        for line in f:
            post_json = json.loads(line)
            queue.put(Post(**post_json), timeout=100000000)

    queue.join()
    print("Waiting for threads to join()")
    for t in threads:
        t.join()


scan_posts()
