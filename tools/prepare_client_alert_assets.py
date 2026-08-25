#!/usr/bin/env python3
"""Build public client-alert assets with opaque IDs from a reviewed MP3 folder."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def alert_id(filename: str) -> str:
    return hashlib.sha256(("allthings140-client-alert\0" + filename).encode()).hexdigest()[:32]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    alerts = []
    for source in sorted(args.source.glob("*.mp3")):
        opaque = alert_id(source.name)
        destination = args.destination / f"{opaque}.mp3"
        shutil.copyfile(source, destination)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(destination),
        ], check=True, capture_output=True, text=True, timeout=30)
        alerts.append({
            "id": opaque,
            "url": f"/api/public/alert-media/{opaque}.mp3",
            "duration_seconds": round(float(probe.stdout.strip()), 3),
            "category": "promotional_alert",
        })
    manifest = {
        "schema_version": 1,
        "interval_seconds": 900,
        "alerts": alerts,
        "version": hashlib.sha256(json.dumps(alerts, sort_keys=True).encode()).hexdigest()[:16],
    }
    (args.destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"alerts": len(alerts), "version": manifest["version"]}))


if __name__ == "__main__":
    main()
