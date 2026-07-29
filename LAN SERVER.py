#!/usr/bin/env python3
"""No-cache LAN development server for the BitByt3s portfolio."""
from __future__ import annotations

import http.server
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

HOST = "0.0.0.0"
PORT_START = 8080
PORT_END = 8199
ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / ".bitbyt3s-server.json"


class ThreadingServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
        sys.stdout.flush()


def find_server() -> tuple[ThreadingServer, int]:
    for port in range(PORT_START, PORT_END + 1):
        try:
            return ThreadingServer((HOST, port), NoCacheHandler), port
        except OSError:
            continue
    raise RuntimeError(f"No free port found between {PORT_START} and {PORT_END}.")


def lan_ips() -> list[str]:
    results: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                results.append(ip)
    except OSError:
        pass
    try:
        output = subprocess.check_output(["hostname", "-I"], text=True, timeout=2)
        for ip in output.split():
            if ":" not in ip and not ip.startswith("127.") and ip not in results:
                results.append(ip)
    except Exception:
        pass
    return results


def open_browser(url: str) -> None:
    def run() -> None:
        time.sleep(0.8)
        try:
            webbrowser.open(url, new=2)
        except Exception:
            try:
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def main() -> int:
    os.chdir(ROOT)
    try:
        server, port = find_server()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    local_url = f"http://localhost:{port}"
    network_urls = [f"http://{ip}:{port}" for ip in lan_ips()]
    STATE_FILE.write_text(json.dumps({
        "pid": os.getpid(), "port": port, "root": str(ROOT),
        "local_url": local_url, "lan_urls": network_urls
    }, indent=2), encoding="utf-8")

    print("\n============================================================")
    print(" BITBYT3S / CODY RICHENBERG — PORTFOLIO SERVER")
    print("============================================================")
    print(f"This laptop:  {local_url}")
    if network_urls:
        print("\nEnter ONE of these exact addresses on your other PC/device:")
        for url in network_urls:
            print(f"  {url}")
    else:
        print("\nThe LAN address could not be detected automatically.")
        print(f"Run: hostname -I   then use http://YOUR-IP:{port}")
    print("\nTesting cache is disabled, so refreshed files should appear immediately.")
    print("Keep this Terminal open. Press Ctrl+C to stop the site.")
    print("You can also run: ./\"STOP SITE - ZORIN.sh\"")
    print("If another device cannot connect, allow the displayed port:")
    print(f"  sudo ufw allow {port}/tcp")
    print("============================================================\n")

    open_browser(local_url)

    def stop(*_: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        STATE_FILE.unlink(missing_ok=True)
        print("\nBitByt3s portfolio server stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
