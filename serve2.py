#!/usr/bin/env python3
"""PhotoFloat modern server — recursive album discovery from config.json sources."""

import json
import os
import random
import threading
import time
from flask import Flask, send_from_directory, jsonify, abort
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
WEB_PATH = os.path.join(BASE_DIR, "web2")
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# Background thumb generation state
bg_status = {"running": False, "current": "", "done": 0, "total": 0}

app = Flask(__name__, static_folder=None)

def is_image(path):
    return os.path.isfile(path) and os.path.splitext(path)[1].lower() in EXTENSIONS

_album_cache = {"data": [], "files": {}, "ts": 0}
_CACHE_TTL = 30  # seconds

def discover_albums(force=False):
    now = time.time()
    if not force and _album_cache["data"] and (now - _album_cache["ts"]) < _CACHE_TTL:
        return _album_cache["data"]
    cfg = load_config()
    albums = []
    file_map = {}
    for source in cfg["sources"]:
        if not os.path.isdir(source):
            continue
        for dirpath, dirnames, filenames in os.walk(source):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            photos = sorted([f for f in filenames if os.path.splitext(f)[1].lower() in EXTENSIONS])
            if photos:
                rel = os.path.relpath(dirpath, source)
                name = os.path.basename(source) if rel == '.' else rel
                a = {
                    "name": name,
                    "abs_path": dirpath,
                    "source": source,
                    "count": len(photos),
                    "cover_file": random.choice(photos)
                }
                albums.append(a)
                file_map[album_id_for(a)] = photos
    _album_cache["data"] = albums
    _album_cache["files"] = file_map
    _album_cache["ts"] = now
    return albums

def get_album_files(album_id):
    discover_albums()
    return _album_cache["files"].get(album_id, [])

def find_album(album_id):
    for a in discover_albums():
        if album_id_for(a) == album_id:
            return a
    return None

def album_id_for(album):
    rel = os.path.relpath(album["abs_path"], album["source"])
    base = os.path.basename(album["source"])
    return base if rel == '.' else base + "/" + rel

def thumb_path_for(cache_key, filename):
    cfg = load_config()
    safe_dir = cache_key.replace("/", "_").replace("\\", "_")
    d = os.path.join(cfg["cache_path"], safe_dir)
    os.makedirs(d, exist_ok=True)
    return d, os.path.splitext(filename)[0] + "_300.jpg"

def generate_thumb(src, dst):
    try:
        print(f"  [thumb] {os.path.basename(src)}")
        img = Image.open(src)
        img.thumbnail((300, 300), Image.LANCZOS)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(dst, "JPEG", quality=85)
    except Exception as e:
        print(f"  [error] {os.path.basename(src)}: {e}")

def bg_generate_all():
    global bg_status
    bg_status = {"running": True, "current": "", "done": 0, "total": 0}
    tasks = []
    for a in discover_albums():
        aid = album_id_for(a)
        for f in os.listdir(a["abs_path"]):
            full = os.path.join(a["abs_path"], f)
            if not os.path.isfile(full) or os.path.splitext(f)[1].lower() not in EXTENSIONS:
                continue
            cache_dir, thumb_name = thumb_path_for(aid, f)
            if not os.path.exists(os.path.join(cache_dir, thumb_name)):
                tasks.append((full, os.path.join(cache_dir, thumb_name), f))
    bg_status["total"] = len(tasks)
    for src, dst, name in tasks:
        bg_status["current"] = name
        generate_thumb(src, dst)
        bg_status["done"] += 1
    bg_status["current"] = ""
    bg_status["running"] = False

def start_bg_generation():
    if not bg_status["running"]:
        threading.Thread(target=bg_generate_all, daemon=True).start()

# --- Routes ---

@app.route("/")
def index():
    return send_from_directory(WEB_PATH, "index.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(os.path.join(WEB_PATH, "static"), path)

@app.route("/api/albums")
def api_albums():
    result = []
    for a in discover_albums():
        aid = album_id_for(a)
        result.append({
            "id": aid, "name": a["name"], "count": a["count"],
            "cover": f"/api/thumb/{aid}/{a['cover_file']}"
        })
    return jsonify(result)

@app.route("/api/photos/<path:album_id>")
def api_photos(album_id):
    album = find_album(album_id)
    if not album:
        abort(404)
    files = get_album_files(album_id)
    photos = [{"name": f, "thumb": f"/api/thumb/{album_id}/{f}", "full": f"/api/photo/{album_id}/{f}"} for f in files]
    return jsonify(photos)

@app.route("/api/photo/<path:album_id>/<filename>")
def api_photo(album_id, filename):
    album = find_album(album_id)
    if not album:
        abort(404)
    return send_from_directory(album["abs_path"], filename)

@app.route("/api/thumb/<path:album_id>/<filename>")
def api_thumb(album_id, filename):
    album = find_album(album_id)
    if not album:
        abort(404)
    cache_dir, thumb_name = thumb_path_for(album_id, filename)
    thumb_full = os.path.join(cache_dir, thumb_name)
    if not os.path.exists(thumb_full):
        original = os.path.join(album["abs_path"], filename)
        if not os.path.isfile(original):
            abort(404)
        generate_thumb(original, thumb_full)
    return send_from_directory(cache_dir, thumb_name)

@app.route("/api/status")
def api_status():
    result = []
    for a in discover_albums():
        aid = album_id_for(a)
        cache_dir, _ = thumb_path_for(aid, "dummy")
        generated = len([f for f in os.listdir(cache_dir) if f.endswith('.jpg')]) if os.path.isdir(cache_dir) else 0
        result.append({"id": aid, "name": a["name"], "path": a["abs_path"], "photos": a["count"], "thumbs": generated})
    return jsonify({"albums": result, "bg": bg_status})

@app.route("/api/generate")
def api_generate():
    start_bg_generation()
    return jsonify({"started": True})

@app.route("/api/cleanup")
def api_cleanup():
    """Remove orphan thumbs for deleted photos."""
    removed = 0
    for a in discover_albums(force=True):
        aid = album_id_for(a)
        cache_dir, _ = thumb_path_for(aid, "dummy")
        if not os.path.isdir(cache_dir):
            continue
        real_files = set(os.path.splitext(f)[0] for f in os.listdir(a["abs_path"])
                        if os.path.splitext(f)[1].lower() in EXTENSIONS)
        for thumb in os.listdir(cache_dir):
            base = thumb.rsplit("_300", 1)[0]
            if base not in real_files:
                os.unlink(os.path.join(cache_dir, thumb))
                removed += 1
    # also clean empty cache dirs
    cfg = load_config()
    for d in os.listdir(cfg["cache_path"]):
        full = os.path.join(cfg["cache_path"], d)
        if os.path.isdir(full) and not os.listdir(full):
            os.rmdir(full)
    return jsonify({"removed": removed})

if __name__ == "__main__":
    cfg = load_config()
    albums = discover_albums()
    print(f"Found {len(albums)} albums:")
    for a in albums:
        print(f"  {album_id_for(a):30s} ({a['count']} photos) -> {a['abs_path']}")
    start_bg_generation()
    print(f"\nOpen http://localhost:{cfg.get('port', 5000)}")
    app.run(host="0.0.0.0", port=cfg.get("port", 5000), debug=True, use_reloader=False)
