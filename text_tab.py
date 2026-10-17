"""TEXT tab: hide / reveal messages with zero-width characters."""
from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from gui import theme as T
from gui.components import (BaseScreen, BusyBar, Card, GlowButton, PasswordField, get_text, label, make_textbox,
                            set_text)
from gui.tasks import TaskRunner, friendly_error
from stego.text_zw import STRIP_WARNING, TextEmbedResult, decode_text, encode_text
from stego.utils import Extracted, StegoError, format_size, read_file, write_file


def _warning(master) -> ctk.CTkLabel:
    return label(master, "⚠ " + STRIP_WARNING, size=11, color=T.AMBER, wraplength=420, justify="left")


class TextHideScreen(BaseScreen):
    """Cover + secret in, stego text out."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.runner = TaskRunner(self)
        self.result: TextEmbedResult | None = None
        self.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure((0, 1), weight=1, uniform="tb")
        cover = Card(left, "Cover text (what everyone sees)")
        cover.grid(row=0, column=0, sticky="nsew", pady=(0, T.GAP))
        cover.body.grid_rowconfigure(0, weight=1)
        self.cover = make_textbox(cover.body, app)
        self.cover.grid(row=0, column=0, sticky="nsew")
        secret = Card(left, "Secret message")
        secret.grid(row=1, column=0, sticky="nsew")
        secret.body.grid_rowconfigure(0, weight=1)
        self.secret = make_textbox(secret.body, app)
        self.secret.grid(row=0, column=0, sticky="nsew")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)
        prot = Card(right, "Protection")
        prot.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        self.password = PasswordField(prot.body)
        self.password.grid(row=0, column=0, sticky="ew")
        self.compress = ctk.BooleanVar(value=bool(app.cfg.get("compress")))
        ctk.CTkCheckBox(prot.body, text="Compress (zlib)", variable=self.compress, font=T.font(12), text_color=T.TEXT,
                        fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, checkmark_color=T.ON_ACCENT).grid(row=1, column=0, sticky="w", pady=(10, 0))
        row = ctk.CTkFrame(right, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(0, T.GAP))
        row.grid_columnconfigure(0, weight=1)
        self.go = GlowButton(row, "Hide  (Ctrl+Enter)", self.on_run, height=44)
        self.go.grid(row=0, column=0, sticky="ew")
        self.busy = BusyBar(row)
        self.busy.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        out = Card(right, "Stego text (looks identical to the cover)")
        out.grid(row=2, column=0, sticky="nsew")
        out.body.grid_rowconfigure(0, weight=1)
        out.body.grid_columnconfigure((0, 1), weight=1)
        self.output = make_textbox(out.body, app, readonly=True)
        self.output.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.info = label(out.body, "", size=11, color=T.MUTED, wraplength=420, justify="left")
        self.info.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        GlowButton(out.body, "Copy", self._copy, variant="secondary").grid(row=2, column=0, sticky="ew", padx=(0, 5), pady=(6, 0))
        GlowButton(out.body, "Save .txt  (Ctrl+S)", self.on_save, variant="secondary").grid(row=2, column=1, sticky="ew", padx=(5, 0), pady=(6, 0))
        _warning(out.body).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def on_open(self) -> None:
        path = filedialog.askopenfilename(initialdir=self.app.cfg.last_dir, filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if path:
            try:
                set_text(self.cover, read_file(path).decode("utf-8"))
                self.app.cfg.remember_dir(path)
            except (StegoError, UnicodeDecodeError) as exc:
                self.app.toast(friendly_error(exc) if isinstance(exc, StegoError) else "That file is not UTF-8 text.", "error")

    def on_run(self) -> None:
        if self.runner.busy:
            return
        cover, secret = get_text(self.cover), get_text(self.secret)
        if not cover.strip():
            return self.app.toast("Type or load a cover text first.", "error")
        if not secret:
            return self.app.toast("Nothing to hide - type a secret message.", "error")
        pw, comp = self.password.get() or None, self.compress.get()
        self.go.configure(state="disabled")
        self.busy.start_busy()
        self.app.set_status("Working: encoding…", "working")
        self.runner.run(lambda: encode_text(cover, secret.encode("utf-8"), password=pw, compress=comp), self._done, self._failed)

    def _finish(self) -> None:
        self.go.configure(state="normal")
        self.busy.stop_busy()

    def _done(self, r: TextEmbedResult) -> None:
        self._finish()
        self.result = r
        set_text(self.output, r.text)
        self.output.configure(state="disabled")
        self.info.configure(text=f"{r.hidden_chars} invisible characters hidden among {r.visible_chars} visible ones "
                                 f"({r.density:.1f} per char) · payload {format_size(r.payload_bytes)} of {format_size(r.capacity_bytes)}")
        self.app.toast("Secret hidden in the text - copy it with the button below", "success")
        self.app.set_status("Done: text encoded", "done")

    def _failed(self, exc: BaseException) -> None:
        self._finish()
        self.app.toast(friendly_error(exc), "error")
        self.app.set_status("Error: " + friendly_error(exc), "error")

    def _copy(self) -> None:
        if not self.result:
            return self.app.toast("Nothing to copy yet.", "info")
        self.clipboard_clear()
        self.clipboard_append(self.result.text)
        self.app.toast("Stego text copied (hidden characters included)", "success")

    def on_save(self) -> None:
        if not self.result:
            return self.app.toast("Hide something first.", "info")
        path = filedialog.asksaveasfilename(initialdir=self.app.cfg.last_dir, initialfile="stego.txt", defaultextension=".txt")
        if path:
            try:
                write_file(path, self.result.text.encode("utf-8"), overwrite=True)
                self.app.cfg.remember_dir(path)
                self.app.toast(f"Saved {path}", "success")
            except StegoError as exc:
                self.app.toast(friendly_error(exc), "error")


class TextRevealScreen(BaseScreen):
    """Paste (or load) stego text, get the secret back."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.runner = TaskRunner(self)
        self.result: Extracted | None = None
        self.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        src = Card(left, "Stego text (paste here)")
        src.grid(row=0, column=0, sticky="nsew", pady=(0, T.GAP))
        src.body.grid_rowconfigure(0, weight=1)
        self.source = make_textbox(src.body, app)
        self.source.grid(row=0, column=0, sticky="nsew")
        GlowButton(src.body, "Load .txt…  (Ctrl+O)", self.on_open, variant="secondary").grid(row=1, column=0, sticky="ew", pady=(T.GAP, 0))
        pw = Card(left, "Password")
        pw.grid(row=1, column=0, sticky="ew", pady=(0, T.GAP))
        self.password = PasswordField(pw.body, strength=False)
        self.password.grid(row=0, column=0, sticky="ew")
        self.go = GlowButton(left, "Reveal  (Ctrl+Enter)", self.on_run, height=44)
        self.go.grid(row=2, column=0, sticky="ew")
        self.busy = BusyBar(left)
        self.busy.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        out = Card(self, "Hidden message")
        out.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        out.body.grid_rowconfigure(0, weight=1)
        out.body.grid_columnconfigure((0, 1), weight=1)
        self.output = make_textbox(out.body, app, readonly=True)
        self.output.grid(row=0, column=0, columnspan=2, sticky="nsew")
        GlowButton(out.body, "Copy", self._copy, variant="secondary").grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(T.GAP, 0))
        GlowButton(out.body, "Save as file…  (Ctrl+S)", self.on_save, variant="secondary").grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(T.GAP, 0))
        _warning(out.body).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def on_open(self) -> None:
        path = filedialog.askopenfilename(initialdir=self.app.cfg.last_dir, filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if path:
            try:
                set_text(self.source, read_file(path).decode("utf-8"))
                self.app.cfg.remember_dir(path)
            except (StegoError, UnicodeDecodeError) as exc:
                self.app.toast(friendly_error(exc) if isinstance(exc, StegoError) else "That file is not UTF-8 text.", "error")

    def on_run(self) -> None:
        if self.runner.busy:
            return
        text, pw = get_text(self.source), self.password.get() or None
        if not text:
            return self.app.toast("Paste the stego text first.", "error")
        self.go.configure(state="disabled")
        self.busy.start_busy()
        self.app.set_status("Working: decoding…", "working")
        self.runner.run(lambda: decode_text(text, password=pw), self._done, self._failed)

    def _finish(self) -> None:
        self.go.configure(state="normal")
        self.busy.stop_busy()

    def _done(self, res: Extracted) -> None:
        self._finish()
        self.result = res
        body = (f"[Hidden file]\nName: {res.filename}\nSize: {format_size(len(res.data))}\n\nUse “Save as file…” to extract it."
                if res.is_file else res.text())
        set_text(self.output, body)
        self.output.configure(state="disabled")
        self.app.toast("Hidden message revealed", "success")
        self.app.set_status("Done: message revealed", "done")

    def _failed(self, exc: BaseException) -> None:
        self._finish()
        self.app.toast(friendly_error(exc), "error")
        self.app.set_status("Error: " + friendly_error(exc), "error")

    def _copy(self) -> None:
        if not self.result or self.result.is_file:
            return self.app.toast("Nothing to copy.", "info")
        self.clipboard_clear()
        self.clipboard_append(self.result.text())
        self.app.toast("Copied to clipboard", "success")

    def on_save(self) -> None:
        if not self.result:
            return self.app.toast("Reveal something first.", "info")
        path = filedialog.asksaveasfilename(initialdir=self.app.cfg.last_dir, initialfile=self.result.filename or "revealed.txt")
        if path:
            try:
                write_file(path, self.result.data, overwrite=True)
                self.app.toast(f"Saved {path}", "success")
            except StegoError as exc:
                self.app.toast(friendly_error(exc), "error")
