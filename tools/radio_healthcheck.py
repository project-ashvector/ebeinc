#!/usr/bin/env python3
"""Check the public AllThings140Radio listener path.

Exit status is 0 only when the website, status API, current track, and stream
are all reachable and internally consistent. The output is human-readable by
default and JSON with --json for cron, systemd, or an external monitor.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SITE = "https://allthings140radio.online/"
DEFAULT_STATUS = "https://status.ebeinc.online/api/public/status"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    status: int | None = None


@dataclass
class Report:
    ok: bool = True
    checked_at: int = field(default_factory=lambda: int(time.time()))
    checks: list[Check] = field(default_factory=list)
    station: dict[str, object] = field(default_factory=dict)

    def add(self, check: Check) -> None:
        self.checks.append(check)
        self.ok = self.ok and check.ok


def request(url: str, timeout: float, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    req = Request(url, headers={"User-Agent": "AllThings140Radio-Healthcheck/1.0", **(headers or {})})
    with urlopen(req, timeout=timeout) as response:
        return response.status, response.read(4096)


def run(site: str, status_url: str, timeout: float, max_track_age: int = 180, visuals_url: str = "") -> Report:
    report = Report()

    try:
        code, body = request(site, timeout)
        report.add(Check("website", code == 200 and b"AllThings140" in body, f"HTTP {code}", code))
    except (HTTPError, URLError, TimeoutError) as error:
        report.add(Check("website", False, str(error)))

    status: dict[str, object] = {}
    try:
        code, body = request(status_url, timeout, {"Accept": "application/json"})
        status = json.loads(body.decode("utf-8"))
        online = status.get("online") is True
        title = str(status.get("current_title") or "").strip()
        report.station = {
            key: status.get(key)
            for key in ("station_name", "online", "mode", "current_title", "current_artist", "listeners", "approved_tracks", "updated_at")
            if key in status
        }
        report.add(Check("status_api", code == 200 and online, f"HTTP {code}; online={online}", code))
        report.add(Check("current_track", online and bool(title), title or "no current track"))
        updated_at = float(status.get("updated_at") or 0)
        age = max(0, int(time.time() - updated_at)) if updated_at else None
        report.add(Check("status_freshness", online and age is not None and age <= max_track_age,
                         f"age={age if age is not None else 'unknown'}s; limit={max_track_age}s"))
    except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError) as error:
        report.add(Check("status_api", False, str(error)))
        report.add(Check("current_track", False, "status unavailable"))

    stream_url = str(status.get("stream_url") or "")
    if stream_url:
        try:
            # Icecast commonly returns 400 to HEAD. A ranged GET confirms that
            # the mount is serving actual audio without holding the stream open.
            code, audio = request(stream_url, timeout, {"Range": "bytes=0-255", "Accept": "audio/mpeg"})
            stream_ok = code in (200, 206) and len(audio) > 0
            report.add(Check("stream", stream_ok, f"HTTP {code}; received {len(audio)} bytes", code))
        except (HTTPError, URLError, TimeoutError) as error:
            report.add(Check("stream", False, str(error)))
    else:
        report.add(Check("stream", False, "status response did not provide stream_url"))

    if visuals_url:
        try:
            code, body = request(visuals_url, timeout, {"Accept": "application/json"})
            v_ok = code == 200 and json.loads(body.decode("utf-8")).get("ok") is True
            report.add(Check("visuals_realtime", v_ok, f"HTTP {code}; ok={v_ok}", code))
        except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError) as error:
            report.add(Check("visuals_realtime", False, str(error)))

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--status", dest="status_url", default=DEFAULT_STATUS)
    parser.add_argument("--visuals", dest="visuals_url", default="https://visuals-realtime-staging.allthings140radio.online/health")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-track-age", type=int, default=180, help="fail when status.updated_at is older than this many seconds")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    report = run(args.site, args.status_url, args.timeout, max(1, args.max_track_age), args.visuals_url)
    if args.json:
        print(json.dumps(asdict(report), separators=(",", ":")))
    else:
        print(f"AllThings140Radio: {'OK' if report.ok else 'FAIL'}")
        for check in report.checks:
            print(f"{'PASS' if check.ok else 'FAIL'} {check.name}: {check.detail}")
        if report.station:
            print(f"Track: {report.station.get('current_title', '—')} — {report.station.get('current_artist', '—')}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
