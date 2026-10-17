"""Analyze: chi-square LSB test with a suspicion gauge."""
from __future__ import annotations

import customtkinter as ctk

from gui import theme as T
from gui.components import BaseScreen, BusyBar, Card, DropZone, Gauge, GlowButton, ImagePreview, StatsCard
from gui.tasks import TaskRunner, friendly_error
from stego.analysis import AnalysisResult, analyze_image


class AnalyzeScreen(BaseScreen):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.runner = TaskRunner(self)
        self.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(3, weight=1)
        self.drop = DropZone(left, app, self._chosen, prompt="Drop an image to analyse")
        self.drop.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        self.go = GlowButton(left, "Run chi-square test  (Ctrl+Enter)", self.on_run, height=44)
        self.go.grid(row=1, column=0, sticky="ew")
        self.busy = BusyBar(left)
        self.busy.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.preview = ImagePreview(left, "Image", "No image chosen")
        self.preview.grid(row=3, column=0, sticky="nsew", pady=(T.GAP, 0))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        card = Card(right, "LSB suspicion")
        card.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        self.gauge = Gauge(card.body)
        self.gauge.grid(row=0, column=0, sticky="ew")
        self.stats = StatsCard(right, "Test details", "Run the test to see the numbers")
        self.stats.grid(row=1, column=0, sticky="ew", pady=(0, T.GAP))
        note = Card(right, "How to read this")
        note.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(note.body, font=T.font(11), text_color=T.MUTED, justify="left", wraplength=400,
                     text="Pairs-of-values chi-square test. LSB embedding makes the counts of 2k and 2k+1 equal, so a "
                          "high p-value is suspicious. It is a heuristic: noisy or synthetic images can score high, and "
                          "short or random-order messages can slip through.").grid(row=0, column=0, sticky="w")

    def _chosen(self, path: str) -> None:
        try:
            self.preview.set_image(path)
            self.gauge.reset()
            self.stats.clear()
        except Exception as exc:  # noqa: BLE001
            self.drop.reset()
            self.app.toast(friendly_error(exc), "error")

    def on_open(self) -> None:
        self.drop.browse()

    def on_run(self) -> None:
        if self.runner.busy:
            return
        if not self.drop.path:
            return self.app.toast("Choose an image first.", "error")
        path = self.drop.path
        self.go.configure(state="disabled")
        self.busy.start_busy()
        self.app.set_status("Working: analysing…", "working")
        self.runner.run(lambda: analyze_image(path), self._done, self._failed)

    def _finish(self) -> None:
        self.go.configure(state="normal")
        self.busy.stop_busy()

    def _done(self, r: AnalysisResult) -> None:
        self._finish()
        self.gauge.set_result(r)
        self.stats.show([("Chi-square", f"{r.chi2:.1f}"), ("Degrees of freedom", str(r.dof)),
                         ("p-value", f"{r.p_value:.4f}"), ("Strongest in", f"first {r.window_fraction:.0%} of pixels")])
        self.app.toast(f"Analysis done: {r.level} suspicion", "success" if r.level == "Low" else "warn")
        self.app.set_status(f"Done: {r.level} suspicion", "done")

    def _failed(self, exc: BaseException) -> None:
        self._finish()
        self.app.toast(friendly_error(exc), "error")
        self.app.set_status("Error: " + friendly_error(exc), "error")
