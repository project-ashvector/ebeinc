#!/usr/bin/env python3
"""Audit the approved AllThings140Radio catalog for repetition and gaps.

This is read-only. It reports catalog size, repeated artist/title pairs, and
tracks that have not been played according to the event log (when available).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("ALLTHINGS140_DB_PATH", "/var/lib/allthings140radio/station.db"))
DEFAULT_STATE = Path(os.environ.get("ALLTHINGS140_ROTATION_STATE_PATH", "/var/lib/allthings140radio/rotation-state.json"))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.db.exists():
        parser.error(f"database not found: {args.db}")
    with sqlite3.connect(args.db) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,title,artist,filename FROM tracks WHERE approved=1 AND enabled=1 ORDER BY id").fetchall()
    artists = Counter((str(row["artist"] or "Unknown artist").strip() or "Unknown artist") for row in rows)
    titles = Counter((str(row["title"] or Path(row["filename"]).stem).strip() or "Untitled") for row in rows)
    state = {}
    if args.state.exists():
        try: state = json.loads(args.state.read_text(encoding="utf-8"))
        except (OSError, ValueError): state = {}
    result = {"approved_enabled": len(rows), "unique_artists": len(artists), "unique_titles": len(titles),
              "rotation_order": len(state.get("rotation_order", [])) if isinstance(state, dict) else 0,
              "seen_this_cycle": len(state.get("rotation_seen", [])) if isinstance(state, dict) else 0,
              "repeated_artists": [{"artist": k, "count": v} for k,v in artists.most_common(args.top) if v > 1],
              "repeated_titles": [{"title": k, "count": v} for k,v in titles.most_common(args.top) if v > 1]}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"Approved playable catalog: {result['approved_enabled']} tracks / {result['unique_artists']} artists")
        print(f"Rotation state: {result['seen_this_cycle']} seen of {result['rotation_order']} tracks")
        for label in ("repeated_artists", "repeated_titles"):
            print(label.replace("_", " ").title() + ":")
            for item in result[label]: print("  ", item)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
