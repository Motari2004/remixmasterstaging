"""
Staging Service — combined viewer + drain.

Two responsibilities, one file:
  • Viewer  — read-only dashboard over the Neon queue
  • Drain   — callable endpoint that pushes pending rows to Buffer

Endpoints:
  GET /                        viewer dashboard
  GET /api/summary             viewer data (14 Buffer niches)
  GET /api/queue/<niche>       pending items for a niche
  GET /api/post/<id>           one staged post
  GET /api/log                 recent sends
  GET /api/cron                run the drain (external cron hits this)
  GET /api/cron/ping           drain health check

Local:  python app.py            (reads config.json for DB URL)
Vercel: vercel --prod           (reads NEON_DATABASE_URL env var)

Deploy: both modes work from this same file.
"""
import os
import sys
import json
import time
import threading
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_from_directory


# ------------------------------------------------------------------
# Path setup — make sibling modules importable
# ------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import db
from buffer import publish, LimitReached


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
TEMPLATES_DIR = os.path.join(_ROOT, "templates")
CONFIG_FILE   = os.path.join(_ROOT, "config.json")

MAX_SENDS_PER_RUN   = int(os.environ.get("MAX_SENDS_PER_RUN", "10"))
MAX_RUNTIME_SECONDS = int(os.environ.get("MAX_RUNTIME_SECONDS", "50"))


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


# Wire the resolved URL into the shared db module.
db.DB_URL = _resolve_db_url()


# =========================================================
# Flask app
# =========================================================
app = Flask(__name__, template_folder="templates")


# ------------------------------------------------------------------
# Viewer routes
# ------------------------------------------------------------------
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


# =========================================================
# Drain — the whole thing lives here now
# =========================================================
def _drain_niche(niche, cfg, deadline):
    result = {"sent": 0, "requeued": 0, "failed": 0, "flipped_to_direct": False}

    while time.time() < deadline:
        if result["sent"] >= MAX_SENDS_PER_RUN:
            break

        post = db.pop_oldest(niche)
        if not post:
            break

        try:
            resp = publish(
                niche=niche,
                video_url=post["video_url"],
                title=post["title"],
                caption=post["caption"],
                cfg=cfg,
            )
            buf_id = ""
            try:
                buf_id = (((resp.get("data") or {}).get("createPost") or {})
                          .get("post") or {}).get("id", "")
            except Exception:
                pass
            db.mark_sent(post["id"], buf_id)
            result["sent"] += 1
            print(f"  ✅ {niche} id={post['id']} buf={buf_id}")

        except LimitReached:
            db.requeue(post["id"])
            result["requeued"] += 1
            print(f"  ⏸️  {niche} limit reached — requeued id={post['id']}")
            break

        except Exception as e:
            db.mark_failed(post["id"], str(e))
            result["failed"] += 1
            print(f"  ❌ {niche} id={post['id']} failed: {e}")

    # Self-heal: if the queue is empty and nothing went wrong, go back to direct.
    try:
        if result["requeued"] == 0 and result["failed"] == 0:
            if db.count_pending(niche) == 0:
                db.set_niche_mode(niche, "direct")
                result["flipped_to_direct"] = True
                print(f"  🔄 {niche} flipped back to direct")
    except Exception as e:
        print(f"  ⚠️  {niche} flip-back failed: {e}")

    try:
        db.mark_last_drain(niche)
    except Exception:
        pass

    return result


def run_drain():
    started = time.time()
    deadline = started + MAX_RUNTIME_SECONDS

    summary = {
        "ok": True,
        "started_at": started,
        "niches": {},
        "totals": {"sent": 0, "requeued": 0, "failed": 0, "flipped": 0},
    }

    try:
        niches = db.get_buffer_niches(include_key=True)
    except Exception as e:
        return {"ok": False, "error": f"Could not load niche configs: {e}",
                "started_at": started}

    if not niches:
        summary["note"] = "No buffer niches in niche_configs"
        summary["duration_ms"] = int((time.time() - started) * 1000)
        return summary

    for niche, cfg in niches.items():
        if time.time() >= deadline:
            summary["note"] = f"Time cap hit after {len(summary['niches'])} niches"
            break
        try:
            r = _drain_niche(niche, cfg, deadline)
            summary["niches"][niche] = r
            summary["totals"]["sent"]     += r["sent"]
            summary["totals"]["requeued"] += r["requeued"]
            summary["totals"]["failed"]   += r["failed"]
            if r["flipped_to_direct"]:
                summary["totals"]["flipped"] += 1
        except Exception as e:
            summary["niches"][niche] = {"error": str(e)}
            print(f"  ❌ Niche {niche} crashed: {e}")

    summary["duration_ms"] = int((time.time() - started) * 1000)
    return summary


@app.route("/api/cron")
def api_cron():
    try:
        result = run_drain()
        return jsonify(result), (200 if result.get("ok") else 500)
    except Exception as e:
        return jsonify(ok=False, error=f"drain crashed: {e}"), 500


@app.route("/api/cron/ping")
def api_cron_ping():
    return jsonify(ok=True, service="staging-service")


# =========================================================
# Local entry point
# =========================================================
if __name__ == "__main__":
    cfg = _load_config()
    port = int(cfg.get("port", 5050))

    print("=" * 60)
    print("👁️  Staging Service (viewer + drain)")
    print("=" * 60)
    print(f"🗄️  Neon URL:  {db.DB_URL[:60]}…")
    print(f"🌐 Port:      {port}")
    print(f"🌍 Open:      http://localhost:{port}")
    print(f"🚰 Drain:     http://localhost:{port}/api/cron")
    print("=" * 60)

    app.run(host="0.0.0.0", port=port, debug=False)