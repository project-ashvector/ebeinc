"""ALLTHINGS140 Hub — update/version safety service.

v1.2.1 deliberately does not pretend a remote deployment happened. The Hub
runs a real local preflight (state, backup, tests, optional local build) and
then directs production changes to the target-specific deployment surface.
"""
from __future__ import annotations

import os
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from hub.config import PROJECT_ROOT, get_config
from hub.registry.app_registry import AppEntry


@dataclass
class VersionComparison:
    appId: str
    appName: str
    localVersion: str
    deployedVersion: str
    projectLatestVersion: str
    hasUpdate: bool
    updateType: str
    details: str


@dataclass
class SafeWorkflowStepResult:
    stepNumber: int
    stepName: str
    isSuccess: bool
    detail: str
    durationMs: float
    error: str = ""


class UpdateService:
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            try:
                project_root = Path(get_config().current_project_path).expanduser().resolve()
            except Exception:
                project_root = PROJECT_ROOT
        self.project_root = project_root

    def get_version_matrix(self, apps: List[AppEntry]) -> List[VersionComparison]:
        """Report only values we can prove locally; deployed versions remain UNKNOWN."""
        project_version = "UNKNOWN"
        version_txt = self.project_root / "VERSION.txt"
        try:
            if version_txt.is_file():
                project_version = version_txt.read_text(encoding="utf-8").strip() or "UNKNOWN"
        except OSError:
            pass

        matrix: List[VersionComparison] = []
        for app in apps:
            local = app.version or "UNKNOWN"
            deployed = "UNKNOWN"
            if app.environment in {"workstation", "local"}:
                details = "Local source discovered. Installed/runtime version is not yet independently verified."
            else:
                details = "Remote/deployed version requires target-specific verification; Hub will not guess."
            if app.dirty:
                details = "UNCOMMITTED EDITS present. Preserve/commit/review before any deployment. " + details
            matrix.append(VersionComparison(
                appId=app.id,
                appName=app.displayName,
                localVersion=local,
                deployedVersion=deployed,
                projectLatestVersion=project_version,
                hasUpdate=False,
                updateType="UNVERIFIED" if deployed == "UNKNOWN" else "SYNCED",
                details=details,
            ))
        return matrix

    def execute_safe_workflow(
        self,
        app: AppEntry,
        progress_callback: Optional[Callable[[SafeWorkflowStepResult], None]] = None,
    ) -> List[SafeWorkflowStepResult]:
        """Run a real *preflight*. It never deploys/restarts production in v1.2.1."""
        results: List[SafeWorkflowStepResult] = []

        def step(num: int, name: str, fn: Callable[[], str]) -> bool:
            start = time.time()
            try:
                detail = fn()
                res = SafeWorkflowStepResult(num, name, True, detail, round((time.time()-start)*1000, 1))
            except Exception as exc:
                res = SafeWorkflowStepResult(num, name, False, "Step failed", round((time.time()-start)*1000, 1), str(exc))
            results.append(res)
            if progress_callback:
                progress_callback(res)
            return res.isSuccess

        work_dir = Path(app.workingDirectory).expanduser().resolve()

        if not step(1, "Detect Current State", lambda: self._state_detail(app, work_dir)):
            return results
        if not step(2, "Identify Deployment Target", lambda: f"{app.environment.upper()} — {app.deploymentTarget}. No production action is performed by this preflight."):
            return results

        backup_path: Optional[Path] = None
        def create_backup() -> str:
            nonlocal backup_path
            if not work_dir.exists():
                raise FileNotFoundError(work_dir)
            out = self.project_root / "backups" / "hub-preflight"
            out.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup_path = out / f"{app.id}-{stamp}.tar.gz"
            excluded = {".git", "node_modules", "target", "build", "build-deb", "dist", ".venv", "__pycache__"}
            def filt(info: tarfile.TarInfo):
                parts = Path(info.name).parts
                if any(part in excluded for part in parts):
                    return None
                return info
            with tarfile.open(backup_path, "w:gz") as tf:
                tf.add(work_dir, arcname=work_dir.name, filter=filt)
            with tarfile.open(backup_path, "r:gz") as tf:
                members = tf.getmembers()
                if not members:
                    raise RuntimeError("Backup archive is empty")
            return f"Verified local rollback snapshot: {backup_path} ({len(members)} entries)"
        if not step(3, "Create Verified Local Backup", create_backup):
            return results

        def run_test() -> str:
            if not app.testCommand:
                return "SKIPPED — no automated test command registered."
            return self._run_trusted_command(app.testCommand, work_dir, timeout=300, label="test")
        if not step(4, "Run Registered Tests", run_test):
            return results

        def run_build() -> str:
            if not app.buildCommand:
                return "SKIPPED — no local build command registered."
            dangerous_tokens = ("wrangler", "dpkg -i", "systemctl", "ssh ", "sudo ", "rm -rf")
            low = app.buildCommand.lower()
            if any(tok in low for tok in dangerous_tokens):
                return f"SKIPPED — build command contains deployment/privileged operation: {app.buildCommand}"
            return self._run_trusted_command(app.buildCommand, work_dir, timeout=600, label="build")
        if not step(5, "Build Local Artifact", run_build):
            return results

        step(6, "Deployment Gate", lambda: "NOT PERFORMED — use Cloudflare Deployment for web or the app/server-specific documented updater. v1.2.1 does not simulate deployment.")
        step(7, "Service Restart Gate", lambda: "NOT PERFORMED — remote restarts are disabled until a verified transactional management API exists.")
        step(8, "Live Health Gate", lambda: "NOT CLAIMED — run Station Health after the real target-specific deployment. Preflight cannot truthfully verify a change that was not deployed.")
        step(9, "Rollback Readiness", lambda: f"Verified local snapshot available: {backup_path}" if backup_path and backup_path.exists() else "No backup available")
        step(10, "Handoff", lambda: "Preflight complete. No production mutation occurred; record any later deployment in Engineering Handoffs.")
        return results

    def _state_detail(self, app: AppEntry, work_dir: Path) -> str:
        if not work_dir.exists():
            raise FileNotFoundError(f"Working directory missing: {work_dir}")
        state = f"{app.displayName}; source version {app.version or 'UNKNOWN'}; branch {app.gitBranch or 'UNKNOWN'}; commit {app.gitHead or 'UNKNOWN'}"
        if app.dirty:
            state += "; WARNING: uncommitted edits detected"
        return state

    @staticmethod
    def _run_trusted_command(command: str, cwd: Path, timeout: int, label: str) -> str:
        # Commands come from the internal static app registry, not user text.
        res = subprocess.run(command, cwd=str(cwd), shell=True, executable="/bin/bash", capture_output=True, text=True, timeout=timeout)
        output = (res.stdout or res.stderr or "").strip()
        tail = output[-1200:] if output else "no output"
        if res.returncode != 0:
            raise RuntimeError(f"{label} command failed (exit {res.returncode}): {tail}")
        return f"Executed: {command}\n{tail}"
