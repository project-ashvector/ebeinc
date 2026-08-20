"""
ALLTHINGS140 Hub — Report Library Service
Discovers, indexes, categorizes, and serves markdown engineering reports.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import DOCS_REPORTS_DIR, PROJECT_ROOT


@dataclass
class EngineeringReport:
    id: str
    title: str
    path: str
    category: str  # audit, repair, rollout, visuals, roadmap, context, general
    dateModified: str
    timestamp: float
    summary: str
    targetApp: str
    isCurrent: bool
    sizeBytes: int


class ReportService:
    """Discovers and manages engineering reports across the project and documents folders."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or PROJECT_ROOT
        self._reports: List[EngineeringReport] = []
        self.reload()

    def reload(self) -> None:
        """Scan directories for all relevant engineering reports."""
        scan_dirs = [
            DOCS_REPORTS_DIR,
            self.project_root / "docs",
            self.project_root / "ALLTHINGS140_PROJECT_CONTEXT",
            self.project_root,
            Path.home()
        ]

        reports: List[EngineeringReport] = []
        seen_paths = set()

        for d in scan_dirs:
            if not d.exists():
                continue
            for item in d.iterdir():
                if not item.is_file():
                    continue
                if not (item.suffix in (".md", ".txt") and ("ALLTHINGS140" in item.name.upper() or "REPORT" in item.name.upper() or item.parent.name == "ALLTHINGS140_PROJECT_CONTEXT")):
                    continue
                if str(item) in seen_paths:
                    continue
                seen_paths.add(str(item))

                rep = self._parse_report(item)
                if rep:
                    reports.append(rep)

        # Sort by timestamp descending
        self._reports = sorted(reports, key=lambda r: r.timestamp, reverse=True)

    def all(self) -> List[EngineeringReport]:
        return self._reports

    def get(self, report_id: str) -> Optional[EngineeringReport]:
        for r in self._reports:
            if r.id == report_id:
                return r
        return None

    def by_category(self, category: str) -> List[EngineeringReport]:
        if category == "all":
            return self.all()
        return [r for r in self._reports if r.category == category]

    def search(self, query: str, category: Optional[str] = None, only_current: bool = False) -> List[EngineeringReport]:
        q = query.lower().strip()
        results = []
        for r in self._reports:
            if category and category != "all" and r.category != category:
                continue
            if only_current and not r.isCurrent:
                continue
            if not q or q in r.title.lower() or q in r.summary.lower() or q in r.path.lower():
                results.append(r)
        return results

    def get_content(self, report_id: str) -> str:
        rep = self.get(report_id)
        if not rep or not os.path.exists(rep.path):
            return "Report file not found."
        try:
            with open(rep.path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"Error reading report: {e}"

    def _parse_report(self, file_path: Path) -> Optional[EngineeringReport]:
        try:
            stat = file_path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))

            # Read first few lines for title and summary
            title = file_path.stem.replace("-", " ").replace("_", " ").title()
            summary = ""
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    first_lines = [f.readline() for _ in range(12)]
                for line in first_lines:
                    line_s = line.strip()
                    if line_s.startswith("# "):
                        title = line_s[2:].strip()
                        break
                    elif line_s.startswith("ALLTHINGS140"):
                        title = line_s
                        break
                for line in first_lines:
                    line_s = line.strip()
                    if line_s and not line_s.startswith("#") and not line_s.startswith("==") and not line_s.startswith("--"):
                        summary = line_s[:120]
                        break
            except Exception:
                pass

            # Infer category
            name_upper = file_path.name.upper()
            if "AUDIT" in name_upper:
                category = "audit"
            elif "REPAIR" in name_upper:
                category = "repair"
            elif "ROLLOUT" in name_upper or "DEPLOY" in name_upper:
                category = "rollout"
            elif "VISUAL" in name_upper or "STAGE" in name_upper:
                category = "visuals"
            elif "ROADMAP" in name_upper:
                category = "roadmap"
            elif file_path.parent.name == "ALLTHINGS140_PROJECT_CONTEXT":
                category = "context"
            else:
                category = "general"

            # Infer target app
            target_app = "all"
            if "VISUAL" in name_upper or "STAGE" in name_upper:
                target_app = "visuals-workstation"
            elif "SERVER" in name_upper or "RADIO" in name_upper:
                target_app = "radio-server"
            elif "DJ" in name_upper:
                target_app = "dj-app"

            # Check if current (modified in last 30 days)
            is_current = (time.time() - mtime) < (30 * 86400)

            report_id = file_path.stem.lower().replace(" ", "-")
            return EngineeringReport(
                id=report_id,
                title=title,
                path=str(file_path),
                category=category,
                dateModified=date_str,
                timestamp=mtime,
                summary=summary or "Engineering documentation & report.",
                targetApp=target_app,
                isCurrent=is_current,
                sizeBytes=size
            )
        except Exception:
            return None
