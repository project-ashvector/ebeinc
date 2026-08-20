"""
ALLTHINGS140 Hub — Section Card & Container Components
Modular cards with consistent borders, padding, titles, subtitles, and safety tags.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from hub.ui.components.guide_link import GuideLink
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_CARD_HOVER,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SectionCard(QFrame):
    """Clean container card with an optional header strip, title, guide link, and action area."""

    def __init__(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        guide_key: Optional[str] = None,
        safety_level: Optional[str] = None,
        elevated: bool = False,
        parent=None
    ):
        super().__init__(parent)
        bg = BG_SURFACE if elevated else BG_CARD
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        if title or subtitle or guide_key or safety_level:
            header_layout = QHBoxLayout()
            header_layout.setSpacing(8)

            if title:
                self.title_lbl = QLabel(title.upper())
                self.title_lbl.setStyleSheet(f"""
                    color: {ACCENT_CYAN};
                    font-size: 11px;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                """)
                header_layout.addWidget(self.title_lbl)

            if safety_level:
                self.safety_badge = SafetyBadge(level=safety_level, compact=True)
                header_layout.addWidget(self.safety_badge)

            if guide_key:
                self.guide_btn = GuideLink(guide_key=guide_key, compact=True)
                header_layout.addWidget(self.guide_btn)

            header_layout.addStretch()
            self.header_actions = QHBoxLayout()
            self.header_actions.setSpacing(6)
            header_layout.addLayout(self.header_actions)

            self.main_layout.addLayout(header_layout)

            if subtitle:
                sub_lbl = QLabel(subtitle)
                sub_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.3;")
                sub_lbl.setWordWrap(True)
                self.main_layout.addWidget(sub_lbl)

    def add_widget(self, widget: QWidget) -> None:
        self.main_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.main_layout.addLayout(layout)
