"""Qt-safe background worker helpers.

All worker callbacks are marshalled back to the GUI thread through Qt signals.
"""
from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, with_progress: bool = False, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.with_progress = with_progress
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                self.kwargs["progress_cb"] = self.signals.progress.emit
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as exc:
            self.signals.error.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        finally:
            self.signals.finished.emit()
