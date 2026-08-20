"""
ALLTHINGS140 Hub — Public Announcements View
Zero-code-deploy CMS for managing public site bulletins, news banners, and takeover alerts.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from hub.services.site_content_service import AnnouncementItem, SiteContentService
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


class AnnouncementEditDialog(QDialog):
    def __init__(self, announcement: Optional[AnnouncementItem] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Announcement" if not announcement else "Edit Announcement")
        self.resize(540, 440)
        self.setStyleSheet(f"QDialog {{ background-color: {BG_DARK}; border: 1px solid {BORDER_LIGHT}; border-radius: 10px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Announcement Headline / Title:"))
        self.title_in = QLineEdit(announcement.title if announcement else "")
        layout.addWidget(self.title_in)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Announcement Severity:"))
        self.type_in = QComboBox()
        self.type_in.addItems(["broadcast", "info", "event", "urgent"])
        if announcement:
            self.type_in.setCurrentText(announcement.type)
        r1.addWidget(self.type_in)
        layout.addLayout(r1)

        layout.addWidget(QLabel("Bulletin Message Body:"))
        self.content_in = QTextEdit(announcement.content if announcement else "")
        self.content_in.setFixedHeight(80)
        layout.addWidget(self.content_in)

        self.chk_web = QCheckBox("Target Web Listener Page (Header Banner)")
        self.chk_web.setChecked(True)
        self.chk_vis = QCheckBox("Target Visuals Overlay Stage (Ticker)")
        layout.addWidget(self.chk_web)
        layout.addWidget(self.chk_vis)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Save Announcement")
        btn_save.setProperty("primary", "true")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        planes = []
        if self.chk_web.isChecked():
            planes.append("web")
        if self.chk_vis.isChecked():
            planes.append("visuals")
        return {
            "title": self.title_in.text().strip(),
            "content": self.content_in.toPlainText().strip(),
            "type": self.type_in.currentText(),
            "targetPlanes": planes
        }


class AnnouncementsView(QWidget):
    open_guide = Signal(str)

    def __init__(self, content_service: SiteContentService, parent=None):
        super().__init__(parent)
        self.content_service = content_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Station Bulletins & Announcements",
            subtitle="Publish public news bulletins, urgent alerts, and schedule changes directly to listener portals.",
            guide_key="page-cloudflare",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="PUBLIC ANNOUNCEMENTS",
            subtitle="Active bulletins broadcast to listener web clients and visuals stage overlays",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_add = QPushButton("➕ Post Announcement")
        btn_add.setProperty("primary", "true")
        btn_add.clicked.connect(self._add)
        card.header_actions.addWidget(btn_add)

        self.table = DataTable(
            columns=["Title / Headline", "Severity", "Date", "Bulletin Message"],
            stretch_column_index=3,
            resize_to_contents_indices=[0, 1, 2]
        )
        self.table.setFixedHeight(340)
        card.add_widget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_del = QPushButton("🗑️ Delete Announcement")
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
        anns = self.content_service.announcements
        self.table.setRowCount(len(anns))
        for row_idx, a in enumerate(anns):
            t_item = QTableWidgetItem(a.title)
            t_item.setData(Qt.UserRole, a.id)
            ty_item = QTableWidgetItem(a.type.upper())
            ty_item.setForeground(Qt.yellow if a.type == "urgent" else Qt.cyan)
            d_item = QTableWidgetItem(a.date)
            c_item = QTableWidgetItem(a.content)

            self.table.setItem(row_idx, 0, t_item)
            self.table.setItem(row_idx, 1, ty_item)
            self.table.setItem(row_idx, 2, d_item)
            self.table.setItem(row_idx, 3, c_item)

    def _add(self) -> None:
        dialog = AnnouncementEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            if d["title"]:
                self.content_service.add_announcement(
                    title=d["title"],
                    content=d["content"],
                    ann_type=d["type"],
                    target_planes=d["targetPlanes"]
                )
                self.refresh()

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        aid = item.data(Qt.UserRole)
        dialog = ConfirmDialog(
            title="Delete Announcement",
            message="Remove this announcement from public view?",
            what_it_does="Deletes bulletin entry from radio/data/site-content.json.",
            what_it_touches="radio/data/site-content.json",
            expected_impact="Announcement will no longer be rendered on the website.",
            rollback_plan="Can be recreated.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Delete Bulletin",
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.content_service.delete_announcement(aid)
            self.refresh()
