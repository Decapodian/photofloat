#!/usr/bin/env python3
"""PhotoFloat modern server — hierarchical album navigation from config.json sources."""

import json
import os
import random
import threading
import time
from flask import Flask, send_from_directory, jsonify, abort
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
WEB_PATH = os.path.join(BASE_DIR, "web")
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# --- Directory cache ---
_dir_cache = {"ts": 0}
_CACHE_TTL = 30

def _resolve_path(album_path):
    """Resolve an album_path like 'boot/boot1/Nube mg misc' to a real filesystem path."""
    cfg = load_config()
    if not album_path:
        return None
    parts = album_path.split("/", 1)
    root_name = parts[0]
    for source in cfg["sources"]:
        if os.path.basename(source) == root_name:
            if len(parts) == 1:
                return source
            return os.path.join(source, parts[1])
    return None

def _list_dir_cached(path):
    """List directory with caching."""
    now = time.time()
    key = path
    if key in _dir_cache and (now - _dir_cache.get(key + "_ts", 0)) < _CACHE_TTL:
        return _dir_cache[key]
    try:
        entries = os.listdir(path)
    except OSError:
        entries = []
    _dir_cache[key] = entries
    _dir_cache[key + "_ts"] = now
    return entries

def _get_contents(real_path):
    """Get subfolders and photos in a directory."""
    entries = _list_dir_cached(real_path)
    subdirs = []
    photos = []
    for e in sorted(entries):
        if e.startswith('.'):
            continue
        full = os.path.join(real_path, e)
        if os.path.isdir(full):
            subdirs.append(e)
        elif os.path.splitext(e)[1].lower() in EXTENSIONS:
            photos.append(e)
    return subdirs, photos

def _find_random_photo(real_path, depth=3):
    """Find a random photo in this dir or subdirs for cover."""
    if depth <= 0:
        return None
    subdirs, photos = _get_contents(real_path)
    if photos:
        return os.path.join(real_path, random.choice(photos))
    for sd in subdirs:
        result = _find_random_photo(os.path.join(real_path, sd), depth - 1)
        if result:
            return result
    return None

# --- Background generation ---
bg_status = {"running": False, "current": "", "done": 0, "total": 0}

def _thumb_dir(album_path):
    cfg = load_config()
    safe = album_path.replace("/", "_").replace("\\", "_").replace(" ", "_")
    d = os.path.join(cfg["cache_path"], safe)
    os.makedirs(d, exist_ok=True)
    return d

def _thumb_name(filename):
    return os.path.splitext(filename)[0] + "_300.jpg"

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
    try:
        cfg = load_config()
        tasks = []
        for source in cfg["sources"]:
            if not os.path.isdir(source):
                continue
            base = os.path.basename(source)
            for dirpath, dirnames, filenames in os.walk(source):
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                rel = os.path.relpath(dirpath, source)
                album_path = base if rel == '.' else base + "/" + rel
                td = _thumb_dir(album_path)
                for f in filenames:
                    if os.path.splitext(f)[1].lower() not in EXTENSIONS:
                        continue
                    tn = _thumb_name(f)
                    if not os.path.exists(os.path.join(td, tn)):
                        tasks.append((os.path.join(dirpath, f), os.path.join(td, tn), f))
        bg_status["total"] = len(tasks)
        print(f"[bg] {len(tasks)} thumbs to generate")
        for src, dst, name in tasks:
            bg_status["current"] = name
            generate_thumb(src, dst)
            bg_status["done"] += 1
    except Exception as e:
        print(f"[bg error] {e}")
    finally:
        bg_status["current"] = ""
        bg_status["running"] = False
        _status_cache["data"] = None
        print("[bg] done")

def start_bg_generation():
    if not bg_status["running"]:
        threading.Thread(target=bg_generate_all, daemon=True).start()

# --- Flask app ---
app = Flask(__name__, static_folder=None)

