"""
Neon helpers. Used by both the viewer (app.py) and the drain (cron.py).

DB_URL resolution:
  • Local:  app.py reads config.json and overrides db.DB_URL at import
  • Vercel: NEON_DATABASE_URL env var (read at import time)
"""
import os
import threading

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    raise RuntimeError("psycopg not installed — add psycopg[binary] to requirements.txt")


DB_URL = os.environ.get("NEON_DATABASE_URL", "")

_lock = threading.Lock()
_conn = None


def get_conn():
    global _conn
    if not DB_URL:
        raise RuntimeError("NEON_DATABASE_URL is not set")
    with _lock:
        if _conn is None or _conn.closed:
            _conn = psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row)
        return _conn


# ------------------------------------------------------------------
# Niche configs
# ------------------------------------------------------------------
def get_buffer_niches(include_key=False):
    """
    Return {niche: cfg} for every publisher='buffer' row in niche_configs.
    If include_key=True, cfg['buffer_api_key'] is populated (drain only).
    """
    cols = "niche, label, platform, buffer_channel_id"
    if include_key:
        cols += ", buffer_api_key"

    with get_conn().cursor() as cur:
        cur.execute(f"""
            SELECT {cols}
              FROM niche_configs
             WHERE publisher = 'buffer'
        """)
        rows = cur.fetchall()

    out = {}
    for r in rows:
        cfg = {
            "label":             r["label"] or r["niche"],
            "platform":          (r["platform"] or "youtube").lower(),
            "buffer_channel_id": r["buffer_channel_id"] or "",
        }
        if include_key:
            cfg["buffer_api_key"] = r["buffer_api_key"] or ""
        out[r["niche"]] = cfg
    return out


# ------------------------------------------------------------------
# Viewer queries
# ------------------------------------------------------------------
def q_summary():
    niches = get_buffer_niches()

    with get_conn().cursor() as cur:
        cur.execute("SELECT niche, mode, last_drain FROM niche_state")
        states = {r["niche"]: r for r in cur.fetchall()}

    rows = []
    for key, cfg in niches.items():
        with get_conn().cursor() as cur:
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
            "key":        key,
            "label":      cfg.get("label", key),
            "platform":   (cfg.get("platform") or "youtube").lower(),
            "mode":       states.get(key, {}).get("mode", "direct"),
            "last_drain": str(states.get(key, {}).get("last_drain") or ""),
            "pending":    pending,
            "sent_today": sent_today,
        })

    rows.sort(key=lambda r: (r["mode"] != "staging", r["label"].lower()))
    return rows


def q_queue(niche):
    with get_conn().cursor() as cur:
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
    with get_conn().cursor() as cur:
        cur.execute("SELECT * FROM staged_posts WHERE id=%s", (post_id,))
        return cur.fetchone()


def q_log():
    with get_conn().cursor() as cur:
        cur.execute("""
            SELECT id, niche, title, sent_at, buffer_post_id
              FROM staged_posts WHERE status='sent'
             ORDER BY sent_at DESC LIMIT 200
        """)
        return cur.fetchall()


# ------------------------------------------------------------------
# Drain queries
# ------------------------------------------------------------------
def pop_oldest(niche):
    with get_conn().cursor() as cur:
        cur.execute("""
            WITH picked AS (
                SELECT id FROM staged_posts
                 WHERE niche=%s AND status='pending'
                 ORDER BY queued_at ASC LIMIT 1
                 FOR UPDATE SKIP LOCKED
            )
            UPDATE staged_posts
               SET status='sending', attempts = attempts + 1
             WHERE id IN (SELECT id FROM picked)
             RETURNING id, niche, video_url, title, caption, attempts
        """, (niche,))
        return cur.fetchone()


def mark_sent(pid, buf_id=""):
    with get_conn().cursor() as cur:
        cur.execute("""
            UPDATE staged_posts
               SET status='sent', sent_at=NOW(),
                   buffer_post_id=%s, error=NULL
             WHERE id=%s
        """, (buf_id, pid))


def mark_failed(pid, err):
    with get_conn().cursor() as cur:
        cur.execute("""
            UPDATE staged_posts SET status='failed', error=%s WHERE id=%s
        """, (str(err)[:500], pid))


def requeue(pid):
    with get_conn().cursor() as cur:
        cur.execute("UPDATE staged_posts SET status='pending' WHERE id=%s", (pid,))


def count_pending(niche):
    with get_conn().cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS n FROM staged_posts
             WHERE niche=%s AND status IN ('pending','sending')
        """, (niche,))
        return cur.fetchone()["n"]


def set_niche_mode(niche, mode):
    assert mode in ("direct", "staging")
    with get_conn().cursor() as cur:
        cur.execute("""
            INSERT INTO niche_state (niche, mode, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (niche) DO UPDATE
              SET mode = EXCLUDED.mode,
                  updated_at = NOW()
        """, (niche, mode))


def mark_last_drain(niche):
    with get_conn().cursor() as cur:
        cur.execute("UPDATE niche_state SET last_drain = NOW() WHERE niche = %s", (niche,))