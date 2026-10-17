"""Reveal > IMAGE: extract hidden data from a stego PNG/BMP."""
from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from gui import theme as T
from gui.components import (BaseScreen, BusyBar, Card, DropZone, GlowButton, ImagePreview, PasswordField,
                            make_textbox, set_text)
from gui.tasks import TaskRunner, friendly_error
from stego.image_lsb import decode_image
from stego.utils import Extracted, StegoError, format_size, write_file


class ImageDecodeScreen(BaseScreen):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.runner = TaskRunner(self)
        self.result: Extracted | None = None
        self.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        self.drop = DropZone(left, app, self._chosen, prompt="Drop the stego image here")
        self.drop.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        pw = Card(left, "Password")
        pw.grid(row=1, column=0, sticky="ew", pady=(0, T.GAP))
        self.password = PasswordField(pw.body, strength=False)
        self.password.grid(row=0, column=0, sticky="ew")
        self.go = GlowButton(left, "Reveal  (Ctrl+Enter)", self.on_run, height=44)
        self.go.grid(row=2, column=0, sticky="ew")
        self.busy = BusyBar(left)
        self.busy.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.preview = ImagePreview(left, "Stego image", "No image chosen")
        self.preview.configure(height=230)
        self.preview.grid(row=4, column=0, sticky="ew", pady=(T.GAP, 0))

        right = Card(self, "Hidden content")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.body.grid_rowconfigure(0, weight=1)
        self.output = make_textbox(right.body, app, readonly=True)
        self.output.grid(row=0, column=0, columnspan=2, sticky="nsew")
        GlowButton(right.body, "Copy", self._copy, variant="secondary").grid(row=1, column=0, sticky="ew", pady=(T.GAP, 0), padx=(0, 5))
        GlowButton(right.body, "Save as file…  (Ctrl+S)", self.on_save, variant="secondary").grid(row=1, column=1, sticky="ew", pady=(T.GAP, 0), padx=(5, 0))
        right.body.grid_columnconfigure((0, 1), weight=1)

    def _chosen(self, path: str) -> None:
        try:
            self.preview.set_image(path)
            self.app.set_status(f"Loaded {path}", "ready")
        except Exception as exc:  # noqa: BLE001
            self.drop.reset()
            self.app.toast(friendly_error(exc), "error")

    def on_open(self) -> None:
        self.drop.browse()

    def on_run(self) -> None:
        if self.runner.busy:
            return
        if not self.drop.path:
            return self.app.toast("Choose a stego image first.", "error")
        path, pw = self.drop.path, self.password.get() or None
        self.go.configure(state="disabled")
        self.busy.start_busy()
        self.app.set_status("Working: extracting…", "working")
        self.runner.run(lambda: decode_image(path, password=pw), self._done, self._failed)

    def _finish(self) -> None:
        self.go.configure(state="normal")
        self.busy.stop_busy()

    def _done(self, res: Extracted) -> None:
        self._finish()
        self.result = res
        if res.is_file:
            set_text(self.output, f"[Hidden file]\nName: {res.filename}\nSize: {format_size(len(res.data))}\n\nUse “Save as file…” to extract it.")
        else:
            set_text(self.output, res.text())
        self.output.configure(state="disabled")
        self.app.toast("Hidden data revealed", "success")
        self.app.set_status("Done: data revealed", "done")

    def _failed(self, exc: BaseException) -> None:
        self._finish()
        self.app.toast(friendly_error(exc), "error")
        self.app.set_status("Error: " + friendly_error(exc), "error")

    def _copy(self) -> None:
        if not self.result or self.result.is_file:
            return self.app.toast("Nothing to copy - the hidden content is a file." if self.result else "Nothing revealed yet.", "info")
        self.clipboard_clear()
        self.clipboard_append(self.result.text())
        self.app.toast("Copied to clipboard", "success")

    def on_save(self) -> None:
        if not self.result:
            return self.app.toast("Reveal something first.", "info")
        name = self.result.filename or "revealed.txt"
        path = filedialog.asksaveasfilename(initialdir=self.app.cfg.last_dir, initialfile=name)
        if not path:
            return
        try:
            write_file(path, self.result.data, overwrite=True)
        except StegoError as exc:
            return self.app.toast(friendly_error(exc), "error")
        self.app.cfg.remember_dir(path)
        self.app.toast(f"Saved {path}", "success")
