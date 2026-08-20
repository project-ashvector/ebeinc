"""
ALLTHINGS140 Hub — Main Dashboard View
High-level operational overview, live metrics, now playing card, quick actions, and alerts.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.registry.app_registry import AppRegistry
from hub.services.activity_service import ActivityService
from hub.services.health_service import HealthService, StationHealthSnapshot
from hub.ui.components.guide_link import GuideLink
from hub.ui.components.page_shell import PageHeader, PageShell
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.section_card import SectionCard
from hub.ui.components.stat_box import StatBox
from hub.ui.components.status_pill import StatusPill
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PINK,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    STATUS_GREEN,
    STATUS_RED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class DashboardView(QWidget):
    """Primary operational command center view."""

    navigate_to = Signal(str)      # Tab name to navigate to
    quick_action = Signal(str)     # Action key
    open_guide = Signal(str)       # Guide section key

    def __init__(
        self,
        app_registry: AppRegistry,
        health_service: HealthService,
        activity_service: ActivityService,
        parent=None
    ):
        super().__init__(parent)
        self.app_registry = app_registry
        self.health_service = health_service
        self.activity_service = activity_service

        self._init_ui()
        self.health_service.subscribe(self.update_health)

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Station Operations Command Center",
            subtitle="Real-time 24/7 telemetry, live track rotation, station health gauges, and guarded operations.",
            guide_key="page-dashboard",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # 1. Now Playing Live Banner Card
        self.now_playing_frame = QFrame()
        self.now_playing_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #18142a, stop:1 #0c1822);
                border: 1px solid {BORDER_SUBTLE};
                border-left: 4px solid {ACCENT_CYAN};
                border-radius: 8px;
            }}
        """)
        np_layout = QHBoxLayout(self.now_playing_frame)
        np_layout.setContentsMargins(18, 14, 18, 14)
        np_layout.setSpacing(16)

        np_info = QVBoxLayout()
        np_info.setSpacing(4)
        self.np_badge = QLabel("● NOW BROADCASTING 24/7 (AUTODJ)")
        self.np_badge.setStyleSheet(f"color: {STATUS_GREEN}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        self.np_track = QLabel("Connecting to 24/7 broadcast authority…")
        self.np_track.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 17px; font-weight: 800;")
        self.np_track.setWordWrap(True)
        self.np_meta = QLabel("AutoDJ Rotation • Heavy Dubstep / Riddim / 140 BPM • Oracle VM 1 Authority")
        self.np_meta.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        np_info.addWidget(self.np_badge)
        np_info.addWidget(self.np_track)
        np_info.addWidget(self.np_meta)
        np_layout.addLayout(np_info, 1)

        self.btn_listen_live = QPushButton("▶ Open Live Player")
        self.btn_listen_live.setProperty("primary", "true")
        self.btn_listen_live.setToolTip("Open https://allthings140radio.online in default browser")
        self.btn_listen_live.clicked.connect(lambda: self.quick_action.emit("open-stream"))
        np_layout.addWidget(self.btn_listen_live)

        self.shell.add_widget(self.now_playing_frame)

        # 2. Key Operational Metrics Grid
        stat_card = SectionCard(
            title="SYSTEM HEALTH & TELEMETRY",
            subtitle="Verified live endpoints and authority status (checked automatically every 15s)",
            guide_key="page-health",
            safety_level="green"
        )
        grid_layout = QGridLayout()
        grid_layout.setSpacing(12)

        self.stat_stream = StatBox("Public Stream", "UNKNOWN", "Waiting for live probe", TEXT_MUTED)
        self.stat_server = StatBox("Broadcast Engine", "UNKNOWN", "Waiting for VM/API probe", TEXT_MUTED)
        self.stat_listeners = StatBox("Active Listeners", "0", "Connected listeners worldwide", ACCENT_PURPLE)
        self.stat_catalog = StatBox("Catalog Integrity", "UNKNOWN", "Waiting for authority data", TEXT_MUTED)

        visuals_app = self.app_registry.get("visuals-workstation")
        visuals_version = visuals_app.version if visuals_app else "UNKNOWN"
        self.stat_visuals = StatBox("Visuals Workstation", visuals_version, "Installed/source registry; verify in Applications", ACCENT_CYAN)
        self.stat_realtime = StatBox("Visuals Realtime", "UNKNOWN", "Waiting for realtime probe", TEXT_MUTED)
        self.stat_cache = StatBox("Hot Cache", "UNKNOWN", "Waiting for authority data", TEXT_MUTED)
        self.stat_backups = StatBox("Station Backups", "UNKNOWN", "Open Backups for verification", TEXT_MUTED)

        grid_layout.addWidget(self.stat_stream, 0, 0)
        grid_layout.addWidget(self.stat_server, 0, 1)
        grid_layout.addWidget(self.stat_listeners, 0, 2)
        grid_layout.addWidget(self.stat_catalog, 0, 3)

        grid_layout.addWidget(self.stat_visuals, 1, 0)
        grid_layout.addWidget(self.stat_realtime, 1, 1)
        grid_layout.addWidget(self.stat_cache, 1, 2)
        grid_layout.addWidget(self.stat_backups, 1, 3)

        stat_card.add_layout(grid_layout)
        self.shell.add_widget(stat_card)

        # 3. Quick Operations Grid
        qa_card = SectionCard(
            title="QUICK OPERATIONS & WORKSPACE LAUNCHERS",
            subtitle="Common operational tasks and application shortcuts",
            guide_key="app-roles",
            safety_level="green"
        )
        qa_layout = QGridLayout()
        qa_layout.setSpacing(10)

        actions = [
            ("🤖 Work on Station Server (Antigravity)", "work-server", "accent", "Open AI coding agent with Station Server context"),
            ("🤖 Work on Visuals Workstation", "work-visuals", "accent", "Open AI coding agent with Visuals App context"),
            ("📻 Launch Desktop DJ App", "launch-dj", "default", "Open station DJ track curation window"),
            ("🎨 Launch Visuals Show-Control", "launch-visuals", "default", "Open Tauri 7-layer canvas show control"),
            ("🌐 Open Web Listener Page", "open-web", "default", "Visit public listener website"),
            ("🟢 Open Green Web Stage", "open-green", "default", "Visit staging visuals portal"),
            ("🩺 Run Full Diagnostics", "run-diagnostics", "primary", "Execute read-only station diagnostics suite"),
            ("💾 Create Station Backup", "create-backup", "default", "Create timestamped rollback snapshot"),
            ("🖥️ SSH to Oracle VM 1 (Broadcast)", "ssh-vm1", "default", "Connect to broadcast server terminal via Tailscale"),
            ("🖥️ SSH to Oracle VM 2 (Visuals)", "ssh-vm2", "default", "Connect to visuals server terminal via Tailscale"),
        ]

        for idx, (lbl, key, btn_type, tooltip) in enumerate(actions):
            btn = QPushButton(lbl)
            btn.setToolTip(tooltip)
            if btn_type == "primary":
                btn.setProperty("primary", "true")
            elif btn_type == "accent":
                btn.setProperty("accent", "true")
            btn.clicked.connect(lambda checked=False, k=key: self.quick_action.emit(k))
            row = idx // 2
            col = idx % 2
            qa_layout.addWidget(btn, row, col)

        qa_card.add_layout(qa_layout)
        self.shell.add_widget(qa_card)

        # 4. Recent Activity Strip
        self.activity_card = SectionCard(
            title="RECENT OPERATIONAL ACTIVITY",
            subtitle="Audit log of recent deployments, tests, and station events",
            guide_key="page-dashboard",
            safety_level="green"
        )
        self.activity_layout = QVBoxLayout()
        self.activity_layout.setSpacing(8)
        self.activity_card.add_layout(self.activity_layout)
        self.shell.add_widget(self.activity_card)

        self.refresh_activity()
        self.shell.add_stretch()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def update_health(self, snapshot: StationHealthSnapshot) -> None:
        """Update dashboard with live health snapshot."""
        if snapshot.current_title:
            artist = snapshot.current_artist or "AllThings140Radio"
            self.np_track.setText(f"{artist} — {snapshot.current_title}")
        else:
            self.np_track.setText("Connecting to 24/7 broadcast authority…")

        if snapshot.live:
            host = snapshot.live_host or "LIVE BROADCAST"
            self.np_badge.setText(f"● NOW LIVE: {host.upper()}")
            self.np_badge.setStyleSheet(f"color: {ACCENT_PINK}; font-size: 11px; font-weight: bold;")
        elif snapshot.online:
            self.np_badge.setText("● BROADCAST AUTHORITY ONLINE")
            self.np_badge.setStyleSheet(f"color: {STATUS_GREEN}; font-size: 11px; font-weight: bold;")
        else:
            self.np_badge.setText("● STATION STATE UNKNOWN / OFFLINE")
            self.np_badge.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;")

        self.stat_stream.update_stat(snapshot.stream_status.upper(), "stream.ebeinc.online/live.mp3")
        self.stat_listeners.update_stat(str(snapshot.listeners) if snapshot.authority_status_verified else "UNKNOWN", "Connected listeners reported by station authority" if snapshot.authority_status_verified else "No authoritative listener count available")
        self.stat_catalog.update_stat(snapshot.catalog_health.upper(), f"{snapshot.approved_tracks} approved tracks reported" if snapshot.approved_tracks else "No authoritative track count reported")
        self.stat_cache.update_stat(snapshot.cache_status.upper(), f"{snapshot.cache_tracks_ready} tracks ready ({snapshot.cache_minutes_ready:.1f}m buffer)" if snapshot.cache_tracks_ready or snapshot.cache_minutes_ready else "No authoritative cache count reported")
        self.stat_realtime.update_stat("ONLINE" if snapshot.realtime_online else ("OFFLINE" if snapshot.vm2_reachable else "UNKNOWN"), "Oracle VM 2 / realtime health")
        self.stat_server.update_stat("ONLINE" if snapshot.vm1_reachable and snapshot.online else ("REACHABLE" if snapshot.vm1_reachable else "UNKNOWN"), "VM1 Tailscale + station authority")

    def refresh_activity(self) -> None:
        while self.activity_layout.count():
            child = self.activity_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        activities = self.activity_service.all_activities()[:5]
        if not activities:
            lbl = QLabel("No recorded activity yet.")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            self.activity_layout.addWidget(lbl)
            return

        for act in activities:
            row = QHBoxLayout()
            row.setSpacing(10)

            pill = StatusPill(act.result)
            comp_lbl = QLabel(f"[{act.component}]")
            comp_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; font-weight: bold;")

            desc_lbl = QLabel(act.detail)
            desc_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
            desc_lbl.setWordWrap(True)

            time_lbl = QLabel(act.formattedDate)
            time_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-family: monospace;")

            row.addWidget(pill)
            row.addWidget(comp_lbl)
            row.addWidget(desc_lbl, 1)
            row.addWidget(time_lbl)
            self.activity_layout.addLayout(row)
