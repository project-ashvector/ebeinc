"""
ALLTHINGS140 Hub — Engineering Handoffs View
Displays persistent engineering handoffs and exports summaries for ChatGPT and peer agents.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.services.handoff_service import EngineeringHandoff, HandoffService
from hub.ui.components.empty_state import EmptyState
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class NewHandoffDialog(QDialog):
    """Dialog for creating a new engineering handoff."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Engineering Handoff")
        self.resize(620, 600)

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

        layout.addWidget(QLabel("Task Title / Objective:"))
        self.title_in = QLineEdit()
        layout.addWidget(self.title_in)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("App ID (e.g. web-frontend):"))
        self.appid_in = QLineEdit("web-frontend")
        r1.addWidget(self.appid_in)

        r1.addWidget(QLabel("Agent:"))
        self.agent_in = QLineEdit("Antigravity")
        r1.addWidget(self.agent_in)
        layout.addLayout(r1)

        layout.addWidget(QLabel("Changes Completed (one per line):"))
        self.changes_in = QTextEdit()
        self.changes_in.setFixedHeight(80)
        layout.addWidget(self.changes_in)

        layout.addWidget(QLabel("Files Changed (one per line):"))
        self.files_in = QTextEdit()
        self.files_in.setFixedHeight(60)
        layout.addWidget(self.files_in)

        layout.addWidget(QLabel("Tests Executed & Health Status:"))
        self.tests_in = QLineEdit()
        self.tests_in.setPlaceholderText("Enter only tests you actually ran and their observed result")
        layout.addWidget(self.tests_in)

        layout.addWidget(QLabel("Remaining Work / Open Gates (one per line):"))
        self.remaining_in = QTextEdit()
        self.remaining_in.setFixedHeight(60)
        layout.addWidget(self.remaining_in)

        layout.addWidget(QLabel("Recommended Next Task:"))
        self.next_task_in = QLineEdit()
        layout.addWidget(self.next_task_in)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Handoff")
        btn_save.setProperty("primary", "true")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        changes = [c.strip() for c in self.changes_in.toPlainText().split("\n") if c.strip()]
        files = [f.strip() for f in self.files_in.toPlainText().split("\n") if f.strip()]
        remaining = [r.strip() for r in self.remaining_in.toPlainText().split("\n") if r.strip()]
        return {
            "task_title": self.title_in.text().strip() or "Engineering Session",
            "app_id": self.appid_in.text().strip() or "general",
            "agent_name": self.agent_in.text().strip() or "Engineer",
            "changes_made": changes,
            "files_changed": files,
            "tests_executed": self.tests_in.text().strip(),
            "deployment_status": "Not recorded",
            "health_status": "Not verified",
            "remaining_work": remaining,
            "recommended_next_task": self.next_task_in.text().strip()
        }


class HandoffsView(QWidget):
    """View managing engineering handoffs and ChatGPT exports."""

    open_guide = Signal(str)

    def __init__(self, handoff_service: HandoffService, parent=None):
        super().__init__(parent)
        self.handoff_service = handoff_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Engineering Handoffs & Audit Logs",
            subtitle="Cross-agent memory logs, task completion reports, and ChatGPT sendoff summaries.",
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
        s_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search engineering handoffs by task, app, or agent…")
        self.search_input.textChanged.connect(self.render_handoffs)
        s_layout.addWidget(self.search_input, 1)

        btn_new = QPushButton("➕ Record New Handoff")
        btn_new.setProperty("primary", "true")
        btn_new.setToolTip("Record manual engineering session handoff")
        btn_new.clicked.connect(self._create_handoff)
        s_layout.addWidget(btn_new)

        self.shell.add_widget(search_card)

        # Container for cards
        self.container = QWidget()
        self.container.setStyleSheet(f"background: {BG_DARK};")
        self.layout_body = QVBoxLayout(self.container)
        self.layout_body.setContentsMargins(0, 0, 0, 0)
        self.layout_body.setSpacing(14)

        self.shell.add_widget(self.container)
        self.render_handoffs()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def render_handoffs(self) -> None:
        while self.layout_body.count():
            child = self.layout_body.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_input.text().strip()
        handoffs = self.handoff_service.search(query)

        if not handoffs:
            empty = EmptyState(
                icon="🤝",
                title="No Handoffs Found",
                description="No engineering handoffs matched your search query.",
                action_text="Clear Search Filter",
                on_action=self.search_input.clear
            )
            self.layout_body.addWidget(empty)
            return

        for h in handoffs:
            card = QFrame()
            card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 16px;")
            c_layout = QVBoxLayout(card)
            c_layout.setSpacing(8)

            t_row = QHBoxLayout()
            title_lbl = QLabel(h.taskTitle)
            title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY};")
            t_row.addWidget(title_lbl)
            t_row.addStretch()

            date_lbl = QLabel(h.formattedDate)
            date_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-family: monospace;")
            t_row.addWidget(date_lbl)
            c_layout.addLayout(t_row)

            m_row = QHBoxLayout()
            m_row.addWidget(QLabel(f"App: <b>{h.appName}</b> ({h.appId}) • Agent: <b>{h.agentName}</b>"))
            m_row.addStretch()
            c_layout.addLayout(m_row)

            # Changes list
            chg_box = QFrame()
            chg_box.setStyleSheet(f"background: {BG_DARK}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 10px;")
            chg_l = QVBoxLayout(chg_box)
            chg_l.setSpacing(4)
            for chg in h.changesMade:
                item_lbl = QLabel(f"• {chg}")
                item_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
                item_lbl.setWordWrap(True)
                chg_l.addWidget(item_lbl)
            c_layout.addWidget(chg_box)

            # Next Task Callout
            next_box = QFrame()
            next_box.setStyleSheet(f"background: rgba(0, 240, 255, 0.05); border-left: 3px solid {ACCENT_CYAN}; padding: 8px;")
            n_l = QHBoxLayout(next_box)
            n_lbl = QLabel(f"👉 Recommended Next: {h.recommendedNextTask}")
            n_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-weight: bold; font-size: 12px;")
            n_lbl.setWordWrap(True)
            n_l.addWidget(n_lbl)
            c_layout.addWidget(next_box)

            btn_row = QHBoxLayout()
            btn_row.addStretch()

            btn_export = QPushButton("📋 Export for ChatGPT")
            btn_export.setProperty("accent", "true")
            btn_export.setToolTip("Format and copy complete handoff prompt ready for ChatGPT")
            btn_export.clicked.connect(lambda checked=False, hid=h.id: self._export_chatgpt(hid))
            btn_row.addWidget(btn_export)

            c_layout.addLayout(btn_row)
            self.layout_body.addWidget(card)

    def _export_chatgpt(self, handoff_id: str) -> None:
        text = self.handoff_service.export_for_chatgpt(handoff_id)
        QApplication.clipboard().setText(text)
        QMessageBox.information(
            self,
            "Handoff Exported",
            "The engineering handoff has been formatted and copied to your clipboard ready to paste into ChatGPT."
        )

    def _create_handoff(self) -> None:
        dialog = NewHandoffDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            d = dialog.get_data()
            self.handoff_service.create(
                app_id=d["app_id"],
                app_name=d["app_id"].title(),
                agent_name=d["agent_name"],
                task_title=d["task_title"],
                changes_made=d["changes_made"],
                files_changed=d["files_changed"],
                tests_executed=d["tests_executed"],
                deployment_status=d["deployment_status"],
                health_status=d["health_status"],
                remaining_work=d["remaining_work"],
                recommended_next_task=d["recommended_next_task"]
            )
            self.render_handoffs()
