"""
ALLTHINGS140 Hub — Metric Stat Box Component
Card displaying high-impact operational metrics (listeners, stream state, catalog health).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class StatBox(QFrame):
    """Card displaying a major operational metric."""

    def __init__(self, label: str, value: str = "—", subtitle: str = "", accent_color: str = ACCENT_CYAN, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {accent_color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        self.label_title = QLabel(label.upper())
        self.label_title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")

        self.label_value = QLabel(value)
        self.label_value.setStyleSheet(f"color: {accent_color}; font-size: 22px; font-weight: 800; font-family: monospace;")

        self.label_sub = QLabel(subtitle)
        self.label_sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self.label_sub.setWordWrap(True)

        layout.addWidget(self.label_title)
        layout.addWidget(self.label_value)
        layout.addWidget(self.label_sub)

    def update_stat(self, value: str, subtitle: Optional[str] = None) -> None:
        self.label_value.setText(value)
        if subtitle is not None:
            self.label_sub.setText(subtitle)
