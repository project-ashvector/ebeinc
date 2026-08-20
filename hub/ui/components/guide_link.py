"""
ALLTHINGS140 Hub — Contextual Help & Guide Link Components
Provides inline '?' buttons and 'What does this do?' links that open relevant guide sections.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class GuideLink(QPushButton):
    """Clickable inline link or button that requests navigation to an in-app Guide section."""

    open_guide = Signal(str)  # Emits guide section key

    def __init__(
        self,
        guide_key: str = "start-here",
        text: str = "?",
        tooltip: str = "Open in-app guide documentation for this feature",
        compact: bool = True,
        parent=None
    ):
        super().__init__(text, parent)
        self.guide_key = guide_key
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)

        if compact:
            self.setFixedSize(22, 22)
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BG_CARD};
                    color: {ACCENT_CYAN};
                    border: 1px solid {BORDER_SUBTLE};
                    border-radius: 11px;
                    font-size: 11px;
                    font-weight: 800;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background-color: {ACCENT_CYAN};
                    color: {BG_DARK};
                    border: 1px solid {ACCENT_CYAN};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {ACCENT_CYAN};
                    border: none;
                    font-size: 12px;
                    font-weight: 600;
                    text-decoration: underline;
                    padding: 2px 4px;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                }}
            """)

        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self.open_guide.emit(self.guide_key)


class HelpTooltip(QLabel):
    """Small informational label with an icon and rich tooltip explanation."""

    def __init__(self, tooltip_text: str, parent=None):
        super().__init__("ℹ️", parent)
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.WhatsThisCursor)
        self.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED};
                font-size: 12px;
                padding: 0 4px;
            }}
            QLabel:hover {{
                color: {ACCENT_CYAN};
            }}
        """)
