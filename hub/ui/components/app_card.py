"""
ALLTHINGS140 Hub — Application Card Component
Rich interactive tile representing a registered application with live status and actions.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.registry.app_registry import AppEntry
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.status_pill import StatusPill
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    BG_CARD,
    BG_CARD_HOVER,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_YELLOW,
    STATUS_AMBER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class AppCard(QFrame):
    """Card widget representing an ALLTHINGS140 application."""

    on_launch = Signal(str)
    on_terminal = Signal(str)
    on_agent = Signal(str)
    on_details = Signal(str)

    def __init__(self, app: AppEntry, parent=None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("AppCard")

        self.setStyleSheet(f"""
            QFrame#AppCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
            }}
            QFrame#AppCard:hover {{
                background-color: {BG_CARD_HOVER};
                border: 1px solid {BORDER_LIGHT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # Header: Name, Version, Status Pill
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_lbl = QLabel(app.displayName)
        self.title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_PRIMARY};")
        header_layout.addWidget(self.title_lbl)

        header_layout.addStretch()

        if app.version:
            v_lbl = QLabel(f"v{app.version}")
            v_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; font-family: monospace;")
            header_layout.addWidget(v_lbl)

        self.status_pill = StatusPill(app.status)
        header_layout.addWidget(self.status_pill)
        layout.addLayout(header_layout)

        # Subtitle: Category & Deployment Target & Dirty state
        sub_layout = QHBoxLayout()
        sub_layout.setSpacing(6)

        cat_lbl = QLabel(f"[{app.category.upper()}]")
        cat_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 10px; font-weight: bold;")
        sub_layout.addWidget(cat_lbl)

        env_lbl = QLabel(f"• {app.deploymentTarget}")
        env_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        sub_layout.addWidget(env_lbl)

        if app.dirty:
            dirty_lbl = QLabel("• UNCOMMITTED EDITS")
            dirty_lbl.setStyleSheet(f"color: {STATUS_AMBER}; font-size: 10px; font-weight: bold;")
            dirty_lbl.setToolTip("Local files have uncommitted git changes.")
            sub_layout.addWidget(dirty_lbl)

        sub_layout.addStretch()
        layout.addLayout(sub_layout)

        # Description
        desc_lbl = QLabel(app.description)
        desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.3;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        layout.addSpacing(4)

        # Action Buttons Row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.btn_agent = QPushButton("🤖 Work On App")
        self.btn_agent.setProperty("accent", "true")
        self.btn_agent.setToolTip("Open AI Coding Agent control center with auto-populated context for this app.")
        self.btn_agent.clicked.connect(lambda: self.on_agent.emit(self.app.id))
        actions_layout.addWidget(self.btn_agent)

        self.btn_terminal = QPushButton("💻 Terminal")
        self.btn_terminal.setToolTip(f"Open terminal in {app.workingDirectory}")
        self.btn_terminal.clicked.connect(lambda: self.on_terminal.emit(self.app.id))
        actions_layout.addWidget(self.btn_terminal)

        self.btn_launch = QPushButton("▶ Launch")
        if app.launchCommand:
            self.btn_launch.setProperty("primary", "true")
            self.btn_launch.setToolTip(f"Execute: {app.launchCommand}")
        else:
            self.btn_launch.setEnabled(False)
            self.btn_launch.setToolTip("No direct GUI launch command configured for this component.")
        self.btn_launch.clicked.connect(lambda: self.on_launch.emit(self.app.id))
        actions_layout.addWidget(self.btn_launch)

        self.btn_details = QPushButton("ℹ️ Details")
        self.btn_details.setToolTip("View full technical specifications, architecture notes, and safeguards.")
        self.btn_details.clicked.connect(lambda: self.on_details.emit(self.app.id))
        actions_layout.addWidget(self.btn_details)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)
