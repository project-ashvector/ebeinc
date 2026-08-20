"""
ALLTHINGS140 Hub — Public Roadmap Management View
Zero-code-deploy CMS for managing public station milestones, phases, and release goals.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.services.site_content_service import RoadmapItem, SiteContentService
from hub.ui.components.confirm_dialog import ConfirmDialog
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class RoadmapEditDialog(QDialog):
    def __init__(self, roadmap: Optional[RoadmapItem] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Roadmap Milestone" if roadmap else "Add Roadmap Milestone")
        self.resize(540, 440)
        self.setStyleSheet(f"QDialog {{ background-color: {BG_DARK}; border: 1px solid {BORDER_LIGHT}; border-radius: 10px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Milestone Title:"))
        self.title_in = QLineEdit(roadmap.title if roadmap else "")
        layout.addWidget(self.title_in)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Quarter / Target:"))
        self.q_in = QLineEdit(roadmap.quarter if roadmap else "Q3 2026")
        r1.addWidget(self.q_in)

        r1.addWidget(QLabel("Phase:"))
        self.phase_in = QLineEdit(roadmap.phase if roadmap else "Phase 2")
        r1.addWidget(self.phase_in)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Status:"))
        self.status_in = QComboBox()
        self.status_in.addItems(["completed", "in-progress", "planned"])
        if roadmap:
            self.status_in.setCurrentText(roadmap.status)
        r2.addWidget(self.status_in)
        layout.addLayout(r2)

        layout.addWidget(QLabel("Milestone Description:"))
        self.desc_in = QTextEdit(roadmap.description if roadmap else "")
        self.desc_in.setFixedHeight(80)
        layout.addWidget(self.desc_in)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Save Milestone")
        btn_save.setProperty("primary", "true")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        return {
            "title": self.title_in.text().strip(),
            "quarter": self.q_in.text().strip(),
            "phase": self.phase_in.text().strip(),
            "status": self.status_in.currentText(),
            "description": self.desc_in.toPlainText().strip()
        }


class RoadmapView(QWidget):
    open_guide = Signal(str)

    def __init__(self, content_service: SiteContentService, parent=None):
        super().__init__(parent)
        self.content_service = content_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Public Station Roadmap",
            subtitle="Manage development milestones, upcoming platform features, and ecosystem release roadmaps.",
            guide_key="page-cloudflare",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="STATION ROADMAP MILESTONES",
            subtitle="Release targets displayed on public website roadmap",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_add = QPushButton("➕ Add Milestone")
        btn_add.setProperty("primary", "true")
        btn_add.clicked.connect(self._add)
        card.header_actions.addWidget(btn_add)

        self.table = DataTable(
            columns=["Title", "Target Quarter", "Phase", "Status", "Description"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 1, 2, 3]
        )
        self.table.setFixedHeight(340)
        card.add_widget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self._edit)
        btn_row.addWidget(btn_edit)
        btn_del = QPushButton("🗑️ Delete Milestone")
        btn_del.setProperty("danger", "true")
        btn_del.clicked.connect(self._delete)
        btn_row.addWidget(btn_del)
        card.add_layout(btn_row)

        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def refresh(self) -> None:
        items = self.content_service.roadmap
        self.table.setRowCount(len(items))
        for row_idx, r in enumerate(items):
            t_item = QTableWidgetItem(r.title)
            t_item.setData(Qt.UserRole, r.id)
            q_item = QTableWidgetItem(r.quarter)
            p_item = QTableWidgetItem(r.phase)
            s_item = QTableWidgetItem(r.status.upper())
            s_item.setForeground(Qt.green if r.status == "completed" else Qt.cyan if r.status == "in-progress" else Qt.gray)
            d_item = QTableWidgetItem(r.description)

            self.table.setItem(row_idx, 0, t_item)
            self.table.setItem(row_idx, 1, q_item)
            self.table.setItem(row_idx, 2, p_item)
            self.table.setItem(row_idx, 3, s_item)
            self.table.setItem(row_idx, 4, d_item)

    def _add(self) -> None:
        dialog = RoadmapEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            if d["title"]:
                self.content_service.add_roadmap_item(
                    title=d["title"],
                    description=d["description"],
                    quarter=d["quarter"],
                    phase=d["phase"],
                    status=d["status"]
                )
                self.refresh()

    def _edit(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        rid = item.data(Qt.UserRole)
        rm = next((r for r in self.content_service.roadmap if r.id == rid), None)
        if not rm:
            return
        dialog = RoadmapEditDialog(roadmap=rm, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            self.content_service.update_roadmap_item(rid, **d)
            self.refresh()

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        rid = item.data(Qt.UserRole)
        dialog = ConfirmDialog(
            title="Delete Milestone",
            message="Remove this roadmap milestone from website?",
            what_it_does="Deletes roadmap entry from radio/data/site-content.json.",
            what_it_touches="radio/data/site-content.json",
            expected_impact="Milestone will no longer appear on public website.",
            rollback_plan="Can be recreated.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Delete Milestone",
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.content_service.roadmap = [r for r in self.content_service.roadmap if r.id != rid]
            self.content_service.save()
            self.refresh()
