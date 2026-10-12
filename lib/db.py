"""
Neon helpers for the Vercel drain function.
"""
import os
import sys
import threading

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("❌ psycopg not installed. requirements.txt should have psycopg[binary]")
    raise


DB_URL = os.environ.get("NEON_DATABASE_URL", "")

_lock = threading.Lock()
_conn = None


def get_conn():
    global _conn
    if not DB_URL:
        raise RuntimeError("NEON_DATABASE_URL env var is not set")
    with _lock:
        if _conn is None or _conn.closed:
            _conn = psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row)
        return _conn


def get_buffer_niches():
    """Return {niche: cfg_dict} for every publisher='buffer' row."""
    with get_conn().cursor() as cur:
        cur.execute("""
            SELECT niche, label, platform,
                   buffer_api_key, buffer_channel_id
              FROM niche_configs
             WHERE publisher = 'buffer'
        """)
        rows = cur.fetchall()
    out = {}
    for r in rows:
        out[r["niche"]] = {
            "label":             r["label"] or r["niche"],
            "platform":          (r["platform"] or "youtube").lower(),
            "buffer_api_key":    r["buffer_api_key"] or "",
            "buffer_channel_id": r["buffer_channel_id"] or "",
        }
    return out


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
        cur.execute("""
            UPDATE niche_state SET last_drain = NOW() WHERE niche = %s
        """, (niche,))