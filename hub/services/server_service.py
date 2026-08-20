"""ALLTHINGS140 Hub — Server Management Service.

This module intentionally starts remote state as UNKNOWN.  Reachability is
supplied by the asynchronous HealthService rather than fabricated metrics.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ServerServiceStatus:
    name: str
    active: Optional[bool]
    status: str
    description: str


@dataclass
class ServerHostInfo:
    id: str
    name: str
    tailscale_name: str
    os_type: str
    role: str
    is_reachable: Optional[bool] = None
    uptime: str = "Unknown"
    cpu_load: str = "Unknown"
    memory_used_mb: int = 0
    memory_total_mb: int = 0
    disk_used_percent: int = 0
    ssh_command: str = ""
    services: List[ServerServiceStatus] = field(default_factory=list)
    notes: str = ""


class ServerService:
    def __init__(self) -> None:
        self._servers = self._build_inventory()

    def _build_inventory(self) -> List[ServerHostInfo]:
        unknown = lambda name, desc: ServerServiceStatus(name, None, "unknown", desc)
        return [
            ServerHostInfo(
                id="oracle-vm1",
                name="Oracle Cloud VM 1 (Broadcast Plane)",
                tailscale_name="allthings140radio-server",
                os_type="Oracle Linux (verify live)",
                role="Broadcast Authority (AutoDJ, stream services, cache/catalog services)",
                ssh_command="tailscale ssh ebmarah@allthings140radio-server",
                services=[
                    unknown("allthings140radio-server.service", "AutoDJ & private control API"),
                    unknown("allthings140radio-cache.service", "Predictive hot cache"),
                    unknown("icecast2.service", "Icecast streaming engine"),
                    unknown("cloudflared.service", "Cloudflare tunnel"),
                    unknown("tailscaled.service", "Tailscale mesh VPN"),
                ],
                notes="Displayed service state is UNKNOWN until verified remotely. Hub is not in the broadcast dependency chain.",
            ),
            ServerHostInfo(
                id="oracle-vm2",
                name="Oracle Cloud VM 2 (Visuals Plane)",
                tailscale_name="allthings140-visuals-realtime",
                os_type="Oracle Linux (verify live)",
                role="Realtime/Visuals server (WebSockets, room presence, reactions/energy)",
                ssh_command="tailscale ssh ebmarah@allthings140-visuals-realtime",
                services=[
                    unknown("allthings140-visuals-realtime.service", "Visuals realtime server"),
                    unknown("cloudflared.service", "Cloudflare tunnel"),
                    unknown("tailscaled.service", "Tailscale mesh VPN"),
                ],
                notes="Displayed service state is UNKNOWN until verified remotely. Hub may close without stopping this VM.",
            ),
        ]

    def get_servers(self) -> List[ServerHostInfo]:
        return self._servers

    def can_open_ssh(self) -> bool:
        return bool(shutil.which("tailscale"))

    def launch_ssh_terminal(self, server_id: str) -> bool:
        server = next((s for s in self._servers if s.id == server_id), None)
        if not server or not self.can_open_ssh():
            return False
        title = f"ALLTHINGS140 — SSH ({server.tailscale_name})"
        # Command is a fixed inventory value; no untrusted user input is interpolated.
        shell_cmd = f"echo '=== {server.name} ==='; {server.ssh_command}; exec bash"
        try:
            if shutil.which("gnome-terminal"):
                subprocess.Popen(["gnome-terminal", f"--title={title}", "--", "bash", "-lc", shell_cmd])
            elif shutil.which("x-terminal-emulator"):
                subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-lc", shell_cmd])
            elif shutil.which("xterm"):
                subprocess.Popen(["xterm", "-title", title, "-e", "bash", "-lc", shell_cmd])
            else:
                return False
            return True
        except OSError:
            return False
