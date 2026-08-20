"""
ALLTHINGS140 Hub — AI & Coding Agent Control Center View
Orchestrates Codex, Antigravity, OpenCode, and Ollama agent launches with smart context headers.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.registry.app_registry import AppRegistry
from hub.services.activity_service import ActivityService
from hub.services.agent_service import AgentService
from hub.services.prompt_service import PromptService
from hub.ui.components.page_shell import PageShell
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.section_card import SectionCard
from hub.ui.components.status_pill import StatusPill
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PINK,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_YELLOW,
    STATUS_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class AgentsView(QWidget):
    """Control center for launching AI coding agents with smart context."""

    open_guide = Signal(str)

    def __init__(
        self,
        app_registry: AppRegistry,
        agent_service: AgentService,
        prompt_service: PromptService,
        activity_service: ActivityService,
        parent=None
    ):
        super().__init__(parent)
        self.app_registry = app_registry
        self.agent_service = agent_service
        self.prompt_service = prompt_service
        self.activity_service = activity_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="AI Coding Agents & Autonomous Workflows",
            subtitle="Coordinate Google Antigravity, Codex, OpenCode, and Local Ollama with auto-injected architecture context.",
            guide_key="page-agents",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # 1. AI Providers Grid Card
        prov_card = SectionCard(
            title="AI CODING RUNTIMES & PROVIDER STATUS",
            subtitle="Detected CLI and local model runtimes on this workstation",
            guide_key="page-agents",
            safety_level="green"
        )

        providers_grid = QGridLayout()
        providers_grid.setSpacing(12)

        providers = self.agent_service.get_providers()
        for idx, prov in enumerate(providers):
            card = QFrame()
            card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 12px;")
            c_layout = QVBoxLayout(card)
            c_layout.setSpacing(6)

            top_row = QHBoxLayout()
            name_lbl = QLabel(prov.name)
            name_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_PRIMARY};")
            top_row.addWidget(name_lbl)
            top_row.addStretch()

            status_pill = StatusPill("AVAILABLE" if prov.is_available else "NOT CONFIGURED")
            top_row.addWidget(status_pill)
            c_layout.addLayout(top_row)

            desc_lbl = QLabel(prov.description)
            desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            desc_lbl.setWordWrap(True)
            c_layout.addWidget(desc_lbl)

            meta_lbl = QLabel(f"Path: {prov.executable or 'Not found'}\nAuth: {prov.auth_status}")
            meta_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-family: monospace;")
            c_layout.addWidget(meta_lbl)

            row = idx // 2
            col = idx % 2
            providers_grid.addWidget(card, row, col)

        prov_card.add_layout(providers_grid)
        self.shell.add_widget(prov_card)

        # 2. "Work On This App" Orchestrator Card
        wf_card = SectionCard(
            title="WORK ON APPLICATION — AGENT ORCHESTRATOR",
            subtitle="Generates smart context headers with DO NOT BREAK rules, filepaths, and architecture constraints.",
            guide_key="page-agents",
            safety_level="yellow",
            elevated=True
        )

        # Form row 1: Target App + Agent Provider
        form_row1 = QHBoxLayout()
        form_row1.setSpacing(14)

        app_group = QVBoxLayout()
        app_lbl = QLabel("Target Application:")
        app_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        app_group.addWidget(app_lbl)

        self.combo_target_app = QComboBox()
        for app in self.app_registry.all():
            self.combo_target_app.addItem(f"{app.displayName} ({app.id})", app.id)
        self.combo_target_app.currentIndexChanged.connect(self._regenerate_prompt)
        app_group.addWidget(self.combo_target_app)
        form_row1.addLayout(app_group, 1)

        prov_group = QVBoxLayout()
        prov_lbl = QLabel("Coding Agent Provider:")
        prov_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        prov_group.addWidget(prov_lbl)

        self.combo_provider = QComboBox()
        for prov in providers:
            if prov.is_available:
                self.combo_provider.addItem(f"{prov.name} ({prov.id})", prov.id)
        prov_group.addWidget(self.combo_provider)
        form_row1.addLayout(prov_group, 1)

        wf_card.add_layout(form_row1)

        # Form row 2: Task Preset + Title
        form_row2 = QHBoxLayout()
        form_row2.setSpacing(14)

        preset_group = QVBoxLayout()
        preset_lbl = QLabel("Task Preset:")
        preset_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        preset_group.addWidget(preset_lbl)

        self.combo_preset = QComboBox()
        self.combo_preset.addItem("Custom Task", "custom")
        for preset in self.prompt_service.all():
            self.combo_preset.addItem(preset.title, preset.id)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        preset_group.addWidget(self.combo_preset)
        form_row2.addLayout(preset_group, 1)

        title_group = QVBoxLayout()
        title_lbl = QLabel("Task Objective / Instructions:")
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        title_group.addWidget(title_lbl)

        self.task_title_input = QLineEdit("Investigate architecture and codebase")
        self.task_title_input.textChanged.connect(self._regenerate_prompt)
        title_group.addWidget(self.task_title_input)
        form_row2.addLayout(title_group, 2)

        wf_card.add_layout(form_row2)

        # Prompt Preview Area
        prev_lbl = QLabel("Generated Smart Context & Task Prompt:")
        prev_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        wf_card.add_widget(prev_lbl)

        self.prompt_preview = QTextEdit()
        self.prompt_preview.setFixedHeight(180)
        self.prompt_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_DARK};
                font-family: monospace;
                font-size: 11px;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        wf_card.add_widget(self.prompt_preview)

        # Launch Button Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_copy_prompt = QPushButton("📋 Copy Prompt")
        self.btn_copy_prompt.setToolTip("Copy generated context prompt to clipboard")
        self.btn_copy_prompt.clicked.connect(self._copy_prompt)
        btn_row.addWidget(self.btn_copy_prompt)

        self.btn_launch_agent = QPushButton("🚀 Launch Agent in Workspace Terminal")
        self.btn_launch_agent.setProperty("primary", "true")
        self.btn_launch_agent.setToolTip("Open dedicated terminal tab with agent runtime and task context")
        self.btn_launch_agent.clicked.connect(self._launch_agent)
        btn_row.addWidget(self.btn_launch_agent)

        wf_card.add_layout(btn_row)
        self.shell.add_widget(wf_card)
        self.shell.add_stretch()

        self._regenerate_prompt()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def set_target_app(self, app_id: str) -> None:
        for i in range(self.combo_target_app.count()):
            if self.combo_target_app.itemData(i) == app_id:
                self.combo_target_app.setCurrentIndex(i)
                break
        self._regenerate_prompt()

    def _on_preset_changed(self, idx: int) -> None:
        preset_id = self.combo_preset.currentData()
        if preset_id == "custom":
            self._regenerate_prompt()
            return
        preset = self.prompt_service.get(preset_id)
        if preset:
            self.task_title_input.setText(preset.title)
            app_id = self.combo_target_app.currentData()
            app = self.app_registry.get(app_id)
            if app:
                smart_prompt = self.agent_service.generate_smart_prompt(app, preset.title, preset.promptText)
                self.prompt_preview.setPlainText(smart_prompt)

    def _regenerate_prompt(self) -> None:
        app_id = self.combo_target_app.currentData()
        app = self.app_registry.get(app_id)
        if not app:
            return
        task_title = self.task_title_input.text().strip() or "General task"
        smart_prompt = self.agent_service.generate_smart_prompt(app, task_title)
        self.prompt_preview.setPlainText(smart_prompt)

    def _copy_prompt(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.prompt_preview.toPlainText())
        QMessageBox.information(self, "Prompt Copied", "Smart context prompt copied to clipboard.")

    def _launch_agent(self) -> None:
        app_id = self.combo_target_app.currentData()
        prov_id = self.combo_provider.currentData()
        app = self.app_registry.get(app_id)
        if not app or not prov_id:
            return

        task_title = self.task_title_input.text().strip() or "General task"
        prompt_text = self.prompt_preview.toPlainText()

        try:
            session = self.agent_service.launch_agent_session(
                provider_id=prov_id,
                app=app,
                task_title=task_title,
                prompt_text=prompt_text
            )
            self.activity_service.log(
                component=app.id,
                action="LAUNCH_AGENT",
                result="SUCCESS",
                detail=f"Launched {prov_id.title()} agent for {app.displayName} ({task_title})."
            )
            QMessageBox.information(
                self,
                "Agent Launched",
                f"Launched {prov_id.title()} in a dedicated workspace terminal:\n\n📁 {session.working_directory}\n🎯 Task: {task_title}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Could not launch agent: {e}")
