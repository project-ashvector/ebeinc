#!/usr/bin/env python3
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

ROOT = os.path.realpath(os.environ.get("MEDIA_ROOT", "/srv/allthings140-visuals/media"))
ORIGIN = os.environ.get("MEDIA_CORS_ORIGIN", "https://allthings140-visuals-green.pages.dev")

class Handler(BaseHTTPRequestHandler):
    server_version = "AT140Media/1.0"

    def _headers(self, length=None, content_type=None, status=200, start=None, end=None, total=None):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header("Access-Control-Expose-Headers", "Accept-Ranges, Content-Length, Content-Range, Content-Type")
        if status >= 400:
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        if start is not None and end is not None and total is not None:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()

    def do_OPTIONS(self):
        self._headers(0, status=204)

    def do_HEAD(self):
        self._serve(False)

    def do_GET(self):
        self._serve(True)

    def _serve(self, body):
        path = unquote(urlsplit(self.path).path)
        if not (path.startswith("/stage/") or path.startswith("/visuals/")):
            self._headers(0, status=404)
            return
        target = os.path.realpath(os.path.join(ROOT, path.lstrip("/")))
        if not target.startswith(ROOT + os.sep) or not os.path.isfile(target):
            self._headers(0, status=404)
            return
        size = os.path.getsize(target)
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        range_header = self.headers.get("Range", "")
        start, end = 0, size - 1
        status = 200
        if range_header.startswith("bytes="):
            spec = range_header[6:].split(",", 1)[0].strip()
            try:
                left, right = spec.split("-", 1)
                if left:
                    start = int(left)
                    end = int(right) if right else size - 1
                else:
                    length = int(right)
                    start = max(0, size - length)
                if start < 0 or start >= size or end < start:
                    raise ValueError
                end = min(end, size - 1)
                status = 206
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Access-Control-Allow-Origin", ORIGIN)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
        length = end - start + 1
        self._headers(
            length,
            ctype,
            status,
            start if status == 206 else None,
            end if status == 206 else None,
            size if status == 206 else None,
        )
        if not body:
            return
        with open(target, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining:
                chunk = fh.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("MEDIA_PORT", "20242"))), Handler).serve_forever()
