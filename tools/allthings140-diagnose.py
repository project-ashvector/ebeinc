#!/usr/bin/env python3
"""Listener-facing and local release health checks for ALLTHINGS140 Radio."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[tuple[str, bool, str]] = []

def record(name: str, ok: bool, detail: str) -> None:
    CHECKS.append((name, ok, detail.replace("\n", " ")[:220]))

def request(name: str, url: str, expect: str | None = None) -> bytes:
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ALLTHINGS140-Diagnostics/1.0", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read(131072)
            mime = response.headers.get_content_type()
            ok = response.status == 200 and (expect is None or expect in mime)
            record(name, ok, f"HTTP {response.status}, {mime}, {time.monotonic()-started:.2f}s")
            return body
    except Exception as exc:
        record(name, False, str(exc)); return b""

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    request("Website", "https://allthings140radio.online/", "text/html")
    raw = request("Metadata", "https://status.ebeinc.online/api/public/status", "application/json")
    if raw:
        try:
            state = json.loads(raw)
            record("Broadcast state", bool(state.get("online") and state.get("stream_url")),
                   f"generation={state.get('station_generation_id')} sequence={state.get('station_sequence')} track={state.get('current_track_id')}")
        except Exception as exc: record("Broadcast state", False, str(exc))
    audio = request("Public stream", "https://stream.ebeinc.online/live.mp3", "audio/")
    if audio: record("Stream payload", len(audio) > 8192, f"received {len(audio)} bytes")
    tests = subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT, capture_output=True, text=True)
    record("Backend tests", tests.returncode == 0, "pass" if tests.returncode == 0 else tests.stderr[-180:])
    android = ROOT / "android/mobile-app/app/build/outputs/apk/debug/app-debug.apk"
    record("Android build", android.exists(), str(android.relative_to(ROOT)) if android.exists() else "run Android build")
    record("Backup manifest", (ROOT / "backups/final-production-baseline-20260813/SHA256SUMS.txt").exists(), "local baseline manifest")
    overall = all(ok for _, ok, _ in CHECKS)
    if args.json:
        print(json.dumps({"checked_at": int(time.time()), "overall": "healthy" if overall else "degraded",
                          "checks": [{"name": n, "ok": o, "detail": d} for n,o,d in CHECKS]}, indent=2))
    else:
        print("ALLTHINGS140 RADIO HEALTH\n")
        for name, ok, detail in CHECKS: print(f"{name:18} {'ONLINE' if ok else 'FAILED':7}  {detail}")
        print(f"\nOverall: {'HEALTHY' if overall else 'DEGRADED'}")
    return 0 if overall else 1

if __name__ == "__main__": raise SystemExit(main())
