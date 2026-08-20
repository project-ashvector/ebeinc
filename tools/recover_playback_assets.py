#!/usr/bin/env python3
"""Safely seed eligible Drive masters missing from the emergency playback mirror."""
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=90, check=False,
    )
    try:
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except ValueError:
        return 0.0


def run(db_path: Path, master: Path, emergency: Path, ledger: Path, apply: bool, rclone_remote: str = "", rclone_config: Path | None = None, min_id: int = 0, max_id: int = 0) -> dict:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT t.id,t.artist,t.title,t.filename,t.approved,t.enabled,t.rights_confirmed,
                  t.created_at,a.sha256 AS recorded_sha256,a.size_bytes AS recorded_size,a.duration AS recorded_duration
           FROM tracks t LEFT JOIN audio_assets a ON a.track_id=t.id
           WHERE t.approved=1 AND t.enabled=1 AND t.rights_confirmed=1 ORDER BY t.id"""
    ).fetchall()
    rows = [row for row in rows if int(row["id"]) >= min_id and (not max_id or int(row["id"]) <= max_id)]
    db.close()
    items = []
    for row in rows:
        source, target = master / row["filename"], emergency / row["filename"]
        if target.is_file():
            continue
        item = dict(row)
        item.update({"source": str(source), "target": str(target), "status": "NOT_FOUND"})
        staged_source = source
        remote_temp = ledger.parent / "verify-temp" / f"{row['id']}-{Path(row['filename']).name}"
        if rclone_remote:
            remote_temp.parent.mkdir(parents=True, exist_ok=True)
            command = ["rclone", "copyto", rclone_remote.rstrip(":") + ":" + str(row["filename"]), str(remote_temp), "--timeout", "2m", "--contimeout", "20s", "--retries", "2", "--low-level-retries", "2"]
            if rclone_config:
                command.extend(["--config", str(rclone_config)])
            try:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
            except subprocess.TimeoutExpired:
                item.update({"status": "MANUAL_REVIEW", "reason": "bounded rclone copy timed out"}); items.append(item); continue
            if completed.returncode != 0 or not remote_temp.is_file():
                item.update({"status": "NOT_FOUND", "reason": completed.stderr[-500:]}); items.append(item); continue
            staged_source = remote_temp
        elif not source.is_file():
            items.append(item)
            continue
        source_size = staged_source.stat().st_size
        source_duration = duration(staged_source)
        source_hash = sha256(staged_source)
        item.update({"source_size": source_size, "source_duration": source_duration, "source_sha256": source_hash})
        recorded_hash = str(row["recorded_sha256"] or "")
        if source_duration < 5 or (recorded_hash and recorded_hash != source_hash):
            item["status"] = "MANUAL_REVIEW"
            item["reason"] = "validation or recorded hash mismatch"
            if rclone_remote:
                remote_temp.unlink(missing_ok=True)
            items.append(item)
            continue
        item["status"] = "FOUND_IN_PRIMARY_DRIVE"
        if apply:
            emergency.mkdir(parents=True, exist_ok=True)
            temporary = emergency / f".{target.name}.{os.getpid()}.partial"
            if temporary.exists():
                raise RuntimeError(f"unexpected temporary path: {temporary}")
            shutil.copyfile(staged_source, temporary)
            copied_hash = sha256(temporary)
            copied_duration = duration(temporary)
            if copied_hash != source_hash or copied_duration < 5:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"copy validation failed: {row['id']} {row['filename']}")
            if target.exists():
                temporary.unlink(missing_ok=True)
                item["status"] = "NO_ACTION"
                item["reason"] = "target appeared during copy"
            else:
                os.replace(temporary, target)
                item["status"] = "FILE_RESTORED"
                item["restored_sha256"] = copied_hash
                item["restored_duration"] = copied_duration
        if rclone_remote:
            remote_temp.unlink(missing_ok=True)
        items.append(item)
    payload = {
        "schema": 1, "operation_id": f"playback-recovery-{int(time.time())}",
        "mode": "apply" if apply else "dry-run", "generated_at": int(time.time()),
        "source": str(master), "destination": str(emergency), "items": items,
        "counts": {status: sum(item["status"] == status for item in items) for status in sorted({item["status"] for item in items})},
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    temporary_ledger = ledger.with_suffix(ledger.suffix + ".tmp")
    temporary_ledger.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary_ledger, ledger)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("/var/lib/allthings140radio/station.db"))
    parser.add_argument("--master", type=Path, default=Path("/mnt/allthings140radio-drive"))
    parser.add_argument("--emergency", type=Path, default=Path("/srv/allthings140radio/data/music"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--rclone-remote", default="")
    parser.add_argument("--rclone-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-id", type=int, default=0)
    parser.add_argument("--max-id", type=int, default=0)
    parser.add_argument("--verify-from-ledger", type=Path)
    args = parser.parse_args()
    if args.verify_from_ledger:
        source_ledger = json.loads(args.verify_from_ledger.read_text(encoding="utf-8"))
        items = []
        for original in source_ledger.get("items", []):
            item = dict(original)
            target = args.emergency / str(item.get("filename", ""))
            if not target.is_file():
                item.update({"status": "NOT_FOUND", "reason": "emergency target absent"})
            else:
                digest, measured_duration = sha256(target), duration(target)
                expected = str(item.get("source_sha256", ""))
                item.update({"restored_sha256": digest, "restored_duration": measured_duration})
                if expected and digest == expected and measured_duration >= 5:
                    item["status"] = "FILE_RESTORED"
                else:
                    item.update({"status": "MANUAL_REVIEW", "reason": "post-copy hash or duration mismatch"})
            items.append(item)
        payload = {"schema": 1, "operation_id": f"playback-recovery-verification-{int(time.time())}", "mode": "post-copy-verification", "generated_at": int(time.time()), "items": items, "counts": {status: sum(item["status"] == status for item in items) for status in sorted({item["status"] for item in items})}}
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        args.ledger.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(payload["counts"], sort_keys=True))
        return 0 if not payload["counts"].get("MANUAL_REVIEW") and not payload["counts"].get("NOT_FOUND") else 2
    result = run(args.db, args.master, args.emergency, args.ledger, args.apply, args.rclone_remote, args.rclone_config, args.min_id, args.max_id)
    print(json.dumps(result["counts"], sort_keys=True))
    return 0 if not result["counts"].get("MANUAL_REVIEW") else 2


if __name__ == "__main__":
    raise SystemExit(main())
