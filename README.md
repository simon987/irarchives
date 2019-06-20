irarchives
==========

[![CodeFactor](https://www.codefactor.io/repository/github/simon987/irarchives/badge/master)](https://www.codefactor.io/repository/github/simon987/irarchives/overview/master)
![GitHub](https://img.shields.io/github/license/simon987/irarchives.svg)

Summary
-------
NSFW reverse image search for reddit

Overview
--------
Many NSFW reddit posts contain more information about an image. 

The repo contains:
* a script to scrape images from reddit posts and store the data in a database.
* a web interface for searching the database

### Database schema
![schema](schema.png)

Requirements
------------
Tested with Python 3.7.2.

Dependencies on Debian: `apt install libgmp-dev libmpfr-dev libmpc-dev`

This project relies on [Architeuthis](https://github.com/simon987/Architeuthis) MITM proxy to respect rate-limits
and handle http errors. 

Notes
-----
There is no database included with the repo for obvious reasons. 
