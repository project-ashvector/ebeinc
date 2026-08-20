"""ALLTHINGS140 Hub — Evidence-based application/source catalog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from hub.registry.app_registry import AppRegistry, AppEntry
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.components.status_pill import StatusPill
from hub.ui.theme import BG_CARD, BORDER_SUBTLE, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY


class CatalogView(QWidget):
    """Read-only catalog based on actual local source evidence from AppRegistry.

    Runtime/remote health is intentionally not inferred here. Use Health/Servers for that.
    """

    open_guide = Signal(str)

    def __init__(self, app_registry: AppRegistry, parent=None):
        super().__init__(parent)
        self.app_registry = app_registry
        self._init_ui()

    def _evidence_status(self, app: AppEntry) -> str:
        work = Path(app.workingDirectory).expanduser()
        if app.environment in {"oracle-vm1", "oracle-vm2", "cloudflare", "mobile"}:
            return "REMOTE / SOURCE FOUND" if work.exists() else "REMOTE / SOURCE UNKNOWN"
        if not work.exists():
            return "SOURCE MISSING"
        cmd = (app.launchCommand or "").strip().split()
        if cmd and (cmd[0].startswith("/") or cmd[0].startswith("~")):
            exe = Path(cmd[0]).expanduser()
            return "INSTALLED / SOURCE FOUND" if exe.exists() else "SOURCE FOUND"
        return "SOURCE FOUND"

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Application & Source Catalog",
            subtitle="Evidence-based local/source inventory. Runtime health and deployed versions are verified on their dedicated pages.",
            guide_key="app-roles",
            safety_level="green",
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.shell)

        card = SectionCard(
            title="DISCOVERED APPLICATIONS & COMPONENTS",
            subtitle="No item is marked healthy, installed, or current unless the Hub has direct evidence for that specific claim.",
            guide_key="app-roles",
            safety_level="green",
        )
        grid = QGridLayout()
        grid.setSpacing(14)

        apps = sorted(self.app_registry.all(), key=lambda a: (a.category, a.displayName.lower()))
        for idx, app in enumerate(apps):
            frame = QFrame()
            frame.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; padding: 14px;")
            lay = QVBoxLayout(frame)
            lay.setSpacing(8)

            top = QHBoxLayout()
            name = QLabel(app.displayName)
            name.setWordWrap(True)
            name.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_PRIMARY};")
            top.addWidget(name, 1)
            ver = QLabel(f"v{app.version}" if app.version and app.version != "unknown" else "version unknown")
            ver.setStyleSheet(f"color: {TEXT_MUTED}; font: 10px monospace;")
            top.addWidget(ver)
            top.addWidget(StatusPill(self._evidence_status(app)))
            lay.addLayout(top)

            desc = QLabel(app.description)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            lay.addWidget(desc)

            work = Path(app.workingDirectory).expanduser()
            detail = QLabel(
                f"Category: {app.category}   Environment: {app.environment}\n"
                f"Source: {work}\n"
                f"Git: {app.gitBranch or 'unknown'} {app.gitHead or ''}{' • UNCOMMITTED EDITS' if app.dirty else ''}"
            )
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color: {TEXT_MUTED}; font: 10px monospace;")
            lay.addWidget(detail)

            row = QHBoxLayout()
            row.addStretch()
            btn = QPushButton("Details")
            btn.clicked.connect(lambda checked=False, a=app: self._show_details(a))
            row.addWidget(btn)
            lay.addLayout(row)
            grid.addWidget(frame, idx // 2, idx % 2)

        card.add_layout(grid)
        self.shell.add_widget(card)
        self.shell.add_stretch()

    def _show_details(self, app: AppEntry) -> None:
        work = Path(app.workingDirectory).expanduser()
        QMessageBox.information(
            self,
            app.displayName,
            "\n".join([
                f"ID: {app.id}",
                f"Environment: {app.environment}",
                f"Source path: {work}",
                f"Source exists: {'Yes' if work.exists() else 'No'}",
                f"Detected/source version: {app.version or 'Unknown'}",
                f"Git branch: {app.gitBranch or 'Unknown'}",
                f"Git revision: {app.gitHead or 'Unknown'}",
                f"Uncommitted edits: {'Yes' if app.dirty else 'No'}",
                "",
                "This page does not claim the remote runtime is online or that this source version is deployed.",
            ]),
        )

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()
