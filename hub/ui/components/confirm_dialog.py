"""
ALLTHINGS140 Hub — Structured Confirmation Modal Dialog
Provides clear, standardized pre-flight impact transparency before executing ORANGE or RED operations:
- What it does
- What it touches (files / services / remote hosts)
- Expected impact (Public audio interruption: None / Expected / Temporary)
- Can I undo it? (Rollback plan)
- Does it affect the live station?
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from hub.ui.components.safety_badge import SafetyBadge
from hub.config import get_config
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_ORANGE,
    SAFETY_RED,
    SAFETY_YELLOW,
    STATUS_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ConfirmDialog(QDialog):
    """Rich structured confirmation modal explaining pre-flight impact."""

    def __init__(
        self,
        title: str,
        message: str,
        what_it_does: str = "",
        what_it_touches: str = "",
        expected_impact: str = "No live broadcast interruption expected.",
        rollback_plan: str = "Automatic or rollback snapshot available.",
        affects_live_station: bool = False,
        safety_level: str = "orange",
        confirm_label: str = "Confirm Action",
        warning_detail: str = "",  # Backward compatibility
        is_danger: bool = False,   # Backward compatibility
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(540)
        self.setModal(True)

        if is_danger and safety_level == "orange":
            safety_level = "red"

        self.safety_level = safety_level.lower()
        self.what_it_does = what_it_does or message
        self.what_it_touches = what_it_touches or "Workstation local files or remote endpoints."
        self.expected_impact = expected_impact or warning_detail or "No live stream interruption expected."
        self.rollback_plan = rollback_plan
        self.affects_live_station = affects_live_station
        self.confirm_label = confirm_label

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 10px;
            }}
        """)

        self._init_ui(title)

    def _init_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 1. Header with Safety Tier Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title_lbl = QLabel(title)
        title_color = SAFETY_RED if self.safety_level == "red" else SAFETY_ORANGE if self.safety_level == "orange" else ACCENT_CYAN
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {title_color};")
        top_row.addWidget(title_lbl, 1)

        badge = SafetyBadge(level=self.safety_level)
        top_row.addWidget(badge)
        layout.addLayout(top_row)

        # 2. Structured "Before You Click" Information Card
        card = QFrame()
        card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 14px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(10)

        def add_info_row(heading: str, value: str, is_highlight: bool = False, highlight_color: str = TEXT_PRIMARY):
            r = QVBoxLayout()
            r.setSpacing(2)
            h = QLabel(heading.upper())
            h.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")
            v = QLabel(value)
            v.setWordWrap(True)
            v.setStyleSheet(f"color: {highlight_color if is_highlight else TEXT_PRIMARY}; font-size: 12px; line-height: 1.3;")
            r.addWidget(h)
            r.addWidget(v)
            c_layout.addLayout(r)

        add_info_row("What It Does", self.what_it_does)
        add_info_row("What It Touches", self.what_it_touches)
        add_info_row("Expected Impact", self.expected_impact)
        add_info_row("Can I Undo It? (Rollback Plan)", self.rollback_plan)

        live_text = "⚠️ YES — May directly affect the live 24/7 broadcast or public listeners." if self.affects_live_station else "✓ NO — Radio broadcast runs independently on Oracle VM 1."
        live_color = SAFETY_RED if self.affects_live_station else STATUS_GREEN
        add_info_row("Does It Affect The Live Station?", live_text, is_highlight=True, highlight_color=live_color)

        layout.addWidget(card)

        # 3. Protected Operator Mode: RED actions require an explicit typed acknowledgement.
        self.confirm_input = None
        protected = False
        try:
            protected = bool(get_config().protected_operator_mode)
        except Exception:
            protected = True  # Fail safe if configuration cannot be read.

        if self.safety_level == "red" and protected:
            verify_box = QFrame()
            verify_box.setStyleSheet(f"background: {BG_SURFACE}; border: 1px solid {SAFETY_RED}; border-radius: 6px; padding: 10px;")
            verify_layout = QVBoxLayout(verify_box)
            verify_layout.setSpacing(6)
            verify_lbl = QLabel("PROTECTED OPERATOR MODE — type CONFIRM to unlock this RED action")
            verify_lbl.setWordWrap(True)
            verify_lbl.setStyleSheet(f"color: {SAFETY_RED}; font-size: 11px; font-weight: 800;")
            verify_layout.addWidget(verify_lbl)
            self.confirm_input = QLineEdit()
            self.confirm_input.setPlaceholderText("Type CONFIRM")
            self.confirm_input.setAccessibleName("Production action confirmation")
            verify_layout.addWidget(self.confirm_input)
            layout.addWidget(verify_box)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton(self.confirm_label)
        if self.safety_level == "red":
            self.btn_confirm.setProperty("danger", "true")
        elif self.safety_level == "orange":
            self.btn_confirm.setProperty("warning", "true")
        else:
            self.btn_confirm.setProperty("primary", "true")

        if self.confirm_input is not None:
            self.btn_confirm.setEnabled(False)
            self.confirm_input.textChanged.connect(
                lambda text: self.btn_confirm.setEnabled(text.strip().upper() == "CONFIRM")
            )
        self.btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_confirm)

        layout.addLayout(btn_layout)
