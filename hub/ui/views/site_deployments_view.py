"""
ALLTHINGS140 Hub — Cloudflare Deployment Center View
Guarded pipeline for Preview deployments, Automated Pre-Flight tests, Manual Promotion, and Rollbacks.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QThreadPool
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.services.cloudflare_deployment_service import CloudflareDeploymentService, SiteDeploymentRecord
from hub.services.system_service import SystemService
from hub.ui.components.confirm_dialog import ConfirmDialog
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.worker import Worker
from hub.ui.theme import (
    ACCENT_CYAN,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_RED,
    STATUS_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SiteDeploymentsView(QWidget):
    """Cloudflare Deployment Center view."""

    open_guide = Signal(str)

    def __init__(self, deploy_service: CloudflareDeploymentService, parent=None):
        super().__init__(parent)
        self.deploy_service = deploy_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Cloudflare Edge Deployment Center",
            subtitle="Guarded preview pipelines, immutable artifact promotion, live smoke tests, and rollback only when a verified previous-production artifact is retained.",
            guide_key="page-cloudflare",
            safety_level="orange"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # 1. Guarded Pipeline Card
        wiz_card = SectionCard(
            title="GUARDED CLOUDFLARE PAGES PIPELINE",
            subtitle="Never deploy directly to live production. Enforces: Local Test → Rollback Backup → Cloudflare Preview → Automated Smoke Test → Manual Visual Verification → Production Promotion.",
            guide_key="page-cloudflare",
            safety_level="yellow",
            elevated=True
        )

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        proj_lbl = QLabel("Target Project:")
        proj_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        ctrl_row.addWidget(proj_lbl)

        self.combo_project = QComboBox()
        self.combo_project.addItem("Web Listener Frontend (ebeinc / radio)", "ebeinc")
        self.combo_project.addItem("Green Web Stage (allthings140-visuals-green)", "allthings140-visuals-green")
        ctrl_row.addWidget(self.combo_project, 1)

        self.btn_create_preview = QPushButton("🚀 Create Preview Deployment")
        self.btn_create_preview.setProperty("primary", "true")
        self.btn_create_preview.setToolTip("Build and deploy private preview URL without affecting live production.")
        self.btn_create_preview.clicked.connect(self._create_preview)
        ctrl_row.addWidget(self.btn_create_preview)

        wiz_card.add_layout(ctrl_row)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setFixedHeight(120)
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_DARK};
                font-family: monospace;
                font-size: 11px;
                color: {STATUS_GREEN};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self.log_console.setPlaceholderText("Ready to run Cloudflare deployment pipelines…")
        wiz_card.add_widget(self.log_console)
        self.shell.add_widget(wiz_card)

        # 2. Deployment History Table Card
        hist_card = SectionCard(
            title="RECENT DEPLOYMENTS & ROLLBACK POINTS",
            subtitle="Audit log of staged previews, promoted releases, and timestamped rollback tarballs.",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_rescan = QPushButton("🔄 Refresh Status")
        btn_rescan.setToolTip("Reload deployment history from local database")
        btn_rescan.clicked.connect(self.refresh_table)
        hist_card.header_actions.addWidget(btn_rescan)

        self.table = DataTable(
            columns=["Target Project", "Environment", "Deployed Date", "Smoke Test Status", "Preview / Live URL"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 1, 2, 3]
        )
        self.table.setFixedHeight(220)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        hist_card.add_widget(self.table)

        # Actions Row
        act_row = QHBoxLayout()
        act_row.setSpacing(10)
        act_row.addStretch()

        self.btn_open_preview = QPushButton("🌐 Open Selected Preview")
        self.btn_open_preview.setEnabled(False)
        self.btn_open_preview.setToolTip("Select a deployment from the table first.")
        self.btn_open_preview.clicked.connect(self._open_selected_preview)
        act_row.addWidget(self.btn_open_preview)

        self.btn_promote = QPushButton("⭐ Promote to Production")
        self.btn_promote.setProperty("accent", "true")
        self.btn_promote.setEnabled(False)
        self.btn_promote.setToolTip("Select a preview from the table first.")
        self.btn_promote.clicked.connect(self._promote_selected)
        act_row.addWidget(self.btn_promote)

        self.btn_rollback = QPushButton("⏪ Deploy Verified Rollback")
        self.btn_rollback.setProperty("danger", "true")
        self.btn_rollback.setEnabled(False)
        self.btn_rollback.setToolTip("Select a record with a saved snapshot archive to restore.")
        self.btn_rollback.clicked.connect(self._rollback_selected)
        act_row.addWidget(self.btn_rollback)

        hist_card.add_layout(act_row)
        self.shell.add_widget(hist_card)
        self.shell.add_stretch()

        self.refresh_table()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _selected_record(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        did = item.data(Qt.UserRole)
        return next((r for r in self.deploy_service.records if r.id == did), None)

    def _on_selection_changed(self) -> None:
        rec = self._selected_record()
        self.btn_open_preview.setEnabled(bool(rec and rec.previewUrl))
        can_promote = bool(rec and rec.targetEnvironment == "preview" and rec.smokeTestPassed and rec.artifactPath)
        self.btn_promote.setEnabled(can_promote)
        self.btn_promote.setToolTip("Promote the exact immutable preview artifact" if can_promote else "Select a smoke-tested preview with a retained immutable artifact.")
        can_rollback = bool(rec and rec.rollbackAvailable and rec.rollbackArtifactPath)
        self.btn_rollback.setEnabled(can_rollback)
        self.btn_rollback.setToolTip("Deploy the retained previous-production artifact" if can_rollback else "No verified previous-production artifact is retained for this record.")

    def refresh_table(self) -> None:
        records = self.deploy_service.all()
        self.table.setRowCount(len(records))
        for row_idx, r in enumerate(records):
            p_item = QTableWidgetItem(r.projectName)
            p_item.setData(Qt.UserRole, r.id)
            e_item = QTableWidgetItem(r.targetEnvironment.upper())
            e_item.setForeground(Qt.green if r.targetEnvironment == "production" and r.smokeTestPassed else Qt.red if "failed" in r.targetEnvironment else Qt.cyan)
            d_item = QTableWidgetItem(r.formattedDate)
            s_item = QTableWidgetItem("PASS (Verified)" if r.smokeTestPassed else "FAIL / UNVERIFIED")
            s_item.setForeground(Qt.green if r.smokeTestPassed else Qt.red)
            u_item = QTableWidgetItem(r.previewUrl or r.productionUrl or "—")
            self.table.setItem(row_idx, 0, p_item)
            self.table.setItem(row_idx, 1, e_item)
            self.table.setItem(row_idx, 2, d_item)
            self.table.setItem(row_idx, 3, s_item)
            self.table.setItem(row_idx, 4, u_item)
        self._on_selection_changed()

    def _log(self, text: str) -> None:
        self.log_console.append(str(text))

    def _run_worker(self, fn, *args, with_progress=False, on_success=None) -> None:
        worker = Worker(fn, *args, with_progress=with_progress)
        if with_progress:
            worker.signals.progress.connect(self._log)
        if on_success:
            worker.signals.result.connect(on_success)
        worker.signals.error.connect(lambda err: self._log(f"✗ {err.splitlines()[0]}"))
        worker.signals.finished.connect(self.refresh_table)
        QThreadPool.globalInstance().start(worker)

    def _create_preview(self) -> None:
        p_name = self.combo_project.currentData()
        dir_rel = "radio" if p_name == "ebeinc" else "visuals-green"
        self.btn_create_preview.setEnabled(False)
        self.log_console.clear()
        self._log(f"=== PREVIEW PIPELINE: {p_name} ===")
        worker = Worker(self.deploy_service.create_preview_deployment, project_name=p_name, directory_rel=dir_rel, with_progress=True)
        worker.signals.progress.connect(self._log)
        worker.signals.result.connect(lambda rec: self._log(f"✓ Preview: {rec.previewUrl}\n✓ Artifact SHA-256: {rec.commitHash}\n✓ Smoke: {rec.smokeTestDetails}"))
        worker.signals.error.connect(lambda err: self._log(f"✗ Preview failed: {err.splitlines()[0]}"))
        worker.signals.finished.connect(lambda: self.btn_create_preview.setEnabled(True))
        worker.signals.finished.connect(self.refresh_table)
        QThreadPool.globalInstance().start(worker)

    def _open_selected_preview(self) -> None:
        rec = self._selected_record()
        if rec and rec.previewUrl:
            SystemService.open_url(rec.previewUrl)

    def _promote_selected(self) -> None:
        rec = self._selected_record()
        if not rec or rec.targetEnvironment != "preview" or not rec.smokeTestPassed:
            return
        rollback_text = "A retained previous-production artifact is available." if rec.rollbackAvailable else "No Hub-created previous-production artifact is available; automatic rollback will NOT be offered."
        dialog = ConfirmDialog(
            title=f"Promote to Production: {rec.projectName}",
            message=f"Deploy the exact tested preview artifact to {rec.productionUrl}?",
            what_it_does=f"Re-verifies preview SHA-256 {rec.commitHash[:12]}… and deploys that same immutable directory to Cloudflare Pages main.",
            what_it_touches="Cloudflare Pages production deployment for this project only.",
            expected_impact="The public website changes immediately. The independent radio audio server is not restarted.",
            rollback_plan=rollback_text,
            affects_live_station=True,
            safety_level="red",
            confirm_label="Deploy Tested Artifact to Production",
            parent=self
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        self.log_console.clear()
        self._log(f"=== PRODUCTION PROMOTION: {rec.projectName} ===")
        self.btn_create_preview.setEnabled(False)
        self.btn_promote.setEnabled(False)
        self.btn_rollback.setEnabled(False)
        worker = Worker(self.deploy_service.promote_to_production, rec.id, with_progress=True)
        worker.signals.progress.connect(self._log)
        worker.signals.result.connect(lambda _: self._log("✓ Production deployment verified live."))
        worker.signals.error.connect(lambda err: self._log(f"✗ Promotion requires attention: {err.splitlines()[0]}"))
        worker.signals.finished.connect(lambda: self.btn_create_preview.setEnabled(True))
        worker.signals.finished.connect(self.refresh_table)
        QThreadPool.globalInstance().start(worker)

    def _rollback_selected(self) -> None:
        rec = self._selected_record()
        if not rec or not rec.rollbackAvailable or not rec.rollbackArtifactPath:
            QMessageBox.warning(self, "Rollback Unavailable", "This deployment does not have a verified retained previous-production artifact. Hub will not pretend a source backup is a production rollback.")
            return
        dialog = ConfirmDialog(
            title=f"Deploy Previous Production: {rec.projectName}",
            message="Deploy the retained previous-production artifact back to Cloudflare production?",
            what_it_does=f"Deploys retained artifact: {rec.rollbackArtifactPath}",
            what_it_touches=f"Cloudflare Pages production for {rec.projectName}.",
            expected_impact="Public site content is changed back to the retained prior artifact. Radio audio services are not restarted.",
            rollback_plan="The currently staged artifact remains retained and can be redeployed later through a new verified preview.",
            affects_live_station=True,
            safety_level="red",
            confirm_label="Deploy Previous Production",
            parent=self
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        self.log_console.clear()
        self.btn_create_preview.setEnabled(False)
        self.btn_promote.setEnabled(False)
        self.btn_rollback.setEnabled(False)
        worker = Worker(self.deploy_service.rollback_to_record, rec.id, with_progress=True)
        worker.signals.progress.connect(self._log)
        worker.signals.result.connect(lambda _: QMessageBox.information(self, "Rollback Verified", "Previous production artifact was deployed and the live smoke test passed."))
        worker.signals.error.connect(lambda err: QMessageBox.critical(self, "Rollback Failed", err.splitlines()[0]))
        worker.signals.finished.connect(lambda: self.btn_create_preview.setEnabled(True))
        worker.signals.finished.connect(self.refresh_table)
        QThreadPool.globalInstance().start(worker)
