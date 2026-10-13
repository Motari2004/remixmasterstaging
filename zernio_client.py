"""
Fast Zernio client for the staging viewer.

Optimisations:
  - Parallel fetch (ThreadPoolExecutor) across all niches
  - Stale-while-revalidate cache: return instantly, refresh in background
  - 5-minute TTL, 3-minute background warmer
  - Cached connection pooling via requests.Session
  - Async refresh route support
"""
import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry


ZERNIO_API = "https://zernio.com/api/v1"
HERE       = os.path.dirname(os.path.abspath(__file__))
CONFIG     = os.path.join(HERE, "config.json")

# ---- Cache tuning ----
SUMMARY_TTL = 300        # 5 min for the summary row
POSTS_TTL   = 600        # 10 min for the post list
WARMER_SEC  = 180        # background warmer every 3 min
MAX_WORKERS = 9          # one per niche

_cache_lock = threading.Lock()
_cache = {}              # {key: (expires_at, value)}
_refresh_locks = {}      # {key: threading.Lock} — prevent duplicate refreshes


# ------------------------------------------------------------------
# HTTP session with connection pooling + retries
# ------------------------------------------------------------------
_session_local = threading.local()


def _session():
    """One requests.Session per thread — reuses TCP connections."""
    s = getattr(_session_local, "session", None)
    if s is None:
        s = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(
            pool_connections=16,
            pool_maxsize=16,
            max_retries=retry,
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _session_local.session = s
    return s


def _api_get(path, api_key, params=None, timeout=15):
    url = ZERNIO_API + path
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    r = _session().get(url, headers=headers, params=params, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"Zernio HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


# ------------------------------------------------------------------
# Cache primitives — stale-while-revalidate
# ------------------------------------------------------------------
def _cache_get(key, allow_stale=True):
    """
    Return (value, is_fresh, is_stale).
      - is_fresh: within TTL
      - is_stale: past TTL but still present (usable, should be refreshed)
    """
    with _cache_lock:
        item = _cache.get(key)
        if not item:
            return None, False, False
        exp, val = item
        now = time.time()
        if now < exp:
            return val, True, False
        if allow_stale:
            return val, False, True
        return None, False, False


def _cache_set(key, val, ttl):
    with _cache_lock:
        _cache[key] = (time.time() + ttl, val)


def _get_refresh_lock(key):
    with _cache_lock:
        lk = _refresh_locks.get(key)
        if lk is None:
            lk = threading.Lock()
            _refresh_locks[key] = lk
        return lk


def _refresh_in_background(fn, key, ttl, *args, **kwargs):
    """Fire-and-forget refresh, deduped by key."""
    lk = _get_refresh_lock(key)
    if not lk.acquire(blocking=False):
        return  # already refreshing
    def _run():
        try:
            val = fn(*args, **kwargs)
            _cache_set(key, val, ttl)
        except Exception as e:
            print(f"⚠️  background refresh {key}: {e}")
        finally:
            lk.release()
    threading.Thread(target=_run, daemon=True).start()


# ------------------------------------------------------------------
# Public: list niches
# ------------------------------------------------------------------
def list_niches():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"⚠️  Cannot read config.json: {e}")
        return {}
    niches = cfg.get("zernio_niches", {})
    return niches if isinstance(niches, dict) else {}


# ------------------------------------------------------------------
# Per-niche: fetch raw data (what a cache miss actually does)
# ------------------------------------------------------------------
def _fetch_summary(niche_key, niche_cfg):
    profile_id = niche_cfg["zernio_profile_id"]
    api_key    = niche_cfg["zernio_api_key"]

    summary = {
        "niche":           niche_key,
        "label":           niche_cfg.get("label", niche_key),
        "profile_id":      profile_id,
        "account_id":      niche_cfg.get("zernio_account_id", ""),
        "queue_name":      "",
        "queue_id":        "",
        "slots_free":      0,
        "slots":           [],
        "scheduled_total": 0,
        "next_slot":       "",
        "error":           None,
    }

    # Both calls happen in parallel via tiny local threads
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_q = pool.submit(_api_get, "/queue/preview", api_key,
                            {"profileId": profile_id})
        fut_p = pool.submit(_api_get, "/posts", api_key,
                            {"profileId": profile_id, "status": "scheduled",
                             "limit": 1})

        try:
            q = fut_q.result(timeout=20)
            summary["queue_name"] = q.get("queueName", "")
            summary["queue_id"]   = q.get("queueId", "")
            summary["slots_free"] = q.get("count", 0)
            slots = q.get("slots") or []
            summary["slots"]      = slots[:12]
            if slots:
                summary["next_slot"] = slots[0]
        except Exception as e:
            summary["error"] = f"queue preview: {e}"

        try:
            p = fut_p.result(timeout=20)
            pag = p.get("pagination") or {}
            summary["scheduled_total"] = int(pag.get("total") or 0)
        except Exception as e:
            summary["error"] = (summary["error"] + " | posts: " + str(e)) \
                               if summary["error"] else f"posts: {e}"

    return summary


def _fetch_posts(niche_key, niche_cfg, page, limit):
    profile_id = niche_cfg["zernio_profile_id"]
    api_key    = niche_cfg["zernio_api_key"]

    raw = _api_get("/posts", api_key, {
        "profileId": profile_id,
        "status":    "scheduled",
        "page":      page,
        "limit":     limit,
    })

    posts = []
    for p in raw.get("posts") or []:
        title = ""
        try:
            title = ((p.get("platforms") or [{}])[0]
                     .get("platformSpecificData", {})
                     .get("title", "") or "")
        except Exception:
            pass
        media_url = ""
        try:
            media_url = (p.get("mediaItems") or [{}])[0].get("url", "")
        except Exception:
            pass
        posts.append({
            "id":            p.get("_id", ""),
            "title":         title,
            "content":       p.get("content", "") or "",
            "scheduled_for": p.get("scheduledFor", ""),
            "status":        p.get("status", ""),
            "media_url":     media_url,
            "queue_id":      p.get("queueId", ""),
            "created_at":    p.get("createdAt", ""),
        })

    return {"posts": posts, "pagination": raw.get("pagination") or {}}


# ------------------------------------------------------------------
# Public: single niche (stale-while-revalidate)
# ------------------------------------------------------------------
def summary_for_niche(niche_key, niche_cfg, force=False):
    key = f"summary:{niche_key}"
    if not force:
        val, fresh, stale = _cache_get(key)
        if val is not None:
            if stale:
                _refresh_in_background(_fetch_summary, key,
                                       SUMMARY_TTL, niche_key, niche_cfg)
            return val
    # Cold cache or forced refresh — do it synchronously
    val = _fetch_summary(niche_key, niche_cfg)
    _cache_set(key, val, SUMMARY_TTL)
    return val


def scheduled_posts_for_niche(niche_key, niche_cfg, page=1, limit=50, force=False):
    key = f"posts:{niche_key}:{page}:{limit}"
    if not force:
        val, fresh, stale = _cache_get(key)
        if val is not None:
            if stale:
                _refresh_in_background(_fetch_posts, key, POSTS_TTL,
                                       niche_key, niche_cfg, page, limit)
            return val
    val = _fetch_posts(niche_key, niche_cfg, page, limit)
    _cache_set(key, val, POSTS_TTL)
    return val


# ------------------------------------------------------------------
# Public: bulk fetch, all niches in parallel
# ------------------------------------------------------------------
def all_summaries(force=False):
    """
    Return a dict {niche_key: summary}. Fetches all niches in parallel.
    Uses stale-while-revalidate per niche.
    """
    niches = list_niches()
    if not niches:
        return {}

    # Fast path — everything from cache
    out = {}
    to_fetch = []
    for key, cfg in niches.items():
        if not force:
            val, fresh, stale = _cache_get(f"summary:{key}")
            if val is not None:
                out[key] = val
                if stale:
                    _refresh_in_background(_fetch_summary, f"summary:{key}",
                                           SUMMARY_TTL, key, cfg)
                continue
        to_fetch.append((key, cfg))

    if not to_fetch:
        return out

    # Parallel fetch of the missing ones
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(to_fetch))) as pool:
        futures = {
            pool.submit(_fetch_summary, key, cfg): (key, cfg)
            for key, cfg in to_fetch
        }
        for fut in as_completed(futures):
            key, _ = futures[fut]
            try:
                val = fut.result(timeout=25)
            except Exception as e:
                val = {
                    "niche": key, "label": key, "error": str(e),
                    "queue_name": "", "slots_free": 0,
                    "scheduled_total": 0, "next_slot": "",
                    "profile_id": "", "account_id": "",
                }
            out[key] = val
            _cache_set(f"summary:{key}", val, SUMMARY_TTL)

    return out


