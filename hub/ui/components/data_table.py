"""
ALLTHINGS140 Hub — Standardized Data Table Component
Provides responsive column stretching, word wrapping, keyboard selection, and styled headers.
Prevents wide tables from stretching or breaking the application window shell.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_CARD_HOVER,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class DataTable(QTableWidget):
    """Refined QTableWidget with responsive column sizing and clean styling."""

    def __init__(
        self,
        columns: List[str],
        stretch_column_index: Optional[int] = -1,
        resize_to_contents_indices: Optional[List[int]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.columns = columns
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)

        # Selection & behavior
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(True)
        self.setWordWrap(True)
        self.setAlternatingRowColors(True)

        # Header sizing
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)

        if resize_to_contents_indices:
            for idx in resize_to_contents_indices:
                if 0 <= idx < len(columns):
                    header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)

        if stretch_column_index is not None:
            if stretch_column_index == -1:
                # Stretch last column by default
                header.setSectionResizeMode(len(columns) - 1, QHeaderView.Stretch)
            elif 0 <= stretch_column_index < len(columns):
                header.setSectionResizeMode(stretch_column_index, QHeaderView.Stretch)

        # Vertical header
        v_header = self.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(38)

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {BG_SURFACE};
                alternate-background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                gridline-color: {BORDER_SUBTLE};
                color: {TEXT_PRIMARY};
                border-radius: 6px;
                selection-background-color: {BG_CARD_HOVER};
                selection-color: {ACCENT_CYAN};
            }}
            QHeaderView::section {{
                background-color: {BG_CARD};
                color: {TEXT_MUTED};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                padding: 8px 10px;
                border: none;
                border-right: 1px solid {BORDER_SUBTLE};
                border-bottom: 1px solid {BORDER_LIGHT};
            }}
        """)
