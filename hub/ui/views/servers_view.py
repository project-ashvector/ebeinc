"""
ALLTHINGS140 Hub — Server Management View
Monitors Oracle VM 1 (Broadcast Plane) and Oracle VM 2 (Visuals Plane) via Tailscale.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.services.server_service import ServerHostInfo, ServerService
from hub.ui.components.confirm_dialog import ConfirmDialog
from hub.ui.components.page_shell import PageShell
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.section_card import SectionCard
from hub.ui.components.status_pill import StatusPill
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
    SAFETY_RED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ServersView(QWidget):
    """View managing Oracle Cloud VM 1 & VM 2 infrastructure."""

    open_guide = Signal(str)

    def __init__(self, server_service: ServerService, parent=None):
        super().__init__(parent)
        self.server_service = server_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Cloud Infrastructure & Server Fleet",
            subtitle="Inspect remote compute instances, systemd service units, and Tailscale mesh connections.",
            guide_key="page-servers",
            safety_level="orange"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        servers = self.server_service.get_servers()
        for server in servers:
            card = SectionCard(
                title=f"{server.name} ({server.id})",
                subtitle=f"Role: {server.role} • Tailscale MagicDNS: {server.tailscale_name} • OS: {server.os_type}",
                guide_key="page-servers",
                safety_level="green" if server.is_reachable else "red"
            )

            # Server status pill in header
            status_pill = StatusPill("UNKNOWN")
            status_pill.setObjectName(f"server-status-{server.id}")
            if not hasattr(self, "status_pills"):
                self.status_pills = {}
            self.status_pills[server.id] = status_pill
            card.header_actions.addWidget(status_pill)

            # Metrics Box
            m_frame = QFrame()
            m_frame.setStyleSheet(f"background: {BG_DARK}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 12px;")
            m_layout = QHBoxLayout(m_frame)
            m_layout.setSpacing(16)

            def add_metric(label: str, val: str):
                c = QVBoxLayout()
                c.setSpacing(2)
                l = QLabel(label.upper())
                l.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 800;")
                v = QLabel(val)
                v.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold; font-family: monospace;")
                c.addWidget(l)
                c.addWidget(v)
                m_layout.addLayout(c)

            add_metric("Uptime", server.uptime)
            add_metric("CPU Load", server.cpu_load)
            add_metric("RAM Memory", "Unknown")
            add_metric("Disk Usage", "Unknown")
            m_layout.addStretch()

            card.add_widget(m_frame)

            # Managed Services List
            svc_title = QLabel("MANAGED SYSTEMD SERVICES:")
            svc_title.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; margin-top: 6px;")
            card.add_widget(svc_title)

            for svc in server.services:
                s_row = QHBoxLayout()
                s_name = QLabel(f"• {svc.name}")
                s_name.setStyleSheet(f"font-family: monospace; font-size: 12px; color: {TEXT_PRIMARY}; font-weight: bold;")
                s_desc = QLabel(f"— {svc.description}")
                s_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
                s_row.addWidget(s_name)
                s_row.addWidget(s_desc, 1)
                s_row.addWidget(StatusPill(svc.status))
                card.add_layout(s_row)

            # Actions Row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(10)
            btn_row.addStretch()

            btn_ssh = QPushButton("🖥️ Open SSH Terminal")
            btn_ssh.setProperty("primary", "true")
            if self.server_service.can_open_ssh():
                btn_ssh.setToolTip(f"Open secure SSH shell via Tailscale to {server.tailscale_name}. This does not assume the VM is online.")
            else:
                btn_ssh.setEnabled(False)
                btn_ssh.setToolTip("Tailscale CLI is not available on this workstation.")
            btn_ssh.clicked.connect(lambda checked=False, sid=server.id: self._open_ssh(sid))
            btn_row.addWidget(btn_ssh)

            btn_restart = QPushButton("🔒 Service Restart (Disabled)")
            btn_restart.setProperty("warning", "true")
            btn_restart.setEnabled(False)
            btn_restart.setToolTip("Disabled in v1.2.1 safety release: the previous button did not perform a real verified restart. Use SSH/Guide until a transactional remote action API is implemented.")
            btn_row.addWidget(btn_restart)

            card.add_layout(btn_row)
            self.shell.add_widget(card)

        self.shell.add_stretch()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()

    def _open_ssh(self, server_id: str) -> None:
        self.server_service.launch_ssh_terminal(server_id)

    def _confirm_restart(self, server_name: str, server_id: str) -> None:
        QMessageBox.information(self, "Restart Disabled", "Remote service restart is disabled in this safety release because the previous implementation only simulated success. Use the SSH terminal and documented runbook until a verified management API is available.")

    def update_health(self, snapshot) -> None:
        if not hasattr(self, "status_pills"):
            return
        vm1 = "REACHABLE" if snapshot.vm1_reachable else "UNKNOWN"
        vm2 = "REACHABLE" if snapshot.vm2_reachable else "UNKNOWN"
        if "oracle-vm1" in self.status_pills:
            self.status_pills["oracle-vm1"].set_status(vm1)
        if "oracle-vm2" in self.status_pills:
            self.status_pills["oracle-vm2"].set_status(vm2)
