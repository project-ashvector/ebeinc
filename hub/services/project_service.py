"""
ALLTHINGS140 Hub — Project Service
Discovers workspace repositories, tracks branch state, and checks working trees.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from hub.services.git_service import GitService, GitSummary

PROJECTS_DIR = Path("/home/ebmarah/Projects")


@dataclass
class ProjectInfo:
    id: str
    displayName: str
    path: str
    relativePath: str
    gitBranch: str
    gitHead: str
    lastCommitMessage: str
    isDirty: bool


class ProjectService:
    """Discovers git project workspaces."""

    def __init__(self, base_dir: Path = PROJECTS_DIR):
        self.base_dir = base_dir

    def discover_projects(self) -> List[ProjectInfo]:
        results: List[ProjectInfo] = []
        if not self.base_dir.exists():
            return results

        # Main repo
        main_repo = self.base_dir / "AllThings140Radio"
        if main_repo.exists():
            summary = GitService.get_summary(main_repo)
            results.append(ProjectInfo(
                id="main-repo",
                displayName="AllThings140Radio (Root Repo)",
                path=str(main_repo),
                relativePath=".",
                gitBranch=summary.branch,
                gitHead=summary.head_hash,
                lastCommitMessage=summary.head_message,
                isDirty=summary.is_dirty
            ))

        # Scan other project directories
        for item in sorted(self.base_dir.iterdir()):
            if item.is_dir() and item != main_repo and (item / ".git").exists():
                summary = GitService.get_summary(item)
                results.append(ProjectInfo(
                    id=item.name.lower(),
                    displayName=item.name,
                    path=str(item),
                    relativePath=item.name,
                    gitBranch=summary.branch,
                    gitHead=summary.head_hash,
                    lastCommitMessage=summary.head_message,
                    isDirty=summary.is_dirty
                ))

        return results
