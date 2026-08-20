"""
ALLTHINGS140 Hub — Takeovers & Transmission Archive Management View
Zero-code-deploy CMS for managing live DJ takeovers, artist bios, tracklists, and broadcast replays.
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

from hub.services.site_content_service import SiteContentService, TakeoverItem
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


class TakeoverEditDialog(QDialog):
    """Dialog for creating or editing a takeover artist entry."""

    def __init__(self, takeover: Optional[TakeoverItem] = None, content_service: Optional[SiteContentService] = None, parent=None):
        super().__init__(parent)
        self.takeover = takeover
        self.content_service = content_service
        self.setWindowTitle("Edit Takeover Artist" if takeover else "Add Takeover Artist")
        self.resize(580, 520)

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

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Artist / Host Name:"))
        self.artist_in = QLineEdit(takeover.artist if takeover else "")
        r1.addWidget(self.artist_in)

        r1.addWidget(QLabel("Status:"))
        self.status_in = QComboBox()
        self.status_in.addItems(["archive", "completed", "live", "upcoming"])
        if takeover:
            self.status_in.setCurrentText(takeover.status)
        r1.addWidget(self.status_in)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Air Date (YYYY-MM-DD):"))
        self.date_in = QLineEdit(takeover.date if takeover else "2026-08-17")
        r2.addWidget(self.date_in)

        r2.addWidget(QLabel("Air Time (e.g. 22:00 UTC):"))
        self.time_in = QLineEdit(takeover.time if takeover else "22:00 UTC")
        r2.addWidget(self.time_in)
        layout.addLayout(r2)

        layout.addWidget(QLabel("Logo / Image:"))
        logo_row = QHBoxLayout()
        self.logo_in = QLineEdit(takeover.logoUrl if takeover else "")
        self.logo_in.setPlaceholderText("Choose an image; Hub copies it into managed site assets")
        logo_row.addWidget(self.logo_in, 1)
        btn_logo = QPushButton("📁 Browse / Import")
        btn_logo.setToolTip("Choose a local image. Hub copies it into radio/assets/hub-managed/takeover/ and stores the relative path.")
        btn_logo.clicked.connect(self._browse_logo)
        logo_row.addWidget(btn_logo)
        layout.addLayout(logo_row)

        layout.addWidget(QLabel("Artist Bio / Station Intro:"))
        self.bio_in = QTextEdit(takeover.bio if takeover else "")
        self.bio_in.setFixedHeight(65)
        layout.addWidget(self.bio_in)

        layout.addWidget(QLabel("Featured Tracklist Highlights (comma separated):"))
        self.tracklist_in = QLineEdit(", ".join(takeover.tracklist) if takeover and takeover.tracklist else "")
        layout.addWidget(self.tracklist_in)

        layout.addWidget(QLabel("Replay Stream URL (optional):"))
        self.replay_in = QLineEdit(takeover.replayUrl if takeover else "")
        layout.addWidget(self.replay_in)

        self.chk_featured = QCheckBox("Featured Archive Highlight")
        self.chk_featured.setChecked(takeover.featured if takeover else False)
        layout.addWidget(self.chk_featured)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Takeover")
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
            rel = self.content_service.import_media(path, "takeover")
            self.logo_in.setText(rel)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", f"Could not import media: {exc}")

    def get_data(self) -> dict:
        tracks = [t.strip() for t in self.tracklist_in.text().split(",") if t.strip()]
        return {
            "artist": self.artist_in.text().strip(),
            "status": self.status_in.currentText(),
            "date": self.date_in.text().strip(),
            "time": self.time_in.text().strip(),
            "logoUrl": self.logo_in.text().strip(),
            "bio": self.bio_in.toPlainText().strip(),
            "tracklist": tracks,
            "replayUrl": self.replay_in.text().strip(),
            "featured": self.chk_featured.isChecked()
        }


class TakeoversView(QWidget):
    open_guide = Signal(str)

    def __init__(self, content_service: SiteContentService, parent=None):
        super().__init__(parent)
        self.content_service = content_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Takeovers & Transmission Archive",
            subtitle="Manage guest artist broadcasts, air times, bios, tracklists, and re-listen transmission archives.",
            guide_key="page-cloudflare",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="TAKEOVER ARTISTS & REPLAYS DIRECTORY",
            subtitle="Guest mixes and archived transmissions displayed on public listener portal",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_add = QPushButton("➕ Add Takeover Artist")
        btn_add.setProperty("primary", "true")
        btn_add.clicked.connect(self._add_takeover)
        card.header_actions.addWidget(btn_add)

        self.table = DataTable(
            columns=["Artist", "Date / Time", "Status", "Bio Excerpt", "Replay Available"],
            stretch_column_index=3,
            resize_to_contents_indices=[0, 1, 2, 4]
        )
        self.table.setFixedHeight(340)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        card.add_widget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self._edit_selected)
        btn_row.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Delete Takeover")
        btn_del.setProperty("danger", "true")
        btn_del.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_del)

        card.add_layout(btn_row)
        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_takeovers()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def refresh_takeovers(self) -> None:
        takeovers = self.content_service.takeovers
        self.table.setRowCount(len(takeovers))

        for row_idx, t in enumerate(takeovers):
            a_item = QTableWidgetItem(t.artist)
            a_item.setData(Qt.UserRole, t.id)
            d_item = QTableWidgetItem(f"{t.date} · {t.time}")
            s_item = QTableWidgetItem(t.status.upper())
            s_item.setForeground(Qt.cyan if t.status == "live" else Qt.green if t.status == "archive" else Qt.white)
            b_item = QTableWidgetItem(t.bio[:70])
            r_item = QTableWidgetItem("YES" if t.replayUrl else "—")

            self.table.setItem(row_idx, 0, a_item)
            self.table.setItem(row_idx, 1, d_item)
            self.table.setItem(row_idx, 2, s_item)
            self.table.setItem(row_idx, 3, b_item)
            self.table.setItem(row_idx, 4, r_item)

    def _add_takeover(self) -> None:
        dialog = TakeoverEditDialog(content_service=self.content_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            if d["artist"]:
                self.content_service.add_takeover(
                    artist=d["artist"],
                    logo_url=d["logoUrl"],
                    date=d["date"],
                    time_str=d["time"],
                    status=d["status"],
                    bio=d["bio"],
                    replay_url=d["replayUrl"],
                    tracklist=d["tracklist"],
                    featured=d["featured"]
                )
                self.refresh_takeovers()

    def _edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        tid = item.data(Qt.UserRole)
        takeover = next((t for t in self.content_service.takeovers if t.id == tid), None)
        if not takeover:
            return
        dialog = TakeoverEditDialog(takeover=takeover, content_service=self.content_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            self.content_service.update_takeover(tid, **d)
            self.refresh_takeovers()

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._edit_selected()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        tid = item.data(Qt.UserRole)
        takeover = next((t for t in self.content_service.takeovers if t.id == tid), None)
        if not takeover:
            return

        dialog = ConfirmDialog(
            title=f"Delete Takeover: {takeover.artist}",
            message=f"Permanently remove takeover archive entry for '{takeover.artist}'?",
            what_it_does=f"Removes '{takeover.artist}' from radio/data/site-content.json.",
            what_it_touches="radio/data/site-content.json",
            expected_impact="Artist archive entry will no longer be visible on public transmission archive.",
            rollback_plan="Can be re-added or restored from a verified backup/source-control state if one exists.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Delete Takeover Entry",
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.content_service.delete_takeover(tid)
            self.refresh_takeovers()
