"""Shared helpers: exceptions, bit/byte conversion, payload envelope and file I/O."""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS = (".png", ".bmp")
IMAGE_FORMATS = ("PNG", "BMP")
JPEG_EXTENSIONS = (".jpg", ".jpeg", ".jpe", ".jfif")
KIND_TEXT = 0
KIND_FILE = 1
JPEG_WARNING = (
    "JPEG is lossy and destroys hidden data. Convert the image to PNG or BMP first."
)


# --------------------------------------------------------------------------- errors
class StegoError(Exception):
    """Base class for all user-facing errors raised by this package."""


class EmptyMessageError(StegoError):
    """Nothing to hide."""


class CapacityError(StegoError):
    """The secret does not fit in the cover."""

    def __init__(self, needed: int, available: int) -> None:
        self.needed = needed
        self.available = available
        super().__init__(
            f"The secret needs {format_size(needed)} (after compression/encryption) but "
            f"this cover can hold at most {format_size(available)}. "
            "Use a larger cover or a smaller secret."
        )


class UnsupportedFormatError(StegoError):
    """Image type is not PNG/BMP (or is not an image at all)."""


class NoHiddenDataError(StegoError):
    """No stego header was found."""


class CorruptedDataError(StegoError):
    """Hidden data was found but is damaged or truncated."""


class PasswordRequiredError(StegoError):
    """The hidden data needs a password and none was supplied."""


class WrongPasswordError(StegoError):
    """Decryption failed: wrong password (or tampered data)."""


class StegoFileNotFoundError(StegoError):
    """An input file does not exist."""


# --------------------------------------------------------------------------- bits
def bytes_to_bits(data: bytes) -> np.ndarray:
    """Return ``data`` as a uint8 array of 0/1 values (MSB first)."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack an array of 0/1 values (MSB first) back into bytes."""
    if bits.size % 8:
        raise CorruptedDataError("Bit stream length is not a multiple of 8.")
    return np.packbits(bits.astype(np.uint8)).tobytes()


def raw_capacity_bytes(width: int, height: int) -> int:
    """Bytes of LSB space in an RGB image (1 bit per colour channel)."""
    return (width * height * 3) // 8


def format_size(n: int) -> str:
    """Human readable size, e.g. ``1.5 KB``."""
    size = float(n)
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


# --------------------------------------------------------------------------- payload envelope
@dataclass(frozen=True)
class Extracted:
    """A recovered secret: raw bytes plus the original file name for file payloads."""

    data: bytes
    filename: str | None = None

    @property
    def is_file(self) -> bool:
        return self.filename is not None

    def text(self) -> str:
        """Decode as UTF-8 text (invalid bytes are replaced)."""
        return self.data.decode("utf-8", errors="replace")


def safe_filename(name: str) -> str:
    """Strip any directory part so extracted names can never escape the target folder."""
    base = os.path.basename(name.replace("\\", "/")).strip().lstrip(".")
    return base or "extracted.bin"


def pack_payload(data: bytes, filename: str | None = None) -> bytes:
    """Wrap a message/file in a tiny envelope: kind byte [+ name] + data."""
    if not data:
        raise EmptyMessageError("Nothing to hide: the message or file is empty.")
    if filename is None:
        return bytes([KIND_TEXT]) + data
    name = safe_filename(filename).encode("utf-8")[:65535]
    return bytes([KIND_FILE]) + struct.pack(">H", len(name)) + name + data


def unpack_payload(raw: bytes) -> Extracted:
    """Inverse of :func:`pack_payload`."""
    if not raw:
        raise CorruptedDataError("Hidden payload is empty.")
    kind = raw[0]
    if kind == KIND_TEXT:
        return Extracted(raw[1:])
    if kind == KIND_FILE and len(raw) >= 3:
        (n,) = struct.unpack(">H", raw[1:3])
        if len(raw) >= 3 + n:
            name = raw[3 : 3 + n].decode("utf-8", errors="replace")
            return Extracted(raw[3 + n :], safe_filename(name))
    raise CorruptedDataError("Hidden payload has an unknown or damaged structure.")


# --------------------------------------------------------------------------- image I/O
def _check_image_path(path: str | os.PathLike) -> Path:
    p = Path(path)
    if not p.is_file():
        raise StegoFileNotFoundError(f"File not found: {p}")
    ext = p.suffix.lower()
    if ext in JPEG_EXTENSIONS:
        raise UnsupportedFormatError(JPEG_WARNING)
    if ext not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Unsupported image type '{ext or 'unknown'}'. Use PNG or BMP (lossless)."
        )
    return p


def _open_image(p: Path) -> Image.Image:
    try:
        im = Image.open(p)
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedFormatError(f"'{p.name}' is not a readable image.") from exc
    if im.format not in IMAGE_FORMATS:
        fmt = im.format
        im.close()
        hint = f" {JPEG_WARNING}" if fmt == "JPEG" else ""
        raise UnsupportedFormatError(
            f"'{p.name}' is really a {fmt} image; only PNG and BMP are supported.{hint}"
        )
    return im


def load_rgb(path: str | os.PathLike) -> np.ndarray:
    """Load a PNG/BMP as an ``(h, w, 3)`` uint8 RGB array (alpha is dropped)."""
    p = _check_image_path(path)
    im = _open_image(p)
    try:
        return np.array(im.convert("RGB"), dtype=np.uint8)
    except (OSError, ValueError, SyntaxError) as exc:
        raise UnsupportedFormatError(f"'{p.name}' is a damaged image file.") from exc
    finally:
        im.close()


def image_size(path: str | os.PathLike) -> tuple[int, int]:
    """Return ``(width, height)`` of a supported image without decoding pixels."""
    p = _check_image_path(path)
    im = _open_image(p)
    try:
        return im.size
    finally:
        im.close()


# --------------------------------------------------------------------------- file I/O
def read_file(path: str | os.PathLike) -> bytes:
    """Read a whole file with friendly errors."""
    p = Path(path)
    if not p.is_file():
        raise StegoFileNotFoundError(f"File not found: {p}")
    try:
        return p.read_bytes()
    except OSError as exc:
        raise StegoError(f"Cannot read '{p}': {exc.strerror or exc}") from exc


def check_output_path(
    output: str | os.PathLike,
    *,
    input_path: str | os.PathLike | None = None,
    overwrite: bool = False,
) -> Path:
    """Validate an output path; never allow it to clobber the input file."""
    out = Path(output)
    if input_path is not None and out.resolve() == Path(input_path).resolve():
        raise StegoError("The output must differ from the input - originals are never overwritten.")
    if not out.parent.exists():
        raise StegoError(f"Output folder does not exist: {out.parent}")
    if out.exists() and not overwrite:
        raise StegoError(f"'{out}' already exists. Choose another name or pass --force.")
    return out


def write_file(path: str | os.PathLike, data: bytes, *, overwrite: bool = False) -> Path:
    """Write bytes to ``path`` (refuses to overwrite unless asked)."""
    out = check_output_path(path, overwrite=overwrite)
    try:
        out.write_bytes(data)
    except OSError as exc:
        raise StegoError(f"Cannot write '{out}': {exc.strerror or exc}") from exc
    return out
