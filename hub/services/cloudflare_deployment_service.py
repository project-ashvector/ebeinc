"""ALLTHINGS140 Hub — guarded Cloudflare Pages deployment service.

Preview and production deploy the exact same immutable staged artifact.  This
module never invents a deployment URL, swallows Wrangler failures, or claims a
rollback exists without a retained previous-production artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Optional

from hub.config import CONFIG_DIR, PROJECT_ROOT, get_config
from hub.util.atomic_io import atomic_write_json

DEPLOYMENTS_FILE = CONFIG_DIR / "site-deployments.json"


@dataclass
class SiteDeploymentRecord:
    id: str
    projectName: str
    targetEnvironment: str
    commitHash: str
    branchName: str
    previewUrl: str
    productionUrl: str
    timestamp: float
    formattedDate: str
    smokeTestPassed: bool
    smokeTestDetails: str
    promotedToProduction: bool = False
    rollbackAvailable: bool = False
    backupArchivePath: str = ""
    artifactPath: str = ""
    rollbackArtifactPath: str = ""


@dataclass
class PreviewSmokeTestResult:
    isSuccess: bool
    httpStatus: int
    responseTimeMs: float
    audioStreamCheck: bool
    siteContentCheck: bool
    details: str
    error: str = ""


class CloudflareDeploymentService:
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            try:
                project_root = Path(get_config().current_project_path).expanduser().resolve()
            except Exception:
                project_root = PROJECT_ROOT
        self.project_root = project_root
        self.records: List[SiteDeploymentRecord] = []
        self.load_error = ""
        self.reload()

    def reload(self) -> None:
        self.records = []
        self.load_error = ""
        if not DEPLOYMENTS_FILE.exists():
            return
        try:
            data = json.loads(DEPLOYMENTS_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("deployment history must be a list")
            for item in data:
                if not isinstance(item, dict):
                    continue
                # Remove the v1.2.0 fabricated onboarding deployment record.
                if item.get("id") == "deploy-initial-prod":
                    continue
                allowed = SiteDeploymentRecord.__dataclass_fields__.keys()
                filtered = {k: v for k, v in item.items() if k in allowed}
                self.records.append(SiteDeploymentRecord(**filtered))
        except Exception as exc:
            self.load_error = str(exc)
            try:
                damaged = DEPLOYMENTS_FILE.with_suffix(DEPLOYMENTS_FILE.suffix + f".corrupt-{int(time.time())}")
                DEPLOYMENTS_FILE.replace(damaged)
            except Exception:
                pass
            self.records = []

    def save(self) -> None:
        atomic_write_json(DEPLOYMENTS_FILE, [asdict(x) for x in self.records])

    def all(self) -> List[SiteDeploymentRecord]:
        return sorted(self.records, key=lambda r: r.timestamp, reverse=True)

    def get_latest_production(self, project_name: str = "ebeinc", exclude_id: str = "") -> Optional[SiteDeploymentRecord]:
        for rec in self.all():
            if rec.id == exclude_id:
                continue
            if rec.projectName == project_name and rec.promotedToProduction and rec.targetEnvironment == "production" and rec.smokeTestPassed:
                return rec
        return None

    def create_preview_deployment(
        self,
        project_name: str = "ebeinc",
        directory_rel: str = "radio",
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> SiteDeploymentRecord:
        now = time.time()
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        deploy_id = f"deploy-{int(now)}"
        branch = f"hub-preview-{stamp}"
        site_dir = (self.project_root / directory_rel).resolve()
        if not (site_dir / "index.html").is_file():
            raise FileNotFoundError(f"index.html not found in {site_dir}")

        self._progress(progress_cb, "1/6: Creating verified local source snapshot…")
        backup_dir = self.project_root / "backups" / "site-source-snapshots"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{project_name}-{stamp}.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tf:
            tf.add(site_dir, arcname=directory_rel)
        with tarfile.open(backup_path, "r:gz") as tf:
            if not tf.getmembers():
                raise RuntimeError("Backup archive verification failed: empty archive")

        self._progress(progress_cb, "2/6: Staging immutable deployment artifact…")
        artifact_root = self.project_root / "backups" / "deploy-artifacts" / deploy_id
        artifact_dir = artifact_root / directory_rel
        if artifact_root.exists():
            shutil.rmtree(artifact_root)
        artifact_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(site_dir, artifact_dir, symlinks=True)
        artifact_hash = self._hash_tree(artifact_dir)
        (artifact_root / "ARTIFACT-SHA256.txt").write_text(artifact_hash + "\n", encoding="utf-8")

        self._progress(progress_cb, "3/6: Deploying preview artifact to Cloudflare Pages…")
        wrangler = self._wrangler_prefix()
        cmd = wrangler + ["pages", "deploy", str(artifact_dir), f"--project-name={project_name}", f"--branch={branch}"]
        res = subprocess.run(cmd, cwd=str(self.project_root), capture_output=True, text=True, timeout=180)
        if res.returncode != 0:
            raise RuntimeError(f"Wrangler preview deploy failed (exit {res.returncode}): {(res.stderr or res.stdout)[-3000:]}")
        preview_url = self._extract_pages_url((res.stdout or "") + "\n" + (res.stderr or ""))
        if not preview_url:
            raise RuntimeError("Wrangler reported success but no pages.dev preview URL could be verified from its output")

        self._progress(progress_cb, f"4/6: Smoke-testing actual preview URL {preview_url}…")
        test = self.run_smoke_test(preview_url, require_player=(project_name == "ebeinc"))

        previous = self.get_latest_production(project_name)
        rollback_artifact = previous.artifactPath if previous and previous.artifactPath and Path(previous.artifactPath).is_dir() else ""
        record = SiteDeploymentRecord(
            id=deploy_id,
            projectName=project_name,
            targetEnvironment="preview",
            commitHash=artifact_hash,
            branchName=branch,
            previewUrl=preview_url,
            productionUrl="https://allthings140radio.online" if project_name == "ebeinc" else "https://allthings140-visuals-green.pages.dev",
            timestamp=now,
            formattedDate=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
            smokeTestPassed=test.isSuccess,
            smokeTestDetails=test.details,
            promotedToProduction=False,
            rollbackAvailable=bool(rollback_artifact),
            backupArchivePath=str(backup_path),
            artifactPath=str(artifact_dir),
            rollbackArtifactPath=rollback_artifact,
        )
        self.records.insert(0, record)
        self.save()
        self._progress(progress_cb, f"5/6: Preview smoke test: {'PASS' if test.isSuccess else 'FAIL'}")
        self._progress(progress_cb, "6/6: Preview recorded. Production remains unchanged.")
        return record

    def promote_to_production(self, deployment_id: str, progress_cb: Optional[Callable[[str], None]] = None) -> bool:
        rec = self._record(deployment_id)
        if rec.targetEnvironment != "preview" or not rec.previewUrl:
            raise RuntimeError("Only a recorded preview artifact can be promoted")
        artifact = Path(rec.artifactPath)
        if not artifact.is_dir():
            raise FileNotFoundError("Immutable preview artifact is missing; create a new preview")
        if self._hash_tree(artifact) != rec.commitHash:
            raise RuntimeError("Preview artifact hash changed after testing; refusing production promotion")

        self._progress(progress_cb, "1/4: Re-running smoke test against preview…")
        preview_test = self.run_smoke_test(rec.previewUrl, require_player=(rec.projectName == "ebeinc"))
        if not preview_test.isSuccess:
            rec.smokeTestPassed = False
            rec.smokeTestDetails = preview_test.details
            self.save()
            raise RuntimeError(f"Preview smoke test failed: {preview_test.details}")

        self._progress(progress_cb, "2/4: Deploying the exact tested artifact to production…")
        wrangler = self._wrangler_prefix()
        cmd = wrangler + ["pages", "deploy", str(artifact), f"--project-name={rec.projectName}", "--branch=main"]
        res = subprocess.run(cmd, cwd=str(self.project_root), capture_output=True, text=True, timeout=180)
        if res.returncode != 0:
            raise RuntimeError(f"Wrangler production deploy failed (exit {res.returncode}): {(res.stderr or res.stdout)[-3000:]}")

        rec.promotedToProduction = True  # deployment occurred, even if validation below fails
        rec.targetEnvironment = "production-validating"
        self.save()

        self._progress(progress_cb, "3/4: Running production smoke test…")
        prod = self.run_smoke_test(rec.productionUrl, require_player=(rec.projectName == "ebeinc"))
        rec.smokeTestPassed = prod.isSuccess
        rec.smokeTestDetails = f"Production: {prod.details}"
        rec.targetEnvironment = "production" if prod.isSuccess else "production-failed"
        self.save()
        if not prod.isSuccess:
            self._progress(progress_cb, "4/4: PRODUCTION DEPLOYED BUT VALIDATION FAILED — use rollback if available.")
            raise RuntimeError(f"Production changed but smoke test failed: {prod.details}")
        self._progress(progress_cb, "4/4: Production deployment verified.")
        return True

    def rollback_to_record(self, deployment_id: str, progress_cb: Optional[Callable[[str], None]] = None) -> bool:
        rec = self._record(deployment_id)
        rollback = Path(rec.rollbackArtifactPath) if rec.rollbackArtifactPath else None
        if not rec.rollbackAvailable or rollback is None or not rollback.is_dir():
            raise FileNotFoundError("No verified previous-production artifact is retained for this deployment")
        self._progress(progress_cb, f"Deploying retained rollback artifact for {rec.projectName}…")
        wrangler = self._wrangler_prefix()
        cmd = wrangler + ["pages", "deploy", str(rollback), f"--project-name={rec.projectName}", "--branch=main"]
        res = subprocess.run(cmd, cwd=str(self.project_root), capture_output=True, text=True, timeout=180)
        if res.returncode != 0:
            raise RuntimeError(f"Rollback deploy failed: {(res.stderr or res.stdout)[-3000:]}")
        test = self.run_smoke_test(rec.productionUrl, require_player=(rec.projectName == "ebeinc"))
        if not test.isSuccess:
            raise RuntimeError(f"Rollback artifact deployed but production validation failed: {test.details}")
        self._progress(progress_cb, "Rollback deployment verified live.")
        return True

    def run_smoke_test(self, url: str, require_player: bool = False) -> PreviewSmokeTestResult:
        start = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ALLTHINGS140-Hub-SmokeTest/1.2.1", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                status = resp.status
                content = resp.read(2 * 1024 * 1024).decode("utf-8", errors="ignore")
            dur = (time.time() - start) * 1000.0
            lower = content.lower()
            branding = "allthings140" in lower
            player_marker = any(marker in lower for marker in ("<audio", "live.mp3", "stream.ebeinc.online", "listen live"))
            obvious_error = "404 not found" in lower or "application error" in lower
            ok = status == 200 and branding and not obvious_error and (player_marker if require_player else True)
            details = f"HTTP {status} in {dur:.0f}ms | branding={'yes' if branding else 'no'} | player-marker={'yes' if player_marker else 'no'} | {len(content)} bytes"
            return PreviewSmokeTestResult(ok, status, round(dur, 1), player_marker, branding, details)
        except Exception as exc:
            dur = (time.time() - start) * 1000.0
            return PreviewSmokeTestResult(False, 0, round(dur, 1), False, False, f"Connection failed: {exc}", str(exc))

    def _wrangler_prefix(self) -> List[str]:
        local = self.project_root / "node_modules" / ".bin" / "wrangler"
        if local.is_file() and os.access(local, os.X_OK):
            return [str(local)]
        global_bin = shutil.which("wrangler")
        if global_bin:
            return [global_bin]
        raise RuntimeError("Wrangler is not installed/pinned. Install Wrangler explicitly; Hub will not auto-download deployment tooling via npx --yes.")

    def _record(self, deployment_id: str) -> SiteDeploymentRecord:
        rec = next((r for r in self.records if r.id == deployment_id), None)
        if not rec:
            raise ValueError(f"Deployment record {deployment_id} not found")
        return rec

    @staticmethod
    def _extract_pages_url(text: str) -> str:
        matches = re.findall(r"https://[^\s\]\[()<>]+\.pages\.dev(?:/[^\s\]\[()<>]*)?", text)
        return matches[-1].rstrip(".,'") if matches else ""

    @staticmethod
    def _progress(cb: Optional[Callable[[str], None]], text: str) -> None:
        if cb:
            cb(text)

    @staticmethod
    def _hash_tree(root: Path) -> str:
        h = hashlib.sha256()
        for file in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = file.relative_to(root).as_posix().encode("utf-8")
            h.update(rel + b"\0")
            with open(file, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
        return h.hexdigest()
