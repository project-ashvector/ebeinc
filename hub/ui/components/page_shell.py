"""
ALLTHINGS140 Hub — Standard Page Shell & Page Header Component
Ensures consistent visual hierarchy, predictable scrolling, header actions, and in-app Guide links across all 22 Hub views.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hub.ui.components.guide_link import GuideLink
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class PageHeader(QFrame):
    """Standard top header for all Hub primary views."""

    open_guide = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        guide_key: Optional[str] = None,
        safety_level: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.guide_key = guide_key
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
                padding-bottom: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Top row with Title, Safety Badge, Guide Link, and Action stretch
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 800;
            color: {TEXT_PRIMARY};
            letter-spacing: 0.5px;
        """)
        top_row.addWidget(self.title_lbl)

        if safety_level:
            self.safety_badge = SafetyBadge(level=safety_level)
            top_row.addWidget(self.safety_badge)

        if guide_key:
            self.guide_btn = GuideLink(guide_key=guide_key, text="? Guide", compact=False)
            self.guide_btn.open_guide.connect(lambda k: self.open_guide.emit(k))
            top_row.addWidget(self.guide_btn)

        top_row.addStretch()

        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(8)
        top_row.addLayout(self.action_layout)

        layout.addLayout(top_row)

        if subtitle:
            self.subtitle_lbl = QLabel(subtitle)
            self.subtitle_lbl.setStyleSheet(f"""
                font-size: 12px;
                color: {TEXT_SECONDARY};
                line-height: 1.3;
            """)
            self.subtitle_lbl.setWordWrap(True)
            layout.addWidget(self.subtitle_lbl)

    def add_action(self, widget: QWidget) -> None:
        self.action_layout.addWidget(widget)


class PageShell(QWidget):
    """Standard root container for Hub views providing a predictable single-scroll viewport."""

    open_guide = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        guide_key: Optional[str] = None,
        safety_level: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.setObjectName("PageShell")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet(f"background-color: {BG_DARK}; border: none;")

        self.content_container = QWidget()
        self.content_container.setStyleSheet(f"background-color: {BG_DARK};")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(24, 20, 24, 24)
        self.content_layout.setSpacing(16)

        # Standard Page Header
        self.header = PageHeader(
            title=title,
            subtitle=subtitle,
            guide_key=guide_key,
            safety_level=safety_level
        )
        self.header.open_guide.connect(lambda k: self.open_guide.emit(k))
        self.content_layout.addWidget(self.header)

        self.scroll_area.setWidget(self.content_container)
        main_layout.addWidget(self.scroll_area)

    def add_widget(self, widget: QWidget) -> None:
        """Add child widget to the content area."""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        """Add child layout to the content area."""
        self.content_layout.addLayout(layout)

    def add_stretch(self) -> None:
        """Add stretch to keep elements pinned to top."""
        self.content_layout.addStretch()

    def reset_scroll(self) -> None:
        """Reset scrollbar position to the top when navigating to this view."""
        self.scroll_area.verticalScrollBar().setValue(0)
        self.scroll_area.horizontalScrollBar().setValue(0)
