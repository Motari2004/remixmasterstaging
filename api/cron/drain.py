"""
Vercel serverless drain: pull staged posts from Neon, push to Buffer.

Triggered by an external cron (cron-job.org) at a fixed interval.

GET /api/cron/drain?secret=XXX
  → drains every Buffer niche found in niche_configs
  → returns JSON summary

Env vars:
  NEON_DATABASE_URL    required
  DRAIN_SECRET         required (matches ?secret=)
  MAX_SENDS_PER_RUN    optional, default 10
  MAX_RUNTIME_SECONDS  optional, default 50
"""
import os
import sys
import json
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Make `lib/` importable — Vercel runs this file from api/cron/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lib import db
from lib.buffer import publish, LimitReached


MAX_SENDS_PER_RUN   = int(os.environ.get("MAX_SENDS_PER_RUN", "10"))
MAX_RUNTIME_SECONDS = int(os.environ.get("MAX_RUNTIME_SECONDS", "50"))
DRAIN_SECRET        = os.environ.get("DRAIN_SECRET", "")


def _drain_niche(niche, cfg, deadline):
    """Drain one niche. Returns dict with counts."""
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

    # ---- Self-heal: flip back to direct if the queue is empty ----
    try:
        if result["requeued"] == 0 and result["failed"] == 0:
            pending = db.count_pending(niche)
            if pending == 0:
                db.set_niche_mode(niche, "direct")
                result["flipped_to_direct"] = True
                print(f"  🔄 {niche} flipped back to direct")
    except Exception as e:
        print(f"  ⚠️  {niche} flip-back check failed: {e}")

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
        niches = db.get_buffer_niches()
    except Exception as e:
        return {
            "ok": False,
            "error": f"Could not load niche configs: {e}",
            "started_at": started,
        }

    if not niches:
        summary["note"] = "No buffer niches found in niche_configs"
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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # ---- Auth ----
        if DRAIN_SECRET:
            provided = (qs.get("secret") or [""])[0]
            if provided != DRAIN_SECRET:
                self._reply(401, {"ok": False, "error": "unauthorized"})
                return

        # ---- Health check (no drain, no auth needed for HEAD) ----
        if parsed.path.endswith("/ping"):
            self._reply(200, {"ok": True, "service": "staging-drain"})
            return

        # ---- Run the drain ----
        try:
            result = run_drain()
            self._reply(200 if result.get("ok") else 500, result)
        except Exception as e:
            self._reply(500, {"ok": False, "error": f"drain crashed: {e}"})

    def do_POST(self):
        self.do_GET()

    def _reply(self, code, payload):
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Vercel captures stdout; suppress default BaseHTTPRequestHandler noise
        print(f"[drain] {fmt % args}")