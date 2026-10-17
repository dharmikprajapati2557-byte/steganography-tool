"""Reusable GhostPixel widgets: cards, buttons, toasts, drop zone, meters, previews."""
from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk
from PIL import Image

from stego import analysis
from stego.utils import format_size

from . import theme as T

try:  # drag & drop is optional - Browse buttons always work
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:  # pragma: no cover
    DND_FILES, HAS_DND = None, False


# --------------------------------------------------------------------------- helpers
def add_glow(widget, normal=T.BORDER, hover=T.CYAN) -> None:
    """Neon border on hover."""
    widget.bind("<Enter>", lambda _e: widget.configure(border_color=hover), add="+")
    widget.bind("<Leave>", lambda _e: widget.configure(border_color=normal), add="+")


def add_focus_glow(widget, normal=T.BORDER, focus=T.CYAN) -> None:
    """Neon border while an input has focus."""
    widget.bind("<FocusIn>", lambda _e: widget.configure(border_color=focus), add="+")
    widget.bind("<FocusOut>", lambda _e: widget.configure(border_color=normal), add="+")


def password_strength(password: str) -> tuple[float, str, tuple[str, str]]:
    """Return ``(0..1 score, label, colour)`` from a rough entropy estimate."""
    if not password:
        return 0.0, "", T.MUTED
    pool = (26 if any(c.islower() for c in password) else 0) + (26 if any(c.isupper() for c in password) else 0)
    pool += (10 if any(c.isdigit() for c in password) else 0)
    pool += (33 if any(not c.isalnum() for c in password) else 0)
    bits = len(password) * math.log2(max(pool, 2)) * math.sqrt(len(set(password)) / len(password))
    score = min(1.0, bits / 80)
    if bits < 28:
        return max(score, 0.08), "Weak", T.RED
    if bits < 50:
        return score, "Fair", T.AMBER
    if bits < 70:
        return score, "Good", T.CYAN
    return score, "Strong", T.ACCENT


def label(master, text="", *, size=13, weight="normal", color=T.TEXT, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=T.font(size, weight), text_color=color, **kw)


# --------------------------------------------------------------------------- basic widgets
class Card(ctk.CTkFrame):
    """Rounded panel with an optional title; put children in ``card.body``."""

    def __init__(self, master, title: str | None = None, **kw) -> None:
        super().__init__(master, fg_color=T.CARD, corner_radius=T.RADIUS,
                         border_width=T.BORDER_W, border_color=T.BORDER, **kw)
        self.grid_columnconfigure(0, weight=1)
        row = 0
        if title:
            label(self, title.upper(), size=11, weight="bold", color=T.CYAN).grid(
                row=0, column=0, sticky="w", padx=T.PAD, pady=(T.GAP + 2, 0))
            row = 1
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=row, column=0, sticky="nsew", padx=T.PAD, pady=(T.GAP - 2, T.PAD - 2))
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(row, weight=1)


class GlowButton(ctk.CTkButton):
    """Button with variants: primary (neon green), secondary, danger, ghost."""

    def __init__(self, master, text: str, command: Callable | None = None, variant: str = "primary", **kw) -> None:
        styles = {
            "primary": dict(fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ON_ACCENT, border_color=T.ACCENT),
            "secondary": dict(fg_color=T.INPUT, hover_color=T.CARD, text_color=T.CYAN, border_color=T.BORDER),
            "danger": dict(fg_color=T.INPUT, hover_color=T.CARD, text_color=T.RED, border_color=T.BORDER),
            "ghost": dict(fg_color="transparent", hover_color=T.CARD, text_color=T.MUTED, border_color=T.BORDER),
        }
        kw.setdefault("height", 38)
        super().__init__(master, text=text, command=command, font=T.font(13, "bold"),
                         corner_radius=T.RADIUS_SM, border_width=T.BORDER_W, **styles[variant], **kw)
        self._normal = styles[variant]["border_color"]
        add_glow(self, self._normal, T.CYAN)


