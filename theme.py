"""GhostPixel theme: every colour, font and spacing value lives here.

Colours are ``(light, dark)`` tuples, so CustomTkinter switches between the
"Stealth Gray" (light) and "Secret Dark / Cyber Stealth" (dark) looks instantly.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from tkinter import font as tkfont

import customtkinter as ctk

APP_NAME = "GhostPixel"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Hide data in plain sight"

# --- colours: (light "Stealth Gray", dark "Secret Dark") -----------------------------
BG = ("#e9e9ef", "#0a0a0f")          # window background
PANEL = ("#dcdce5", "#12121a")       # sidebar / top bar / status bar
CARD = ("#f6f6fa", "#1a1a24")        # cards
INPUT = ("#ffffff", "#0f0f16")       # text boxes, entries, preview wells
BORDER = ("#c4c4d0", "#2a2a38")
ACCENT = ("#00a86b", "#00ff9c")      # neon green (primary)
ACCENT_HOVER = ("#008f5a", "#00cc7d")
ON_ACCENT = ("#ffffff", "#0a0a0f")   # text drawn on top of ACCENT
CYAN = ("#0086ad", "#00d4ff")        # secondary / focus glow
RED = ("#d4183d", "#ff3b5c")         # errors
AMBER = ("#b87500", "#ffb020")       # warnings
TEXT = ("#1a1a22", "#e0e0e0")
MUTED = ("#5c5c70", "#7a7a8c")

# --- spacing -----------------------------------------------------------------------
RADIUS = 12
RADIUS_SM = 8
PAD = 16
GAP = 10
BORDER_W = 1
SIDEBAR_W = 210
TOPBAR_H = 56
STATUS_H = 30
MIN_SIZE = (1000, 650)
DEFAULT_SIZE = (1180, 760)

# --- fonts -------------------------------------------------------------------------
FONT_CANDIDATES = ("JetBrains Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo", "Courier New")
_family = "Courier"

ICONS = {"hide": "◼", "reveal": "◻", "analyze": "◈", "settings": "⚙", "about": "ⓘ",
         "eye": "◉", "eye_off": "◎", "moon": "☾", "sun": "☀"}


def init_fonts() -> None:
    """Pick the first installed monospace family (call once after the root window exists)."""
    global _family
    available = set(tkfont.families())
    _family = next((f for f in FONT_CANDIDATES if f in available), "Courier")
    font.cache_clear()


@lru_cache(maxsize=None)
def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    """Shared monospace font."""
    return ctk.CTkFont(family=_family, size=size, weight=weight)


def set_mode(mode: str) -> None:
    """``"dark"`` or ``"light"``."""
    ctk.set_appearance_mode(mode)


def asset(name: str) -> Path:
    """Path of a bundled asset (works from source and from a PyInstaller bundle)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "gui" / "assets" / name
