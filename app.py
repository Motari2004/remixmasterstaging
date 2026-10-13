"""
Staging Viewer — read-only dashboard.

Two panels:
  - Buffer niches (from Neon queue)
  - Zernio niches (live from Zernio's API, cached + warmed)

Serves a single-page UI at /. Does NOT publish or write to Buffer.
"""
import os
import sys
import json
import threading

from flask import Flask, request, jsonify, send_from_directory

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("❌ psycopg not installed. Run: pip install \"psycopg[binary]\"")
    sys.exit(1)

import zernio_client


BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        print(f"❌ config.json: {e}")
        return {}


CONFIG  = _load_config()
DB_URL  = CONFIG.get("neon_database_url", "")
PORT    = int(CONFIG.get("port", 5050))

RM_SETTINGS = CONFIG.get("remixmaster_settings",
                         r"C:\Users\PC\Desktop\remixmaster\settings.json")


def _load_rm_settings():
    try:
        with open(RM_SETTINGS, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        print(f"⚠️  remixmaster settings: {e}")
        return {}


def _buffer_niches():
    s = _load_rm_settings()
    niches = s.get("NICHES", {})
    if not isinstance(niches, dict):
        return {}
    return {
        k: v for k, v in niches.items()
        if isinstance(v, dict) and (v.get("publisher") or "").lower() == "buffer"
    }


# ------------------------------------------------------------------
# DB
# ------------------------------------------------------------------
_lock = threading.Lock()
_conn = None


def conn():
    global _conn
    with _lock:
        if _conn is None or _conn.closed:
            _conn = psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row)
        return _conn


def init_schema():
    with conn().cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS staged_posts (
                id              BIGSERIAL PRIMARY KEY,
                niche           TEXT NOT NULL,
                video_url       TEXT NOT NULL,
                title           TEXT NOT NULL,
                caption         TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                error           TEXT,
                queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                sent_at         TIMESTAMPTZ,
                buffer_post_id  TEXT,
                attempts        INT NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS niche_state (
                niche        TEXT PRIMARY KEY,
                mode         TEXT NOT NULL DEFAULT 'direct',
                last_drain   TIMESTAMPTZ,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def q_summary():
    niches = _buffer_niches()
    with conn().cursor() as cur:
        cur.execute("SELECT niche, mode, last_drain FROM niche_state")
        states = {r["niche"]: r for r in cur.fetchall()}
    rows = []
    for key, cfg in niches.items():
        with conn().cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS n FROM staged_posts
                 WHERE niche=%s AND status IN ('pending','sending')
            """, (key,))
            pending = cur.fetchone()["n"]
            cur.execute("""
                SELECT COUNT(*) AS n FROM staged_posts
                 WHERE niche=%s AND status='sent'
                   AND sent_at >= CURRENT_DATE
            """, (key,))
            sent_today = cur.fetchone()["n"]
        rows.append({
            "key": key,
            "label": cfg.get("label", key),
            "platform": (cfg.get("platform") or "youtube").lower(),
            "mode": states.get(key, {}).get("mode", "direct"),
            "last_drain": str(states.get(key, {}).get("last_drain") or ""),
            "pending": pending,
            "sent_today": sent_today,
        })
    rows.sort(key=lambda r: (r["mode"] != "staging", r["label"].lower()))
    return rows


def q_queue(niche):
    with conn().cursor() as cur:
        cur.execute("""
            SELECT id, video_url, title, caption, status, attempts,
                   queued_at, sent_at, buffer_post_id, error
              FROM staged_posts WHERE niche=%s
             ORDER BY CASE status
                        WHEN 'pending' THEN 0
                        WHEN 'sending' THEN 1
                        WHEN 'failed'  THEN 2
                        WHEN 'sent'    THEN 3
                        ELSE 4
                      END, queued_at DESC LIMIT 500
        """, (niche,))
        items = cur.fetchall()
        cur.execute("SELECT mode FROM niche_state WHERE niche=%s", (niche,))
        r = cur.fetchone()
        mode = r["mode"] if r else "direct"
    return mode, items


def q_post(pid):
    with conn().cursor() as cur:
        cur.execute("SELECT * FROM staged_posts WHERE id=%s", (pid,))
        return cur.fetchone()


def q_log():
    with conn().cursor() as cur:
        cur.execute("""
            SELECT id, niche, title, sent_at, buffer_post_id
              FROM staged_posts WHERE status='sent'
             ORDER BY sent_at DESC LIMIT 200
        """)
        return cur.fetchall()


# ------------------------------------------------------------------
# Flask
# ------------------------------------------------------------------
app = Flask(__name__, template_folder="templates")


@app.route("/")
def index():
    return send_from_directory(TEMPLATES_DIR, "index.html")


@app.route("/api/summary")
def api_summary():
    return jsonify(success=True, rows=q_summary())


@app.route("/api/queue/<niche>")
def api_queue(niche):
    mode, items = q_queue(niche)
    return jsonify(success=True, niche=niche, mode=mode, items=items)


@app.route("/api/post/<int:pid>")
def api_post(pid):
    it = q_post(pid)
    if not it:
        return jsonify(success=False, error="not found"), 404
    return jsonify(success=True, item=it)


@app.route("/api/log")
def api_log():
    return jsonify(success=True, rows=q_log())


# ---- Zernio panel (cached + parallel) ----
@app.route("/api/zernio/niches")
def api_zernio_niches():
    """
    Return one summary per Zernio niche.

    ?force=1 forces a fresh fetch (synchronous, slower).
    Otherwise: cached values return instantly; stale ones refresh in background.
    """
    force = request.args.get("force") in ("1", "true", "yes")
    try:
        summaries = zernio_client.all_summaries(force=force)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

    rows = sorted(summaries.values(), key=lambda r: r.get("label", "").lower())
    return jsonify(success=True, rows=rows, cached=not force)


@app.route("/api/zernio/posts/<niche>")
def api_zernio_posts(niche):
    niches = zernio_client.list_niches()
    cfg = niches.get(niche)
    if not cfg:
        return jsonify(success=False, error="unknown niche"), 404
    page   = int(request.args.get("page", 1))
    limit  = int(request.args.get("limit", 50))
    force  = request.args.get("force") in ("1", "true", "yes")
    try:
        result = zernio_client.scheduled_posts_for_niche(
            niche, cfg, page=page, limit=limit, force=force
        )
        return jsonify(success=True, niche=niche, **result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/zernio/refresh", methods=["POST"])
def api_zernio_refresh():
    """
    Force-refresh the entire Zernio summary in the background.
    Returns immediately; caller should re-fetch /niches in ~1-2s.
    """
    try:
        def _run():
            zernio_client.all_summaries(force=True)
        threading.Thread(target=_run, daemon=True).start()
        return jsonify(success=True, message="refresh started")
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/zernio/stats")
def api_zernio_stats():
    return jsonify(success=True, **zernio_client.cache_stats())


if __name__ == "__main__":
    print("=" * 60)
    print("👁️  Staging Viewer")
    print("=" * 60)
    print(f"🗄️  Neon URL:        {DB_URL[:50]}…")
    print(f"🌐 Port:            {PORT}")
    try:
        init_schema()
        print("✅ Schema ready")
    except Exception as e:
        print(f"❌ Schema init failed: {e}")
    zernio_n = len(zernio_client.list_niches())
    print(f"🎬 Zernio niches:   {zernio_n}  (from config.json)")
    print(f"🅱️  Buffer niches:   {len(_buffer_niches())}  (from remixmaster)")

    # Warm the cache in the background
    zernio_client.start_warmer()

    print(f"🌍 Open:            http://localhost:{PORT}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)