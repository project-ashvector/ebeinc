"""
ALLTHINGS140 Hub — Empty State Component
Provides helpful messaging and action suggestions when a list, search, or inventory is empty.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class EmptyState(QFrame):
    """Visual container for empty states, searches, or initial inventory."""

    def __init__(
        self,
        icon: str = "📦",
        title: str = "No Items Found",
        description: str = "There are no entries matching your current filters or query.",
        action_text: Optional[str] = None,
        on_action=None,
        parent=None
    ):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border: 1px dashed {BORDER_SUBTLE};
                border-radius: 8px;
                padding: 24px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 32px;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_PRIMARY};")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; max-width: 420px;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_lbl)

        if action_text and on_action:
            btn = QPushButton(action_text)
            btn.setProperty("primary", "true")
            btn.clicked.connect(on_action)
            btn_row = QHBoxLayout()
            btn_row.setAlignment(Qt.AlignCenter)
            btn_row.addWidget(btn)
            layout.addLayout(btn_row)
