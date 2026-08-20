#!/usr/bin/env python3
"""Loopback-only Icecast proxy that keeps source credentials out of argv."""
from __future__ import annotations

import argparse
import base64
import selectors
import socket
import socketserver
from pathlib import Path

MAX_HEADER = 64 * 1024


def authenticated_header(header: bytes, credential: str) -> bytes:
    marker = b"\r\n\r\n"
    if marker not in header:
        raise ValueError("incomplete HTTP header")
    head, body = header.split(marker, 1)
    lines = head.split(b"\r\n")
    auth = b"Authorization: Basic " + base64.b64encode(f"source:{credential}".encode())
    filtered = [line for line in lines if not line.lower().startswith(b"authorization:")]
    method = filtered[0].split(b" ", 1)[0].upper()
    if method not in {b"SOURCE", b"PUT"}:
        return b"\r\n".join(filtered) + marker + body
    return b"\r\n".join([filtered[0], auth, *filtered[1:]]) + marker + body


class RelayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        config = self.server.config  # type: ignore[attr-defined]
        incoming = bytearray()
        while b"\r\n\r\n" not in incoming:
            chunk = self.request.recv(8192)
            if not chunk:
                return
            incoming.extend(chunk)
            if len(incoming) > MAX_HEADER:
                return
        credential = Path(config.secret_file).read_text(encoding="utf-8").strip()
        if not credential:
            return
        with socket.create_connection((config.upstream_host, config.upstream_port), timeout=10) as upstream:
            upstream.sendall(authenticated_header(bytes(incoming), credential))
            self.request.setblocking(False)
            upstream.setblocking(False)
            selector = selectors.DefaultSelector()
            selector.register(self.request, selectors.EVENT_READ, upstream)
            selector.register(upstream, selectors.EVENT_READ, self.request)
            while True:
                events = selector.select(timeout=60)
                if not events:
                    continue
                for key, _ in events:
                    destination = key.data
                    try:
                        data = key.fileobj.recv(64 * 1024)
                    except (ConnectionResetError, OSError):
                        return
                    if not data:
                        return
                    try:
                        destination.sendall(data)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return


class RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=14001)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, default=14000)
    parser.add_argument("--secret-file", default="/etc/allthings140radio/icecast-source.secret")
    args = parser.parse_args()
    with RelayServer((args.listen_host, args.listen_port), RelayHandler) as server:
        server.config = args
        server.serve_forever(poll_interval=0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
