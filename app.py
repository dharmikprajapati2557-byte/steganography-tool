"""GhostPixel main window: top bar, sidebar, pages, status bar, shortcuts, splash."""
from __future__ import annotations

import sys
import tkinter as tk

import customtkinter as ctk

from . import theme as T
from .components import BaseScreen, TabbedPage, ToastManager, GlowButton, label
from .config import Config
from .screens.analyze import AnalyzeScreen
from .screens.image_decode import ImageDecodeScreen
from .screens.image_encode import ImageEncodeScreen
from .screens.settings import AboutScreen, SettingsScreen
from .screens.text_tab import TextHideScreen, TextRevealScreen

try:
    from tkinterdnd2 import TkinterDnD
    _DND_BASES: tuple[type, ...] = (TkinterDnD.DnDWrapper,)
except ImportError:  # drag & drop becomes unavailable, Browse still works
    TkinterDnD, _DND_BASES = None, ()

NAV = [("hide", "Hide (Encode)"), ("reveal", "Reveal (Decode)"), ("analyze", "Analyze"),
       ("settings", "Settings"), ("about", "About")]
STATUS_COLORS = {"ready": T.MUTED, "working": T.CYAN, "done": T.ACCENT, "error": T.RED}


def center(win: tk.Misc, w: int, h: int) -> None:
    """Centre a window of size ``w`` x ``h`` on the screen."""
    win.geometry(f"{w}x{h}+{max(0, (win.winfo_screenwidth() - w) // 2)}+{max(0, (win.winfo_screenheight() - h) // 3)}")


class Splash(tk.Toplevel):
    """Borderless splash that fades in, holds, fades out, then calls ``done``."""

    def __init__(self, root: tk.Misc, done) -> None:
        super().__init__(root)
        self.done = done
        self.overrideredirect(True)
        self._alpha(0.0)
        self.configure(bg="#0a0a0f", highlightthickness=2, highlightbackground="#00ff9c", highlightcolor="#00ff9c")
        center(self, 460, 270)
        try:
            img = ctk.CTkImage(light_image=_open_logo(), dark_image=_open_logo(), size=(96, 96))
            ctk.CTkLabel(self, text="", image=img, fg_color="#0a0a0f").pack(pady=(34, 8))
        except Exception:  # noqa: BLE001 - splash must never block start-up
            pass
        ctk.CTkLabel(self, text=T.APP_NAME.upper(), font=T.font(28, "bold"), text_color="#00ff9c", fg_color="#0a0a0f").pack()
        ctk.CTkLabel(self, text=T.APP_TAGLINE, font=T.font(12), text_color="#00d4ff", fg_color="#0a0a0f").pack(pady=(4, 0))
        self.lift()
        self.after(30, self._fade, 0)

    def _alpha(self, value: float) -> None:
        try:
            self.attributes("-alpha", max(0.0, min(1.0, value)))
        except tk.TclError:
            pass

    def _fade(self, step: int) -> None:
        if step <= 14:
            self._alpha(step / 14)
            self.after(28, self._fade, step + 1)
        elif step == 15:
            self.after(650, self._fade, 16)
        elif step <= 24:
            self._alpha(1 - (step - 15) / 9)
            self.after(28, self._fade, step + 1)
        else:
            self.destroy()
            self.done()


def _open_logo():
    from PIL import Image
    return Image.open(T.asset("logo.png"))


