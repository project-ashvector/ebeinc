#!/usr/bin/env python3
"""Local-only browser fixture for the persistent account-alert scheduler."""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RADIO = ROOT / "radio"
QA_ALERT = ROOT / "android/mobile-app/app/src/debug/res/raw/at140_qa_alert.mp3"
QA_STREAM = Path("/tmp/at140-qa-stream.mp3")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(RADIO), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/public/alert-catalog"):
            body = json.dumps({
                "schema_version": 1,
                "interval_seconds": 900,
                "server_stream_alert_injection_enabled": True,
                "client_account_alerts_enabled": False,
                "alerts": [{
                    "id": "00000000000000000000000000000000",
                    "url": "/qa-alert.mp3",
                    "duration_seconds": 0.55,
                    "category": "qa_tone",
                }],
                "version": "qa",
                "server_time": 0,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if self.path == "/qa-alert.mp3":
            return self.serve_file(QA_ALERT)
        if self.path == "/qa-stream.mp3":
            return self.serve_file(QA_STREAM)
        return super().do_GET()

    def serve_file(self, path):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18776), Handler).serve_forever()
