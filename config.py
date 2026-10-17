"""Tiny JSON config: remembers the theme and last used folder."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".ghostpixel" / "config.json"
DEFAULTS: dict[str, Any] = {"theme": "dark", "last_dir": "", "compress": True, "random_order": False}


class Config:
    """Load/save ``config.json``; failures are silent (the app must never crash on this)."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self.data: dict[str, Any] = dict(DEFAULTS)
        try:
            self.data.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

    def get(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def remember_dir(self, file_path: str) -> None:
        folder = str(Path(file_path).parent)
        if folder != self.data.get("last_dir"):
            self.set("last_dir", folder)

    @property
    def last_dir(self) -> str:
        d = self.data.get("last_dir") or ""
        return d if d and Path(d).is_dir() else str(Path.home())
