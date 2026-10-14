"""
Staging Viewer — read-only dashboard + cron drain.

Reads niche configs from staging-service/settings.json
(or env var SETTINGS_JSON on Vercel).
Reads staging data from Neon.

/api/cron drains the oldest pending staged posts into Buffer queues.
"""
import os
import sys
import json
import time
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify, send_from_directory

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("❌ psycopg not installed. Run: pip install \"psycopg[binary]\"")
    sys.exit(1)

import zernio_client


BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


# ------------------------------------------------------------------
# Settings loader — env var on Vercel, file locally
# ------------------------------------------------------------------
def _load_settings():
    # 1. Env var (Vercel)
    raw = os.environ.get("SETTINGS_JSON")
    if raw:
        try:
            return json.loads(raw)
        except Exception as e:
            print(f"⚠️  SETTINGS_JSON is not valid JSON: {e}")

    # 2. settings.json
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  settings.json unreadable: {e}")

    # 3. Fallback: legacy config.json (only neon url + port)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return {"NICHES": {}, **cfg}
        except Exception:
            pass

    return {"NICHES": {}}


SETTINGS = _load_settings()
NICHES   = SETTINGS.get("NICHES", {}) or {}


def _db_url():
    return (
        os.environ.get("NEON_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or SETTINGS.get("NEON_DATABASE_URL")
        or ""
    )


DB_URL = _db_url()
PORT   = int(os.environ.get("PORT", SETTINGS.get("PORT", 5050)))


def _buffer_niches():
    return {
        k: v for k, v in NICHES.items()
        if isinstance(v, dict) and (v.get("publisher") or "").lower() == "buffer"
    }


def _zernio_configs():
    out = {}
    for k, v in NICHES.items():
        if not isinstance(v, dict):
            continue
        if (v.get("publisher") or "").lower() != "zernio":
            continue
        if not v.get("zernio_api_key") or not v.get("zernio_profile_id"):
            continue
        out[k] = {
            "label":             v.get("label", k),
            "zernio_api_key":    v["zernio_api_key"],
            "zernio_account_id": v.get("zernio_account_id", ""),
            "zernio_profile_id": v["zernio_profile_id"],
            "platform":          (v.get("platform") or "youtube").lower(),
            "channel_link":      v.get("channel_link", ""),
        }
    return out


# ------------------------------------------------------------------
# Neon
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
        # Index for fast oldest-first lookups during drain
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_staged_pending
              ON staged_posts (niche, queued_at)
              WHERE status = 'pending'
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
# Buffer client (inline — no separate module needed)
# ------------------------------------------------------------------
BUFFER_API = "https://api.buffer.com"
BUFFER_POSTS_PER_RUN = int(os.environ.get("BUFFER_POSTS_PER_RUN", "3"))
BUFFER_MAX_ATTEMPTS  = int(os.environ.get("BUFFER_MAX_ATTEMPTS", "3"))


def _buffer_gql(api_key, query, variables=None):
    """One GraphQL call to Buffer. Raises on failure."""
    r = requests.post(
        BUFFER_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Buffer HTTP {r.status_code}: {r.text[:240]}")
    payload = r.json()
    if payload.get("errors"):
        # Buffer GraphQL errors
        msgs = "; ".join(e.get("message", "?") for e in payload["errors"])
        raise RuntimeError(f"Buffer GraphQL: {msgs}")
    return payload.get("data") or {}


def _buffer_queue_post(api_key, channel_id, video_url, title, caption):
    """
    Post a video to a Buffer channel's queue.
    Uses the same createPost/addToQueue shape as remixmaster's buffer.py.
    Returns the created post id.
    """
    first_line = (title or "").strip()
    rest = (caption or "").strip()
    text = first_line
    if rest:
        text = f"{first_line}\n\n{rest}"
    if len(text) > 2200:
        text = text[:2197].rstrip() + "..."

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        post { id status }
      }
    }
    """
    variables = {
        "input": {
            "channelId": channel_id,
            "text": text,
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [{"video": {"url": video_url}}],
        }
    }
    data = _buffer_gql(api_key, query, variables)
    post = ((data.get("createPost") or {}).get("post") or {})
    return post.get("id") or ""


# ------------------------------------------------------------------
# Cron drain
# ------------------------------------------------------------------
def _claim_oldest_pending(niche, limit):
    """
    Atomically claim the N oldest pending rows for a niche.
    Marks them 'sending' so concurrent runs don't double-post.
    Returns the claimed rows.
    """
    with conn().cursor() as cur:
        cur.execute("""
            WITH claimed AS (
                SELECT id FROM staged_posts
                 WHERE niche=%s AND status='pending'
                 ORDER BY queued_at ASC
                 LIMIT %s
                 FOR UPDATE SKIP LOCKED
            )
            UPDATE staged_posts sp
               SET status='sending'
              FROM claimed
             WHERE sp.id = claimed.id
         RETURNING sp.id, sp.video_url, sp.title, sp.caption, sp.attempts
        """, (niche, limit))
        return cur.fetchall()


def _mark_sent(pid, buffer_post_id):
    with conn().cursor() as cur:
        cur.execute("""
            UPDATE staged_posts
               SET status='sent',
                   sent_at=NOW(),
                   buffer_post_id=%s,
                   error=NULL
             WHERE id=%s
        """, (buffer_post_id, pid))


def _mark_failed(pid, err_msg, attempts):
    """Increment attempts; park as 'failed' after max, else back to 'pending'."""
    new_attempts = (attempts or 0) + 1
    new_status = "failed" if new_attempts >= BUFFER_MAX_ATTEMPTS else "pending"
    with conn().cursor() as cur:
        cur.execute("""
            UPDATE staged_posts
               SET status=%s,
                   attempts=%s,
                   error=%s
             WHERE id=%s
        """, (new_status, new_attempts, err_msg[:500], pid))


def _drain_niche(niche_key, cfg):
    """
    Push up to BUFFER_POSTS_PER_RUN oldest pending posts for one niche
    into its Buffer channel. Returns a summary dict.
    """
    api_key = (cfg.get("buffer_api_key")
               or SETTINGS.get("BUFFER_API_KEY")
               or "").strip()
    channel_id = (cfg.get("buffer_channel_id") or "").strip()

    result = {
        "niche": niche_key,
        "label": cfg.get("label", niche_key),
        "pushed": 0,
        "failed": 0,
        "buffer_ids": [],
        "error": None,
    }

    if not api_key:
        result["error"] = "no buffer_api_key"
        return result
    if not channel_id:
        result["error"] = "no buffer_channel_id"
        return result

    claimed = _claim_oldest_pending(niche_key, BUFFER_POSTS_PER_RUN)
    if not claimed:
        result["reason"] = "no pending posts"
        return result

    for row in claimed:
        try:
            bid = _buffer_queue_post(
                api_key,
                channel_id,
                row["video_url"],
                row["title"],
                row["caption"],
            )
            _mark_sent(row["id"], bid)
            result["pushed"] += 1
            result["buffer_ids"].append(bid)
        except Exception as e:
            _mark_failed(row["id"], str(e), row["attempts"])
            result["failed"] += 1
            # Log the first failure reason
            if not result["error"]:
                result["error"] = str(e)[:200]

    return result


def _run_drain():
    """Iterate every Buffer niche and drain a few posts into each."""
    niches = _buffer_niches()
    results = []
    for niche_key, cfg in niches.items():
        try:
            results.append(_drain_niche(niche_key, cfg))
        except Exception as e:
            results.append({
                "niche": niche_key,
                "label": cfg.get("label", niche_key),
                "pushed": 0, "failed": 0,
                "error": f"drain error: {e}",
            })
    return results


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


# ---- Zernio ----
@app.route("/api/zernio/niches")
def api_zernio_niches():
    zernio_client.set_niches(_zernio_configs())
    force = request.args.get("force") in ("1", "true", "yes")
    try:
        summaries = zernio_client.all_summaries(force=force)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    rows = sorted(summaries.values(), key=lambda r: r.get("label", "").lower())
    return jsonify(success=True, rows=rows, cached=not force)


@app.route("/api/zernio/posts/<niche>")
def api_zernio_posts(niche):
    zernio_client.set_niches(_zernio_configs())
    niches = zernio_client.list_niches()
    cfg = niches.get(niche)
    if not cfg:
        return jsonify(success=False, error="unknown niche"), 404
    page  = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    force = request.args.get("force") in ("1", "true", "yes")
    try:
        result = zernio_client.scheduled_posts_for_niche(
            niche, cfg, page=page, limit=limit, force=force
        )
        return jsonify(success=True, niche=niche, **result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/zernio/refresh", methods=["POST"])
def api_zernio_refresh():
    try:
        def _run():
            zernio_client.set_niches(_zernio_configs())
            zernio_client.all_summaries(force=True)
        threading.Thread(target=_run, daemon=True).start()
        return jsonify(success=True, message="refresh started")
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/zernio/stats")
def api_zernio_stats():
    return jsonify(success=True, **zernio_client.cache_stats())


# ---- Cron drain ----
@app.route("/api/cron")
def api_cron():
    """
    Vercel / cron-job.org target.

    Auth: if CRON_SECRET is set, caller must send
          Authorization: Bearer <CRON_SECRET>.

    Behavior: for each Buffer niche, pushes the oldest pending staged
              posts (up to BUFFER_POSTS_PER_RUN) into that niche's
              Buffer channel via addToQueue. Marks sent or failed in Neon.

    Query params:
      ?dry=1      -> do not post or update Neon; just report what would happen
      ?niche=KEY  -> only run for one niche
    """
    secret = os.environ.get("CRON_SECRET")
    if secret:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {secret}":
            return jsonify(success=False, error="unauthorized"), 401

    dry = request.args.get("dry") in ("1", "true", "yes")
    only = request.args.get("niche")

    t0 = time.time()

    if only:
        all_niches = _buffer_niches()
        cfg = all_niches.get(only)
        if not cfg:
            return jsonify(success=False, error=f"unknown niche: {only}"), 404
        if dry:
            with conn().cursor() as cur:
                cur.execute("""
                    SELECT id, title FROM staged_posts
                     WHERE niche=%s AND status='pending'
                     ORDER BY queued_at ASC LIMIT %s
                """, (only, BUFFER_POSTS_PER_RUN))
                rows = cur.fetchall()
            return jsonify(
                success=True,
                dry_run=True,
                niche=only,
                would_push=[{"id": r["id"], "title": r["title"]} for r in rows],
            )
        result = _drain_niche(only, cfg)
        return jsonify(
            success=True,
            ran_at=datetime.now(timezone.utc).isoformat(),
            elapsed_s=round(time.time() - t0, 2),
            results=[result],
        )

    if dry:
        niches = _buffer_niches()
        preview = []
        for key, cfg in niches.items():
            with conn().cursor() as cur:
                cur.execute("""
                    SELECT id, title FROM staged_posts
                     WHERE niche=%s AND status='pending'
                     ORDER BY queued_at ASC LIMIT %s
                """, (key, BUFFER_POSTS_PER_RUN))
                rows = cur.fetchall()
            preview.append({
                "niche": key,
                "label": cfg.get("label", key),
                "would_push": [
                    {"id": r["id"], "title": r["title"]} for r in rows
                ],
            })
        return jsonify(success=True, dry_run=True, preview=preview)

    results = _run_drain()
    return jsonify(
        success=True,
        ran_at=datetime.now(timezone.utc).isoformat(),
        elapsed_s=round(time.time() - t0, 2),
        posts_per_niche=BUFFER_POSTS_PER_RUN,
        results=results,
    )


# ------------------------------------------------------------------
# Boot (local dev only — Vercel uses `app` directly)
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("👁️  Staging Viewer")
    print("=" * 60)
    print(f"🗄️  Neon URL:        {DB_URL[:50]}…")
    print(f"🌐 Port:            {PORT}")
    print(f"📄 Settings:        "
          f"{'env var SETTINGS_JSON' if os.environ.get('SETTINGS_JSON') else SETTINGS_FILE}")
    print(f"🅱️  Buffer post/run: {BUFFER_POSTS_PER_RUN}")
    print(f"🅱️  Buffer max tries:{BUFFER_MAX_ATTEMPTS}")
    try:
        init_schema()
        print("✅ Schema ready")
    except Exception as e:
        print(f"❌ Schema init failed: {e}")
    zc = _zernio_configs()
    zernio_client.set_niches(zc)
    print(f"🎬 Zernio niches:   {len(zc)}")
    print(f"🅱️  Buffer niches:   {len(_buffer_niches())}")
    zernio_client.start_warmer()
    print(f"🌍 Open:            http://localhost:{PORT}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)