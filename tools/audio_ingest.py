#!/usr/bin/env python3
"""Validate, hash, deduplicate, and admit staged radio audio safely."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

SUPPORTED = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}


def parse_filename(name: str) -> tuple[str, str, str]:
    stem = Path(name).stem.strip()
    normalized = re.sub(r"\s*(?:_?[-–—]_?)\s*", " - ", stem).strip()
    parts = re.split(r"\s+-\s+", normalized, maxsplit=1)
    if len(parts) == 2 and all(parts) and len(parts[0]) <= 120:
        return parts[0].strip(), parts[1].strip(), "high"
    return "", stem, "low"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels:format=duration:format_tags=artist,title",
        "-of", "json", str(path),
    ], capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError("ffprobe could not decode the file")
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise ValueError("no audio stream")
    duration = float((data.get("format") or {}).get("duration") or 0)
    if not 5 <= duration <= 8 * 60 * 60:
        raise ValueError(f"unreasonable duration: {duration:.1f}s")
    stream = streams[0]
    tags = {str(k).lower(): str(v).strip() for k, v in (data.get("format", {}).get("tags") or {}).items()}
    return {"codec": stream.get("codec_name"), "sample_rate": int(stream.get("sample_rate") or 0),
            "channels": int(stream.get("channels") or 0), "duration": duration,
            "artist": tags.get("artist", ""), "title": tags.get("title", "")}


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
      CREATE TABLE IF NOT EXISTS audio_assets(
        id INTEGER PRIMARY KEY, track_id INTEGER UNIQUE, sha256 TEXT NOT NULL UNIQUE,
        source_path TEXT NOT NULL, size_bytes INTEGER NOT NULL, codec TEXT NOT NULL,
        sample_rate INTEGER NOT NULL, channels INTEGER NOT NULL, duration REAL NOT NULL,
        metadata_confidence TEXT NOT NULL, ingested_at INTEGER NOT NULL,
        FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE SET NULL);
      CREATE TABLE IF NOT EXISTS ingest_events(
        id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL);
    """)


def ingest(source: Path, ready: Path, failed: Path, db_path: Path, dry_run: bool = False) -> dict:
    if source.suffix.lower() not in SUPPORTED:
        raise ValueError("unsupported audio format")
    before = source.stat()
    info = probe(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("file changed during validation")
    digest = sha256(source)
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        ensure_schema(db)
        existing = db.execute("SELECT track_id,source_path FROM audio_assets WHERE sha256=?", (digest,)).fetchone()
        if existing:
            db.execute("INSERT INTO ingest_events(source_path,sha256,state,detail,created_at) VALUES(?,?,?,?,?)",
                       (str(source), digest, "duplicate", f"existing track {existing['track_id']}", int(time.time())))
            db.commit()
            return {"state": "duplicate", "sha256": digest, "existing_track_id": existing["track_id"]}
        parsed_artist, parsed_title, parsed_confidence = parse_filename(source.name)
        artist = info["artist"] or parsed_artist
        title = info["title"] or parsed_title
        confidence = "high" if info["artist"] and info["title"] else parsed_confidence
        destination = ready / source.name
        if destination.exists():
            destination = ready / f"{source.stem}-{digest[:12]}{source.suffix.lower()}"
        result = {"state": "ready", "sha256": digest, "artist": artist, "title": title,
                  "confidence": confidence, "destination": str(destination), **info}
        if dry_run:
            result["state"] = "dry-run"
            return result
        ready.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".partial")
        shutil.copy2(source, temporary)
        if sha256(temporary) != digest:
            temporary.unlink(missing_ok=True)
            raise ValueError("copy verification failed")
        os.replace(temporary, destination)
        now = int(time.time())
        cursor = db.execute("INSERT INTO tracks(title,artist,filename,rights_confirmed,approved,enabled,created_at) VALUES(?,?,?,?,?,?,?)",
                            (title, artist, destination.name, 0, 0, 1, now))
        db.execute("INSERT INTO audio_assets(track_id,sha256,source_path,size_bytes,codec,sample_rate,channels,duration,metadata_confidence,ingested_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (cursor.lastrowid, digest, str(source), before.st_size, info["codec"] or "", info["sample_rate"], info["channels"], info["duration"], confidence, now))
        db.execute("INSERT INTO ingest_events(source_path,sha256,state,detail,created_at) VALUES(?,?,?,?,?)",
                   (str(source), digest, "ready_for_review", destination.name, now))
        db.commit()
        result.update(state="ready_for_review", track_id=cursor.lastrowid)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("ALLTHINGS140_DB_PATH", "/var/lib/allthings140radio/station.db")))
    parser.add_argument("--ready", type=Path, default=Path(os.environ.get("ALLTHINGS140_INGEST_READY", "/srv/allthings140radio/ingest/READY")))
    parser.add_argument("--failed", type=Path, default=Path(os.environ.get("ALLTHINGS140_INGEST_FAILED", "/srv/allthings140radio/ingest/FAILED")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(ingest(args.source, args.ready, args.failed, args.db, args.dry_run), indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"state": "failed", "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
