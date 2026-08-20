"""
ALLTHINGS140 Hub — Configuration & User Preferences
Manages local configuration, persistence, directories, and defaults.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(os.environ.get("ALLTHINGS140_PROJECT_ROOT", "/home/ebmarah/Projects/AllThings140Radio")).expanduser().resolve()
CANONICAL_PROJECTS_ROOT = Path("/home/ebmarah/Projects").resolve()
DOCS_REPORTS_DIR = Path("/home/ebmarah/Documents/ALLTHINGS140-Reports").resolve()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "allthings140-hub"
CONFIG_FILE = CONFIG_DIR / "config.json"
HANDOFFS_FILE = CONFIG_DIR / "handoffs.json"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
ACTIVITY_FILE = CONFIG_DIR / "activity.json"
HEALTH_HISTORY_FILE = CONFIG_DIR / "health_history.json"


@dataclass
class AIProviderConfig:
    id: str
    name: str
    executable: str
    enabled: bool = True
    default_model: str = ""
    extra_args: List[str] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConnectedPC:
    id: str
    name: str
    hostname_or_ip: str
    tailscale_name: str
    os_type: str = "linux"
    status: str = "unknown"
    role: str = "workstation"
    notes: str = ""


@dataclass
class SharedFolder:
    id: str
    name: str
    path: str
    description: str
    folder_type: str = "media"  # media, music, backup, staging, export
    is_critical: bool = False


@dataclass
class HubConfig:
    version: str = "1.2.1"
    current_project_path: str = str(PROJECT_ROOT)
    poll_interval_seconds: int = 15
    auto_refresh_health: bool = True
    theme: str = "allthings140-dark"
    default_ai_provider: str = "antigravity"
    ai_providers: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "antigravity": {
            "id": "antigravity",
            "name": "Google Antigravity (agy)",
            "executable": "/home/ebmarah/.local/bin/agy",
            "enabled": True,
            "default_model": "inherit",
            "extra_args": []
        },
        "codex": {
            "id": "codex",
            "name": "OpenAI Codex CLI",
            "executable": "/home/ebmarah/.local/bin/codex",
            "enabled": True,
            "default_model": "",
            "extra_args": []
        },
        "opencode": {
            "id": "opencode",
            "name": "OpenCode CLI",
            "executable": "/home/ebmarah/.opencode/bin/opencode",
            "enabled": True,
            "default_model": "",
            "extra_args": []
        },
        "ollama": {
            "id": "ollama",
            "name": "Local Ollama LLM",
            "executable": "/usr/local/bin/ollama",
            "enabled": True,
            "default_model": "llama3.2:3b",
            "extra_args": ["run", "llama3.2:3b"]
        }
    })
    connected_pcs: List[Dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "workstation-zorin",
            "name": "Main Zorin Workstation",
            "hostname_or_ip": "127.0.0.1",
            "tailscale_name": "at140-workstation",
            "os_type": "Zorin OS 17 (Linux)",
            "status": "unknown",
            "role": "Development / Show Control",
            "notes": "Primary workstation running Hub, DJ App, Visuals App"
        },
        {
            "id": "oracle-vm1",
            "name": "Oracle Cloud VM 1 (Broadcast Authority)",
            "hostname_or_ip": "allthings140radio-server",
            "tailscale_name": "allthings140radio-server",
            "os_type": "Oracle Linux 9.8",
            "status": "unknown",
            "role": "24/7 Broadcast Server (AutoDJ + Icecast + Hot Cache)",
            "notes": "Plane 2 station authority. Ports 14080 (API), 14000 (Icecast)"
        },
        {
            "id": "oracle-vm2",
            "name": "Oracle Cloud VM 2 (Visuals & Realtime)",
            "hostname_or_ip": "allthings140-visuals-realtime",
            "tailscale_name": "allthings140-visuals-realtime",
            "os_type": "Oracle Linux 9.8",
            "status": "unknown",
            "role": "Plane 3 Realtime WebSocket Server + Media Staging",
            "notes": "Plane 3 room presence, chat, reactions, energy"
        }
    ])
    shared_folders: List[Dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "desktop-visuals",
            "name": "Desktop Visuals Library",
            "path": "/home/ebmarah/Videos/at140radio/desktop visuals",
            "description": "Stage and Visual media files used by Show Control; current count is discovered elsewhere.",
            "folder_type": "media",
            "is_critical": True
        },
        {
            "id": "emergency-mirror",
            "name": "Station Emergency Music Mirror",
            "path": "/srv/allthings140radio/data/music",
            "description": "Station emergency music mirror; current file/integrity state must be verified live.",
            "folder_type": "music",
            "is_critical": True
        },
        {
            "id": "station-db",
            "name": "Station Database & State",
            "path": "/var/lib/allthings140radio",
            "description": "SQLite station.db, catalog integrity, rotation state",
            "folder_type": "data",
            "is_critical": True
        },
        {
            "id": "project-backups",
            "name": "Local Workstation Backups",
            "path": "/home/ebmarah/Projects/AllThings140Radio/backups",
            "description": "Local pre-deployment and component backup archives",
            "folder_type": "backup",
            "is_critical": False
        },
        {
            "id": "music-backups",
            "name": "Master Music Backups",
            "path": "/home/ebmarah/Music/ALLTHINGS140/ALLTHINGS140_BACKUPS",
            "description": "Master audio archive and emergency dumps",
            "folder_type": "backup",
            "is_critical": False
        }
    ])
    terminal_emulator: str = "auto"  # auto, gnome-terminal, x-terminal-emulator, xterm
    notifications_enabled: bool = False
    backup_retention_days: int = 30
    safe_update_auto_backup: bool = True
    safe_update_auto_test: bool = True
    protected_operator_mode: bool = True
    first_run_tour_completed: bool = False


def get_config() -> HubConfig:
    """Load configuration from disk, creating defaults if missing."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        cfg = HubConfig()
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return HubConfig(**{k: v for k, v in data.items() if k in HubConfig.__dataclass_fields__})
    except Exception:
        # Preserve a damaged configuration instead of silently destroying operator state.
        try:
            import time
            damaged = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + f".corrupt-{int(time.time())}")
            CONFIG_FILE.replace(damaged)
        except Exception:
            pass
        cfg = HubConfig()
        save_config(cfg)
        return cfg


def save_config(config: HubConfig) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    from hub.util.atomic_io import atomic_write_json
    atomic_write_json(CONFIG_FILE, asdict(config))
