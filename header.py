"""Container format: header packing plus the compress -> encrypt pipeline.

Header (38 bytes, big endian)::

    magic(4) 'STGO' | version(1) | flags(1) | length(4) | salt(16) | nonce(12)

``length`` is the size of the body that follows. The whole header is passed to
AES-GCM as associated data, so tampering with it makes decryption fail.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from . import crypto
from .utils import (
    CorruptedDataError,
    Extracted,
    NoHiddenDataError,
    PasswordRequiredError,
    UnsupportedFormatError,
    pack_payload,
    unpack_payload,
)

MAGIC = b"STGO"
VERSION = 1
FLAG_ENCRYPTED = 0x01
FLAG_COMPRESSED = 0x02
FLAG_RANDOM = 0x04
CRC_SIZE = 4
MAX_DECOMPRESSED = 1 << 30

_STRUCT = struct.Struct(">4sBBI16s12s")
HEADER_SIZE = _STRUCT.size  # 38


@dataclass(frozen=True)
class Header:
    """Parsed header fields."""

    version: int
    flags: int
    length: int
    salt: bytes
    nonce: bytes

    @property
    def encrypted(self) -> bool:
        return bool(self.flags & FLAG_ENCRYPTED)

    @property
    def compressed(self) -> bool:
        return bool(self.flags & FLAG_COMPRESSED)

    @property
    def random_order(self) -> bool:
        return bool(self.flags & FLAG_RANDOM)


def pack_header(flags: int, length: int, salt: bytes, nonce: bytes, version: int = VERSION) -> bytes:
    """Serialise a header."""
    return _STRUCT.pack(MAGIC, version, flags, length, salt, nonce)


def unpack_header(raw: bytes) -> Header:
    """Parse a header; raises :class:`NoHiddenDataError` if the magic bytes are absent."""
    if len(raw) < HEADER_SIZE:
        raise NoHiddenDataError("No hidden data found (too little data for a header).")
    magic, version, flags, length, salt, nonce = _STRUCT.unpack(raw[:HEADER_SIZE])
    if magic != MAGIC:
        raise NoHiddenDataError("No hidden data found (signature not present).")
    if version > VERSION:
        raise UnsupportedFormatError(
            f"Hidden data uses format v{version}; this tool only understands v{VERSION}."
        )
    return Header(version, flags, length, salt, nonce)


def build_blob(
    data: bytes,
    *,
    filename: str | None = None,
    password: str | None = None,
    compress: bool = True,
    random_order: bool = False,
) -> bytes:
    """Envelope -> zlib -> (AES-GCM | CRC32) -> header + body."""
    payload = pack_payload(data, filename)
    flags = FLAG_RANDOM if random_order else 0
    body = payload
    if compress:
        packed = zlib.compress(payload, 9)
        if len(packed) < len(payload):  # only keep compression if it helps
            body, flags = packed, flags | FLAG_COMPRESSED
    salt, nonce = crypto.random_salt(), crypto.random_nonce()
    if password:
        flags |= FLAG_ENCRYPTED
        length = len(body) + crypto.TAG_SIZE
        header = pack_header(flags, length, salt, nonce)
        return header + crypto.encrypt(body, password, salt, nonce, header)
    body += struct.pack(">I", zlib.crc32(body))
    return pack_header(flags, len(body), salt, nonce) + body


def open_blob(header_bytes: bytes, header: Header, body: bytes, password: str | None) -> Extracted:
    """Reverse of :func:`build_blob` (decrypt / verify CRC, decompress, unwrap)."""
    if header.encrypted:
        if not password:
            raise PasswordRequiredError("This data is password protected - please enter the password.")
        body = crypto.decrypt(body, password, header.salt, header.nonce, header_bytes)
    else:
        if len(body) < CRC_SIZE:
            raise CorruptedDataError("Hidden data is truncated.")
        body, (crc,) = body[:-CRC_SIZE], struct.unpack(">I", body[-CRC_SIZE:])
        if zlib.crc32(body) != crc:
            raise CorruptedDataError("Hidden data is corrupted (checksum mismatch).")
    if header.compressed:
        body = _decompress(body)
    return unpack_payload(body)


def _decompress(body: bytes) -> bytes:
    d = zlib.decompressobj()
    try:
        out = d.decompress(body, MAX_DECOMPRESSED)
    except zlib.error as exc:
        raise CorruptedDataError("Hidden data could not be decompressed.") from exc
    if not d.eof or d.unconsumed_tail:
        raise CorruptedDataError("Hidden data could not be decompressed.")
    return out


def estimate_blob_size(
    data: bytes, filename: str | None = None, *, encrypted: bool = False, compress: bool = True
) -> int:
    """Cheap size estimate of the full blob (used by live capacity meters)."""
    payload = pack_payload(data, filename)
    size = len(payload)
    if compress:
        size = min(size, len(zlib.compress(payload, 6)))
    return HEADER_SIZE + size + (crypto.TAG_SIZE if encrypted else CRC_SIZE)
