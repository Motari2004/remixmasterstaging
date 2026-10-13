"""
Zernio client — niches are handed in per request via set_niches().

Fast: parallel fetch, stale-while-revalidate, background warmer.
Works on Vercel and locally (no file reads).
"""
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

SUMMARY_TTL = 300
POSTS_TTL   = 600
WARMER_SEC  = 180
MAX_WORKERS = 9

_cache_lock = threading.Lock()
_cache = {}
_refresh_locks = {}

_session_local = threading.local()


# ------------------------------------------------------------------
# HTTP
# ------------------------------------------------------------------
def _session():
    s = getattr(_session_local, "session", None)
    if s is None:
        s = requests.Session()
        retry = Retry(total=2, backoff_factor=0.3,
                      status_forcelist=(500, 502, 503, 504),
                      allowed_methods=("GET",))
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16,
                              max_retries=retry)
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
# Cache (stale-while-revalidate)
# ------------------------------------------------------------------
def _cache_get(key, allow_stale=True):
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
    lk = _get_refresh_lock(key)
    if not lk.acquire(blocking=False):
        return
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
# Niche list — supplied by the caller each request
# ------------------------------------------------------------------
_niches_cache = {"value": {}, "expires": 0}
_niches_lock = threading.Lock()
NICHES_TTL = 300


def set_niches(niches):
    """Viewer calls this per request with the settings-derived dict."""
    with _niches_lock:
        _niches_cache["value"] = niches or {}
        _niches_cache["expires"] = time.time() + NICHES_TTL


def list_niches():
    with _niches_lock:
        return dict(_niches_cache["value"] or {})


# ------------------------------------------------------------------
# Fetchers
# ------------------------------------------------------------------
def _fetch_summary(niche_key, niche_cfg):
    profile_id = niche_cfg["zernio_profile_id"]
    api_key    = niche_cfg["zernio_api_key"]

    summary = {
        "niche":           niche_key,
        "label":           niche_cfg.get("label", niche_key),
        "platform":        (niche_cfg.get("platform") or "youtube").lower(),
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

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_q = pool.submit(_api_get, "/queue/preview", api_key,
                            {"profileId": profile_id})
        fut_p = pool.submit(_api_get, "/posts", api_key,
                            {"profileId": profile_id,
                             "status": "scheduled", "limit": 1})

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
# Public API
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


def all_summaries(force=False):
    niches = list_niches()
    if not niches:
        return {}

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

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(to_fetch)))) as pool:
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
                    "platform": "",
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
    global _warmer_started
    with _warmer_lock:
        if _warmer_started:
            return
        _warmer_started = True

    def _loop():
        try:
            all_summaries(force=False)
        except Exception as e:
            print(f"⚠️  warmer initial: {e}")
        while True:
            time.sleep(WARMER_SEC)
            try:
                all_summaries(force=False)
            except Exception as e:
                print(f"⚠️  warmer loop: {e}")

    threading.Thread(target=_loop, daemon=True, name="zernio-warmer").start()
    print(f"🔥 Zernio warmer started (every {WARMER_SEC}s)")


def cache_stats():
    now = time.time()
    with _cache_lock:
        entries = [{"key": k, "ttl_left": max(0, int(exp - now)), "fresh": exp > now}
                   for k, (exp, _) in _cache.items()]
    return {
        "entries": entries, "entry_count": len(entries),
        "warmer_on": _warmer_started,
        "summary_ttl": SUMMARY_TTL, "posts_ttl": POSTS_TTL,
        "warmer_sec": WARMER_SEC,
    }