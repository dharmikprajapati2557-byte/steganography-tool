"""Run blocking work off the Tk thread and deliver the result back on it."""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable


class TaskRunner:
    """One background job at a time; callbacks always run on the UI thread."""

    def __init__(self, widget) -> None:
        self.widget = widget
        self._queue: queue.Queue = queue.Queue()
        self.busy = False

    def run(self, work: Callable[[], Any], on_success: Callable[[Any], None],
            on_error: Callable[[BaseException], None]) -> bool:
        if self.busy:
            return False
        self.busy = True

        def target() -> None:
            try:
                self._queue.put(("ok", work()))
            except BaseException as exc:  # noqa: BLE001 - forwarded to the UI
                self._queue.put(("err", exc))

        threading.Thread(target=target, daemon=True).start()
        self._poll(on_success, on_error)
        return True

    def _poll(self, on_success, on_error) -> None:
        try:
            kind, value = self._queue.get_nowait()
        except queue.Empty:
            try:
                self.widget.after(40, self._poll, on_success, on_error)
            except Exception:  # widget destroyed
                self.busy = False
            return
        self.busy = False
        (on_success if kind == "ok" else on_error)(value)


def friendly_error(exc: BaseException) -> str:
    """User-facing text for any exception (core errors are already phrased for humans)."""
    from stego.utils import StegoError

    if isinstance(exc, StegoError):
        return str(exc)
    if isinstance(exc, MemoryError):
        return "Not enough memory for this image. Try a smaller one."
    return f"Unexpected error: {exc}"
