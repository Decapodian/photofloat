# PhotoFloat

A modern, self-hosted photo gallery with hierarchical album navigation, dark theme UI, and on-demand thumbnail generation.

Based on the original [PhotoFloat](https://github.com/alexjj/photofloat) by alexjj (which was based on [zx2c4/PhotoFloat](https://www.zx2c4.com/projects/photofloat/)).

## What changed

- **Python 3** — full migration from Python 2
- **Modern web UI** — dark theme, CSS grid, lightbox with keyboard navigation
- **Hierarchical browsing** — subfolders become sub-albums automatically
- **config.json** — define source folders, no need to copy photos anywhere
- **On-demand thumbnails** — generated when you browse, or in background
- **Live status panel** — see generation progress in real time
- **Sort options** — by name, date, or size
- **No nginx required** — runs standalone with Flask

## Quick start

### Requirements

```
pip install flask Pillow python-dateutil
```

### Configure

Edit `config.json`:

```json
{
    "sources": [
        "/path/to/your/photos",
        "/another/photo/folder"
    ],
    "cache_path": "/home/youruser/.photofloat/cache",
    "port": 5000
}
```

Subfolders within each source are discovered as albums automatically.

### Run

```
python3 serve.py
```

Open http://localhost:5000

### Usage

- Browse albums by clicking through the hierarchy
- Use breadcrumbs to navigate back
- Click any photo to open the lightbox (arrow keys to navigate, Esc to close)
- Use the sort dropdown to order photos by name, date, or size
- Click **⚙ Status** to see thumbnail generation progress
- Click **🔄 Regenerate** to generate missing thumbnails in background
- Click **🧹 Cleanup** to remove orphan thumbnails

## Scanner (legacy)

The original Python 3 scanner is still available in `scanner/` for batch thumbnail generation:

```
cd scanner
python3 main.py /path/to/albums /path/to/cache
```

## License

GPLv2 — see [LICENSE](LICENSE)
