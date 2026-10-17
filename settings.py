"""Settings and About pages."""
from __future__ import annotations

import customtkinter as ctk

from gui import theme as T
from gui.components import BaseScreen, Card, GlowButton, label
from stego import __version__ as CORE_VERSION


class SettingsScreen(BaseScreen):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        card = Card(self, "Appearance")
        card.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        self.theme_switch = ctk.CTkSwitch(card.body, text="Light “Stealth Gray” theme", font=T.font(13), text_color=T.TEXT,
                                          progress_color=T.ACCENT, command=self._theme)
        self.theme_switch.grid(row=0, column=0, sticky="w")
        if app.cfg.get("theme") == "light":
            self.theme_switch.select()

        defaults = Card(self, "Defaults")
        defaults.grid(row=1, column=0, sticky="ew", pady=(0, T.GAP))
        for i, (key, text) in enumerate((("compress", "Compress by default"), ("random_order", "Random pixel order by default"))):
            var = ctk.BooleanVar(value=bool(app.cfg.get(key)))
            ctk.CTkCheckBox(defaults.body, text=text, variable=var, font=T.font(12), text_color=T.TEXT,
                            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, checkmark_color=T.ON_ACCENT,
                            command=lambda k=key, v=var: app.cfg.set(k, bool(v.get()))).grid(row=i, column=0, sticky="w", pady=(0 if i == 0 else 8, 0))
        label(defaults.body, "Applies to new sessions.", size=11, color=T.MUTED).grid(row=2, column=0, sticky="w", pady=(8, 0))

        data = Card(self, "Stored data")
        data.grid(row=2, column=0, sticky="ew")
        label(data.body, f"Config file: {app.cfg.path}", size=11, color=T.MUTED, wraplength=640, justify="left").grid(row=0, column=0, sticky="w")
        GlowButton(data.body, "Forget last used folder", lambda: (app.cfg.set("last_dir", ""), app.toast("Folder forgotten", "info")),
                   variant="secondary", width=220).grid(row=1, column=0, sticky="w", pady=(10, 0))

    def _theme(self) -> None:
        self.app.set_theme("light" if self.theme_switch.get() else "dark")


class AboutScreen(BaseScreen):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        card = Card(self, f"About {T.APP_NAME}")
        card.grid(row=0, column=0, sticky="ew")
        lines = [
            (f"{T.APP_NAME} v{T.APP_VERSION}  ·  core v{CORE_VERSION}", 15, "bold", T.ACCENT),
            (T.APP_TAGLINE, 12, "normal", T.CYAN),
            ("Image steganography (LSB, PNG/BMP) and text steganography (zero-width characters), with optional "
             "AES-256-GCM encryption (Scrypt key derivation) and zlib compression.", 12, "normal", T.TEXT),
            ("Steganography hides data; encryption protects it. Use a password for anything sensitive.", 12, "bold", T.AMBER),
            ("Keep stego images as PNG/BMP: JPEG and social-media re-compression destroy hidden data. "
             "Many apps strip zero-width characters from text.", 12, "normal", T.MUTED),
            ("Intended for privacy, learning, watermarking and CTFs. Not for illegal purposes.", 12, "normal", T.MUTED),
            ("Shortcuts:  Ctrl+O open   ·   Ctrl+S save   ·   Ctrl+Enter run", 12, "normal", T.TEXT),
        ]
        for i, (text, size, weight, color) in enumerate(lines):
            label(card.body, text, size=size, weight=weight, color=color, wraplength=700, justify="left").grid(
                row=i, column=0, sticky="w", pady=(0, 8))
