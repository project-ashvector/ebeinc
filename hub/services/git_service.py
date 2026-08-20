"""
ALLTHINGS140 Hub — Git Service
Provides inspection, branch state, dirty working-tree tracking, and commit history.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GitFileChange:
    status: str  # M, A, D, ??, R
    path: str
    is_staged: bool


@dataclass
class GitCommit:
    hash: str
    author: str
    relative_time: str
    message: str


@dataclass
class GitSummary:
    path: str
    is_git: bool
    branch: str
    head_hash: str
    head_message: str
    is_dirty: bool
    ahead: int
    behind: int
    modified_count: int
    untracked_count: int
    changes: List[GitFileChange] = field(default_factory=list)
    recent_commits: List[GitCommit] = field(default_factory=list)


class GitService:
    """Safely inspects git repository state without destructive commands."""

    @staticmethod
    def get_summary(repo_path: Path | str) -> GitSummary:
        p = Path(repo_path)
        if not p.exists() or not (p / ".git").exists():
            return GitSummary(
                path=str(p),
                is_git=False,
                branch="",
                head_hash="",
                head_message="",
                is_dirty=False,
                ahead=0,
                behind=0,
                modified_count=0,
                untracked_count=0
            )

        branch = GitService._run_git(p, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
        head_line = GitService._run_git(p, ["log", "-1", "--format=%h %s"]) or ""
        head_hash = head_line.split(" ", 1)[0] if head_line else ""
        head_msg = head_line.split(" ", 1)[1] if " " in head_line else ""

        # Status porcelain
        raw_status = GitService._run_git(p, ["status", "--porcelain"]) or ""
        changes: List[GitFileChange] = []
        modified = 0
        untracked = 0

        for line in raw_status.split("\n"):
            if not line.strip():
                continue
            code = line[:2]
            fpath = line[3:].strip()
            if code == "??":
                untracked += 1
                changes.append(GitFileChange(status="??", path=fpath, is_staged=False))
            else:
                modified += 1
                is_staged = code[0] not in (" ", "?")
                status_char = code[0] if is_staged else code[1]
                changes.append(GitFileChange(status=status_char, path=fpath, is_staged=is_staged))

        # Commits log
        raw_log = GitService._run_git(p, ["log", "-15", "--format=%h|%an|%ar|%s"]) or ""
        commits: List[GitCommit] = []
        for line in raw_log.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append(GitCommit(
                    hash=parts[0],
                    author=parts[1],
                    relative_time=parts[2],
                    message=parts[3]
                ))

        # Ahead/behind
        ahead = 0
        behind = 0
        if branch != "unknown":
            ab_str = GitService._run_git(p, ["rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"]) or ""
            ab_parts = ab_str.strip().split()
            if len(ab_parts) == 2:
                ahead = int(ab_parts[0]) if ab_parts[0].isdigit() else 0
                behind = int(ab_parts[1]) if ab_parts[1].isdigit() else 0

        return GitSummary(
            path=str(p),
            is_git=True,
            branch=branch,
            head_hash=head_hash,
            head_message=head_msg,
            is_dirty=len(changes) > 0,
            ahead=ahead,
            behind=behind,
            modified_count=modified,
            untracked_count=untracked,
            changes=changes,
            recent_commits=commits
        )

    @staticmethod
    def get_diff(repo_path: Path | str, file_path: Optional[str] = None) -> str:
        p = Path(repo_path)
        cmd = ["diff"]
        if file_path:
            cmd.extend(["--", file_path])
        return GitService._run_git(p, cmd) or ""

    @staticmethod
    def _run_git(cwd: Path, args: List[str]) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                return res.stdout.strip()
            return None
        except Exception:
            return None
