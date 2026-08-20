"""
ALLTHINGS140 Hub — Desktop Application Entrypoint
Initializes Qt6, sets application identity (WM_CLASS) for Linux dock matching, and opens MainWindow.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QLockFile, QStandardPaths
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from hub.ui.main_window import MainWindow
from hub.ui.theme import get_application_stylesheet


def main() -> int:
    # Set proper Wayland/X11 application identity
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("allthings140-hub")
    app.setApplicationDisplayName("ALLTHINGS140 Hub")
    app.setDesktopFileName("allthings140-hub.desktop")
    app.setStyleSheet(get_application_stylesheet())

    # A control-plane GUI should have one writer instance by default. This prevents
    # concurrent JSON/CMS/deployment mutations from two accidental Hub windows.
    lock_root = Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation) or "/tmp")
    lock = QLockFile(str(lock_root / f"allthings140-hub-{os.getuid()}.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        QMessageBox.warning(None, "ALLTHINGS140 Hub Already Running", "Another Hub instance is already running for this user. Close it before opening a second control session.")
        return 2
    app._hub_instance_lock = lock  # keep lock alive for entire QApplication lifetime

    # Set icon
    icon_path = Path(__file__).parent / "assets" / "icons" / "allthings140-hub-512x512.png"
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    window = MainWindow()
    window.setObjectName("allthings140-hub")
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
