"""
ALLTHINGS140 Hub — Partners Management View
Zero-code-deploy CMS for managing underground record labels, sound systems, and festival partners.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.services.site_content_service import PartnerItem, SiteContentService
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


class PartnerEditDialog(QDialog):
    def __init__(self, partner: Optional[PartnerItem] = None, content_service: Optional[SiteContentService] = None, parent=None):
        super().__init__(parent)
        self.partner = partner
        self.content_service = content_service
        self.setWindowTitle("Edit Partner" if partner else "Add New Partner")
        self.resize(540, 480)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Partner Name:"))
        self.name_in = QLineEdit(partner.name if partner else "")
        layout.addWidget(self.name_in)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Category:"))
        self.cat_in = QComboBox()
        self.cat_in.addItems(["Record Label", "Sound System", "Collective", "Festival", "Gear & Studio", "Media"])
        if partner:
            self.cat_in.setCurrentText(partner.category)
        r1.addWidget(self.cat_in)
        layout.addLayout(r1)

        layout.addWidget(QLabel("Logo / Image:"))
        logo_row = QHBoxLayout()
        self.logo_in = QLineEdit(partner.logoUrl if partner else "")
        self.logo_in.setPlaceholderText("Choose an image; Hub copies it into managed site assets")
        logo_row.addWidget(self.logo_in, 1)
        btn_logo = QPushButton("📁 Browse / Import")
        btn_logo.setToolTip("Choose a local image. Hub copies it into radio/assets/hub-managed/partner/ and stores the relative path.")
        btn_logo.clicked.connect(self._browse_logo)
        logo_row.addWidget(btn_logo)
        layout.addLayout(logo_row)

        layout.addWidget(QLabel("Website URL:"))
        self.url_in = QLineEdit(partner.websiteUrl if partner else "https://")
        layout.addWidget(self.url_in)

        layout.addWidget(QLabel("Partner Description / Mission:"))
        self.desc_in = QTextEdit(partner.description if partner else "")
        self.desc_in.setFixedHeight(70)
        layout.addWidget(self.desc_in)

        self.chk_active = QCheckBox("Active on Public Website")
        self.chk_active.setChecked(partner.active if partner else True)
        layout.addWidget(self.chk_active)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Partner")
        btn_save.setProperty("primary", "true")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _browse_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose Logo / Image", str(Path.home()), "Images (*.png *.webp *.jpg *.jpeg *.svg);;All supported (*.png *.webp *.jpg *.jpeg *.svg *.mp4)")
        if not path:
            return
        if not self.content_service:
            self.logo_in.setText(path)
            return
        try:
            rel = self.content_service.import_media(path, "partner")
            self.logo_in.setText(rel)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", f"Could not import media: {exc}")

    def get_data(self) -> dict:
        return {
            "name": self.name_in.text().strip(),
            "category": self.cat_in.currentText(),
            "logoUrl": self.logo_in.text().strip(),
            "websiteUrl": self.url_in.text().strip(),
            "description": self.desc_in.toPlainText().strip(),
            "active": self.chk_active.isChecked()
        }


class PartnersView(QWidget):
    open_guide = Signal(str)

    def __init__(self, content_service: SiteContentService, parent=None):
        super().__init__(parent)
        self.content_service = content_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Ecosystem Partners & Labels",
            subtitle="Manage underground record labels, sound systems, and festival collectives affiliated with ALLTHINGS140.",
            guide_key="page-cloudflare",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="PARTNERS DIRECTORY",
            subtitle="Public affiliates displayed on the website partner roster",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_add = QPushButton("➕ Add New Partner")
        btn_add.setProperty("primary", "true")
        btn_add.clicked.connect(self._add_partner)
        card.header_actions.addWidget(btn_add)

        self.table = DataTable(
            columns=["Partner Name", "Category", "Website", "Active"],
            stretch_column_index=0,
            resize_to_contents_indices=[1, 3]
        )
        self.table.setFixedHeight(340)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        card.add_widget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self._edit_selected)
        btn_row.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Delete Partner")
        btn_del.setProperty("danger", "true")
        btn_del.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_del)

        card.add_layout(btn_row)
        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_partners()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def refresh_partners(self) -> None:
        partners = self.content_service.partners
        self.table.setRowCount(len(partners))

        for row_idx, p in enumerate(partners):
            n_item = QTableWidgetItem(p.name)
            n_item.setData(Qt.UserRole, p.id)
            c_item = QTableWidgetItem(p.category.upper())
            c_item.setForeground(Qt.cyan)
            u_item = QTableWidgetItem(p.websiteUrl)
            a_item = QTableWidgetItem("YES" if p.active else "NO")
            a_item.setForeground(Qt.green if p.active else Qt.gray)

            self.table.setItem(row_idx, 0, n_item)
            self.table.setItem(row_idx, 1, c_item)
            self.table.setItem(row_idx, 2, u_item)
            self.table.setItem(row_idx, 3, a_item)

    def _add_partner(self) -> None:
        dialog = PartnerEditDialog(content_service=self.content_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            if d["name"]:
                self.content_service.add_partner(
                    name=d["name"],
                    logo_url=d["logoUrl"],
                    website=d["websiteUrl"],
                    description=d["description"],
                    category=d["category"],
                    active=d["active"]
                )
                self.refresh_partners()

    def _edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        pid = item.data(Qt.UserRole)
        partner = next((p for p in self.content_service.partners if p.id == pid), None)
        if not partner:
            return
        dialog = PartnerEditDialog(partner=partner, content_service=self.content_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            self.content_service.update_partner(pid, **d)
            self.refresh_partners()

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._edit_selected()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        pid = item.data(Qt.UserRole)
        partner = next((p for p in self.content_service.partners if p.id == pid), None)
        if not partner:
            return

        dialog = ConfirmDialog(
            title=f"Delete Partner: {partner.name}",
            message=f"Remove partner '{partner.name}' from website configuration?",
            what_it_does=f"Removes partner entry from radio/data/site-content.json.",
            what_it_touches="radio/data/site-content.json",
            expected_impact="Partner will no longer appear on public website upon next deployment.",
            rollback_plan="Can be re-added or restored from a verified backup/source-control state if one exists.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Delete Partner",
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.content_service.delete_partner(pid)
            self.refresh_partners()
