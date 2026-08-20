"""
ALLTHINGS140 Hub — Update Center & Safe Deployment View
Manages version diffs, update detection, and the 10-step safe update workflow wizard.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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

from hub.registry.app_registry import AppRegistry
from hub.services.update_service import UpdateService
from hub.ui.components.confirm_dialog import ConfirmDialog
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.components.status_pill import StatusPill
from hub.ui.worker import Worker
from PySide6.QtCore import QThreadPool
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_ORANGE,
    STATUS_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class UpdatesView(QWidget):
    """View managing application updates and the 10-step safe update wizard."""

    open_guide = Signal(str)

    def __init__(self, app_registry: AppRegistry, update_service: UpdateService, parent=None):
        super().__init__(parent)
        self.app_registry = app_registry
        self.update_service = update_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Application Versions & Update Safety",
            subtitle="Verify local source state and run real preflight checks. Remote/deployed versions are shown UNKNOWN until independently verified.",
            guide_key="page-updates",
            safety_level="yellow"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # 1. Version Comparison Card with DataTable
        tbl_card = SectionCard(
            title="DEPLOYMENT MATRIX & VERSION PARITY",
            subtitle="Comparing local workstation repository version against currently deployed server/staging runtime.",
            guide_key="page-updates",
            safety_level="green"
        )

        # Action: Rescan
        btn_refresh = QPushButton("🔄 Rescan Versions")
        btn_refresh.setToolTip("Scan git tags, package.json, and installed binary headers")
        btn_refresh.clicked.connect(self.refresh_versions)
        tbl_card.header_actions.addWidget(btn_refresh)

        self.table = DataTable(
            columns=["Application", "Local Version", "Deployed Version", "Update State", "Details & Readiness"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 1, 2, 3]
        )
        self.table.setFixedHeight(260)
        tbl_card.add_widget(self.table)
        self.shell.add_widget(tbl_card)

        # 2. Safe 10-Step Workflow Wizard Card
        wiz_card = SectionCard(
            title="10-STEP UPDATE PREFLIGHT",
            subtitle="Runs real local state/backup/tests/build checks. It deliberately does NOT deploy or restart remote production in v1.2.1.",
            guide_key="page-updates",
            safety_level="orange",
            elevated=True
        )

        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        app_lbl = QLabel("Select Target Application:")
        app_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        sel_row.addWidget(app_lbl)

        self.combo_app = QComboBox()
        self.combo_app.addItem("— Select an Application —", None)
        for app in self.app_registry.all():
            self.combo_app.addItem(f"{app.displayName} ({app.id})", app.id)
        self.combo_app.currentIndexChanged.connect(self._on_app_selected)
        sel_row.addWidget(self.combo_app, 1)

        self.btn_run_wf = QPushButton("🧪 Run Update Preflight")
        self.btn_run_wf.setProperty("warning", "true")
        self.btn_run_wf.setEnabled(False)
        self.btn_run_wf.setToolTip("Select an application first. Preflight creates a verified local backup and runs registered tests/builds without deploying production.")
        self.btn_run_wf.clicked.connect(self._run_safe_workflow)
        sel_row.addWidget(self.btn_run_wf)

        wiz_card.add_layout(sel_row)

        self.disabled_explanation_lbl = QLabel("Select an application to run a non-production preflight.")
        self.disabled_explanation_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-style: italic;")
        wiz_card.add_widget(self.disabled_explanation_lbl)

        self.workflow_output = QLabel("Workflow output log will appear here during execution…")
        self.workflow_output.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-family: monospace; background: {BG_DARK}; padding: 14px; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;")
        self.workflow_output.setWordWrap(True)
        wiz_card.add_widget(self.workflow_output)

        self.shell.add_widget(wiz_card)
        self.shell.add_stretch()

        self.refresh_versions()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _on_app_selected(self, idx: int) -> None:
        app_id = self.combo_app.currentData()
        if app_id:
            self.btn_run_wf.setEnabled(True)
            self.btn_run_wf.setToolTip(f"Run non-production preflight for {self.combo_app.currentText()}.")
            self.disabled_explanation_lbl.setText(f"Ready to run local preflight for {self.combo_app.currentText()}. No production deploy/restart will occur.")
            self.disabled_explanation_lbl.setStyleSheet(f"color: {SAFETY_GREEN}; font-size: 11px;")
        else:
            self.btn_run_wf.setEnabled(False)
            self.btn_run_wf.setToolTip("Select an application first. Preflight creates a verified local backup and runs registered tests/builds without deploying production.")
            self.disabled_explanation_lbl.setText("Select an application to run a non-production preflight.")
            self.disabled_explanation_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-style: italic;")

    def refresh_versions(self) -> None:
        apps = self.app_registry.all()
        matrix = self.update_service.get_version_matrix(apps)
        self.table.setRowCount(len(matrix))

        for row_idx, item in enumerate(matrix):
            n_item = QTableWidgetItem(item.appName)
            l_item = QTableWidgetItem(f"v{item.localVersion}")
            d_item = QTableWidgetItem(f"v{item.deployedVersion}")
            u_item = QTableWidgetItem(item.updateType)
            u_item.setForeground(Qt.cyan if item.hasUpdate else Qt.gray)
            det_item = QTableWidgetItem(item.details)

            self.table.setItem(row_idx, 0, n_item)
            self.table.setItem(row_idx, 1, l_item)
            self.table.setItem(row_idx, 2, d_item)
            self.table.setItem(row_idx, 3, u_item)
            self.table.setItem(row_idx, 4, det_item)

    def _run_safe_workflow(self) -> None:
        app_id = self.combo_app.currentData()
        if not app_id:
            return
        app = self.app_registry.get(app_id)
        if not app:
            return

        dialog = ConfirmDialog(
            title=f"Run Update Preflight: {app.displayName}",
            message=f"Run verified local preflight checks for {app.displayName}?",
            what_it_does="Creates a local source snapshot, runs the registered test command, and performs a local build when the build command is non-privileged.",
            what_it_touches=f"Local workspace only: {app.workingDirectory} and backups/hub-preflight/.",
            expected_impact="No Cloudflare deploy, VM restart, systemd change, dpkg install, or production mutation is performed.",
            rollback_plan="The source tree is not overwritten; a verified tar snapshot is created before tests/builds.",
            affects_live_station=False,
            safety_level="yellow",
            confirm_label="Run Preflight",
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            self.btn_run_wf.setEnabled(False)
            self.workflow_output.setText(f"Running real preflight for {app.displayName}…")
            worker = Worker(self.update_service.execute_safe_workflow, app)
            worker.signals.result.connect(lambda steps: self._show_preflight_result(app.displayName, steps))
            worker.signals.error.connect(lambda err: self._show_preflight_error(err))
            worker.signals.finished.connect(lambda: self.btn_run_wf.setEnabled(True))
            QThreadPool.globalInstance().start(worker)

    def _show_preflight_result(self, app_name: str, steps) -> None:
        lines = [f"=== UPDATE PREFLIGHT: {app_name} ==="]
        all_ok = True
        for step in steps:
            mark = "✓" if step.isSuccess else "✗"
            all_ok = all_ok and step.isSuccess
            detail = step.detail if step.isSuccess else f"{step.detail}: {step.error}"
            lines.append(f"{mark} Step {step.stepNumber}: {step.stepName} — {detail}")
        lines.append("\nNO PRODUCTION CHANGE WAS PERFORMED BY THIS PREFLIGHT.")
        self.workflow_output.setText("\n".join(lines))
        color = STATUS_GREEN if all_ok else "#ff6b6b"
        self.workflow_output.setStyleSheet(f"color: {color}; font-size: 12px; font-family: monospace; background: {BG_DARK}; padding: 14px; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;")

    def _show_preflight_error(self, error: str) -> None:
        self.workflow_output.setText("Preflight failed before completion:\n" + error)
