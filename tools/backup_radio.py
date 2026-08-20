#!/usr/bin/env python3
"""Create a timestamped, non-destructive AllThings140Radio backup."""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import time
from pathlib import Path

def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("backups"))
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("ALLTHINGS140_DB_PATH", "/var/lib/allthings140radio/station.db")))
    parser.add_argument("--state", type=Path, default=Path(os.environ.get("ALLTHINGS140_ROTATION_STATE_PATH", "/var/lib/allthings140radio/rotation-state.json")))
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("ALLTHINGS140_CONFIG_PATH", "/etc/allthings140radio/config.json")))
    args = parser.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    target = args.output / stamp
    target.mkdir(parents=True, exist_ok=False)
    if args.db.exists():
        with sqlite3.connect(args.db) as source, sqlite3.connect(target / "station.db") as backup:
            source.backup(backup)
    copy_if_exists(args.state, target / "rotation-state.json")
    copy_if_exists(args.config, target / "config.json")
    print(target)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
