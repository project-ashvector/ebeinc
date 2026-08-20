"""
ALLTHINGS140 Hub — Report Library View
Discovers and views engineering reports, audits, repair summaries, and architectural docs.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.services.report_service import EngineeringReport, ReportService
from hub.services.system_service import SystemService
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ReportsView(QWidget):
    """Integrated report library and markdown reader."""

    open_guide = Signal(str)

    def __init__(self, report_service: ReportService, parent=None):
        super().__init__(parent)
        self.report_service = report_service
        self.current_category = "all"
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Engineering Reports & Architecture Library",
            subtitle="Explore project audits, architectural blueprints, handoff logs, and troubleshooting records.",
            guide_key="page-agents",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # Header Search Card
        search_card = QFrame()
        search_card.setStyleSheet(f"background: {BG_SURFACE}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 12px;")
        s_layout = QHBoxLayout(search_card)
        s_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search engineering reports, audits, and architecture docs…")
        self.search_input.textChanged.connect(self.filter_reports)
        s_layout.addWidget(self.search_input, 1)

        btn_rescan = QPushButton("🔄 Rescan Reports")
        btn_rescan.setToolTip("Scan workspace and documents folder for new markdown reports")
        btn_rescan.clicked.connect(self._rescan)
        s_layout.addWidget(btn_rescan)

        self.shell.add_widget(search_card)

        # Splitter: Left Table + Right Viewer
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {BORDER_SUBTLE}; width: 3px; }}")

        # Left: Table of Reports
        left_widget = QWidget()
        left_widget.setStyleSheet(f"background: {BG_DARK};")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.table = DataTable(
            columns=["Report Title", "Category", "Date"],
            stretch_column_index=0,
            resize_to_contents_indices=[1, 2]
        )
        self.table.itemSelectionChanged.connect(self._on_report_selected)
        left_layout.addWidget(self.table)

        splitter.addWidget(left_widget)

        # Right: Markdown Reader
        right_widget = QWidget()
        right_widget.setStyleSheet(f"background: {BG_DARK};")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        top_r = QHBoxLayout()
        self.report_title_lbl = QLabel("Select a report to view")
        self.report_title_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_PRIMARY};")
        top_r.addWidget(self.report_title_lbl, 1)

        self.btn_open_file = QPushButton("📄 Open Folder")
        self.btn_open_file.setEnabled(False)
        self.btn_open_file.setToolTip("Open folder containing this report")
        self.btn_open_file.clicked.connect(self._open_in_editor)
        top_r.addWidget(self.btn_open_file)
        right_layout.addLayout(top_r)

        self.reader = QTextEdit()
        self.reader.setReadOnly(True)
        self.reader.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                font-family: monospace;
                font-size: 12px;
                color: {TEXT_PRIMARY};
                padding: 14px;
            }}
        """)
        right_layout.addWidget(self.reader)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 680])

        self.shell.add_widget(splitter)
        self.filter_reports()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _rescan(self) -> None:
        self.report_service.reload()
        self.filter_reports()

    def filter_reports(self) -> None:
        query = self.search_input.text().strip()
        reports = self.report_service.search(query, self.current_category)

        self.table.setRowCount(len(reports))
        for row_idx, r in enumerate(reports):
            t_item = QTableWidgetItem(r.title)
            t_item.setData(Qt.UserRole, r.id)
            c_item = QTableWidgetItem(r.category.upper())
            c_item.setForeground(Qt.cyan)
            d_item = QTableWidgetItem(r.dateModified)

            self.table.setItem(row_idx, 0, t_item)
            self.table.setItem(row_idx, 1, c_item)
            self.table.setItem(row_idx, 2, d_item)

        if reports:
            self.table.selectRow(0)

    def _on_report_selected(self) -> None:
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        row = self.table.currentRow()
        item = self.table.item(row, 0)
        if not item:
            return
        report_id = item.data(Qt.UserRole)
        rep = self.report_service.get(report_id)
        if rep:
            self.report_title_lbl.setText(rep.title)
            content = self.report_service.get_content(rep.id)
            self.reader.setPlainText(content)
            self.btn_open_file.setEnabled(True)
            self.current_report_path = rep.path

    def _open_in_editor(self) -> None:
        if hasattr(self, "current_report_path") and self.current_report_path:
            SystemService.open_folder(self.current_report_path)
