"""
ALLTHINGS140 Hub — Sponsors Management View
Zero-code-deploy CMS for managing station and website sponsors, tiers, logos, and campaigns.
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
    QFrame,
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

from hub.services.site_content_service import SiteContentService, SponsorItem
from hub.ui.components.confirm_dialog import ConfirmDialog
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
    SAFETY_RED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SponsorEditDialog(QDialog):
    """Dialog for creating or editing a sponsor entry."""

    def __init__(self, sponsor: Optional[SponsorItem] = None, content_service: Optional[SiteContentService] = None, parent=None):
        super().__init__(parent)
        self.sponsor = sponsor
        self.content_service = content_service
        self.setWindowTitle("Edit Sponsor" if sponsor else "Add New Sponsor")
        self.resize(540, 500)

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

        layout.addWidget(QLabel("Sponsor Brand Name:"))
        self.name_in = QLineEdit(sponsor.name if sponsor else "")
        layout.addWidget(self.name_in)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Sponsorship Tier:"))
        self.tier_in = QComboBox()
        self.tier_in.addItems(["Headline", "Stage", "Underground", "Community"])
        if sponsor:
            self.tier_in.setCurrentText(sponsor.tier)
        r1.addWidget(self.tier_in)
        layout.addLayout(r1)

        layout.addWidget(QLabel("Logo / Image:"))
        logo_row = QHBoxLayout()
        self.logo_in = QLineEdit(sponsor.logoUrl if sponsor else "")
        self.logo_in.setPlaceholderText("Choose an image; Hub copies it into managed site assets")
        logo_row.addWidget(self.logo_in, 1)
        btn_logo = QPushButton("📁 Browse / Import")
        btn_logo.setToolTip("Choose a local image. Hub copies it into radio/assets/hub-managed/sponsor/ and stores the relative path.")
        btn_logo.clicked.connect(self._browse_logo)
        logo_row.addWidget(btn_logo)
        layout.addLayout(logo_row)

        layout.addWidget(QLabel("Website URL:"))
        self.url_in = QLineEdit(sponsor.websiteUrl if sponsor else "https://")
        layout.addWidget(self.url_in)

        layout.addWidget(QLabel("Sponsor Description / Copy:"))
        self.desc_in = QTextEdit(sponsor.description if sponsor else "")
        self.desc_in.setFixedHeight(70)
        layout.addWidget(self.desc_in)

        r2 = QHBoxLayout()
        self.chk_active = QCheckBox("Active on Public Website")
        self.chk_active.setChecked(sponsor.active if sponsor else True)
        r2.addWidget(self.chk_active)

        self.chk_featured = QCheckBox("Featured Highlight")
        self.chk_featured.setChecked(sponsor.featured if sponsor else False)
        r2.addWidget(self.chk_featured)
        layout.addLayout(r2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Sponsor")
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
            rel = self.content_service.import_media(path, "sponsor")
            self.logo_in.setText(rel)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", f"Could not import media: {exc}")

    def get_data(self) -> dict:
        return {
            "name": self.name_in.text().strip(),
            "tier": self.tier_in.currentText(),
            "logoUrl": self.logo_in.text().strip(),
            "websiteUrl": self.url_in.text().strip(),
            "description": self.desc_in.toPlainText().strip(),
            "active": self.chk_active.isChecked(),
            "featured": self.chk_featured.isChecked()
        }


class SponsorsView(QWidget):
    """View managing site sponsors."""

    open_guide = Signal(str)

    def __init__(self, content_service: SiteContentService, parent=None):
        super().__init__(parent)
        self.content_service = content_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Station Sponsors & Brand Partners",
            subtitle="Manage sponsor tiers, logos, website links, and public copy displayed on the listener portal.",
            guide_key="page-cloudflare",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="ACTIVE SPONSORS DIRECTORY",
            subtitle="Changes update local JSON state immediately and go live on next Cloudflare deployment.",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_add = QPushButton("➕ Add New Sponsor")
        btn_add.setProperty("primary", "true")
        btn_add.clicked.connect(self._add_sponsor)
        card.header_actions.addWidget(btn_add)

        self.table = DataTable(
            columns=["Sponsor Name", "Tier", "Website", "Active", "Featured"],
            stretch_column_index=0,
            resize_to_contents_indices=[1, 3, 4]
        )
        self.table.setFixedHeight(340)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        card.add_widget(self.table)

        # Actions Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self._edit_selected)
        btn_row.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Delete Sponsor")
        btn_del.setProperty("danger", "true")
        btn_del.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_del)

        card.add_layout(btn_row)
        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_sponsors()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def refresh_sponsors(self) -> None:
        sponsors = self.content_service.sponsors
        self.table.setRowCount(len(sponsors))

        for row_idx, s in enumerate(sponsors):
            n_item = QTableWidgetItem(s.name)
            n_item.setData(Qt.UserRole, s.id)
            t_item = QTableWidgetItem(s.tier.upper())
            t_item.setForeground(Qt.cyan if s.tier == "Headline" else Qt.white)
            u_item = QTableWidgetItem(s.websiteUrl)
            a_item = QTableWidgetItem("YES" if s.active else "NO")
            a_item.setForeground(Qt.green if s.active else Qt.gray)
            f_item = QTableWidgetItem("★ FEATURED" if s.featured else "—")
            f_item.setForeground(Qt.yellow if s.featured else Qt.gray)

            self.table.setItem(row_idx, 0, n_item)
            self.table.setItem(row_idx, 1, t_item)
            self.table.setItem(row_idx, 2, u_item)
            self.table.setItem(row_idx, 3, a_item)
            self.table.setItem(row_idx, 4, f_item)

    def _add_sponsor(self) -> None:
        dialog = SponsorEditDialog(content_service=self.content_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            if d["name"]:
                self.content_service.add_sponsor(
                    name=d["name"],
                    logo_url=d["logoUrl"],
                    website=d["websiteUrl"],
                    description=d["description"],
                    tier=d["tier"],
                    active=d["active"],
                    featured=d["featured"]
                )
                self.refresh_sponsors()

    def _edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        sid = item.data(Qt.UserRole)
        sponsor = next((s for s in self.content_service.sponsors if s.id == sid), None)
        if not sponsor:
            return
        dialog = SponsorEditDialog(sponsor=sponsor, content_service=self.content_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            self.content_service.update_sponsor(sid, **d)
            self.refresh_sponsors()

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._edit_selected()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        sid = item.data(Qt.UserRole)
        sponsor = next((s for s in self.content_service.sponsors if s.id == sid), None)
        if not sponsor:
            return

        dialog = ConfirmDialog(
            title=f"Delete Sponsor: {sponsor.name}",
            message=f"Permanently remove sponsor '{sponsor.name}' from website configuration?",
            what_it_does=f"Removes '{sponsor.name}' entry from radio/data/site-content.json.",
            what_it_touches="radio/data/site-content.json",
            expected_impact="Sponsor will no longer be rendered on the website upon next deployment.",
            rollback_plan="Can be re-added or restored from a verified backup/source-control state if one exists.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Delete Sponsor Entry",
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.content_service.delete_sponsor(sid)
            self.refresh_sponsors()