class BusyBar(ctk.CTkProgressBar):
    """Indeterminate bar that is invisible while idle."""

    def __init__(self, master) -> None:
        super().__init__(master, mode="indeterminate", height=6, fg_color=T.BORDER, progress_color=T.ACCENT)
        self._running = False

    def start_busy(self) -> None:
        if not self._running:
            self._running = True
            self.configure(progress_color=T.ACCENT)
            self.start()

    def stop_busy(self) -> None:
        if self._running:
            self._running = False
            self.stop()
        self.configure(mode="determinate")
        self.set(0)
        self.configure(mode="indeterminate")


class BaseScreen(ctk.CTkFrame):
    """Common base: gives every screen access to the app plus shortcut hooks."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

    def on_open(self) -> None: ...   # Ctrl+O
    def on_save(self) -> None: ...   # Ctrl+S
    def on_run(self) -> None: ...    # Ctrl+Enter


def make_textbox(master, app, height: int = 100, readonly: bool = False) -> ctk.CTkTextbox:
    """Styled text box wired for focus glow and the global shortcuts."""
    tb = ctk.CTkTextbox(master, height=height, font=T.font(12), fg_color=T.INPUT, text_color=T.TEXT,
                        border_width=T.BORDER_W, border_color=T.BORDER, corner_radius=T.RADIUS_SM, wrap="word")
    add_focus_glow(tb)
    app.shield(tb)
    if readonly:
        tb.configure(state="disabled")
    return tb


def set_text(tb: ctk.CTkTextbox, text: str) -> None:
    """Replace the content of a (possibly read-only) text box."""
    tb.configure(state="normal")
    tb.delete("1.0", "end")
    tb.insert("1.0", text)


def get_text(tb: ctk.CTkTextbox) -> str:
    return tb.get("1.0", "end-1c")


# --------------------------------------------------------------------------- toasts
class ToastManager:
    """Non-blocking notifications stacked in the top-right corner."""

    COLORS = {"success": T.ACCENT, "error": T.RED, "info": T.CYAN, "warn": T.AMBER}

    def __init__(self, root) -> None:
        self.root = root
        self.toasts: list[ctk.CTkFrame] = []

    def show(self, message: str, kind: str = "info", duration: int = 4200) -> None:
        color = self.COLORS.get(kind, T.CYAN)
        frame = ctk.CTkFrame(self.root, fg_color=T.CARD, corner_radius=T.RADIUS,
                             border_width=2, border_color=color)
        lbl = label(frame, message, size=12, wraplength=330, justify="left")
        lbl.pack(padx=T.PAD, pady=T.GAP + 2)
        for w in (frame, lbl):
            w.bind("<Button-1>", lambda _e, f=frame: self._dismiss(f))
        self.toasts.append(frame)
        self._layout()
        frame.after(duration, lambda: self._dismiss(frame))

    def _dismiss(self, frame) -> None:
        if frame in self.toasts:
            self.toasts.remove(frame)
            frame.destroy()
            self._layout()

    def _layout(self) -> None:
        self.root.update_idletasks()
        y = T.TOPBAR_H + 10
        for t in self.toasts:
            t.place(relx=1.0, x=-16, y=y, anchor="ne")
            t.lift()
            y += t.winfo_reqheight() + 8


# --------------------------------------------------------------------------- inputs
class DropZone(ctk.CTkFrame):
    """Drag-and-drop target (tkinterdnd2) with a Browse button."""

    def __init__(self, master, app, on_file: Callable[[str], None], *,
                 extensions: tuple[str, ...] = (".png", ".bmp"),
                 prompt: str = "Drop a PNG / BMP image here",
                 filetypes: list[tuple[str, str]] | None = None) -> None:
        super().__init__(master, fg_color=T.INPUT, corner_radius=T.RADIUS, border_width=2, border_color=T.BORDER)
        self.app, self.on_file, self.extensions = app, on_file, extensions
        self.filetypes = filetypes or [("Images", "*.png *.bmp"), ("All files", "*.*")]
        self.path: str | None = None
        self.grid_columnconfigure(0, weight=1)
        self.title = label(self, prompt, size=13, weight="bold", color=T.CYAN)
        self.title.grid(row=0, column=0, padx=T.PAD, pady=(T.PAD, 2))
        self.sub = label(self, "or", size=11, color=T.MUTED)
        self.sub.grid(row=1, column=0)
        GlowButton(self, "Browse…", self.browse, variant="secondary", width=120, height=32).grid(
            row=2, column=0, pady=(6, T.PAD))
        add_glow(self, T.BORDER, T.ACCENT)
        if HAS_DND:
            for w in (self, self.title, self.sub):
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._dropped)
                except Exception:  # DnD not initialised on the root - Browse still works
                    break

    def browse(self) -> None:
        path = filedialog.askopenfilename(initialdir=self.app.cfg.last_dir, filetypes=self.filetypes)
        if path:
            self.set_file(path)

    def _dropped(self, event) -> None:
        files = self.tk.splitlist(event.data)
        if not files:
            return
        if Path(files[0]).suffix.lower() not in self.extensions:
            self.app.toast(f"Unsupported file. Use: {', '.join(self.extensions)}", "error")
            return
        self.set_file(files[0])

    def set_file(self, path: str) -> None:
        self.path = path
        self.app.cfg.remember_dir(path)
        self.title.configure(text=Path(path).name, text_color=T.ACCENT)
        self.sub.configure(text="click Browse or drop another file to replace")
        self.on_file(path)

    def reset(self) -> None:
        self.path = None
        self.title.configure(text="Drop a file here", text_color=T.CYAN)
        self.sub.configure(text="or")


class PasswordField(ctk.CTkFrame):
    """Password entry with show/hide eye and an optional strength bar."""

    def __init__(self, master, *, strength: bool = True, on_change: Callable[[], None] | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.on_change = on_change
        self.var = tk.StringVar()
        self.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(self, textvariable=self.var, show="•", height=36, font=T.font(13),
                                  placeholder_text="Password (optional)", fg_color=T.INPUT, text_color=T.TEXT,
                                  border_color=T.BORDER, border_width=T.BORDER_W, corner_radius=T.RADIUS_SM)
        self.entry.grid(row=0, column=0, sticky="ew")
        add_focus_glow(self.entry)
        self.eye = ctk.CTkButton(self, text=T.ICONS["eye"], width=38, height=36, font=T.font(15),
                                 fg_color=T.INPUT, hover_color=T.CARD, text_color=T.MUTED,
                                 border_width=T.BORDER_W, border_color=T.BORDER, corner_radius=T.RADIUS_SM,
                                 command=self._toggle)
        self.eye.grid(row=0, column=1, padx=(6, 0))
        add_glow(self.eye)
        self.bar = self.hint = None
        if strength:
            self.bar = ctk.CTkProgressBar(self, height=6, fg_color=T.BORDER, progress_color=T.RED)
            self.bar.set(0)
            self.bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            self.hint = label(self, "", size=11, color=T.MUTED)
            self.hint.grid(row=1, column=1, padx=(6, 0), pady=(8, 0))
        self.var.trace_add("write", lambda *_: self._changed())

    def _toggle(self) -> None:
        hidden = self.entry.cget("show") == "•"
        self.entry.configure(show="" if hidden else "•")
        self.eye.configure(text=T.ICONS["eye_off"] if hidden else T.ICONS["eye"])

    def _changed(self) -> None:
        if self.bar is not None:
            score, text, color = password_strength(self.var.get())
            self.bar.set(score)
            self.bar.configure(progress_color=color)
            self.hint.configure(text=text, text_color=color)
        if self.on_change:
            self.on_change()

    def get(self) -> str:
        return self.var.get()


# --------------------------------------------------------------------------- feedback widgets
class CapacityMeter(Card):
    """Used / maximum capacity bar; turns red when (nearly) full."""

    def __init__(self, master) -> None:
        super().__init__(master, "Capacity")
        self.text = label(self.body, "Choose a cover image", size=12, color=T.MUTED)
        self.text.grid(row=0, column=0, sticky="w")
        self.bar = ctk.CTkProgressBar(self.body, height=12, fg_color=T.BORDER, progress_color=T.ACCENT, corner_radius=6)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

    def update_meter(self, used: int, capacity: int | None) -> bool:
        """Return True if the secret fits."""
        if capacity is None:
            self.bar.set(0)
            self.text.configure(text="Choose a cover image", text_color=T.MUTED)
            return False
        ratio = used / capacity if capacity > 0 else (0 if used == 0 else 2)
        color = T.RED if ratio >= 0.95 else T.AMBER if ratio >= 0.75 else T.ACCENT
        self.bar.set(min(1.0, ratio))
        self.bar.configure(progress_color=color)
        note = "  - TOO BIG" if ratio > 1 else "  - full" if ratio >= 0.95 else ""
        self.text.configure(text=f"{format_size(used)} of {format_size(capacity)}  ({ratio * 100:.1f}%){note}",
                            text_color=color if ratio >= 0.75 else T.TEXT)
        return ratio <= 1


class StatsCard(Card):
    """Key / value rows (e.g. MSE and PSNR after encoding)."""

    def __init__(self, master, title: str, empty: str = "Nothing yet") -> None:
        super().__init__(master, title)
        self.empty = empty
        self.clear()

    def clear(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        label(self.body, self.empty, size=12, color=T.MUTED).grid(row=0, column=0, sticky="w")

    def show(self, rows: list[tuple[str, str]]) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        for i, (k, v) in enumerate(rows):
            label(self.body, k, size=12, color=T.MUTED).grid(row=i, column=0, sticky="w")
            label(self.body, v, size=13, weight="bold", color=T.ACCENT).grid(row=i, column=1, sticky="e", padx=(T.PAD, 0))
        self.body.grid_columnconfigure(1, weight=0)


class ImagePreview(ctk.CTkFrame):
    """Titled image well that re-fits its picture when the window is resized."""

    def __init__(self, master, title: str, placeholder: str = "No image") -> None:
        super().__init__(master, fg_color=T.CARD, corner_radius=T.RADIUS, border_width=T.BORDER_W,
                         border_color=T.BORDER, width=220, height=200)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        label(self, title.upper(), size=11, weight="bold", color=T.CYAN).grid(row=0, column=0, sticky="w", padx=T.PAD, pady=(10, 0))
        self.view = ctk.CTkLabel(self, text=placeholder, font=T.font(12), text_color=T.MUTED,
                                 fg_color=T.INPUT, corner_radius=T.RADIUS_SM)
        self.view.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.placeholder = placeholder
        self._pil: Image.Image | None = None
        self._job = None
        self._size = (0, 0)
        self.bind("<Configure>", self._on_resize)

    def set_image(self, path_or_image: str | Path | Image.Image) -> None:
        img = Image.open(path_or_image) if not isinstance(path_or_image, Image.Image) else path_or_image
        img = img.convert("RGB")
        img.thumbnail((1400, 1400))
        self._pil = img
        self._render()

    def clear(self) -> None:
        self._pil = None
        self.view.configure(image=None, text=self.placeholder)

    def _on_resize(self, _e) -> None:
        size = (self.winfo_width(), self.winfo_height())
        if self._pil is not None and (abs(size[0] - self._size[0]) > 8 or abs(size[1] - self._size[1]) > 8):
            if self._job:
                self.after_cancel(self._job)
            self._job = self.after(120, self._render)

    def _render(self) -> None:
        self._job = None
        if self._pil is None:
            return
        self._size = (self.winfo_width(), self.winfo_height())
        w, h = max(60, self._size[0] - 34), max(60, self._size[1] - 62)
        ratio = min(w / self._pil.width, h / self._pil.height)
        size = (max(1, int(self._pil.width * ratio)), max(1, int(self._pil.height * ratio)))
        ci = ctk.CTkImage(light_image=self._pil, dark_image=self._pil, size=size)
        self.view.configure(image=ci, text="")
        self._ci = ci  # keep a reference


class Gauge(ctk.CTkFrame):
    """Low / Medium / High suspicion gauge with a moving marker."""

    ZONES = (("LOW", T.ACCENT), ("MEDIUM", T.AMBER), ("HIGH", T.RED))

    def __init__(self, master) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.track = ctk.CTkFrame(self, fg_color="transparent", height=34)
        self.track.grid(row=0, column=0, sticky="ew", pady=(6, 0))
        for i, (_n, color) in enumerate(self.ZONES):
            ctk.CTkFrame(self.track, fg_color=color, corner_radius=4).place(
                relx=i / 3 + 0.004, rely=0.25, relwidth=1 / 3 - 0.008, relheight=0.5)
        self.marker = ctk.CTkFrame(self.track, fg_color=T.TEXT, width=6, corner_radius=3)
        names = ctk.CTkFrame(self, fg_color="transparent")
        names.grid(row=1, column=0, sticky="ew")
        for i, (n, color) in enumerate(self.ZONES):
            names.grid_columnconfigure(i, weight=1, uniform="z")
            label(names, n, size=11, weight="bold", color=color).grid(row=0, column=i)
        self.verdict = label(self, "—", size=20, weight="bold", color=T.MUTED)
        self.verdict.grid(row=2, column=0, pady=(12, 0))
        self.note = label(self, "Run the analysis to see the result.", size=12, color=T.MUTED, wraplength=420, justify="center")
        self.note.grid(row=3, column=0, pady=(4, 0))

    @staticmethod
    def _position(p: float) -> float:
        lo, hi = analysis.MEDIUM_P, analysis.HIGH_P
        if p < lo:
            return (p / lo) / 3
        if p < hi:
            return 1 / 3 + ((p - lo) / (hi - lo)) / 3
        return 2 / 3 + ((p - hi) / (1 - hi)) / 3

    def set_result(self, res: analysis.AnalysisResult) -> None:
        color = {"Low": T.ACCENT, "Medium": T.AMBER, "High": T.RED}[res.level]
        pos = min(0.985, max(0.015, self._position(res.p_value)))
        self.marker.place(relx=pos, rely=0.5, relheight=0.95, anchor="center")
        self.marker.lift()
        self.verdict.configure(text=f"{res.level.upper()} SUSPICION", text_color=color)
        self.note.configure(text=res.summary, text_color=T.TEXT)

    def reset(self) -> None:
        self.marker.place_forget()
        self.verdict.configure(text="—", text_color=T.MUTED)
        self.note.configure(text="Run the analysis to see the result.", text_color=T.MUTED)


class TabbedPage(ctk.CTkFrame):
    """IMAGE / TEXT tabs: a segmented button over stacked screens."""

    def __init__(self, master, factories: dict[str, Callable[[ctk.CTkFrame], ctk.CTkFrame]]) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        names = list(factories)
        self.seg = ctk.CTkSegmentedButton(
            self, values=names, command=self.select, font=T.font(12, "bold"), fg_color=T.PANEL,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER, unselected_color=T.PANEL,
            unselected_hover_color=T.CARD, text_color=T.TEXT, corner_radius=T.RADIUS_SM)
        self.seg.grid(row=0, column=0, sticky="w", pady=(0, T.GAP))
        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.grid(row=1, column=0, sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.screens = {n: f(holder) for n, f in factories.items()}
        for s in self.screens.values():
            s.grid(row=0, column=0, sticky="nsew")
        self.current = names[0]
        self.seg.set(self.current)
        self.select(self.current)

    def select(self, name: str) -> None:
        self.current = name
        self.screens[name].tkraise()

    def active(self):
        return self.screens[self.current]
