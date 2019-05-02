#!/usr/bin/env bash

sudo docker run --rm -dit --name tmp_dev_irarchives -p 8080:80 \
    -v $(pwd)/:/usr/local/apache2/htdocs/ httpd:2.4