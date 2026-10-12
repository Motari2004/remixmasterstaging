"""
Staging Viewer — read-only dashboard.

Local:  python app.py                 (reads config.json)
Vercel: api/index.py imports `app`    (reads NEON_DATABASE_URL env var)
"""
import os
import sys
import json

from flask import Flask, jsonify, send_from_directory

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import db


BASE_DIR      = _ROOT
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")


def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"⚠️  config.json: {e}")
        return {}


def _resolve_db_url():
    """Env var wins; config.json is the local fallback."""
    url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if url:
        print("🔗 Using NEON_DATABASE_URL from environment")
        return url
    cfg = _load_config()
    url = (cfg.get("neon_database_url") or "").strip()
    if url:
        print("🔗 Using neon_database_url from config.json")
        return url
    print("❌ No Neon URL — set NEON_DATABASE_URL or add it to config.json")
    return ""


# Wire the resolved URL into db BEFORE any query runs.
db.DB_URL = _resolve_db_url()


app = Flask(__name__, template_folder="templates")


@app.route("/")
def index():
    return send_from_directory(TEMPLATES_DIR, "index.html")


@app.route("/api/summary")
def api_summary():
    return jsonify(success=True, rows=db.q_summary())


@app.route("/api/queue/<niche>")
def api_queue(niche):
    mode, items = db.q_queue(niche)
    return jsonify(success=True, niche=niche, mode=mode, items=items)


@app.route("/api/post/<int:pid>")
def api_post(pid):
    it = db.q_post(pid)
    if not it:
        return jsonify(success=False, error="not found"), 404
    return jsonify(success=True, item=it)


@app.route("/api/log")
def api_log():
    return jsonify(success=True, rows=db.q_log())


if __name__ == "__main__":
    cfg = _load_config()
    port = int(cfg.get("port", 5050))

    print("=" * 60)
    print("👁️  Staging Viewer (read-only)")
    print("=" * 60)
    print(f"🗄️  Neon URL:  {db.DB_URL[:60]}…")
    print(f"🌐 Port:      {port}")
    print(f"🌍 Open:      http://localhost:{port}")
    print("=" * 60)

    app.run(host="0.0.0.0", port=port, debug=False)