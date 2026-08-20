"""
ALLTHINGS140 Hub — Settings View
Modular settings tabs for Projects, AI Providers, Connected PCs, Shared Folders, and Advanced.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hub.config import CONFIG_DIR, CONFIG_FILE, get_config, save_config
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.components.tour_dialog import TourDialog
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_ORANGE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsView(QWidget):
    """Modular settings management view."""

    open_guide = Signal(str)
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Hub Preferences & Station Configuration",
            subtitle="Manage project root paths, connected infrastructure nodes, AI models, and operator safety modes.",
            guide_key="start-here",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        tabs = QTabWidget()

        # Tab 1: Operator Safety & Workflow
        t_safety = QWidget()
        l_safety = QVBoxLayout(t_safety)
        l_safety.setContentsMargins(16, 16, 16, 16)
        l_safety.setSpacing(14)

        card_safe = SectionCard(
            title="PROTECTED OPERATOR MODE",
            subtitle="Locks advanced destructive actions behind pre-flight structured impact confirmations.",
            guide_key="start-here",
            safety_level="green"
        )

        self.chk_protected = QCheckBox("Enable Protected Operator Mode (Recommended)")
        self.chk_protected.setChecked(self.config.protected_operator_mode)
        self.chk_protected.setStyleSheet("font-size: 13px; font-weight: bold;")
        card_safe.add_widget(self.chk_protected)

        expl_lbl = QLabel("When enabled: Prevents accidental destructive actions (e.g. production deployments, server restarts, media deletions) without structured multi-point verification.")
        expl_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.3;")
        expl_lbl.setWordWrap(True)
        card_safe.add_widget(expl_lbl)

        self.chk_auto_backup = QCheckBox("Verified local rollback snapshot is mandatory during update preflight")
        self.chk_auto_backup.setChecked(True)
        self.chk_auto_backup.setEnabled(False)
        self.chk_auto_backup.setToolTip("Safety requirement: update preflight always creates and verifies a local snapshot before tests/builds.")
        card_safe.add_widget(self.chk_auto_backup)

        self.chk_notif = QCheckBox("Desktop notifications (not implemented in v1.2.1)")
        self.chk_notif.setChecked(False)
        self.chk_notif.setEnabled(False)
        self.chk_notif.setToolTip("Reserved for a future release; the Hub will not claim notifications are active.")
        card_safe.add_widget(self.chk_notif)

        l_safety.addWidget(card_safe)

        # Tour re-run card
        card_tour = SectionCard(
            title="OPERATOR ORIENTATION TOUR",
            subtitle="Interactive 5-step walkthrough explaining ecosystem planes, safety colors, and 24/7 independence.",
            guide_key="start-here",
            safety_level="green"
        )
        btn_tour = QPushButton("▶ Launch Operator Orientation Tour")
        btn_tour.setProperty("primary", "true")
        btn_tour.clicked.connect(self._launch_tour)
        card_tour.add_widget(btn_tour)
        l_safety.addWidget(card_tour)

        l_safety.addStretch()
        tabs.addTab(t_safety, "🛡️ Safety & Workflow")

        # Tab 2: Projects
        t_proj = QWidget()
        l_proj = QVBoxLayout(t_proj)
        l_proj.setContentsMargins(16, 16, 16, 16)
        l_proj.setSpacing(12)

        card_proj = SectionCard(title="PRIMARY REPOSITORY ROOT", subtitle="Local Git workspace directory")
        self.proj_root_in = QLineEdit(self.config.current_project_path)
        card_proj.add_widget(self.proj_root_in)
        l_proj.addWidget(card_proj)
        l_proj.addStretch()
        tabs.addTab(t_proj, "📁 Projects")

        # Tab 3: AI Providers
        t_ai = QWidget()
        l_ai = QVBoxLayout(t_ai)
        l_ai.setContentsMargins(16, 16, 16, 16)
        l_ai.setSpacing(12)

        for p_id, p_data in self.config.ai_providers.items():
            box = QFrame()
            box.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 12px;")
            b_l = QVBoxLayout(box)
            b_l.setSpacing(4)
            b_l.addWidget(QLabel(f"<b>{p_data.get('name', p_id)}</b>"))
            b_l.addWidget(QLabel(f"Executable: <code>{p_data.get('executable')}</code>"))
            l_ai.addWidget(box)

        l_ai.addStretch()
        tabs.addTab(t_ai, "🤖 AI Providers")

        # Tab 4: Connected Infrastructure
        t_pcs = QWidget()
        l_pcs = QVBoxLayout(t_pcs)
        l_pcs.setContentsMargins(16, 16, 16, 16)
        l_pcs.setSpacing(10)

        for pc in self.config.connected_pcs:
            p_box = QFrame()
            p_box.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 12px;")
            pb_l = QVBoxLayout(p_box)
            pb_l.setSpacing(4)
            pb_l.addWidget(QLabel(f"<b>{pc.get('name')}</b> ({pc.get('hostname_or_ip')})"))
            pb_l.addWidget(QLabel(f"Role: {pc.get('role')} • Tailscale: {pc.get('tailscale_name')}"))
            l_pcs.addWidget(p_box)

        l_pcs.addStretch()
        tabs.addTab(t_pcs, "🖥️ Connected Hosts")

        # Tab 5: Shared Folders
        t_folders = QWidget()
        l_folders = QVBoxLayout(t_folders)
        l_folders.setContentsMargins(16, 16, 16, 16)
        l_folders.setSpacing(10)

        for sf in self.config.shared_folders:
            f_box = QFrame()
            f_box.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 12px;")
            fb_l = QVBoxLayout(f_box)
            fb_l.setSpacing(4)
            fb_l.addWidget(QLabel(f"<b>{sf.get('name')}</b> — <code>{sf.get('path')}</code>"))
            fb_l.addWidget(QLabel(sf.get('description', '')))
            l_folders.addWidget(f_box)

        l_folders.addStretch()
        tabs.addTab(t_folders, "📂 Shared Folders")

        self.shell.add_widget(tabs)

        # Save Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_save = QPushButton("💾 Save Preferences")
        btn_save.setProperty("primary", "true")
        btn_save.setToolTip("Save configuration preferences to config.json")
        btn_save.clicked.connect(self._save_settings)
        btn_row.addWidget(btn_save)

        self.shell.add_layout(btn_row)
        self.shell.add_stretch()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _launch_tour(self) -> None:
        tour = TourDialog(parent=self)
        tour.exec_()

    def _save_settings(self) -> None:
        self.config.current_project_path = self.proj_root_in.text().strip()
        self.config.notifications_enabled = False
        self.config.safe_update_auto_backup = True
        self.config.protected_operator_mode = self.chk_protected.isChecked()
        save_config(self.config)
        self.settings_changed.emit()
        QMessageBox.information(self, "Settings Saved", "Preferences saved. Changes to the primary repository path take effect after restarting the Hub so every service uses the same root.")
