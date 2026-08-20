"""
ALLTHINGS140 Hub — Project Registry & Workspace Manager
Scans, models, and tracks project workspaces and git repositories.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import CANONICAL_PROJECTS_ROOT, PROJECT_ROOT


@dataclass
class ProjectWorkspace:
    id: str
    name: str
    path: str
    type: str
    is_git: bool = True
    current_branch: str = "main"
    git_head: str = ""
    git_head_message: str = ""
    is_dirty: bool = False
    dirty_files: List[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    recent_commits: List[Dict[str, str]] = field(default_factory=list)
    description: str = ""
    apps_count: int = 0


class ProjectRegistry:
    """Discovers and manages project workspaces."""

    def __init__(self, canonical_root: Optional[Path] = None):
        self.canonical_root = canonical_root or CANONICAL_PROJECTS_ROOT
        self._projects: Dict[str, ProjectWorkspace] = {}
        self.active_project_id: str = "AllThings140Radio"
        self.reload()

    def reload(self) -> None:
        """Scan canonical projects from projects.json or directory listing."""
        projects_map: Dict[str, ProjectWorkspace] = {}

        # 1. Primary ALLTHINGS140 Radio workspace
        primary_path = str(PROJECT_ROOT)
        primary_ws = ProjectWorkspace(
            id="AllThings140Radio",
            name="ALLTHINGS140 Radio",
            path=primary_path,
            type="24/7 Heavy Dubstep Radio & Show-Control Ecosystem",
            is_git=True,
            description="Authoritative repository containing broadcast server, DJ app, visuals workstation, web frontend, and infrastructure.",
            apps_count=16
        )
        self._enrich_git_state(primary_ws)
        projects_map[primary_ws.id] = primary_ws

        # 2. Additional projects from projects.json
        projects_json_path = self.canonical_root / "projects.json"
        if projects_json_path.exists():
            try:
                with open(projects_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("projects", []):
                    p_name = item.get("name", "")
                    p_path = item.get("path", "")
                    if not p_name or p_name == "AllThings140Radio":
                        continue
                    ws = ProjectWorkspace(
                        id=p_name,
                        name=p_name,
                        path=p_path,
                        type=item.get("type", "project"),
                        is_git=item.get("git", False),
                        description=f"Workspace: {p_name} ({item.get('type', 'project')})"
                    )
                    self._enrich_git_state(ws)
                    projects_map[ws.id] = ws
            except Exception:
                pass

        self._projects = projects_map

    def get_active(self) -> ProjectWorkspace:
        return self._projects.get(self.active_project_id, self._projects.get("AllThings140Radio", list(self._projects.values())[0]))

    def set_active(self, project_id: str) -> Optional[ProjectWorkspace]:
        if project_id in self._projects:
            self.active_project_id = project_id
            return self._projects[project_id]
        return None

    def get(self, project_id: str) -> Optional[ProjectWorkspace]:
        return self._projects.get(project_id)

    def all(self) -> List[ProjectWorkspace]:
        return list(self._projects.values())

    def _enrich_git_state(self, ws: ProjectWorkspace) -> None:
        """Inspect live git branch, status, and recent commits."""
        p_path = Path(ws.path)
        if not p_path.exists() or not (p_path / ".git").exists():
            ws.is_git = False
            return

        try:
            # Branch
            r_branch = subprocess.run(
                ["git", "-C", str(p_path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=3
            )
            if r_branch.returncode == 0:
                ws.current_branch = r_branch.stdout.strip()

            # HEAD SHA & Message
            r_head = subprocess.run(
                ["git", "-C", str(p_path), "log", "-1", "--format=%h %s"],
                capture_output=True, text=True, timeout=3
            )
            if r_head.returncode == 0 and r_head.stdout.strip():
                parts = r_head.stdout.strip().split(" ", 1)
                ws.git_head = parts[0]
                ws.git_head_message = parts[1] if len(parts) > 1 else ""

            # Dirty files
            r_status = subprocess.run(
                ["git", "-C", str(p_path), "status", "--porcelain"],
                capture_output=True, text=True, timeout=3
            )
            if r_status.returncode == 0:
                lines = [l.strip() for l in r_status.stdout.strip().split("\n") if l.strip()]
                ws.is_dirty = len(lines) > 0
                ws.dirty_files = lines[:30]

            # Recent commits (last 10)
            r_log = subprocess.run(
                ["git", "-C", str(p_path), "log", "-10", "--format=%h|%an|%ar|%s"],
                capture_output=True, text=True, timeout=3
            )
            if r_log.returncode == 0 and r_log.stdout.strip():
                commits = []
                for line in r_log.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    pieces = line.split("|", 3)
                    if len(pieces) == 4:
                        commits.append({
                            "hash": pieces[0],
                            "author": pieces[1],
                            "date": pieces[2],
                            "message": pieces[3]
                        })
                ws.recent_commits = commits

            # Ahead/Behind
            r_ab = subprocess.run(
                ["git", "-C", str(p_path), "rev-list", "--left-right", "--count", f"{ws.current_branch}...origin/{ws.current_branch}"],
                capture_output=True, text=True, timeout=3
            )
            if r_ab.returncode == 0 and r_ab.stdout.strip():
                counts = r_ab.stdout.strip().split()
                if len(counts) == 2:
                    ws.ahead = int(counts[0])
                    ws.behind = int(counts[1])
        except Exception:
            pass
