"""
Drain staged posts from Neon into Buffer.

Usage:
  python drain.py                # drain every Buffer niche
  python drain.py marketmentor   # drain one niche
  python drain.py --dry-run      # show what would be sent, no API calls

Behavior per niche:
  - Pops the oldest 'pending' row.
  - Pushes it to Buffer.
  - On success: marks 'sent'.
  - On 'Scheduled posts limit reached': requeues the row, stops for this niche.
  - On other errors: marks 'failed', continues with the next row.

Register with Windows Task Scheduler to run every few hours.
"""
import os
import sys
import json
import threading

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("❌ psycopg not installed. Run: pip install \"psycopg[binary]\"")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ requests not installed. Run: pip install requests")
    sys.exit(1)


BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")
BUFFER_API_URL = "https://api.buffer.com"


def _load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f) or {}


CONFIG      = _load_config()
DB_URL      = CONFIG.get("neon_database_url", "")
RM_SETTINGS = CONFIG.get("remixmaster_settings",
                         r"C:\Users\PC\Desktop\remixmaster\settings.json")


def _load_rm_settings():
    with open(RM_SETTINGS, "r", encoding="utf-8") as f:
        return json.load(f) or {}


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


def pop_oldest(niche):
    with conn().cursor() as cur:
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
    with conn().cursor() as cur:
        cur.execute("""
            UPDATE staged_posts
               SET status='sent', sent_at=NOW(),
                   buffer_post_id=%s, error=NULL
             WHERE id=%s
        """, (buf_id, pid))


def mark_failed(pid, err):
    with conn().cursor() as cur:
        cur.execute("""
            UPDATE staged_posts SET status='failed', error=%s WHERE id=%s
        """, (str(err)[:500], pid))


def requeue(pid):
    with conn().cursor() as cur:
        cur.execute("UPDATE staged_posts SET status='pending' WHERE id=%s", (pid,))


# ------------------------------------------------------------------
# Buffer
# ------------------------------------------------------------------
class LimitReached(Exception):
    pass


def publish(niche, video_url, title, caption, dry_run=False):
    if dry_run:
        return {"dry_run": True}

    niches = _buffer_niches()
    cfg = niches.get(niche)
    if not cfg:
        raise RuntimeError(f"No Buffer config for '{niche}'")

    api_key = (cfg.get("buffer_api_key") or "").strip()
    if not api_key:
        api_key = (_load_rm_settings().get("BUFFER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(f"No Buffer API key for '{niche}'")

    channel_id = (cfg.get("buffer_channel_id") or "").strip()
    if not channel_id:
        raise RuntimeError(f"No buffer_channel_id for '{niche}'")

    platform = (cfg.get("platform") or "youtube").lower()

    def _utf16(s):
        return len(s.encode("utf-16-le")) // 2

    if platform == "instagram":
        text = f"{title}\n\n{caption}" if caption else title
        if len(text) > 2200:
            text = text[:2197].rstrip() + "..."
        metadata = {"instagram": {
            "type": "reel", "shouldShareToFeed": True, "isAiGenerated": True,
        }}
    elif platform == "tiktok":
        text = f"{title}\n\n{caption}" if caption else title
        if len(text) > 2200:
            text = text[:2197].rstrip() + "..."
        metadata = {"tiktok": {"title": title[:150],
                               "isAiGenerated": True}}
    elif platform == "facebook":
        text = f"{title}\n\n{caption}" if caption else title
        metadata = {"facebook": {"type": "reel"}}
    else:
        t = title or ""
        if _utf16(t) > 100:
            while t and _utf16(t) > 100:
                t = t[:-1].rstrip()
            t = t[:-3].rstrip() + "..."
        text = caption or ""
        metadata = {"youtube": {
            "title": t, "categoryId": "24",
            "privacy": "public", "madeForKids": True,
        }}

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id dueAt status } }
        ... on MutationError { message }
      }
    }
    """

    payload = {"query": mutation, "variables": {"input": {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "assets": [{"video": {"url": video_url}}],
        "metadata": metadata,
    }}}

    r = requests.post(
        BUFFER_API_URL, json=payload,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        timeout=30,
    )
    result = r.json()
    blob = json.dumps(result).lower()

    if "scheduled posts limit reached" in blob or \
       ("scheduled posts limit" in blob and "reached" in blob):
        raise LimitReached("Scheduled posts limit reached")

    if "errors" in result:
        raise RuntimeError(str(result["errors"]))

    br = (result.get("data") or {}).get("createPost") or {}
    if isinstance(br, dict) and br.get("message"):
        msg = br["message"]
        if "scheduled posts limit" in msg.lower():
            raise LimitReached(msg)
        raise RuntimeError(msg)

    return result


def drain_one(niche, dry_run=False):
    sent = 0
    while True:
        post = pop_oldest(niche)
        if not post:
            break
        try:
            resp = publish(post["niche"], post["video_url"],
                           post["title"], post["caption"], dry_run=dry_run)
            buf_id = ""
            try:
                buf_id = (((resp.get("data") or {}).get("createPost") or {})
                          .get("post") or {}).get("id", "")
            except Exception:
                pass
            if dry_run:
                requeue(post["id"])
            else:
                mark_sent(post["id"], buf_id)
            sent += 1
            print(f"  ✅ sent id={post['id']} buf={buf_id}")
        except LimitReached:
            requeue(post["id"])
            print(f"  ⏸️  limit reached — requeued id={post['id']}")
            break
        except Exception as e:
            mark_failed(post["id"], str(e))
            print(f"  ❌ failed id={post['id']}: {e}")
    return sent


def main():
    args = [a for a in sys.argv[1:]]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    niches = list(_buffer_niches().keys())
    if args:
        niches = [n for n in args if n in niches] or args

    print("=" * 60)
    print(f"🚰 Draining {len(niches)} niche(s){' (dry run)' if dry_run else ''}")
    print("=" * 60)

    total = 0
    for n in niches:
        print(f"\n▶ {n}")
        try:
            c = drain_one(n, dry_run=dry_run)
            print(f"  → {c} sent")
            total += c
        except Exception as e:
            print(f"  ❌ {e}")

    print()
    print(f"🏁 Total sent: {total}")


if __name__ == "__main__":
    main()