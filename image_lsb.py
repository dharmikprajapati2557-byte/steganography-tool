"""LSB image steganography (PNG/BMP, RGB, numpy-vectorised)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from . import analysis
from .crypto import seed_from_password
from .header import HEADER_SIZE, build_blob, open_blob, unpack_header
from .utils import (
    IMAGE_EXTENSIONS,
    CapacityError,
    CorruptedDataError,
    Extracted,
    NoHiddenDataError,
    PasswordRequiredError,
    StegoError,
    UnsupportedFormatError,
    bits_to_bytes,
    bytes_to_bits,
    check_output_path,
    image_size,
    load_rgb,
    raw_capacity_bytes,
)

HEADER_BITS = HEADER_SIZE * 8


@dataclass(frozen=True)
class EmbedResult:
    """What :func:`encode_image` reports back."""

    output_path: Path
    payload_bytes: int     # bytes stored after the header (compressed/encrypted size)
    capacity_bytes: int    # maximum payload_bytes this cover could hold
    used_percent: float
    mse: float
    psnr: float


def image_capacity_bytes(path: str | os.PathLike) -> int:
    """Maximum payload (after compression/encryption) a cover can hold: w*h*3/8 - header."""
    w, h = image_size(path)
    return max(0, raw_capacity_bytes(w, h) - HEADER_SIZE)


def _body_positions(
    total_values: int, n_bits: int, *, random_order: bool, password: str | None, salt: bytes
) -> np.ndarray:
    """Indices (into the flat RGB array) that carry the body. The header is always sequential."""
    if not random_order:
        return np.arange(HEADER_BITS, HEADER_BITS + n_bits, dtype=np.int64)
    if not password:
        raise PasswordRequiredError("Random pixel order needs the password.")
    # RandomState's stream is frozen across numpy versions, so images stay decodable.
    rng = np.random.RandomState(seed_from_password(password, salt))
    return HEADER_BITS + rng.permutation(total_values - HEADER_BITS)[:n_bits]


def encode_image(
    input_path: str | os.PathLike,
    output_path: str | os.PathLike,
    data: bytes,
    *,
    filename: str | None = None,
    password: str | None = None,
    compress: bool = True,
    random_order: bool = False,
    overwrite: bool = False,
) -> EmbedResult:
    """Hide ``data`` (a message, or a file when ``filename`` is given) in a PNG/BMP.

    The original is never modified; the stego image is written to ``output_path``.
    """
    password = password or None
    if random_order and not password:
        raise StegoError("Random pixel order needs a password (it seeds the pixel shuffle).")
    cover = load_rgb(input_path)  # input problems (missing / JPEG / bad file) are reported first
    out = check_output_path(output_path, input_path=input_path, overwrite=overwrite)
    if out.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError("Save the result as .png or .bmp - JPEG would destroy the hidden data.")

    blob = build_blob(data, filename=filename, password=password,
                      compress=compress, random_order=random_order)
    capacity = max(0, raw_capacity_bytes(cover.shape[1], cover.shape[0]) - HEADER_SIZE)
    payload_bytes = len(blob) - HEADER_SIZE
    if payload_bytes > capacity:
        raise CapacityError(payload_bytes, capacity)

    header = unpack_header(blob[:HEADER_SIZE])
    bits = bytes_to_bits(blob)
    flat = cover.reshape(-1).copy()
    flat[:HEADER_BITS] = (flat[:HEADER_BITS] & 0xFE) | bits[:HEADER_BITS]
    pos = _body_positions(flat.size, bits.size - HEADER_BITS, random_order=random_order,
                          password=password, salt=header.salt)
    flat[pos] = (flat[pos] & 0xFE) | bits[HEADER_BITS:]
    stego = flat.reshape(cover.shape)

    try:
        Image.fromarray(stego, "RGB").save(out)
    except OSError as exc:
        raise StegoError(f"Could not save '{out}': {exc}") from exc

    m, p = analysis.compare_images(cover, stego)
    used = 100.0 * payload_bytes / capacity if capacity else 100.0
    return EmbedResult(out, payload_bytes, capacity, used, m, p)


def decode_image(path: str | os.PathLike, *, password: str | None = None) -> Extracted:
    """Extract and decrypt the secret hidden in a stego image."""
    password = password or None
    flat = load_rgb(path).reshape(-1)
    if flat.size < HEADER_BITS:
        raise NoHiddenDataError("No hidden data found (image is too small).")
    header_bytes = bits_to_bytes(flat[:HEADER_BITS] & 1)
    header = unpack_header(header_bytes)
    if header.length * 8 > flat.size - HEADER_BITS:
        raise CorruptedDataError("A header was found but its length does not fit the image - data is corrupted.")
    pos = _body_positions(flat.size, header.length * 8, random_order=header.random_order,
                          password=password, salt=header.salt)
    body = bits_to_bytes(flat[pos] & 1)
    return open_blob(header_bytes, header, body, password)
