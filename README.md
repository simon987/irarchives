irarchives
==========

Summary
-------
NSFW reverse image search for reddit

Overview
--------
Many NSFW reddit posts contain more information about an image. 

The repo contains:
* a script to scrape images from reddit posts and store the data in a database.
* a web interface for searching the database

Requirements
------------
Tested with Python 2.6.x. Should work with 2.7 and possibly 2.5 (not compatible with 2.4 due to JSON limitations).

The image calculations require Python Imaging Library, or [PIL](http://www.pythonware.com/products/pil/).

Notes
-----
There is no database included with the repo for obvious reasons. 
