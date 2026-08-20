"""
ALLTHINGS140 Hub — Operational Activity & Audit Log View
Displays full historical activity logs, filterable by component, action, and date.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hub.services.activity_service import ActivityItem, ActivityService
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
    STATUS_GREEN,
    STATUS_RED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ActivityView(QWidget):
    open_guide = Signal(str)

    def __init__(self, activity_service: ActivityService, parent=None):
        super().__init__(parent)
        self.activity_service = activity_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Operational Activity & Audit Log",
            subtitle="Immutable event log tracking all deployments, health scans, agent runs, and station operations.",
            guide_key="page-dashboard",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        card = SectionCard(
            title="AUDIT LOG ENTRIES",
            subtitle="Recorded in ~/.config/allthings140-hub/activity.json",
            guide_key="page-dashboard",
            safety_level="green"
        )

        # Filter row
        f_row = QHBoxLayout()
        f_row.setSpacing(10)

        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍 Search event details or components…")
        self.search_in.textChanged.connect(self.refresh_log)
        f_row.addWidget(self.search_in, 1)

        btn_clear = QPushButton("🗑️ Clear Audit Log")
        btn_clear.clicked.connect(self._clear_log)
        f_row.addWidget(btn_clear)
        card.add_layout(f_row)

        self.table = DataTable(
            columns=["Timestamp", "Component", "Action Type", "Status", "Event Detail"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 1, 2, 3]
        )
        self.table.setFixedHeight(400)
        card.add_widget(self.table)

        self.shell.add_widget(card)
        self.shell.add_stretch()

        self.refresh_log()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def refresh_log(self) -> None:
        query = self.search_in.text().strip().lower()
        items = self.activity_service.all_activities()
        if query:
            items = [i for i in items if query in i.detail.lower() or query in i.component.lower() or query in i.action.lower()]

        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            d_item = QTableWidgetItem(item.formattedDate)
            c_item = QTableWidgetItem(item.component)
            c_item.setForeground(Qt.cyan)
            a_item = QTableWidgetItem(item.action)
            s_item = QTableWidgetItem(item.result)
            s_item.setForeground(Qt.green if item.result == "SUCCESS" else Qt.yellow if item.result == "WARNING" else Qt.red)
            det_item = QTableWidgetItem(item.detail)

            self.table.setItem(row_idx, 0, d_item)
            self.table.setItem(row_idx, 1, c_item)
            self.table.setItem(row_idx, 2, a_item)
            self.table.setItem(row_idx, 3, s_item)
            self.table.setItem(row_idx, 4, det_item)

    def _clear_log(self) -> None:
        self.activity_service.clear()
        self.refresh_log()
