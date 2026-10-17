"""Text steganography with zero-width Unicode characters (2 bits per character)."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

import numpy as np

from .header import HEADER_SIZE, build_blob, open_blob, unpack_header
from .utils import (
    CapacityError,
    CorruptedDataError,
    Extracted,
    NoHiddenDataError,
    StegoError,
)

# 00, 01, 10, 11
ZW_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060")
_SYMBOL = {c: i for i, c in enumerate(ZW_CHARS)}
_BYTE_TABLE = [
    "".join(ZW_CHARS[(b >> shift) & 3] for shift in (6, 4, 2, 0)) for b in range(256)
]
MAX_DENSITY = 16  # default limit: hidden characters per visible character

STRIP_WARNING = (
    "Some apps (messengers, social networks, web forms, some editors) strip or "
    "normalise zero-width characters, which destroys the hidden message."
)


@dataclass(frozen=True)
class TextEmbedResult:
    """What :func:`encode_text` returns."""

    text: str
    visible_chars: int
    hidden_chars: int
    payload_bytes: int
    capacity_bytes: int

    @property
    def density(self) -> float:
        return self.hidden_chars / max(1, self.visible_chars)


def text_capacity_bytes(cover_len: int, max_density: int = MAX_DENSITY) -> int:
    """Payload bytes a cover of ``cover_len`` characters may carry at ``max_density``."""
    return max(0, cover_len * max_density // 4 - HEADER_SIZE)


def contains_zero_width(text: str) -> bool:
    """True if ``text`` already contains any of the four signalling characters."""
    return any(c in text for c in ZW_CHARS)


def visible_text(text: str) -> str:
    """``text`` with the four zero-width characters removed."""
    return text.translate({ord(c): None for c in ZW_CHARS})


def bytes_to_zw(data: bytes) -> str:
    """Encode bytes as zero-width characters (4 per byte)."""
    return "".join(_BYTE_TABLE[b] for b in data)


def zw_to_bytes(text: str) -> bytes:
    """Decode zero-width characters from ``text``; every other character is ignored."""
    symbols = [_SYMBOL[c] for c in text if c in _SYMBOL]
    symbols = symbols[: len(symbols) // 4 * 4]
    if not symbols:
        return b""
    a = np.array(symbols, dtype=np.uint8).reshape(-1, 4)
    return ((a[:, 0] << 6) | (a[:, 1] << 4) | (a[:, 2] << 2) | a[:, 3]).astype(np.uint8).tobytes()


def _safe_gaps(cover: str) -> list[int]:
    """Indices ``i`` after which a hidden character may be inserted without splitting
    combining marks, variation selectors, emoji modifiers or CRLF pairs."""
    n, gaps = len(cover), []
    for i, ch in enumerate(cover):
        nxt = cover[i + 1] if i + 1 < n else ""
        if nxt and (
            unicodedata.combining(nxt)
            or "\ufe00" <= nxt <= "\ufe0f"
            or "\U0001f3fb" <= nxt <= "\U0001f3ff"
            or (ch == "\r" and nxt == "\n")
        ):
            continue
        gaps.append(i)
    return gaps


def _insert(cover: str, hidden: str, spread: bool) -> str:
    gaps = _safe_gaps(cover)
    buckets: dict[int, list[str]] = {}
    m, h = len(gaps), len(hidden)
    for j, ch in enumerate(hidden):
        gap = gaps[(j * m) // h] if spread else gaps[0]
        buckets.setdefault(gap, []).append(ch)
    out: list[str] = []
    for i, ch in enumerate(cover):
        out.append(ch)
        if i in buckets:
            out.append("".join(buckets[i]))
    return "".join(out)


def encode_text(
    cover: str,
    data: bytes,
    *,
    filename: str | None = None,
    password: str | None = None,
    compress: bool = True,
    spread: bool = True,
    max_density: int = MAX_DENSITY,
) -> TextEmbedResult:
    """Hide ``data`` inside ``cover``; the visible text is preserved exactly."""
    if not cover:
        raise StegoError("The cover text is empty.")
    if contains_zero_width(cover):
        raise StegoError(
            "The cover text already contains zero-width characters (U+200B/C/D, U+2060). "
            "Remove them (or use a different cover) so decoding stays unambiguous."
        )
    blob = build_blob(data, filename=filename, password=password or None, compress=compress)
    capacity = text_capacity_bytes(len(cover), max_density)
    payload = len(blob) - HEADER_SIZE
    if payload > capacity:
        raise CapacityError(payload, capacity)
    hidden = bytes_to_zw(blob)
    return TextEmbedResult(_insert(cover, hidden, spread), len(cover), len(hidden), payload, capacity)


def decode_text(text: str, *, password: str | None = None) -> Extracted:
    """Recover the secret from stego text (ordinary characters are ignored)."""
    raw = zw_to_bytes(text)
    if not raw:
        raise NoHiddenDataError("No hidden data found: the text contains no zero-width characters.")
    header = unpack_header(raw[:HEADER_SIZE])
    end = HEADER_SIZE + header.length
    if len(raw) < end:
        raise CorruptedDataError(
            "Hidden data is incomplete - the text was probably edited or an app stripped some characters."
        )
    return open_blob(raw[:HEADER_SIZE], header, raw[HEADER_SIZE:end], password or None)
