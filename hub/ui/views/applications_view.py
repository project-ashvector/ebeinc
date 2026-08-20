"""
ALLTHINGS140 Hub — Applications View
Interactive registry of all ecosystem applications, show-control workstations, and services.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.registry.app_registry import AppEntry, AppRegistry
from hub.services.system_service import SystemService
from hub.ui.components.app_card import AppCard
from hub.ui.components.empty_state import EmptyState
from hub.ui.components.page_shell import PageShell
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.status_pill import StatusPill
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class AppDetailsDialog(QDialog):
    """Detailed metadata and management dialog for an application."""

    def __init__(self, app: AppEntry, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle(f"Application Specifications — {app.displayName}")
        self.resize(620, 540)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Title row
        title_row = QHBoxLayout()
        title_lbl = QLabel(app.displayName)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {TEXT_PRIMARY};")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(StatusPill(app.status))
        layout.addLayout(title_row)

        desc_lbl = QLabel(app.description)
        desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; line-height: 1.3;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Meta Table
        table_frame = QFrame()
        table_frame.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 12px;")
        t_layout = QVBoxLayout(table_frame)
        t_layout.setSpacing(8)

        def add_row(key: str, val: str):
            r = QHBoxLayout()
            k = QLabel(f"{key}:")
            k.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 800;")
            k.setFixedWidth(130)
            v = QLabel(val)
            v.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-family: monospace;")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            r.addWidget(k)
            r.addWidget(v, 1)
            t_layout.addLayout(r)

        add_row("Identifier", app.id)
        add_row("Version", app.version or "N/A")
        add_row("Tech Stack", app.techStack)
        add_row("Environment", f"{app.environment.upper()} ({app.deploymentTarget})")
        add_row("Working Directory", app.workingDirectory)
        add_row("Git Branch / Commit", f"{app.gitBranch} ({app.gitHead or 'clean'})")
        add_row("Service Name", app.serviceName or "None (client / standalone tool)")
        add_row("Health URL", app.healthUrl or "Standard station health")
        if app.dependencies:
            add_row("Dependencies", ", ".join(app.dependencies))

        layout.addWidget(table_frame)

        # Operational Notes & DO NOT BREAK rules
        if app.notes:
            notes_box = QFrame()
            notes_box.setStyleSheet(f"background: rgba(0, 240, 255, 0.06); border: 1px solid {BORDER_LIGHT}; border-left: 3px solid {ACCENT_CYAN}; border-radius: 6px; padding: 10px;")
            n_layout = QVBoxLayout(notes_box)
            n_layout.setSpacing(4)
            n_title = QLabel("🛡️ OPERATIONAL SAFEGUARDS & RECOVERY")
            n_title.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; font-weight: 800;")
            n_text = QLabel(app.notes)
            n_text.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; line-height: 1.3;")
            n_text.setWordWrap(True)
            n_layout.addWidget(n_title)
            n_layout.addWidget(n_text)
            layout.addWidget(notes_box)

        layout.addStretch()

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_folder = QPushButton("📁 Open Folder")
        btn_folder.setToolTip(f"Open directory: {app.workingDirectory}")
        btn_folder.clicked.connect(lambda: SystemService.open_folder(app.workingDirectory))
        btn_row.addWidget(btn_folder)

        btn_term = QPushButton("💻 Open Terminal")
        btn_term.setToolTip(f"Open terminal in {app.workingDirectory}")
        btn_term.clicked.connect(lambda: SystemService.open_terminal(app.workingDirectory, f"ALLTHINGS140 — {app.displayName}"))
        btn_row.addWidget(btn_term)

        btn_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)


class ApplicationsView(QWidget):
    """View rendering the full application and service registry."""

    launch_agent = Signal(str)  # Emits app_id
    open_guide = Signal(str)

    def __init__(self, app_registry: AppRegistry, parent=None):
        super().__init__(parent)
        self.app_registry = app_registry
        self.current_category = "all"
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Applications & Service Registry",
            subtitle="Explore, launch, and manage registered applications across all four operational planes.",
            guide_key="app-roles",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # Header Search & Category Filter Row
        search_card = QFrame()
        search_card.setStyleSheet(f"background: {BG_SURFACE}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 12px;")
        s_layout = QVBoxLayout(search_card)
        s_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search applications by name, tech stack, or keywords…")
        self.search_input.textChanged.connect(self.filter_apps)
        s_layout.addWidget(self.search_input)

        # Filter Tabs Row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(6)

        self.filter_buttons = {}
        categories = [
            ("all", "All Components"),
            ("broadcast", "Broadcast & Radio"),
            ("visuals", "Visuals & Stage"),
            ("web", "Website & APIs"),
            ("mobile", "Mobile & Chat"),
            ("tools", "Tools & Recovery"),
            ("infra", "Cloud Infrastructure")
        ]

        for cat_id, cat_name in categories:
            btn = QPushButton(cat_name)
            btn.setCheckable(True)
            if cat_id == "all":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=cat_id: self.set_category(c))
            self.filter_buttons[cat_id] = btn
            filter_layout.addWidget(btn)

        filter_layout.addStretch()
        s_layout.addLayout(filter_layout)
        self.shell.add_widget(search_card)

        # Cards Container
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet(f"background: {BG_DARK};")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)

        self.shell.add_widget(self.cards_container)
        self.render_cards()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def set_category(self, category: str) -> None:
        self.current_category = category
        for cid, btn in self.filter_buttons.items():
            btn.setChecked(cid == category)
        self.filter_apps()

    def filter_apps(self) -> None:
        self.render_cards()

    def render_cards(self) -> None:
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_input.text().strip()
        apps = self.app_registry.search(query)
        if self.current_category != "all":
            apps = [a for a in apps if a.category == self.current_category]

        if not apps:
            empty = EmptyState(
                icon="📦",
                title="No Applications Found",
                description="No registered applications matched your search or category filter.",
                action_text="Clear Search Filters",
                on_action=self._clear_filters
            )
            self.cards_layout.addWidget(empty)
            return

        for app in apps:
            card = AppCard(app)
            card.on_launch.connect(self._handle_launch)
            card.on_terminal.connect(self._handle_terminal)
            card.on_agent.connect(lambda app_id: self.launch_agent.emit(app_id))
            card.on_details.connect(self._handle_details)
            self.cards_layout.addWidget(card)

    def _clear_filters(self) -> None:
        self.search_input.clear()
        self.set_category("all")

    def _handle_launch(self, app_id: str) -> None:
        app = self.app_registry.get(app_id)
        if not app or not app.launchCommand:
            return
        cmd = app.launchCommand.strip()
        if cmd.startswith("http") or cmd.startswith("xdg-open"):
            SystemService.open_url(cmd.replace("xdg-open ", "", 1))
            return
        if app.environment == "workstation":
            SystemService.open_terminal(app.workingDirectory, f"ALLTHINGS140 — {app.displayName}", cmd)
            return
        if app.environment in {"oracle-vm1", "oracle-vm2"} and (cmd.startswith("tailscale ssh ") or cmd.startswith("ssh ")):
            SystemService.open_terminal(app.workingDirectory, f"ALLTHINGS140 — {app.displayName}", cmd)
            return
        QMessageBox.information(
            self,
            "Launch Not Available Here",
            f"{app.displayName} runs in {app.environment}. Hub will not start its source code locally because that could create a conflicting runtime. Use the correct server/app-specific control path instead."
        )

    def _handle_terminal(self, app_id: str) -> None:
        app = self.app_registry.get(app_id)
        if app:
            SystemService.open_terminal(app.workingDirectory, f"ALLTHINGS140 — {app.displayName}")

    def _handle_details(self, app_id: str) -> None:
        app = self.app_registry.get(app_id)
        if app:
            dialog = AppDetailsDialog(app, self)
            dialog.exec_()