class App(ctk.CTk, *_DND_BASES):
    """Application window."""

    def __init__(self) -> None:
        super().__init__()
        self.withdraw()
        if TkinterDnD is not None:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception:  # noqa: BLE001
                pass
        T.init_fonts()
        self.cfg = Config()
        T.set_mode(self.cfg.get("theme"))
        self.title(f"{T.APP_NAME} - {T.APP_TAGLINE}")
        self.minsize(*T.MIN_SIZE)
        center(self, *T.DEFAULT_SIZE)
        self.configure(fg_color=T.BG)
        self._set_icon()
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.current = "hide"
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self._build()
        self.toasts = ToastManager(self)
        self._bind_shortcuts()
        self.show_page("hide")
        self.set_status("Ready", "ready")
        Splash(self, self._reveal_window)

    # ---- construction
    def _set_icon(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self.after(250, lambda: self.iconbitmap(str(T.asset("icon.ico"))))  # CTk resets the icon at ~200 ms
            else:
                self._icon = tk.PhotoImage(file=str(T.asset("icon.png")))
                self.iconphoto(True, self._icon)
        except Exception:  # noqa: BLE001
            pass

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=0, height=T.TOPBAR_H)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.grid_propagate(False)
        top.grid_columnconfigure(2, weight=1)
        try:
            logo = ctk.CTkImage(light_image=_open_logo(), dark_image=_open_logo(), size=(32, 32))
            ctk.CTkLabel(top, text="", image=logo).grid(row=0, column=0, padx=(T.PAD, 8), pady=10)
        except Exception:  # noqa: BLE001
            pass
        label(top, T.APP_NAME, size=18, weight="bold", color=T.ACCENT).grid(row=0, column=1, sticky="w")
        label(top, f"v{T.APP_VERSION}", size=11, color=T.MUTED).grid(row=0, column=2, sticky="w", padx=10)
        self.theme_btn = GlowButton(top, "", self._toggle_theme, variant="secondary", width=120, height=32)
        self.theme_btn.grid(row=0, column=3, padx=T.PAD)
        self._sync_theme_button()

        side = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=0, width=T.SIDEBAR_W)
        side.grid(row=1, column=0, sticky="ns")
        side.grid_propagate(False)
        for i, (key, text) in enumerate(NAV):
            btn = ctk.CTkButton(side, text=f"  {T.ICONS[key]}   {text}", anchor="w", height=44, font=T.font(13, "bold"),
                                corner_radius=T.RADIUS_SM, border_width=T.BORDER_W, command=lambda k=key: self.show_page(k))
            btn.grid(row=i if i < 3 else i + 1, column=0, sticky="ew", padx=T.GAP, pady=(T.PAD if i == 0 else 4, 0))
            self.nav_buttons[key] = btn
        side.grid_rowconfigure(3, weight=1)  # pushes Settings/About to the bottom

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=1, sticky="nsew", padx=T.PAD, pady=T.PAD)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=0, height=T.STATUS_H)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        self.dot = label(bar, "●", size=12, color=T.MUTED)
        self.dot.grid(row=0, column=0, padx=(T.PAD, 6), pady=3)
        self.status = label(bar, "", size=11, color=T.TEXT)
        self.status.grid(row=0, column=1, sticky="w")

    def _make_page(self, name: str) -> ctk.CTkFrame:
        if name == "hide":
            return TabbedPage(self.content, {"IMAGE": lambda p: ImageEncodeScreen(p, self),
                                             "TEXT": lambda p: TextHideScreen(p, self)})
        if name == "reveal":
            return TabbedPage(self.content, {"IMAGE": lambda p: ImageDecodeScreen(p, self),
                                             "TEXT": lambda p: TextRevealScreen(p, self)})
        return {"analyze": AnalyzeScreen, "settings": SettingsScreen, "about": AboutScreen}[name](self.content, self)

    # ---- navigation / state
    def show_page(self, name: str) -> None:
        if name not in self.pages:
            self.pages[name] = self._make_page(name)
            self.pages[name].grid(row=0, column=0, sticky="nsew")
        self.current = name
        self.pages[name].tkraise()
        for key, btn in self.nav_buttons.items():
            on = key == name
            btn.configure(fg_color=T.CARD if on else "transparent", text_color=T.ACCENT if on else T.TEXT,
                          border_color=T.ACCENT if on else T.PANEL, hover_color=T.CARD)
        self.set_status("Ready", "ready")

    def current_screen(self):
        page = self.pages.get(self.current)
        return page.active() if isinstance(page, TabbedPage) else page

    def set_status(self, text: str, kind: str = "ready") -> None:
        self.dot.configure(text_color=STATUS_COLORS.get(kind, T.MUTED))
        self.status.configure(text=text, text_color=T.RED if kind == "error" else T.TEXT)

    def toast(self, message: str, kind: str = "info") -> None:
        self.toasts.show(message, kind)

    # ---- theme
    def set_theme(self, mode: str) -> None:
        self.cfg.set("theme", mode)
        T.set_mode(mode)
        self._sync_theme_button()
        settings = self.pages.get("settings")
        if isinstance(settings, SettingsScreen):
            (settings.theme_switch.select if mode == "light" else settings.theme_switch.deselect)()

    def _toggle_theme(self) -> None:
        self.set_theme("light" if self.cfg.get("theme") == "dark" else "dark")

    def _sync_theme_button(self) -> None:
        dark = self.cfg.get("theme") == "dark"
        self.theme_btn.configure(text=f"{T.ICONS['moon'] if dark else T.ICONS['sun']}  {'Dark' if dark else 'Light'}")

    # ---- shortcuts
    def dispatch(self, method: str) -> str:
        screen = self.current_screen()
        fn = getattr(screen, method, None) if isinstance(screen, BaseScreen) else None
        if callable(fn):
            fn()
        return "break"

    def shield(self, textbox: ctk.CTkTextbox) -> None:
        """Text widgets bind Ctrl+O / Ctrl+Enter themselves; route them to the app instead."""
        textbox.bind("<Control-o>", lambda _e: self.dispatch("on_open"))
        textbox.bind("<Control-Return>", lambda _e: self.dispatch("on_run"))

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-o>", lambda _e: self.dispatch("on_open"))
        self.bind_all("<Control-s>", lambda _e: self.dispatch("on_save"))
        self.bind_all("<Control-Return>", lambda _e: self.dispatch("on_run"))

    def _reveal_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()


def main() -> None:
    """Entry point."""
    App().mainloop()


if __name__ == "__main__":
    main()
