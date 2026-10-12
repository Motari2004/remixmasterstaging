"""
Staging Viewer — read-only dashboard over the Neon queue.

Reads:
  - niche_configs in Neon  (preferred, synced by Remix Master)
  - settings.json locally  (fallback when niche_configs is empty)

Never writes. Never publishes. Never touches Buffer.

Publishing is handled by:
  - Remix Master (writes to Neon when Buffer is full)
  - The Vercel drain function (cron) — pushes staged rows to Buffer
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


CONFIG = _load_config()
DB_URL = CONFIG.get("neon_database_url", "")
PORT   = int(CONFIG.get("port", 5050))

# Resolve RM_SETTINGS relative to BASE_DIR unless it's an absolute path.
# This makes the same config work locally and on a remote host.
_rm_setting = CONFIG.get("remixmaster_settings", "settings.json")
if not os.path.isabs(_rm_setting):
    RM_SETTINGS = os.path.join(BASE_DIR, _rm_setting)
else:
    RM_SETTINGS = _rm_setting


def _load_rm_settings():
    """Read the local bundled settings.json (secrets already stripped)."""
    try:
        with open(RM_SETTINGS, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        print(f"⚠️  Bundled settings.json not found at: {RM_SETTINGS}")
        return {}
    except Exception as e:
        print(f"⚠️  Could not read {RM_SETTINGS}: {e}")
        return {}


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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS niche_configs (
                niche              TEXT PRIMARY KEY,
                label              TEXT,
                publisher          TEXT,
                platform           TEXT,
                buffer_api_key     TEXT,
                buffer_channel_id  TEXT,
                updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


# ------------------------------------------------------------------
# Niche list resolution
# ------------------------------------------------------------------
def _buffer_niches():
    """
    Return {niche: cfg} for every Buffer niche we know about.

    Order of preference:
      1. Neon niche_configs table  (populated by Remix Master sync)
      2. Local settings.json       (bundled copy, secrets stripped)
    """
    # ---- 1. Neon ----
    try:
        with conn().cursor() as cur:
            cur.execute("""
                SELECT niche, label, platform,
                       buffer_channel_id
                  FROM niche_configs
                 WHERE publisher = 'buffer'
            """)
            rows = cur.fetchall()
        if rows:
            out = {
                r["niche"]: {
                    "label":             r["label"] or r["niche"],
                    "platform":          (r["platform"] or "youtube").lower(),
                    "buffer_channel_id": r["buffer_channel_id"] or "",
                }
                for r in rows
            }
            print(f"📚 Loaded {len(out)} Buffer niche(s) from Neon")
            return out
    except Exception as e:
        print(f"⚠️  Could not read niche_configs from Neon ({e})")

    # ---- 2. Local settings.json ----
    s = _load_rm_settings()
    niches = s.get("NICHES", {})
    if not isinstance(niches, dict):
        print(f"⚠️  No NICHES in {RM_SETTINGS}")
        return {}

    buffer_map = {
        k: v for k, v in niches.items()
        if isinstance(v, dict) and (v.get("publisher") or "").lower() == "buffer"
    }
    print(f"📚 Loaded {len(buffer_map)} Buffer niche(s) from {RM_SETTINGS}")
    return buffer_map


# ------------------------------------------------------------------
# Queries
# ------------------------------------------------------------------
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
            "key":         key,
            "label":       cfg.get("label", key),
            "platform":    (cfg.get("platform") or "youtube").lower(),
            "mode":        states.get(key, {}).get("mode", "direct"),
            "last_drain":  str(states.get(key, {}).get("last_drain") or ""),
            "pending":     pending,
            "sent_today":  sent_today,
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


def q_post(post_id):
    with conn().cursor() as cur:
        cur.execute("SELECT * FROM staged_posts WHERE id=%s", (post_id,))
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


if __name__ == "__main__":
    print("=" * 60)
    print("👁️  Staging Viewer (read-only)")
    print("=" * 60)
    print(f"🗄️  Neon URL:        {DB_URL[:50]}…")
    print(f"📄 Settings source: {RM_SETTINGS}")
    print(f"🌐 Port:            {PORT}")
    try:
        init_schema()
        print("✅ Schema ready")
    except Exception as e:
        print(f"❌ Schema init failed: {e}")
    print(f"🌍 Open:            http://localhost:{PORT}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=PORT, debug=False)