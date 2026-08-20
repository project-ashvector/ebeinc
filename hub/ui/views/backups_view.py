"""
ALLTHINGS140 Hub — Backup Center View
Manages workstation backups, snapshots, rollback archives, and disaster recovery.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hub.services.backup_service import BackupService, BackupSnapshot
from hub.services.system_service import SystemService
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class BackupsView(QWidget):
    """View displaying backup snapshots and disaster recovery tooling."""

    open_guide = Signal(str)

    def __init__(self, backup_service: BackupService, parent=None):
        super().__init__(parent)
        self.backup_service = backup_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Station Backups & Disaster Recovery",
            subtitle="Immutable snapshot archives, pre-deployment restore points, and emergency music library fallbacks.",
            guide_key="page-backups",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # Main Card
        card = SectionCard(
            title="SNAPSHOT ARCHIVES INVENTORY (backups/)",
            subtitle="Verified .tar.gz archives created prior to updates and deployments",
            guide_key="page-backups",
            safety_level="green"
        )

        btn_create = QPushButton("💾 Create New Snapshot")
        btn_create.setProperty("primary", "true")
        btn_create.setToolTip("Create immediate snapshot of broadcast engine and visuals")
        btn_create.clicked.connect(self._create_snapshot)
        card.header_actions.addWidget(btn_create)

        btn_folder = QPushButton("📁 Open Backups Folder")
        btn_folder.setToolTip("Open local backups folder on workstation")
        btn_folder.clicked.connect(self._open_folder)
        card.header_actions.addWidget(btn_folder)

        self.table = DataTable(
            columns=["Snapshot Name", "Component", "Type", "Created Date", "Size"],
            stretch_column_index=0,
            resize_to_contents_indices=[1, 2, 3, 4]
        )
        self.table.setFixedHeight(380)
        card.add_widget(self.table)

        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_backups()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def refresh_backups(self) -> None:
        backups = self.backup_service.all()
        self.table.setRowCount(len(backups))

        for row_idx, b in enumerate(backups):
            n_item = QTableWidgetItem(b.name)
            c_item = QTableWidgetItem(b.component)
            t_item = QTableWidgetItem(b.backupType.upper())
            t_item.setForeground(Qt.cyan)
            d_item = QTableWidgetItem(b.dateFormatted)
            s_item = QTableWidgetItem(b.sizeFormatted)

            self.table.setItem(row_idx, 0, n_item)
            self.table.setItem(row_idx, 1, c_item)
            self.table.setItem(row_idx, 2, t_item)
            self.table.setItem(row_idx, 3, d_item)
            self.table.setItem(row_idx, 4, s_item)

    def _open_folder(self) -> None:
        SystemService.open_folder(self.backup_service.project_root / "backups")

    def _create_snapshot(self) -> None:
        try:
            snap = self.backup_service.create_component_backup(
                component_name="station-manual",
                source_paths=["radio/visuals/index.html", "tools/server.py", "tools/dj_app.py"]
            )
            self.refresh_backups()
            QMessageBox.information(self, "Backup Created", f"Created station snapshot:\n\n{snap.name} ({snap.sizeFormatted})")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", f"Could not create snapshot: {e}")
