MayOne.us RELOADED
==================

We're trying a different architecture on GAE.

This project is licensed under the Apache License, version 2.

CODERS NEEDED!
--------------
If you can contribute and know python, or html/CSS, contact yt@hjfreyer.com, or file a bug, or go to Freenode IRC #mayone and volunteer.

Design sketch
-------------

The majority of the site is just basic static content, as it should
be. That markup lives in "markup/" in the form of jade files. If you
don't know what those are, they're very simple, and remove literally
50% of HTML's boilerplate so they're worth it. Read the 3 minute
tutorial.

Stylesheets are in "stylesheets/" as sass files. See last paragraph
for why that's good.

Ideally there will be little enough JS that no framework will be necessary (fingers crossed).

The backend will be very simple with two endpoints

1. Pledge. This has to be done in coordination with stripe so that stripe stores the credit card info, and we only store an opaque token and the pledge amount. This will write to what'll be probably the only table in the datastore.
2. GetTotal: Simple sum over pledges. Store it in memcache, expire every few minutes. Boom.

Hacking
-------
To run the server, you need to have the Python App Engine SDK installed, as well as npm (which we use for the build system), and sass for compiling the stylesheets.

After checking out the code, run `npm install`. To start the server, rung `npm start` and go to http://localhost:8080. That's it!
