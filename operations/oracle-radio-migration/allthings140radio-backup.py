#!/usr/bin/python3
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

source = Path("/var/lib/allthings140radio/station.db")
backup_dir = Path("/srv/allthings140radio/backups")
backup_dir.mkdir(parents=True, exist_ok=True)
temporary = backup_dir / ".station.db.tmp"
latest = backup_dir / "station.db.latest"

if temporary.exists():
    temporary.unlink()

with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30) as src:
    with sqlite3.connect(temporary) as dst:
        src.backup(dst)
        result = dst.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"database backup check failed: {result}")

os.chmod(temporary, 0o640)
os.replace(temporary, latest)

# Keep one dated recovery point per day for the last seven days.
dated = backup_dir / time.strftime("station-%Y%m%d.db", time.gmtime())
if not dated.exists():
    with latest.open("rb") as src, dated.open("xb") as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)
    os.chmod(dated, 0o640)

dated_files = sorted(backup_dir.glob("station-????????.db"))
for old in dated_files[:-7]:
    old.unlink()
