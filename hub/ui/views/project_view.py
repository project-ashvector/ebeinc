"""
ALLTHINGS140 Hub — Project Workspaces View
Multi-repository explorer, branch inspector, and quick terminal launchers.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hub.services.project_service import ProjectInfo, ProjectService
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
    STATUS_AMBER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ProjectView(QWidget):
    open_guide = Signal(str)

    def __init__(self, project_service: ProjectService, parent=None):
        super().__init__(parent)
        self.project_service = project_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Local Git Workspaces & Branches",
            subtitle="Explore project directories, active branches, uncommitted git modifications, and quick actions.",
            guide_key="app-roles",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="REGISTERED CODEBASE WORKSPACES",
            subtitle="Local repositories under /home/ebmarah/Projects/",
            guide_key="app-roles",
            safety_level="green"
        )

        btn_rescan = QPushButton("🔄 Rescan Repositories")
        btn_rescan.clicked.connect(self.refresh_projects)
        card.header_actions.addWidget(btn_rescan)

        self.table = DataTable(
            columns=["Workspace Name", "Relative Path", "Git Branch", "Git Status", "Last Commit"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 1, 2, 3]
        )
        self.table.setFixedHeight(340)
        self.table.itemSelectionChanged.connect(self._on_sel_changed)
        card.add_widget(self.table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_folder = QPushButton("📁 Open Folder")
        self.btn_folder.setEnabled(False)
        self.btn_folder.clicked.connect(self._open_folder)
        btn_row.addWidget(self.btn_folder)

        self.btn_term = QPushButton("💻 Open Terminal")
        self.btn_term.setProperty("primary", "true")
        self.btn_term.setEnabled(False)
        self.btn_term.clicked.connect(self._open_terminal)
        btn_row.addWidget(self.btn_term)

        card.add_layout(btn_row)
        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_projects()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _on_sel_changed(self) -> None:
        row = self.table.currentRow()
        has_sel = row >= 0
        self.btn_folder.setEnabled(has_sel)
        self.btn_term.setEnabled(has_sel)

    def refresh_projects(self) -> None:
        projects = self.project_service.discover_projects()
        self.table.setRowCount(len(projects))

        for row_idx, p in enumerate(projects):
            n_item = QTableWidgetItem(p.displayName)
            n_item.setData(Qt.UserRole, p.path)
            pth_item = QTableWidgetItem(p.relativePath or ".")
            b_item = QTableWidgetItem(p.gitBranch)
            b_item.setForeground(Qt.cyan)

            s_item = QTableWidgetItem("DIRTY (Uncommitted)" if p.isDirty else "CLEAN")
            s_item.setForeground(Qt.yellow if p.isDirty else Qt.green)

            c_item = QTableWidgetItem(f"{p.gitHead} — {p.lastCommitMessage}")

            self.table.setItem(row_idx, 0, n_item)
            self.table.setItem(row_idx, 1, pth_item)
            self.table.setItem(row_idx, 2, b_item)
            self.table.setItem(row_idx, 3, s_item)
            self.table.setItem(row_idx, 4, c_item)

    def _open_folder(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        path = item.data(Qt.UserRole)
        SystemService.open_folder(path)

    def _open_terminal(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        path = item.data(Qt.UserRole)
        SystemService.open_terminal(path, f"Workspace: {item.text()}")
