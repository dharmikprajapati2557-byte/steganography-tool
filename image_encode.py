"""Hide > IMAGE: embed a message/file into a PNG/BMP."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gui import theme as T
from gui.components import (BaseScreen, BusyBar, CapacityMeter, Card, DropZone, GlowButton, ImagePreview,
                            PasswordField, StatsCard, get_text, label, make_textbox)
from gui.tasks import TaskRunner, friendly_error
from stego.header import HEADER_SIZE, estimate_blob_size
from stego.image_lsb import EmbedResult, encode_image, image_capacity_bytes
from stego.utils import StegoError, format_size, read_file

MAX_ATTACH = 64 * 1024 * 1024


class ImageEncodeScreen(BaseScreen):
    """Left: inputs. Right: cover / stego previews and the quality report."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.runner = TaskRunner(self)
        self.capacity: int | None = None
        self.attachment: tuple[str, bytes] | None = None
        self._meter_job = None
        self.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        self.drop = DropZone(left, app, self._cover_chosen)
        self.drop.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))

        secret = Card(left, "Secret")
        secret.grid(row=1, column=0, sticky="ew", pady=(0, T.GAP))
        self.mode = ctk.CTkSegmentedButton(secret.body, values=["Text", "File"], command=self._mode_changed,
                                           font=T.font(12, "bold"), fg_color=T.PANEL, selected_color=T.CYAN,
                                           selected_hover_color=T.CYAN, unselected_color=T.PANEL,
                                           text_color=T.TEXT)
        self.mode.set("Text")
        self.mode.grid(row=0, column=0, sticky="w")
        self.text = make_textbox(secret.body, app, height=110)
        self.text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.text.bind("<KeyRelease>", lambda _e: self._schedule_meter())
        self.file_row = ctk.CTkFrame(secret.body, fg_color="transparent")
        GlowButton(self.file_row, "Attach file…", self._attach, variant="secondary", width=130).pack(side="left")
        self.file_label = label(self.file_row, "No file attached", size=12, color=T.MUTED)
        self.file_label.pack(side="left", padx=T.GAP)

        prot = Card(left, "Protection")
        prot.grid(row=2, column=0, sticky="ew", pady=(0, T.GAP))
        self.password = PasswordField(prot.body, on_change=self._schedule_meter)
        self.password.grid(row=0, column=0, sticky="ew")
        self.compress = ctk.BooleanVar(value=bool(app.cfg.get("compress")))
        self.random = ctk.BooleanVar(value=bool(app.cfg.get("random_order")))
        for i, (txt, var) in enumerate((("Compress (zlib)", self.compress), ("Random pixel order (needs password)", self.random))):
            ctk.CTkCheckBox(prot.body, text=txt, variable=var, font=T.font(12), text_color=T.TEXT,
                            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, checkmark_color=T.ON_ACCENT,
                            command=self._schedule_meter).grid(row=1 + i, column=0, sticky="w", pady=(10 if i == 0 else 6, 0))

        self.meter = CapacityMeter(left)
        self.meter.grid(row=3, column=0, sticky="ew", pady=(0, T.GAP))
        self.go = GlowButton(left, "Hide Data  (Ctrl+Enter)", self.on_run, height=44)
        self.go.grid(row=4, column=0, sticky="ew")
        self.busy = BusyBar(left)
        self.busy.grid(row=5, column=0, sticky="ew", pady=(10, 0))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure((0, 1), weight=1, uniform="pv")
        right.grid_rowconfigure(0, weight=1)
        self.cover_view = ImagePreview(right, "Cover", "Drop a cover image")
        self.cover_view.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.stego_view = ImagePreview(right, "Stego", "Result appears here")
        self.stego_view.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.stats = StatsCard(right, "Quality report", "Hide some data to see MSE / PSNR")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(T.GAP, 0))

    # ---- inputs
    def _mode_changed(self, mode: str) -> None:
        if mode == "Text":
            self.file_row.grid_forget()
            self.text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        else:
            self.text.grid_forget()
            self.file_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._schedule_meter()

    def _attach(self) -> None:
        path = filedialog.askopenfilename(initialdir=self.app.cfg.last_dir)
        if not path:
            return
        try:
            if Path(path).stat().st_size > MAX_ATTACH:
                raise StegoError("That file is too large to hide (limit 64 MB).")
            self.attachment = (Path(path).name, read_file(path))
        except (StegoError, OSError) as exc:
            self.app.toast(friendly_error(exc), "error")
            return
        self.app.cfg.remember_dir(path)
        self.file_label.configure(text=f"{self.attachment[0]} ({format_size(len(self.attachment[1]))})", text_color=T.ACCENT)
        self._schedule_meter()

    def _cover_chosen(self, path: str) -> None:
        try:
            self.capacity = image_capacity_bytes(path)
            self.cover_view.set_image(path)
        except Exception as exc:  # noqa: BLE001
            self.capacity = None
            self.drop.reset()
            self.cover_view.clear()
            self.app.toast(friendly_error(exc), "error")
            self.app.set_status("Cover image rejected", "error")
        else:
            self.app.set_status(f"Cover loaded: {self.capacity:,} bytes of capacity", "ready")
        self._schedule_meter()

    # ---- meter
    def _secret(self) -> tuple[bytes, str | None]:
        if self.mode.get() == "File":
            return (self.attachment[1], self.attachment[0]) if self.attachment else (b"", None)
        return get_text(self.text).encode("utf-8"), None

    def _schedule_meter(self) -> None:
        if self._meter_job:
            self.after_cancel(self._meter_job)
        self._meter_job = self.after(250, self._refresh_meter)

    def _refresh_meter(self) -> bool:
        self._meter_job = None
        data, name = self._secret()
        used = 0
        if data:
            used = estimate_blob_size(data, name, encrypted=bool(self.password.get()), compress=self.compress.get()) - HEADER_SIZE
        return self.meter.update_meter(used, self.capacity)

    # ---- run
    def on_open(self) -> None:
        self.drop.browse()

    def on_save(self) -> None:
        self.on_run()

    def on_run(self) -> None:
        if self.runner.busy:
            return
        if not self.drop.path or self.capacity is None:
            return self.app.toast("Choose a cover image first.", "error")
        data, name = self._secret()
        if not data:
            return self.app.toast("Nothing to hide - type a message or attach a file.", "error")
        pw = self.password.get() or None
        if self.random.get() and not pw:
            return self.app.toast("Random pixel order needs a password.", "error")
        if not self._refresh_meter():
            return self.app.toast("The secret is too big for this image. Use a larger cover or a smaller secret.", "error")
        cover = self.drop.path
        out = filedialog.asksaveasfilename(title="Save stego image", initialdir=self.app.cfg.last_dir,
                                           initialfile=f"{Path(cover).stem}_stego.png", defaultextension=".png",
                                           filetypes=[("PNG image", "*.png"), ("BMP image", "*.bmp")])
        if not out:
            return
        self.app.cfg.remember_dir(out)
        compress, random_order = self.compress.get(), self.random.get()  # Tk variables: read on the UI thread
        self._set_busy(True)
        self.runner.run(
            lambda: encode_image(cover, out, data, filename=name, password=pw, compress=compress,
                                 random_order=random_order, overwrite=True),
            self._done, self._failed)

    def _set_busy(self, busy: bool) -> None:
        self.go.configure(state="disabled" if busy else "normal")
        (self.busy.start_busy if busy else self.busy.stop_busy)()
        if busy:
            self.app.set_status("Working: embedding data…", "working")

    def _done(self, r: EmbedResult) -> None:
        self._set_busy(False)
        self.stego_view.set_image(r.output_path)
        psnr = "∞ (identical)" if r.psnr == float("inf") else f"{r.psnr:.2f} dB"
        self.stats.show([("MSE", f"{r.mse:.5f}"), ("PSNR", psnr),
                         ("Payload", f"{format_size(r.payload_bytes)} of {format_size(r.capacity_bytes)} ({r.used_percent:.2f}%)"),
                         ("Saved as", r.output_path.name)])
        self.app.toast(f"Data hidden in {r.output_path.name}", "success")
        self.app.set_status(f"Done: saved {r.output_path}", "done")

    def _failed(self, exc: BaseException) -> None:
        self._set_busy(False)
        self.app.toast(friendly_error(exc), "error")
        self.app.set_status("Error: " + friendly_error(exc), "error")
