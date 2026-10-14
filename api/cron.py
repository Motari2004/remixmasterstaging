"""
Vercel cron endpoint.

Vercel auto-serves any file under /api/ as a serverless function.
This one returns 200 OK so the cron job doesn't 404.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timezone


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {
            "ok": True,
            "task": "cron",
            "time": datetime.now(timezone.utc).isoformat(),
            "env": os.environ.get("VERCEL_ENV", "local"),
        }
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)