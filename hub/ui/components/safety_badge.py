"""
ALLTHINGS140 Hub — Safety Level Badge Component
Visually classifies operations into 4 distinct safety tiers:
1. GREEN: Safe / Read-Only (no state modification)
2. YELLOW: Local Change (modifies local configs/drafts only)
3. ORANGE: Remote Service Change (restarts/alters VM services)
4. RED: Production / Destructive (deploys, rollbacks, purges)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from hub.ui.theme import (
    SAFETY_GREEN,
    SAFETY_GREEN_BG,
    SAFETY_GREEN_BORDER,
    SAFETY_ORANGE,
    SAFETY_ORANGE_BG,
    SAFETY_ORANGE_BORDER,
    SAFETY_RED,
    SAFETY_RED_BG,
    SAFETY_RED_BORDER,
    SAFETY_YELLOW,
    SAFETY_YELLOW_BG,
    SAFETY_YELLOW_BORDER,
    TEXT_PRIMARY,
)


class SafetyBadge(QFrame):
    """Visual safety indicator badge for actions and operations."""

    LEVELS = {
        "green": {
            "label": "SAFE / READ-ONLY",
            "icon": "🟢",
            "color": SAFETY_GREEN,
            "bg": SAFETY_GREEN_BG,
            "border": SAFETY_GREEN_BORDER,
            "tooltip": "Safe action: Reads telemetry or views local files. Does not change production or local data."
        },
        "yellow": {
            "label": "LOCAL CHANGE",
            "icon": "🟡",
            "color": SAFETY_YELLOW,
            "bg": SAFETY_YELLOW_BG,
            "border": SAFETY_YELLOW_BORDER,
            "tooltip": "Local change: Modifies local configuration or workspace files. Live production is not affected."
        },
        "orange": {
            "label": "REMOTE SERVICE CHANGE",
            "icon": "🟠",
            "color": SAFETY_ORANGE,
            "bg": SAFETY_ORANGE_BG,
            "border": SAFETY_ORANGE_BORDER,
            "tooltip": "Remote service change: Interacts with VM services. May cause brief service reconnects."
        },
        "red": {
            "label": "PRODUCTION / DESTRUCTIVE",
            "icon": "🔴",
            "color": SAFETY_RED,
            "bg": SAFETY_RED_BG,
            "border": SAFETY_RED_BORDER,
            "tooltip": "Production or destructive action: Affects live stream, deletes assets, or deploys to Cloudflare."
        }
    }

    def __init__(self, level: str = "green", custom_text: Optional[str] = None, compact: bool = False, parent=None):
        super().__init__(parent)
        self.level_key = level.lower()
        self.custom_text = custom_text
        self.compact = compact
        self._init_ui()

    def _init_ui(self) -> None:
        cfg = self.LEVELS.get(self.level_key, self.LEVELS["green"])
        text = self.custom_text or (cfg["icon"] if self.compact else f"{cfg['icon']}  {cfg['label']}")

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {cfg["bg"]};
                border: 1px solid {cfg["border"]};
                border-radius: 4px;
                padding: { '2px 6px' if self.compact else '3px 8px' };
            }}
        """)
        self.setToolTip(cfg["tooltip"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.label = QLabel(text)
        self.label.setStyleSheet(f"""
            color: {cfg["color"]};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self.label)

    def set_level(self, level: str, custom_text: Optional[str] = None) -> None:
        self.level_key = level.lower()
        self.custom_text = custom_text
        cfg = self.LEVELS.get(self.level_key, self.LEVELS["green"])
        text = self.custom_text or (cfg["icon"] if self.compact else f"{cfg['icon']}  {cfg['label']}")

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {cfg["bg"]};
                border: 1px solid {cfg["border"]};
                border-radius: 4px;
                padding: { '2px 6px' if self.compact else '3px 8px' };
            }}
        """)
        self.setToolTip(cfg["tooltip"])
        self.label.setText(text)
        self.label.setStyleSheet(f"""
            color: {cfg["color"]};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)

    def text(self) -> str:
        """Return the badge text."""
        return self.label.text()
