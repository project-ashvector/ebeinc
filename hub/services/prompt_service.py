"""
ALLTHINGS140 Hub — Prompt Library Service
Manages reusable task prompts, presets, tags, and persistence.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import PROMPTS_FILE
from hub.util.atomic_io import atomic_write_json


@dataclass
class PromptTemplate:
    id: str
    title: str
    description: str
    targetApp: str  # app_id or "all"
    agentProvider: str  # "any", "antigravity", "codex", "opencode"
    promptText: str
    tags: List[str] = field(default_factory=list)
    createdAt: float = field(default_factory=time.time)
    updatedAt: float = field(default_factory=time.time)
    lastUsed: float = 0.0


class PromptService:
    """Manages CRUD and presets for engineering prompts."""

    def __init__(self):
        self._prompts: Dict[str, PromptTemplate] = {}
        self.reload()

    def reload(self) -> None:
        """Load prompts from disk or initialize with rich built-in presets."""
        if PROMPTS_FILE.exists():
            try:
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._prompts = {
                    item["id"]: PromptTemplate(**item)
                    for item in data
                    if "id" in item
                }
                return
            except Exception:
                try:
                    damaged = PROMPTS_FILE.with_suffix(PROMPTS_FILE.suffix + f".corrupt-{int(time.time())}")
                    PROMPTS_FILE.replace(damaged)
                except Exception:
                    pass

        # Populate built-in presets (templates, not operational history).
        self._prompts = {p.id: p for p in self._get_default_presets()}
        self.save()

    def save(self) -> None:
        PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(PROMPTS_FILE, [asdict(p) for p in self._prompts.values()])

    def all(self) -> List[PromptTemplate]:
        return sorted(self._prompts.values(), key=lambda p: p.title)

    def get(self, prompt_id: str) -> Optional[PromptTemplate]:
        return self._prompts.get(prompt_id)

    def search(self, query: str, tag: Optional[str] = None, app_id: Optional[str] = None) -> List[PromptTemplate]:
        q = query.lower().strip()
        results = []
        for p in self.all():
            if tag and tag not in p.tags:
                continue
            if app_id and p.targetApp not in ("all", app_id):
                continue
            if not q or q in p.title.lower() or q in p.description.lower() or any(q in t.lower() for t in p.tags):
                results.append(p)
        return results

    def create(self, title: str, description: str, prompt_text: str, target_app: str = "all", provider: str = "any", tags: Optional[List[str]] = None) -> PromptTemplate:
        prompt_id = f"prompt-{int(time.time())}-{title.lower().replace(' ', '-')[:20]}"
        p = PromptTemplate(
            id=prompt_id,
            title=title,
            description=description,
            targetApp=target_app,
            agentProvider=provider,
            promptText=prompt_text,
            tags=tags or ["custom"],
            createdAt=time.time(),
            updatedAt=time.time()
        )
        self._prompts[p.id] = p
        self.save()
        return p

    def update(self, prompt_id: str, title: str, description: str, prompt_text: str, target_app: str, provider: str, tags: List[str]) -> Optional[PromptTemplate]:
        p = self.get(prompt_id)
        if not p:
            return None
        p.title = title
        p.description = description
        p.promptText = prompt_text
        p.targetApp = target_app
        p.agentProvider = provider
        p.tags = tags
        p.updatedAt = time.time()
        self.save()
        return p

    def duplicate(self, prompt_id: str) -> Optional[PromptTemplate]:
        p = self.get(prompt_id)
        if not p:
            return None
        new_id = f"prompt-{int(time.time())}-copy"
        new_p = PromptTemplate(
            id=new_id,
            title=f"{p.title} (Copy)",
            description=p.description,
            targetApp=p.targetApp,
            agentProvider=p.agentProvider,
            promptText=p.promptText,
            tags=list(p.tags),
            createdAt=time.time(),
            updatedAt=time.time()
        )
        self._prompts[new_p.id] = new_p
        self.save()
        return new_p

    def delete(self, prompt_id: str) -> bool:
        if prompt_id in self._prompts:
            del self._prompts[prompt_id]
            self.save()
            return True
        return False

    def record_usage(self, prompt_id: str) -> None:
        p = self.get(prompt_id)
        if p:
            p.lastUsed = time.time()
            self.save()

    def _get_default_presets(self) -> List[PromptTemplate]:
        return [
            PromptTemplate(
                id="preset-deep-dive",
                title="Deep Dive Investigation",
                description="Comprehensive architectural and codebase inspection for thorough discovery.",
                targetApp="all",
                agentProvider="any",
                promptText="Perform an exhaustive technical deep dive into this application. Inspect architecture, data flows, configuration, critical dependencies, performance bottlenecks, and recent changes. Provide a complete architectural breakdown without modifying production files.",
                tags=["audit", "investigation", "architecture"]
            ),
            PromptTemplate(
                id="preset-bug-hunt",
                title="Targeted Bug Hunt & Fix",
                description="Reproduce, isolate, and safely resolve a specific bug with regression tests.",
                targetApp="all",
                agentProvider="any",
                promptText="Investigate and isolate the root cause of the reported issue. Create a minimal reproduction test case, implement a surgical fix adhering to zero-downtime safeguards, verify no regressions across the test suite, and document the resolution in an engineering handoff.",
                tags=["bugfix", "remediation", "testing"]
            ),
            PromptTemplate(
                id="preset-prod-audit",
                title="Production Pre-Flight Audit",
                description="Validate all health endpoints, hashes, and deployment criteria before a release.",
                targetApp="all",
                agentProvider="any",
                promptText="Run a full pre-flight audit against production standards. Verify: (1) local health HTTP 200, (2) live stream audio bytes, (3) catalog integrity state, (4) baseline hashes, (5) zero uncommitted stray edits, and (6) rollback backup readiness.",
                tags=["production", "audit", "preflight"]
            ),
            PromptTemplate(
                id="preset-visuals-overhaul",
                title="Visuals Workstation Review",
                description="Validate 7-layer canvas compositing, 16:9 geometry, and Green staging parity.",
                targetApp="visuals-workstation",
                agentProvider="antigravity",
                promptText="Inspect the Visuals show-control workstation. Verify 16:9 canonical geometry alignment, async Rust backend non-blocking behavior, 7-layer stacking order, ffprobe media scanning, and 1-click Green staging synchronization.",
                tags=["visuals", "staging", "rust", "tauri"]
            ),
            PromptTemplate(
                id="preset-update-deploy",
                title="Safe Update & Deploy Workflow",
                description="Execute the 10-step safe update workflow with backup, build, test, and verification.",
                targetApp="all",
                agentProvider="any",
                promptText="Execute a safe update workflow: (1) Detect current version and git status, (2) Create timestamped rollback backup, (3) Run automated test suite, (4) Compile production bundle, (5) Deploy to target environment, (6) Verify live HTTP 200 health, and (7) Record engineering handoff.",
                tags=["deployment", "updates", "workflow"]
            ),
            PromptTemplate(
                id="preset-security-review",
                title="Security & Secrets Audit",
                description="Verify no API keys, private keys, or tokens are exposed or committed.",
                targetApp="all",
                agentProvider="any",
                promptText="Scan repository files and working trees for any plaintext credentials, Discord tokens, Stripe keys, Cloudflare secrets, or SSH keys. Ensure .gitignore covers all sensitive files and verify file permissions.",
                tags=["security", "secrets", "compliance"]
            ),
            PromptTemplate(
                id="preset-backup-verification",
                title="Backup & Disaster Recovery Audit",
                description="Verify snapshot integrity, emergency music mirror file counts, and DB backups.",
                targetApp="backup-recovery",
                agentProvider="any",
                promptText="Verify all station backups: (1) SQLite station.db snapshots, (2) Emergency music mirror (575 files), (3) Local pre-deployment backups, (4) Off-host encrypted archives, and (5) Restore runbook readiness.",
                tags=["backups", "recovery", "integrity"]
            ),
            PromptTemplate(
                id="preset-test-everything",
                title="Full Test Suite Execution",
                description="Run all backend, frontend, geometry parity, and integration test suites.",
                targetApp="all",
                agentProvider="any",
                promptText="Execute the complete test matrix across all components: Python unit tests, Tauri Rust unit tests, Node.js geometry parity tests, site smoke tests, and healthcheck diagnostics. Report pass/fail scores with actionable details for any failure.",
                tags=["testing", "ci", "verification"]
            )
        ]
