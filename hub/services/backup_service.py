"""
ALLTHINGS140 Hub — Backup & Disaster Recovery Service
Discovers local and remote backups, creates timestamped component snapshots, and tracks retention.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import PROJECT_ROOT


@dataclass
class BackupSnapshot:
    id: str
    name: str
    path: str
    backupType: str  # db, component, full-workspace, offhost, emergency-mirror
    component: str
    timestamp: float
    dateFormatted: str
    sizeBytes: int
    sizeFormatted: str
    isRestorable: bool = True
    integrityStatus: str = "unverified"


class BackupService:
    """Discovers, inventories, and executes station backups."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or PROJECT_ROOT
        self._backups: List[BackupSnapshot] = []
        self.reload()

    def reload(self) -> None:
        """Scan known backup directories for archives and snapshot folders."""
        scan_roots = [
            self.project_root / "backups",
            Path("/home/ebmarah/Music/ALLTHINGS140/ALLTHINGS140_BACKUPS"),
            Path("/home/ebmarah/Backups/ALLTHINGS140"),
            self.project_root
        ]

        found: List[BackupSnapshot] = []
        seen_paths = set()

        for root_dir in scan_roots:
            if not root_dir.exists():
                continue
            try:
                for entry in root_dir.iterdir():
                    path_str = str(entry)
                    if path_str in seen_paths:
                        continue

                    # Check if backup archive or backup directory
                    name_lower = entry.name.lower()
                    is_backup = (
                        "backup" in name_lower or
                        "snapshot" in name_lower or
                        entry.parent.name in ("backups", "ALLTHINGS140_BACKUPS")
                    )
                    if not is_backup:
                        continue

                    seen_paths.add(path_str)
                    snap = self._inspect_backup_path(entry)
                    if snap:
                        found.append(snap)
            except Exception:
                pass

        self._backups = sorted(found, key=lambda b: b.timestamp, reverse=True)

    def all(self) -> List[BackupSnapshot]:
        return self._backups

    def get(self, backup_id: str) -> Optional[BackupSnapshot]:
        for b in self._backups:
            if b.id == backup_id:
                return b
        return None

    def create_component_backup(self, component_name: str, source_paths: List[str], notes: str = "") -> BackupSnapshot:
        """Create a timestamped compressed tarball backup of specific files/directories."""
        backups_dir = self.project_root / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        now = time.time()
        timestamp_str = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        archive_name = f"backup-{component_name}-{timestamp_str}.tar.gz"
        archive_path = backups_dir / archive_name

        resolved = []
        missing = []
        for sp in source_paths:
            p = Path(sp) if Path(sp).is_absolute() else self.project_root / sp
            if not p.exists():
                missing.append(str(p))
            else:
                resolved.append((p, p.name if Path(sp).is_absolute() else sp))
        if missing:
            raise FileNotFoundError("Backup aborted; required sources missing: " + ", ".join(missing))
        with tarfile.open(archive_path, "w:gz") as tar:
            for p, arcname in resolved:
                tar.add(str(p), arcname=arcname)
        # Read the archive fully enough to validate headers before claiming success.
        with tarfile.open(archive_path, "r:gz") as verify:
            verify.getmembers()

        self.reload()
        return self.get(archive_path.stem) or self._inspect_backup_path(archive_path)

    def _inspect_backup_path(self, entry: Path) -> Optional[BackupSnapshot]:
        try:
            stat = entry.stat()
            mtime = stat.st_mtime
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))

            if entry.is_file():
                size = stat.st_size
            else:
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())

            size_fmt = self._format_size(size)

            # Determine component and type
            name = entry.name
            btype = "component"
            component = "general"

            if "station" in name.lower() or "db" in name.lower():
                btype = "db"
                component = "radio-server"
            elif "visual" in name.lower() or "stage" in name.lower():
                btype = "component"
                component = "visuals-workstation"
            elif "control" in name.lower() or "dj" in name.lower():
                btype = "component"
                component = "dj-app"
            elif "mirror" in name.lower() or "music" in name.lower():
                btype = "emergency-mirror"
                component = "radio-server"

            integrity = "unverified"
            restorable = entry.exists()
            if entry.is_file() and (entry.name.endswith(".tar.gz") or entry.suffix in {".tgz", ".tar"}):
                try:
                    with tarfile.open(entry, "r:*") as tf:
                        tf.getmembers()
                    integrity = "verified"
                except (tarfile.TarError, OSError):
                    integrity = "failed"
                    restorable = False
            elif entry.is_dir():
                integrity = "directory-present"

            snap_id = entry.stem.lower().replace(" ", "-")
            return BackupSnapshot(
                id=snap_id,
                name=entry.name,
                path=str(entry),
                backupType=btype,
                component=component,
                timestamp=mtime,
                dateFormatted=date_str,
                sizeBytes=size,
                sizeFormatted=size_fmt,
                isRestorable=restorable,
                integrityStatus=integrity
            )
        except Exception:
            return None

    def _format_size(self, bytes_num: int) -> str:
        if bytes_num < 1024:
            return f"{bytes_num} B"
        elif bytes_num < 1024 * 1024:
            return f"{bytes_num / 1024:.1f} KB"
        elif bytes_num < 1024 * 1024 * 1024:
            return f"{bytes_num / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_num / (1024 * 1024 * 1024):.2f} GB"
