"""
ALLTHINGS140 Hub — Status Pill Component
Custom styled badge representing operational health and lifecycle states.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from hub.ui.theme import (
    STATUS_AMBER,
    STATUS_AMBER_BG,
    STATUS_BLUE,
    STATUS_BLUE_BG,
    STATUS_GREEN,
    STATUS_GREEN_BG,
    STATUS_RED,
    STATUS_RED_BG,
    TEXT_MUTED,
)


class StatusPill(QLabel):
    """A compact, color-coded status badge."""

    def __init__(self, status_text: str = "UNKNOWN", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.set_status(status_text)

    def set_status(self, text: str) -> None:
        raw = text.upper().strip()
        self.setText(f"  {raw}  ")

        # Color rules
        if any(w in raw for w in ("HEALTHY", "ACTIVE", "ONLINE", "SUCCESS", "VERIFIED", "SYNCED")):
            fg = STATUS_GREEN
            bg = STATUS_GREEN_BG
            border = STATUS_GREEN
        elif any(w in raw for w in ("WARNING", "DEGRADED", "STAGING", "DIRTY", "UNCOMMITTED")):
            fg = STATUS_AMBER
            bg = STATUS_AMBER_BG
            border = STATUS_AMBER
        elif any(w in raw for w in ("CRITICAL", "OFFLINE", "FAILED", "ERROR")):
            fg = STATUS_RED
            bg = STATUS_RED_BG
            border = STATUS_RED
        elif any(w in raw for w in ("STANDALONE", "TOOL", "SERVICE", "WORKSTATION", "ARTIFACT", "INFO")):
            fg = STATUS_BLUE
            bg = STATUS_BLUE_BG
            border = STATUS_BLUE
        else:
            fg = TEXT_MUTED
            bg = "rgba(100, 116, 139, 0.12)"
            border = TEXT_MUTED

        self.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
                font-weight: bold;
                font-size: 10px;
                letter-spacing: 0.5px;
                padding: 2px 6px;
            }}
        """)
