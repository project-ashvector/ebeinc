"""
ALLTHINGS140 Hub — Engineering Handoff Service
Records, indexes, and exports cross-agent engineering handoffs and session summaries.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import HANDOFFS_FILE
from hub.util.atomic_io import atomic_write_json


@dataclass
class EngineeringHandoff:
    id: str
    timestamp: float
    formattedDate: str
    projectId: str
    appId: str
    appName: str
    agentName: str
    taskTitle: str
    changesMade: List[str]
    filesChanged: List[str]
    testsExecuted: str
    deploymentStatus: str
    healthStatus: str
    remainingWork: List[str]
    recommendedNextTask: str
    reportPath: str = ""


class HandoffService:
    """Stores and retrieves engineering handoffs across AI coding sessions."""

    def __init__(self):
        self._handoffs: List[EngineeringHandoff] = []
        self.reload()

    def reload(self) -> None:
        """Load handoffs from disk or initialize with historical onboarding handoffs."""
        if HANDOFFS_FILE.exists():
            try:
                with open(HANDOFFS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._handoffs = [EngineeringHandoff(**item) for item in data]
                return
            except Exception:
                try:
                    damaged = HANDOFFS_FILE.with_suffix(HANDOFFS_FILE.suffix + f".corrupt-{int(time.time())}")
                    HANDOFFS_FILE.replace(damaged)
                except Exception:
                    pass
                self._handoffs = []
                return

        # A new Hub starts with an empty audit store; it never invents history.
        self._handoffs = []

    def save(self) -> None:
        atomic_write_json(HANDOFFS_FILE, [asdict(h) for h in self._handoffs])

    def all(self) -> List[EngineeringHandoff]:
        return sorted(self._handoffs, key=lambda h: h.timestamp, reverse=True)

    def get(self, handoff_id: str) -> Optional[EngineeringHandoff]:
        for h in self._handoffs:
            if h.id == handoff_id:
                return h
        return None

    def by_app(self, app_id: str) -> List[EngineeringHandoff]:
        return [h for h in self.all() if h.appId == app_id]

    def search(self, query: str) -> List[EngineeringHandoff]:
        q = query.lower().strip()
        if not q:
            return self.all()
        return [
            h for h in self.all()
            if q in h.taskTitle.lower() or q in h.appName.lower() or q in h.agentName.lower() or any(q in c.lower() for c in h.changesMade)
        ]

    def create(
        self,
        app_id: str,
        app_name: str,
        agent_name: str,
        task_title: str,
        changes_made: List[str],
        files_changed: List[str],
        tests_executed: str,
        deployment_status: str,
        health_status: str,
        remaining_work: List[str],
        recommended_next_task: str,
        report_path: str = "",
        project_id: str = "AllThings140Radio"
    ) -> EngineeringHandoff:
        now = time.time()
        formatted_date = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now))
        handoff_id = f"handoff-{int(now)}-{app_id}"

        h = EngineeringHandoff(
            id=handoff_id,
            timestamp=now,
            formattedDate=formatted_date,
            projectId=project_id,
            appId=app_id,
            appName=app_name,
            agentName=agent_name,
            taskTitle=task_title,
            changesMade=changes_made,
            filesChanged=files_changed,
            testsExecuted=tests_executed,
            deploymentStatus=deployment_status,
            healthStatus=health_status,
            remainingWork=remaining_work,
            recommendedNextTask=recommended_next_task,
            reportPath=report_path
        )
        self._handoffs.insert(0, h)
        self.save()
        return h

    def export_for_chatgpt(self, handoff_id: str) -> str:
        """Format an engineering handoff for clean ChatGPT / peer AI handoff."""
        h = self.get(handoff_id)
        if not h:
            return "Handoff not found."

        lines = [
            f"# ENGINEERING HANDOFF: {h.taskTitle}",
            f"**Timestamp:** {h.formattedDate}",
            f"**Project:** {h.projectId} | **Application:** {h.appName} (`{h.appId}`)",
            f"**Authoring Agent:** {h.agentName}",
            "",
            "## 1. CHANGES COMPLETED",
        ]
        for item in h.changesMade:
            lines.append(f"- {item}")

        lines.extend([
            "",
            "## 2. FILES MODIFIED / CREATED",
        ])
        for f in h.filesChanged:
            lines.append(f"- `{f}`")

        lines.extend([
            "",
            f"## 3. VERIFICATION & TESTS\n{h.testsExecuted}",
            "",
            f"## 4. DEPLOYMENT STATUS\n{h.deploymentStatus}",
            "",
            f"## 5. SYSTEM HEALTH\n{h.healthStatus}",
            "",
            "## 6. REMAINING WORK / OPEN GATES",
        ])
        for rw in h.remainingWork:
            lines.append(f"- {rw}")

        if h.reportPath:
            lines.extend([
                "",
                f"## 7. FULL REPORT\n`{h.reportPath}`"
            ])

        lines.extend([
            "",
            f"## 8. RECOMMENDED NEXT TASK\n👉 {h.recommendedNextTask}"
        ])
        return "\n".join(lines)