# ------------------------------------------------------------------
# Background warmer
# ------------------------------------------------------------------
_warmer_started = False
_warmer_lock = threading.Lock()


def start_warmer():
    """Spawn a daemon thread that keeps the summary cache warm."""
    global _warmer_started
    with _warmer_lock:
        if _warmer_started:
            return
        _warmer_started = True

    def _loop():
        # Initial warm
        try:
            all_summaries(force=False)
        except Exception as e:
            print(f"⚠️  warmer initial: {e}")
        while True:
            time.sleep(WARMER_SEC)
            try:
                all_summaries(force=False)   # refresh stale in background
            except Exception as e:
                print(f"⚠️  warmer loop: {e}")

    threading.Thread(target=_loop, daemon=True, name="zernio-warmer").start()
    print(f"🔥 Zernio warmer started (every {WARMER_SEC}s)")


def cache_stats():
    """For the /api/zernio/stats route."""
    now = time.time()
    with _cache_lock:
        entries = []
        for k, (exp, val) in _cache.items():
            entries.append({
                "key":     k,
                "ttl_left": max(0, int(exp - now)),
                "fresh":   exp > now,
            })
    return {
        "entries":      entries,
        "entry_count":  len(entries),
        "warmer_on":    _warmer_started,
        "summary_ttl":  SUMMARY_TTL,
        "posts_ttl":    POSTS_TTL,
        "warmer_sec":   WARMER_SEC,
    }