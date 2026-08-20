#!/usr/bin/env python3
"""Read-only catalog/storage integrity analysis for AllThings140Radio."""
from __future__ import annotations

import hashlib
import argparse
import csv
import json
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


VARIANT_WORDS = re.compile(r"\b(vip|remix|live|edit|extended|bootleg|mix|version|remaster(?:ed)?)\b", re.I)


def normalized_text(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stat(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False, "path": "", "canonical_path": "", "size_bytes": None}
    try:
        exists = path.is_file()
        return {
            "exists": exists,
            "path": str(path),
            "canonical_path": str(path.resolve(strict=False)),
            "size_bytes": path.stat().st_size if exists else None,
        }
    except OSError:
        return {"exists": False, "path": str(path), "canonical_path": str(path), "size_bytes": None}


def scan_catalog(
    db_path: Path,
    master_dir: Path,
    emergency_dir: Path | None,
    playback_resolver: Callable[[str], Path],
    event_log_path: Path | None = None,
    compute_hashes: bool = False,
) -> dict[str, Any]:
    """Classify catalog records without changing the database or asset store."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    rows = [dict(row) for row in db.execute(
        """SELECT t.*,a.sha256,a.size_bytes AS recorded_size_bytes,a.duration,
                  a.source_path,a.ingested_at
           FROM tracks t LEFT JOIN audio_assets a ON a.track_id=t.id ORDER BY t.id"""
    )]
    audit_rows = [dict(row) for row in db.execute(
        "SELECT id,action,detail,created_at FROM audit_log ORDER BY id"
    )]
    db.close()

    last_plays: dict[int, int] = {}
    if event_log_path and event_log_path.exists():
        try:
            for line in event_log_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event") == "track_started" and event.get("track_id") is not None:
                    last_plays[int(event["track_id"])] = max(last_plays.get(int(event["track_id"]), 0), int(event.get("ts", 0)))
        except (OSError, ValueError, TypeError):
            pass

    filename_ids: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        filename_ids[str(row["filename"])].append(int(row["id"]))

    records: list[dict[str, Any]] = []
    hash_groups: dict[str, list[int]] = defaultdict(list)
    metadata_groups: dict[str, list[int]] = defaultdict(list)
    canonical_groups: dict[str, list[int]] = defaultdict(list)
    referenced_names: set[str] = set()
    for row in rows:
        filename = str(row["filename"])
        referenced_names.add(filename)
        master = _stat(master_dir / filename)
        emergency = _stat(emergency_dir / filename if emergency_dir else None)
        playback = _stat(playback_resolver(filename))
        stored = bool(master["exists"] or emergency["exists"])
        eligible = bool(row["approved"] and row["enabled"] and row["rights_confirmed"])
        digest = str(row.get("sha256") or "")
        source_for_hash = Path(master["path"]) if master["exists"] else (Path(emergency["path"]) if emergency["exists"] else None)
        if compute_hashes and source_for_hash and not digest:
            try:
                digest = sha256_file(source_for_hash)
            except OSError:
                pass
        if digest:
            hash_groups[digest].append(int(row["id"]))
        canonical = master["canonical_path"] if master["exists"] else emergency["canonical_path"]
        if canonical:
            canonical_groups[canonical].append(int(row["id"]))
        metadata_key = normalized_text(row["artist"]) + "|" + normalized_text(row["title"])
        if metadata_key != "|":
            metadata_groups[metadata_key].append(int(row["id"]))
        audit = [item for item in audit_rows if str(item.get("detail", "")) == filename or str(item.get("detail", "")).startswith(f"{row['id']}:") or filename in str(item.get("detail", ""))]
        status = (
            "UNAPPROVED" if not row["approved"] else
            "DISABLED" if not row["enabled"] else
            "RIGHTS_BLOCKED" if not row["rights_confirmed"] else
            "MISSING_AUDIO" if not stored else
            "PLAYABLE" if playback["exists"] else
            "STORED_NOT_PLAYBACK_READY"
        )
        records.append({
            **row,
            "album": "",
            "import_method": "managed_upload" if any(item.get("action") == "track_uploaded" for item in audit) else "unknown",
            "expected_filename": filename,
            "expected_path": str(master_dir / filename),
            "master": master,
            "emergency": emergency,
            "playback": playback,
            "resolved_path": playback["path"] if playback["exists"] else "",
            "stored_audio": stored,
            "playback_ready": bool(playback["exists"]),
            "eligible": eligible,
            "status": status,
            "shared_filename_ids": filename_ids[filename],
            "last_played_at": last_plays.get(int(row["id"]), 0),
            "audit_events": audit,
            "recovery_status": "NOT_REQUIRED" if stored else "NOT_FOUND",
            "likely_duplicate_groups": [],
        })

    by_id = {int(record["id"]): record for record in records}
    duplicate_groups: list[dict[str, Any]] = []
    exact_members: set[int] = set()
    for digest, ids in hash_groups.items():
        if len(ids) > 1:
            exact_members.update(ids)
            duplicate_groups.append({"classification": "EXACT_AUDIO_DUPLICATE", "confidence": "exact", "sha256": digest, "track_ids": ids, "automatic_cleanup_eligible": True})
    for canonical, ids in canonical_groups.items():
        if len(ids) > 1 and not set(ids).issubset(exact_members):
            duplicate_groups.append({"classification": "SHARED_CANONICAL_FILE", "confidence": "exact_reference", "canonical_path": canonical, "track_ids": ids, "automatic_cleanup_eligible": False})
    for key, ids in metadata_groups.items():
        if len(ids) < 2 or set(ids).issubset(exact_members):
            continue
        variants = any(VARIANT_WORDS.search(str(by_id[i].get("title", ""))) for i in ids)
        duplicate_groups.append({
            "classification": "METADATA_COLLISION" if variants else "PROBABLE_METADATA_DUPLICATE",
            "confidence": "review_only",
            "metadata_key": key,
            "track_ids": ids,
            "automatic_cleanup_eligible": False,
        })

    for index, group in enumerate(duplicate_groups, 1):
        for track_id in group["track_ids"]:
            by_id[track_id]["likely_duplicate_groups"].append({"group": index, "classification": group["classification"], "confidence": group["confidence"]})

    orphan_files: list[dict[str, Any]] = []
    try:
        for path in master_dir.iterdir():
            if path.is_file() and path.name not in referenced_names:
                orphan_files.append({"filename": path.name, "path": str(path), "size_bytes": path.stat().st_size})
    except OSError:
        pass
    counts = defaultdict(int)
    for record in records:
        counts[record["status"].lower()] += 1
    counts.update({
        "total_catalog": len(records),
        "approved_enabled": sum(bool(r["approved"] and r["enabled"]) for r in records),
        "missing_approved_audio": sum(bool(r["eligible"] and not r["stored_audio"]) for r in records),
        "playback_ready": sum(bool(r["eligible"] and r["playback_ready"]) for r in records),
        "stored_not_playback_ready": sum(bool(r["eligible"] and r["stored_audio"] and not r["playback_ready"]) for r in records),
        "shared_filename_records": sum(len(r["shared_filename_ids"]) > 1 for r in records),
        "exact_duplicate_groups": sum(g["classification"] == "EXACT_AUDIO_DUPLICATE" for g in duplicate_groups),
        "probable_duplicate_groups": sum(g["confidence"] == "review_only" for g in duplicate_groups),
        "orphan_files": len(orphan_files),
    })
    health = "degraded" if counts["missing_approved_audio"] else "healthy"
    return {"schema": 1, "generated_at": int(time.time()), "health": health, "counts": dict(counts), "records": records, "duplicate_groups": duplicate_groups, "orphan_files": orphan_files}


def write_reports(report: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "catalog-integrity.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    fields = ["id", "artist", "title", "album", "filename", "expected_filename", "expected_path", "resolved_path", "status", "approved", "enabled", "rights_confirmed", "created_at", "import_method", "source_path", "sha256", "recorded_size_bytes", "duration", "stored_audio", "playback_ready", "shared_filename_ids", "likely_duplicate_groups", "last_played_at", "audit_events", "recovery_status"]
    with (output / "catalog-integrity.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in report["records"]:
            writer.writerow({key: json.dumps(record.get(key), ensure_ascii=False) if isinstance(record.get(key), (list, dict)) else record.get(key) for key in fields})
    counts = report["counts"]
    lines = ["# AllThings140Radio catalog integrity report", "", f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report['generated_at']))}", f"Health: **{report['health'].upper()}**", "", "## Counts", ""]
    lines.extend(f"- {key.replace('_', ' ').title()}: {value}" for key, value in sorted(counts.items()))
    lines.extend(["", "## Records requiring attention", "", "| ID | Status | Artist | Title | Expected filename |", "|---:|---|---|---|---|"])
    for record in report["records"]:
        if record["status"] != "PLAYABLE":
            clean = lambda value: str(value or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {record['id']} | {record['status']} | {clean(record['artist'])} | {clean(record['title'])} | {clean(record['filename'])} |")
    (output / "catalog-integrity.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--emergency", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--hashes", action="store_true")
    parser.add_argument("--recovery-ledger", type=Path, action="append", default=[])
    args = parser.parse_args()
    report = scan_catalog(args.db, args.master, args.emergency, lambda name: args.emergency / name, args.events, args.hashes)
    recovered: dict[str, dict[str, Any]] = {}
    for ledger_path in args.recovery_ledger:
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            for item in ledger.get("items", []):
                recovered[str(item.get("filename", ""))] = item
        except (OSError, ValueError, TypeError):
            continue
    for record in report["records"]:
        item = recovered.get(str(record["filename"]))
        if item:
            record["recovery_status"] = item.get("status", record["recovery_status"])
            record["recovery_evidence"] = item
    write_reports(report, args.output)
    print(json.dumps({"health": report["health"], "counts": report["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
