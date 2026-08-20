"""
ALLTHINGS140 Hub — Operator First-Run Tour Dialog
Interactive 5-step walkthrough introducing the Hub, 24/7 broadcast independence, safety tiers, and guide system.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


TOUR_SLIDES: List[Tuple[str, str, str]] = [
    (
        "👋 Welcome to ALLTHINGS140 Hub",
        "The central operations center for 24/7 dubstep & bass radio.",
        """• <b>24/7 Radio Independence:</b> The radio broadcast runs 24/7 on Oracle VM 1. You can open and close the Hub at any time with zero downtime.<br><br>
• <b>Operations Console:</b> Use this console to monitor health, manage applications, launch AI coding agents, update website content, and deploy safely.<br><br>
• <b>Workstation Role:</b> This workstation provides management tools like the Desktop DJ app and Visuals Show-Control."""
    ),
    (
        "📊 Live Station Telemetry",
        "Understanding real-time health metrics at a glance.",
        """• <b>Now Broadcasting:</b> Displays the live track and AutoDJ rotation state.<br><br>
• <b>Public Stream:</b> Confirms audio byte throughput from the Icecast relay.<br><br>
• <b>Catalog Integrity:</b> Confirms all 569+ approved tracks are verified and playable.<br><br>
• <b>Health Status:</b> Green gauges indicate healthy telemetry. Diagnostic checks are 100% read-only and never interrupt audio."""
    ),
    (
        "🛡️ The 4-Tier Safety Level System",
        "Clear color-coding ensures you always know what is safe.",
        """• 🟢 <b>GREEN (Safe / Read-Only):</b> Telemetry checks, log inspection, folder viewing. Zero production changes.<br><br>
• 🟡 <b>YELLOW (Local Change):</b> Modifying local preferences, generating local builds, editing CMS drafts.<br><br>
• 🟠 <b>ORANGE (Remote Service Change):</b> Restarting VM systemd services. Always requires confirmation.<br><br>
• 🔴 <b>RED (Production / Destructive):</b> Promoting Cloudflare deployments, deleting media, restoring backups. Enforces structured impact verification."""
    ),
    (
        "🚀 Guarded Workflows & Rollbacks",
        "Zero-downtime deployments with verified rollback points.",
        """• <b>10-Step Safe Update Wizard:</b> Guarantees automated pre-update rollback snapshots before modifying any files.<br><br>
• <b>Cloudflare Preview Pipeline:</b> Test changes on private preview URLs before manual production promotion.<br><br>
• <b>Emergency Music Mirror:</b> High-availability local fallback music repository containing 575 verified audio tracks."""
    ),
    (
        "📖 In-App Guide & Contextual Help",
        "Searchable documentation built for non-developer operators.",
        """• <b>Searchable Guide Tab:</b> Access complete architectural references, app ownership maps, and troubleshooting instructions.<br><br>
• <b>Contextual '?' Help:</b> Click any inline question mark to jump directly to the relevant manual article.<br><br>
• <b>Protected Operator Mode:</b> Keeps advanced destructive actions securely locked behind pre-flight confirmations."""
    )
]


class TourDialog(QDialog):
    """First-run interactive tour modal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ALLTHINGS140 Hub — Operator Orientation")
        self.setFixedWidth(560)
        self.setFixedHeight(400)
        self.setModal(True)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 10px;
            }}
        """)

        self.current_slide = 0
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        # Slide Content Card
        self.card = QFrame()
        self.card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 18px;")
        c_layout = QVBoxLayout(self.card)
        c_layout.setSpacing(10)

        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {ACCENT_CYAN};")
        c_layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel()
        self.subtitle_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; font-weight: 600;")
        c_layout.addWidget(self.subtitle_lbl)

        self.body_lbl = QLabel()
        self.body_lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_PRIMARY}; line-height: 1.4;")
        self.body_lbl.setWordWrap(True)
        c_layout.addWidget(self.body_lbl, 1)

        layout.addWidget(self.card, 1)

        # Bottom row: Checkbox, Progress Dots, Navigation
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.chk_dont_show = QCheckBox("Don't show again")
        self.chk_dont_show.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        bottom_row.addWidget(self.chk_dont_show)

        bottom_row.addStretch()

        self.progress_lbl = QLabel("1 / 5")
        self.progress_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        bottom_row.addWidget(self.progress_lbl)

        self.btn_prev = QPushButton("◀ Back")
        self.btn_prev.clicked.connect(self._prev_slide)
        bottom_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setProperty("primary", "true")
        self.btn_next.clicked.connect(self._next_slide)
        bottom_row.addWidget(self.btn_next)

        layout.addLayout(bottom_row)
        self._render_slide()

    def _render_slide(self) -> None:
        title, sub, body = TOUR_SLIDES[self.current_slide]
        self.title_lbl.setText(title)
        self.subtitle_lbl.setText(sub)
        self.body_lbl.setText(body)
        self.progress_lbl.setText(f"{self.current_slide + 1} / {len(TOUR_SLIDES)}")
        self.btn_prev.setEnabled(self.current_slide > 0)
        self.btn_next.setText("Finish ✓" if self.current_slide == len(TOUR_SLIDES) - 1 else "Next ▶")

    def _prev_slide(self) -> None:
        if self.current_slide > 0:
            self.current_slide -= 1
            self._render_slide()

    def _next_slide(self) -> None:
        if self.current_slide < len(TOUR_SLIDES) - 1:
            self.current_slide += 1
            self._render_slide()
        else:
            self.accept()

    def dont_show_again(self) -> bool:
        return self.chk_dont_show.isChecked()
