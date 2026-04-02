#!/usr/bin/env python3
"""Simple dev server for photofloat - serves web UI + albums/cache directly."""

import os
import sys
from flask import Flask, send_from_directory, send_file

ALBUM_PATH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/photofloat_test/albums"
CACHE_PATH = sys.argv[2] if len(sys.argv) > 2 else "/tmp/photofloat_test/cache"
WEB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(WEB_PATH, "index.html")

@app.route("/css/<path:path>")
def css(path):
    return send_from_directory(os.path.join(WEB_PATH, "css"), path)

@app.route("/js/<path:path>")
def js(path):
    return send_from_directory(os.path.join(WEB_PATH, "js"), path)

@app.route("/fonts/<path:path>")
def fonts(path):
    return send_from_directory(os.path.join(WEB_PATH, "fonts"), path)

@app.route("/img/<path:path>")
def img(path):
    return send_from_directory(os.path.join(WEB_PATH, "img"), path)

@app.route("/albums/<path:path>")
def albums(path):
    return send_from_directory(ALBUM_PATH, path)

@app.route("/cache/<path:path>")
def cache(path):
    full = os.path.join(CACHE_PATH, path)
    if not os.path.isfile(full):
        # JS strips "root-" prefix, try adding it back
        alt = os.path.join(CACHE_PATH, "root-" + path)
        if os.path.isfile(alt):
            return send_from_directory(CACHE_PATH, "root-" + path)
    return send_from_directory(CACHE_PATH, path)

@app.route("/auth")
def auth():
    return "", 200

if __name__ == "__main__":
    print(f"Albums: {ALBUM_PATH}")
    print(f"Cache:  {CACHE_PATH}")
    print(f"Web:    {WEB_PATH}")
    print(f"Open http://localhost:5000 in your browser")
    app.run(host="0.0.0.0", port=5000, debug=True)
