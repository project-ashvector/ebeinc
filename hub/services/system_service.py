"""
ALLTHINGS140 Hub — System & Desktop Integration Service
Manages native desktop integration, terminals, browser links, and folder exploration.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional


class SystemService:
    """Provides safe platform integration for Linux and Zorin OS desktop."""

    @staticmethod
    def open_folder(folder_path: str | Path) -> bool:
        p = Path(folder_path)
        if not p.exists():
            return False
        try:
            subprocess.Popen(["xdg-open", str(p)])
            return True
        except Exception:
            return False

    @staticmethod
    def open_url(url: str) -> bool:
        try:
            subprocess.Popen(["xdg-open", url])
            return True
        except Exception:
            return False

    @staticmethod
    def open_terminal(working_dir: str | Path, title: Optional[str] = None, command_to_run: Optional[str] = None) -> bool:
        wd = str(Path(working_dir).resolve())
        t = title or "ALLTHINGS140 Terminal"

        if command_to_run:
            shell_cmd = f"cd '{wd}' && {command_to_run}; exec bash"
        else:
            shell_cmd = f"cd '{wd}'; exec bash"

        try:
            if shutil.which("gnome-terminal"):
                subprocess.Popen([
                    "gnome-terminal",
                    f"--title={t}",
                    f"--working-directory={wd}",
                    "--",
                    "bash", "-c", shell_cmd
                ])
                return True
            elif shutil.which("x-terminal-emulator"):
                subprocess.Popen(["x-terminal-emulator", "-e", f"bash -c \"{shell_cmd}\""], cwd=wd)
                return True
            elif shutil.which("xterm"):
                subprocess.Popen(["xterm", "-title", t, "-e", f"bash -c \"{shell_cmd}\""], cwd=wd)
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def send_notification(title: str, message: str) -> None:
        if shutil.which("notify-send"):
            try:
                subprocess.Popen(["notify-send", title, message, "-a", "ALLTHINGS140 Hub"])
            except Exception:
                pass

    @staticmethod
    def run_async(cmd: list[str] | str, cwd: Optional[str] = None, on_complete: Optional[Callable[[int, str, str], None]] = None) -> None:
        def _target():
            try:
                if isinstance(cmd, str):
                    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
                else:
                    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
                if on_complete:
                    on_complete(res.returncode, res.stdout, res.stderr)
            except Exception as e:
                if on_complete:
                    on_complete(1, "", str(e))

        t = threading.Thread(target=_target, daemon=True)
        t.start()
