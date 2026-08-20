"""
ALLTHINGS140 Hub — Health & Diagnostics View
Detailed telemetry gauges, endpoint verification tables, and station diagnostic runs.
"""

from __future__ import annotations

from typing import Optional
import subprocess

from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hub.services.health_service import HealthService, StationHealthSnapshot
from hub.ui.components.data_table import DataTable
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.components.stat_box import StatBox
from hub.ui.components.status_pill import StatusPill
from hub.ui.worker import Worker
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


class HealthView(QWidget):
    """Deep diagnostics and healthcheck inspector."""

    open_guide = Signal(str)
    refresh_requested = Signal()

    def __init__(self, health_service: HealthService, parent=None):
        super().__init__(parent)
        self.health_service = health_service
        self.worker_pool = QThreadPool.globalInstance()
        self._diag_running = False
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Station Health & Deep Diagnostics",
            subtitle="Real-time status probes for public website, live audio streaming, and authority APIs.",
            guide_key="page-health",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # 1. Endpoint Breakdown Card
        card_ep = SectionCard(
            title="CHECKED ENDPOINTS & HEALTH METRICS",
            subtitle="Read-only endpoint checks. Running diagnostics will never interrupt broadcast or live listeners.",
            guide_key="page-health",
            safety_level="green"
        )

        self.btn_run_check = QPushButton("🩺 Run Diagnostics")
        self.btn_run_check.setProperty("primary", "true")
        self.btn_run_check.setToolTip("Run tools/allthings140-diagnose.py station diagnostic suite")
        self.btn_run_check.clicked.connect(self._run_diagnostics)
        card_ep.header_actions.addWidget(self.btn_run_check)

        self.table = DataTable(
            columns=["Endpoint Name", "Target URL / Resource", "Status", "Latency", "Result Detail"],
            stretch_column_index=4,
            resize_to_contents_indices=[0, 2, 3]
        )
        self.table.setFixedHeight(220)
        card_ep.add_widget(self.table)
        self.shell.add_widget(card_ep)

        # 2. Diagnostic Output Console Card
        card_console = SectionCard(
            title="DIAGNOSTIC RUN OUTPUT (tools/allthings140-diagnose.py)",
            subtitle="Terminal output from read-only station verification scripts",
            guide_key="page-health",
            safety_level="green"
        )

        self.diag_console = QTextEdit()
        self.diag_console.setReadOnly(True)
        self.diag_console.setFixedHeight(200)
        self.diag_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_DARK};
                font-family: monospace;
                font-size: 11px;
                color: {STATUS_GREEN};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        self.diag_console.setPlaceholderText("Click 'Run Diagnostics' to execute deep station diagnosis…")
        card_console.add_widget(self.diag_console)
        self.shell.add_widget(card_console)

        self.shell.add_stretch()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def update_health(self, snapshot: StationHealthSnapshot) -> None:
        self.table.setRowCount(len(snapshot.checks))
        for row_idx, check in enumerate(snapshot.checks):
            n_item = QTableWidgetItem(check.name)
            t_item = QTableWidgetItem(check.target)
            s_item = QTableWidgetItem("PASS (Healthy)" if check.is_healthy else "FAIL (Warning)")
            s_item.setForeground(Qt.green if check.is_healthy else Qt.red)
            l_item = QTableWidgetItem(f"{check.response_time_ms} ms")
            d_item = QTableWidgetItem(check.detail[:90])

            self.table.setItem(row_idx, 0, n_item)
            self.table.setItem(row_idx, 1, t_item)
            self.table.setItem(row_idx, 2, s_item)
            self.table.setItem(row_idx, 3, l_item)
            self.table.setItem(row_idx, 4, d_item)

    def _execute_diagnostics(self):
        script = self.health_service.project_root / "tools" / "allthings140-diagnose.py"
        if not script.is_file():
            raise FileNotFoundError(f"Diagnostic script not found: {script}")
        proc = subprocess.run(
            ["python3", str(script)],
            cwd=str(self.health_service.project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _run_diagnostics(self) -> None:
        if self._diag_running:
            return
        self._diag_running = True
        self.btn_run_check.setEnabled(False)
        self.diag_console.setPlainText("Running read-only station diagnostics in the background...\n")

        worker = Worker(self._execute_diagnostics)

        def on_result(result):
            code, stdout, stderr = result
            output = stdout or stderr or f"Diagnostics completed with exit code {code}."
            if code != 0:
                output = f"EXIT CODE: {code}\n\n{output}"
            self.diag_console.setPlainText(output)
            self.refresh_requested.emit()

        def on_error(message: str):
            self.diag_console.setPlainText(f"Diagnostic run failed safely.\n\n{message}")

        def on_finished():
            self._diag_running = False
            self.btn_run_check.setEnabled(True)

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self.worker_pool.start(worker)
