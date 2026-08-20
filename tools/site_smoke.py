#!/usr/bin/env python3
"""Read-only production smoke test for the public AllThings140Radio site."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

@dataclass
class Result:
    name: str
    ok: bool
    detail: str

def get(url: str, timeout: float) -> tuple[int, bytes, str]:
    request = Request(url, headers={"User-Agent": "AllThings140Radio-Smoke/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read(200000), response.headers.get("content-type", "")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="https://allthings140radio.online")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    base = args.site.rstrip("/")
    checks: list[Result] = []
    def check(name: str, path: str, *, contains: bytes | None = None) -> None:
        try:
            code, body, content_type = get(base + path, args.timeout)
            ok = code == 200 and (contains is None or contains in body)
            detail = f"HTTP {code}; {content_type.split(';', 1)[0]}"
            if contains is not None and contains not in body: detail += "; expected marker missing"
            checks.append(Result(name, ok, detail))
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            checks.append(Result(name, False, str(error)))
    check("home", "/", contains=b"styles.css?v=0.7.")
    check("stylesheet", "/styles.css", contains=b".nav-menu")
    check("app", "/app.js", contains=b"schedule")
    check("visuals", "/visuals/", contains=b"visualVideo")
    check("obs_now_playing", "/obs/now-playing/", contains=b"Now Playing")
    check("obs_takeover_logo", "/obs/takeover-logo/", contains=b"Takeover Logos")
    for name, path, marker in (("status_api", "/api/public/status", b"online"), ("schedule_api", "/api/public/schedule", b"takeovers")):
        check(name, path, contains=marker)
    report = {"ok": all(item.ok for item in checks), "checks": [asdict(item) for item in checks]}
    if args.json: print(json.dumps(report, separators=(",", ":")))
    else:
        print(f"AllThings140Radio smoke: {'OK' if report['ok'] else 'FAIL'}")
        for item in checks: print(f"{'PASS' if item.ok else 'FAIL'} {item.name}: {item.detail}")
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