@app.route("/")
def index():
    return send_from_directory(WEB_PATH, "index.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(os.path.join(WEB_PATH, "static"), path)

@app.route("/api/browse")
@app.route("/api/browse/<path:album_path>")
def api_browse(album_path=""):
    """Browse a directory: returns subalbums + photos."""
    cfg = load_config()

    if not album_path:
        # Root: show sources as top-level albums
        items = []
        for source in cfg["sources"]:
            if not os.path.isdir(source):
                continue
            name = os.path.basename(source)
            cover_file = _find_random_photo(source)
            cover = f"/api/cover?path={cover_file}" if cover_file else ""
            items.append({"name": name, "id": name, "type": "album", "cover": cover})
        return jsonify({"path": "", "albums": items, "photos": []})

    real_path = _resolve_path(album_path)
    if not real_path or not os.path.isdir(real_path):
        abort(404)

    subdirs, photos = _get_contents(real_path)

    albums = []
    for sd in subdirs:
        sub_id = album_path + "/" + sd
        cover_file = _find_random_photo(os.path.join(real_path, sd))
        cover = f"/api/cover?path={cover_file}" if cover_file else ""
        albums.append({"name": sd, "id": sub_id, "type": "album", "cover": cover})

    photo_list = []
    for f in photos:
        full = os.path.join(real_path, f)
        mtime = os.path.getmtime(full)
        size = os.path.getsize(full)
        photo_list.append({
            "name": f,
            "thumb": f"/api/thumb/{album_path}/{f}",
            "full": f"/api/photo/{album_path}/{f}",
            "date": mtime,
            "size": size
        })

    return jsonify({"path": album_path, "albums": albums, "photos": photo_list})

@app.route("/api/cover")
def api_cover():
    """Serve a cover thumbnail from absolute path."""
    path = os.path.abspath(os.path.normpath(os.path.expanduser(
        __import__('flask').request.args.get('path', ''))))
    # security: only serve from configured sources
    cfg = load_config()
    allowed = False
    for source in cfg["sources"]:
        if path.startswith(os.path.abspath(source)):
            allowed = True
            break
    if not allowed or not os.path.isfile(path):
        abort(404)
    # generate thumb on the fly
    cfg = load_config()
    cover_cache = os.path.join(cfg["cache_path"], "_covers")
    os.makedirs(cover_cache, exist_ok=True)
    thumb = os.path.join(cover_cache, str(hash(path)) + ".jpg")
    if not os.path.exists(thumb):
        generate_thumb(path, thumb)
    return send_from_directory(cover_cache, os.path.basename(thumb))

@app.route("/api/photo/<path:album_path>/<filename>")
def api_photo(album_path, filename):
    real_path = _resolve_path(album_path)
    if not real_path:
        abort(404)
    return send_from_directory(real_path, filename)

@app.route("/api/thumb/<path:album_path>/<filename>")
def api_thumb(album_path, filename):
    real_path = _resolve_path(album_path)
    if not real_path:
        abort(404)
    td = _thumb_dir(album_path)
    tn = _thumb_name(filename)
    full = os.path.join(td, tn)
    if not os.path.exists(full):
        original = os.path.join(real_path, filename)
        if not os.path.isfile(original):
            abort(404)
        generate_thumb(original, full)
    return send_from_directory(td, tn)

_status_cache = {"data": None, "ts": 0}

@app.route("/api/status")
def api_status():
    now = time.time()
    if _status_cache["data"] and (now - _status_cache["ts"]) < 10:
        return jsonify({"albums": _status_cache["data"], "bg": bg_status})
    cfg = load_config()
    result = []
    for source in cfg["sources"]:
        if not os.path.isdir(source):
            continue
        base = os.path.basename(source)
        for dirpath, dirnames, filenames in os.walk(source):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            photos = [f for f in filenames if os.path.splitext(f)[1].lower() in EXTENSIONS]
            if not photos:
                continue
            rel = os.path.relpath(dirpath, source)
            album_path = base if rel == '.' else base + "/" + rel
            td = _thumb_dir(album_path)
            generated = len([f for f in os.listdir(td) if f.endswith('.jpg')]) if os.path.isdir(td) else 0
            result.append({"name": album_path, "path": dirpath, "photos": len(photos), "thumbs": generated})
    _status_cache["data"] = result
    _status_cache["ts"] = now
    return jsonify({"albums": result, "bg": bg_status})

@app.route("/api/generate")
def api_generate():
    _status_cache["data"] = None
    _status_cache["ts"] = 0
    start_bg_generation()
    return jsonify({"started": True})

@app.route("/api/cleanup")
def api_cleanup():
    cfg = load_config()
    removed = 0
    for source in cfg["sources"]:
        if not os.path.isdir(source):
            continue
        base = os.path.basename(source)
        for dirpath, dirnames, filenames in os.walk(source):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            rel = os.path.relpath(dirpath, source)
            album_path = base if rel == '.' else base + "/" + rel
            td = _thumb_dir(album_path)
            if not os.path.isdir(td):
                continue
            real_files = set(os.path.splitext(f)[0] for f in filenames
                            if os.path.splitext(f)[1].lower() in EXTENSIONS)
            for thumb in os.listdir(td):
                b = thumb.rsplit("_300", 1)[0]
                if b not in real_files:
                    os.unlink(os.path.join(td, thumb))
                    removed += 1
    return jsonify({"removed": removed})

if __name__ == "__main__":
    cfg = load_config()
    print(f"Sources: {cfg['sources']}")
    start_bg_generation()
    print(f"Open http://localhost:{cfg.get('port', 5000)}")
    app.run(host="0.0.0.0", port=cfg.get("port", 5000), debug=True, use_reloader=False)
