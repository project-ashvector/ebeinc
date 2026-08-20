"""
ALLTHINGS140 Hub — Site Media Asset Library View
Manages public site logos, artwork, video backgrounds, and tracks active usage.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
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

from hub.services.site_content_service import MediaAsset, SiteContentService
from hub.services.system_service import SystemService
from hub.ui.components.confirm_dialog import ConfirmDialog
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_RED,
    SAFETY_YELLOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class MediaLibraryView(QWidget):
    """View managing site assets in radio/assets/."""

    open_guide = Signal(str)

    def __init__(self, content_service: SiteContentService, parent=None):
        super().__init__(parent)
        self.content_service = content_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Site Media & Asset Library",
            subtitle="Catalog and inspect logos, flyers, background MP4s, and SVG icons stored in radio/assets/.",
            guide_key="page-media",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # Main Table Card
        card = SectionCard(
            title="MEDIA ASSETS INVENTORY",
            subtitle="Static scan checks radio/index.html, styles.css, and CMS data. Unreferenced assets may be loaded dynamically for takeovers or staging.",
            guide_key="page-media",
            safety_level="green"
        )

        # Header action buttons
        btn_upload = QPushButton("➕ Import Media")
        btn_upload.setProperty("primary", "true")
        btn_upload.setToolTip("Copy a selected image/video into the Hub-managed site assets folder")
        btn_upload.clicked.connect(self._import_media)
        card.header_actions.addWidget(btn_upload)

        btn_rescan = QPushButton("🔄 Rescan Assets")
        btn_rescan.setToolTip("Rescan disk and HTML templates for asset references")
        btn_rescan.clicked.connect(self._rescan)
        card.header_actions.addWidget(btn_rescan)

        btn_folder = QPushButton("📁 Open Assets Folder")
        btn_folder.setToolTip(f"Open {self.content_service.assets_dir}")
        btn_folder.clicked.connect(lambda: SystemService.open_folder(self.content_service.assets_dir))
        card.header_actions.addWidget(btn_folder)

        # DataTable
        self.table = DataTable(
            columns=["Filename", "Category", "Size", "Upload Date", "Active Usage References"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 1, 2, 3]
        )
        self.table.setMinimumHeight(400)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        card.add_widget(self.table)

        # Bottom Actions Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.selected_info_lbl = QLabel("Select an asset to view details or remove.")
        self.selected_info_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        btn_row.addWidget(self.selected_info_lbl, 1)

        self.btn_del = QPushButton("📦 Quarantine Asset")
        self.btn_del.setProperty("danger", "true")
        self.btn_del.setEnabled(False)
        self.btn_del.setToolTip("Select an asset from the table first to enable deletion.")
        self.btn_del.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_del)

        card.add_layout(btn_row)
        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_assets()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                self.btn_del.setEnabled(True)
                self.btn_del.setToolTip(f"Move '{item.text()}' to reversible quarantine")
                self.selected_info_lbl.setText(f"Selected: {item.text()}")
                self.selected_info_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px; font-weight: bold;")
                return
        self.btn_del.setEnabled(False)
        self.btn_del.setToolTip("Select an asset from the table first to enable deletion.")
        self.selected_info_lbl.setText("Select an asset to view details or remove.")
        self.selected_info_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

    def _rescan(self) -> None:
        self.content_service.scan_media_assets()
        self.refresh_assets()

    def refresh_assets(self) -> None:
        assets = self.content_service.media_assets
        self.table.setRowCount(len(assets))

        for row_idx, a in enumerate(assets):
            f_item = QTableWidgetItem(a.filename)
            f_item.setData(Qt.UserRole, a.absolutePath)
            c_item = QTableWidgetItem(a.usageCategory.upper())
            c_item.setForeground(Qt.cyan)
            s_item = QTableWidgetItem(a.sizeFormatted)
            d_item = QTableWidgetItem(a.uploadDate)

            if a.usedIn:
                u_text = f"Active: {', '.join(a.usedIn)}"
                u_item = QTableWidgetItem(u_text)
                u_item.setForeground(Qt.green)
            else:
                u_text = "Unreferenced in static code (Verify before deletion)"
                u_item = QTableWidgetItem(u_text)
                u_item.setForeground(Qt.yellow)

            self.table.setItem(row_idx, 0, f_item)
            self.table.setItem(row_idx, 1, c_item)
            self.table.setItem(row_idx, 2, s_item)
            self.table.setItem(row_idx, 3, d_item)
            self.table.setItem(row_idx, 4, u_item)

    def _import_media(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Site Media", "", "Media (*.png *.webp *.jpg *.jpeg *.svg *.mp4)")
        if not path:
            return
        try:
            rel = self.content_service.import_media(path, "general")
            self._rescan()
            QMessageBox.information(self, "Media Imported", f"Imported as:\n{rel}")
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        path = item.data(Qt.UserRole)
        filename = item.text()

        asset = next((a for a in self.content_service.media_assets if a.absolutePath == path), None)
        in_use = bool(asset and asset.usedIn)
        if in_use:
            QMessageBox.warning(self, "Asset In Use", f"{filename} is referenced by: {', '.join(asset.usedIn)}. Remove those references first; Hub will not quarantine an actively used asset.")
            return
        impact_warning = "No static/CMS references were detected. Dynamic runtime references cannot be proven, so the file will be moved to reversible quarantine rather than deleted."

        dialog = ConfirmDialog(
            title=f"Quarantine Asset: {filename}",
            message=f"Move '{filename}' out of live site assets into quarantine?",
            what_it_does=f"Moves '{filename}' into backups/site-media-quarantine so it can be restored.",
            what_it_touches=f"Path: {path}",
            expected_impact=impact_warning,
            rollback_plan="File is preserved in a timestamped quarantine folder and can be restored manually.",
            affects_live_station=False,
            safety_level="red",
            confirm_label="Quarantine Asset",
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            try:
                dest = self.content_service.quarantine_media(path)
                self._rescan()
                QMessageBox.information(self, "Asset Quarantined", f"Asset moved safely to:\n{dest}")
            except Exception as exc:
                QMessageBox.critical(self, "Quarantine Failed", f"Could not quarantine asset: {exc}")
