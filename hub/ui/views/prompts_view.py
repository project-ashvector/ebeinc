"""
ALLTHINGS140 Hub — Prompt Library View
Manages reusable task prompts, presets, tag filtering, and CRUD operations.
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

from hub.services.prompt_service import PromptService, PromptTemplate
from hub.ui.components.confirm_dialog import ConfirmDialog
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
    SAFETY_YELLOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class PromptEditDialog(QDialog):
    """Dialog for creating or editing a prompt template."""

    def __init__(self, prompt: Optional[PromptTemplate] = None, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.setWindowTitle("Edit Prompt Template" if prompt else "Create New Prompt Template")
        self.resize(580, 500)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Prompt Title:"))
        self.title_input = QLineEdit(prompt.title if prompt else "")
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Description:"))
        self.desc_input = QLineEdit(prompt.description if prompt else "")
        layout.addWidget(self.desc_input)

        layout.addWidget(QLabel("Tags (comma separated):"))
        self.tags_input = QLineEdit(", ".join(prompt.tags) if prompt else "custom, task")
        layout.addWidget(self.tags_input)

        layout.addWidget(QLabel("Prompt Template Text:"))
        self.text_input = QTextEdit(prompt.promptText if prompt else "")
        self.text_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_CARD};
                font-family: monospace;
                font-size: 11px;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.text_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Prompt")
        btn_save.setProperty("primary", "true")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        return {
            "title": self.title_input.text().strip(),
            "description": self.desc_input.text().strip(),
            "tags": tags,
            "prompt_text": self.text_input.toPlainText().strip()
        }


class PromptsView(QWidget):
    """View rendering the prompt library and presets."""

    run_prompt = Signal(str, str)  # prompt_text, prompt_title
    open_guide = Signal(str)

    def __init__(self, prompt_service: PromptService, parent=None):
        super().__init__(parent)
        self.prompt_service = prompt_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Prompt Library & Agent Presets",
            subtitle="Reusable engineering directives, architecture review templates, and diagnostic prompts.",
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
        self.search_input.setPlaceholderText("🔍 Search prompt templates by title, description, or tags…")
        self.search_input.textChanged.connect(self.render_prompts)
        s_layout.addWidget(self.search_input, 1)

        btn_new = QPushButton("➕ Create New Prompt")
        btn_new.setProperty("primary", "true")
        btn_new.setToolTip("Create a custom reusable prompt template")
        btn_new.clicked.connect(self._create_prompt)
        s_layout.addWidget(btn_new)

        self.shell.add_widget(search_card)

        # Container for cards
        self.prompts_container = QWidget()
        self.prompts_container.setStyleSheet(f"background: {BG_DARK};")
        self.prompts_layout = QVBoxLayout(self.prompts_container)
        self.prompts_layout.setContentsMargins(0, 0, 0, 0)
        self.prompts_layout.setSpacing(12)

        self.shell.add_widget(self.prompts_container)
        self.render_prompts()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def render_prompts(self) -> None:
        while self.prompts_layout.count():
            child = self.prompts_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_input.text().strip()
        prompts = self.prompt_service.search(query)

        if not prompts:
            empty = EmptyState(
                icon="📝",
                title="No Prompts Found",
                description="No prompt templates matched your search criteria.",
                action_text="Clear Search Filter",
                on_action=self.search_input.clear
            )
            self.prompts_layout.addWidget(empty)
            return

        for p in prompts:
            card = QFrame()
            card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 14px;")
            c_layout = QVBoxLayout(card)
            c_layout.setSpacing(8)

            t_row = QHBoxLayout()
            title_lbl = QLabel(p.title)
            title_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_PRIMARY};")
            t_row.addWidget(title_lbl)
            t_row.addStretch()

            for tag in p.tags:
                tag_lbl = QLabel(f"#{tag}")
                tag_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 10px; font-weight: bold; background: {BG_DARK}; padding: 2px 6px; border-radius: 4px;")
                t_row.addWidget(tag_lbl)

            c_layout.addLayout(t_row)

            desc_lbl = QLabel(p.description)
            desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            desc_lbl.setWordWrap(True)
            c_layout.addWidget(desc_lbl)

            text_preview = QLabel(p.promptText)
            text_preview.setStyleSheet(f"color: {TEXT_MUTED}; font-family: monospace; font-size: 11px; background: {BG_DARK}; padding: 8px; border-radius: 4px;")
            text_preview.setWordWrap(True)
            text_preview.setMaximumHeight(60)
            c_layout.addWidget(text_preview)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            btn_copy = QPushButton("📋 Copy Text")
            btn_copy.clicked.connect(lambda checked=False, pt=p.promptText, pid=p.id: self._copy_text(pt, pid))
            btn_row.addWidget(btn_copy)

            btn_run = QPushButton("🚀 Run with Agent")
            btn_run.setProperty("accent", "true")
            btn_run.clicked.connect(lambda checked=False, pt=p.promptText, tit=p.title: self.run_prompt.emit(pt, tit))
            btn_row.addWidget(btn_run)

            btn_row.addStretch()

            btn_edit = QPushButton("✏️ Edit")
            btn_edit.clicked.connect(lambda checked=False, pid=p.id: self._edit_prompt(pid))
            btn_row.addWidget(btn_edit)

            btn_dup = QPushButton("📑 Duplicate")
            btn_dup.clicked.connect(lambda checked=False, pid=p.id: self._duplicate_prompt(pid))
            btn_row.addWidget(btn_dup)

            if not p.id.startswith("preset-"):
                btn_del = QPushButton("🗑️ Delete")
                btn_del.setProperty("danger", "true")
                btn_del.clicked.connect(lambda checked=False, pid=p.id, tit=p.title: self._delete_prompt(pid, tit))
                btn_row.addWidget(btn_del)

            c_layout.addLayout(btn_row)
            self.prompts_layout.addWidget(card)

    def _copy_text(self, text: str, prompt_id: str) -> None:
        QApplication.clipboard().setText(text)
        self.prompt_service.record_usage(prompt_id)
        QMessageBox.information(self, "Copied", "Prompt text copied to clipboard.")

    def _create_prompt(self) -> None:
        dialog = PromptEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["title"]:
                self.prompt_service.create(
                    title=data["title"],
                    description=data["description"],
                    prompt_text=data["prompt_text"],
                    tags=data["tags"]
                )
                self.render_prompts()

    def _edit_prompt(self, prompt_id: str) -> None:
        p = self.prompt_service.get(prompt_id)
        if not p:
            return
        dialog = PromptEditDialog(prompt=p, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            self.prompt_service.update(
                prompt_id=prompt_id,
                title=data["title"],
                description=data["description"],
                prompt_text=data["prompt_text"],
                target_app=p.targetApp,
                provider=p.agentProvider,
                tags=data["tags"]
            )
            self.render_prompts()

    def _duplicate_prompt(self, prompt_id: str) -> None:
        self.prompt_service.duplicate(prompt_id)
        self.render_prompts()

    def _delete_prompt(self, prompt_id: str, title: str) -> None:
        dialog = ConfirmDialog(
            title=f"Delete Prompt: {title}",
            message=f"Permanently delete prompt template '{title}'?",
            what_it_does=f"Removes template '{title}' from local prompt registry.",
            what_it_touches=f"Path: {self.prompt_service.prompts_file}",
            expected_impact="Template will no longer appear in prompt presets.",
            rollback_plan="Can be recreated manually.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Delete Template",
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.prompt_service.delete(prompt_id)
            self.render_prompts()
