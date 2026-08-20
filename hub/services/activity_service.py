"""
ALLTHINGS140 Hub — Activity Log & Notifications Service
Records all operations, actions, health transitions, and actionable notifications.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import ACTIVITY_FILE
from hub.util.atomic_io import atomic_write_json


@dataclass
class ActivityEntry:
    id: str
    timestamp: float
    formattedDate: str
    component: str
    action: str  # LAUNCH_AGENT, RUN_HEALTHCHECK, CREATE_BACKUP, UPDATE_APP, RESTART_SERVICE, OPEN_REPORT, VIEW_LOGS, APP_LAUNCH
    result: str  # SUCCESS, WARNING, FAILED, INFO
    detail: str
    userTriggered: bool = True


ActivityItem = ActivityEntry


@dataclass
class HubNotification:
    id: str
    title: str
    message: str
    severity: str  # info, warning, critical
    timestamp: float
    component: str
    isDismissed: bool = False
    actionLink: str = ""


class ActivityService:
    """Manages audit logging and notification alerts for the Hub."""

    def __init__(self):
        self._activities: List[ActivityEntry] = []
        self._notifications: List[HubNotification] = []
        self.reload()

    def reload(self) -> None:
        if ACTIVITY_FILE.exists():
            try:
                with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._activities = [ActivityEntry(**item) for item in data.get("activities", [])]
                self._notifications = [HubNotification(**item) for item in data.get("notifications", [])]
                # v1.2.0 shipped demo audit entries as if they were real. Remove only
                # those known canned IDs during migration.
                self._activities = [a for a in self._activities if not a.id.startswith("act-init-")]
                self._notifications = [n for n in self._notifications if n.id not in {"notif-1", "notif-2"}]
                return
            except Exception:
                try:
                    damaged = ACTIVITY_FILE.with_suffix(ACTIVITY_FILE.suffix + f".corrupt-{int(time.time())}")
                    ACTIVITY_FILE.replace(damaged)
                except Exception:
                    pass
                self._activities = []
                self._notifications = []
                return
        self._activities = []
        self._notifications = []

    def save(self) -> None:
        atomic_write_json(ACTIVITY_FILE, {
            "activities": [asdict(a) for a in self._activities],
            "notifications": [asdict(n) for n in self._notifications],
        })

    def log(self, component: str, action: str, result: str, detail: str, user_triggered: bool = True) -> ActivityEntry:
        now = time.time()
        formatted_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        entry = ActivityEntry(
            id=f"act-{int(now * 1000)}",
            timestamp=now,
            formattedDate=formatted_date,
            component=component,
            action=action,
            result=result,
            detail=detail,
            userTriggered=user_triggered
        )
        self._activities.insert(0, entry)
        if len(self._activities) > 500:
            self._activities = self._activities[:500]
        self.save()
        return entry

    def all_activities(self) -> List[ActivityEntry]:
        return self._activities

    def active_notifications(self) -> List[HubNotification]:
        return [n for n in self._notifications if not n.isDismissed]

    def add_notification(self, title: str, message: str, severity: str, component: str, action_link: str = "") -> HubNotification:
        now = time.time()
        notif = HubNotification(
            id=f"notif-{int(now * 1000)}",
            title=title,
            message=message,
            severity=severity,
            timestamp=now,
            component=component,
            actionLink=action_link
        )
        self._notifications.insert(0, notif)
        self.save()
        return notif

    def dismiss_notification(self, notif_id: str) -> None:
        for n in self._notifications:
            if n.id == notif_id:
                n.isDismissed = True
                break
        self.save()

