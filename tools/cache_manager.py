#!/usr/bin/env python3
"""Predictive, bounded local playback cache for AllThings140Radio.

Google Drive remains the source of truth.  This process only stages complete,
validated copies (or same-filesystem hard links) locally before AutoDJ needs
them.  Cache files are disposable and are never removed from the master.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

DB = Path(os.environ.get("ALLTHINGS140_DB_PATH", "/var/lib/allthings140radio/station.db"))
DATA = Path(os.environ.get("ALLTHINGS140_DATA_DIR", "/var/lib/allthings140radio"))
DRIVE = Path(os.environ.get("ALLTHINGS140_MUSIC_DIR", "/mnt/allthings140radio-drive"))
EMERGENCY = Path(os.environ.get("ALLTHINGS140_FALLBACK_MUSIC_DIR", "/srv/allthings140radio/data/music"))
CACHE = Path(os.environ.get("ALLTHINGS140_CACHE_DIR", "/srv/allthings140radio/cache"))
READY = CACHE / "READY"
TEMP = CACHE / "TEMP"
STATE = CACHE / "cache-state.json"
INDEX = CACHE / "cache-index.json"
TARGET_MINUTES = float(os.environ.get("HOT_CACHE_TARGET_MINUTES", "120"))
MIN_MINUTES = float(os.environ.get("HOT_CACHE_MIN_MINUTES", "45"))
MAX_BYTES = int(float(os.environ.get("HOT_CACHE_MAX_GB", "5")) * 1024**3)
MIN_FREE_PERCENT = float(os.environ.get("HOT_CACHE_MIN_FREE_PERCENT", "12"))
MAX_PREFETCH_TRACKS = int(os.environ.get("HOT_CACHE_MAX_TRACKS", "50"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def duration(path: Path) -> float:
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True, capture_output=True, timeout=45, check=False)
        return float(p.stdout.strip()) if p.returncode == 0 else 0.0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def valid(path: Path, expected_hash: str = "") -> bool:
    if not path.is_file() or path.stat().st_size <= 0 or duration(path) < 5:
        return False
    if expected_hash and sha256(path) != expected_hash:
        return False
    return True


def load_state() -> dict:
    try:
        value = json.loads(STATE.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(value: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True))
    os.replace(tmp, STATE)


def tracks() -> list[dict]:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("""SELECT t.id,t.title,t.artist,t.filename,a.sha256,a.duration
                         FROM tracks t LEFT JOIN audio_assets a ON a.track_id=t.id
                         WHERE t.approved=1 AND t.enabled=1 ORDER BY t.id""").fetchall()
    db.close()
    return [dict(r) for r in rows]


def planned(rows: list[dict]) -> list[dict]:
    order = []
    try:
        rotation = json.loads((DATA / "rotation-state.json").read_text())
        order = [int(v) for v in rotation.get("rotation_order", [])]
        start = int(rotation.get("rotation_index", 0))
        order = order[start:] + order[:start]
    except (OSError, ValueError, TypeError):
        pass
    by_id = {int(r["id"]): r for r in rows}
    ordered = [by_id[i] for i in order if i in by_id]
    ordered.extend(r for r in rows if r not in ordered)
    result, minutes = [], 0.0
    for row in ordered:
        result.append(row)
        minutes += float(row.get("duration") or 0.0) / 60.0
        if minutes >= TARGET_MINUTES or len(result) >= MAX_PREFETCH_TRACKS:
            break
    return result


def cache_name(row: dict) -> str:
    suffix = Path(str(row["filename"])).suffix.lower() or ".audio"
    return f"{int(row['id'])}-{str(row.get('sha256') or 'unhashed')[:16]}{suffix}"


def stage(row: dict, state: dict, index: dict) -> bool:
    name = cache_name(row)
    target = READY / name
    expected = str(row.get("sha256") or "")
    # Existing READY files were atomically validated by this manager.  Avoid
    # re-probing and re-hashing the same large library on every reconciliation.
    if target.exists() and target.stat().st_size > 0:
        index[str(row["filename"])] = str(target)
        state.setdefault(name, {}).update({"track_id": int(row["id"]), "status": "READY", "last_used": int(time.time()), "size": target.stat().st_size, "duration": float(row.get("duration") or duration(target) or 0)})
        return True
    source = EMERGENCY / str(row["filename"])
    if not source.exists():
        source = DRIVE / str(row["filename"])
    if not source.exists():
        state.setdefault(name, {}).update({"track_id": int(row["id"]), "status": "FAILED", "last_error": "source unavailable", "failed_at": int(time.time())})
        return False
    TEMP.mkdir(parents=True, exist_ok=True); READY.mkdir(parents=True, exist_ok=True)
    partial = TEMP / (name + ".partial")
    try:
        if partial.exists(): partial.unlink()
        try:
            os.link(source, partial)
        except OSError:
            shutil.copyfile(source, partial)
        if not valid(partial, expected):
            raise ValueError("ffprobe or SHA-256 validation failed")
        os.replace(partial, target)
        index[str(row["filename"])] = str(target)
        state[name] = {"track_id": int(row["id"]), "status": "READY", "source": str(source), "cached_at": int(time.time()), "last_used": int(time.time()), "size": target.stat().st_size, "duration": float(row.get("duration") or duration(target) or 0)}
        return True
    except Exception as exc:
        try: partial.unlink()
        except OSError: pass
        state[name] = {"track_id": int(row["id"]), "status": "FAILED", "last_error": str(exc), "failed_at": int(time.time())}
        return False


def evict(state: dict, protected: set[str]) -> None:
    usage = shutil.disk_usage(CACHE)
    files = sorted((p for p in READY.iterdir() if p.is_file() and p.name not in protected), key=lambda p: state.get(p.name, {}).get("last_used", 0)) if READY.exists() else []
    total = sum(p.stat().st_size for p in READY.iterdir() if p.is_file()) if READY.exists() else 0
    while files and (total > MAX_BYTES or (usage.free / usage.total * 100) < MIN_FREE_PERCENT):
        path = files.pop(0)
        size = path.stat().st_size
        path.unlink(missing_ok=True); total -= size
        state.pop(path.name, None)
        usage = shutil.disk_usage(CACHE)


def run_once() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True); READY.mkdir(exist_ok=True); TEMP.mkdir(exist_ok=True)
    state, index = load_state(), {}
    rows = tracks(); queue = planned(rows); ready, minutes = 0, 0.0
    protected = set()
    for row in queue:
        name = cache_name(row); protected.add(name)
        if stage(row, state, index):
            ready += 1
            minutes += float(state.get(name, {}).get("duration") or row.get("duration") or 0.0) / 60.0
    # Keep a small local emergency set available without duplicating the source.
    emergency = sum(1 for row in rows if (EMERGENCY / str(row["filename"])).is_file())
    evict(state, protected)
    for row in rows:
        name = cache_name(row)
        target = READY / name
        if target.is_file() and target.stat().st_size > 0:
            index[str(row["filename"])] = str(target)
    payload = {"schema": 1, "status": "healthy" if minutes >= MIN_MINUTES else "degraded", "tracks_ready": ready, "minutes_ready": round(minutes, 1), "target_minutes": TARGET_MINUTES, "min_minutes": MIN_MINUTES, "cache_bytes": sum(p.stat().st_size for p in READY.iterdir() if p.is_file()), "max_bytes": MAX_BYTES, "emergency_tracks": emergency, "drive": "connected" if DRIVE.exists() else "offline", "updated_at": int(time.time())}
    state["_summary"] = payload; save(state)
    tmp = INDEX.with_suffix(".tmp"); tmp.write_text(json.dumps(index, indent=2, sort_keys=True)); os.replace(tmp, INDEX)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=["once", "status", "run"], nargs="?", default="once")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(load_state().get("_summary", {"status": "unknown"}), indent=2)); return 0
    if args.command == "run":
        while True:
            try: print(json.dumps(run_once()), flush=True)
            except Exception as exc: print(json.dumps({"status": "error", "error": str(exc)}), flush=True)
            time.sleep(30)
    print(json.dumps(run_once(), indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
