"""AES-256-GCM encryption with a Scrypt-derived key (never a raw password as key)."""
from __future__ import annotations

import hashlib
import os

import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .utils import WrongPasswordError

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # 256 bit
TAG_SIZE = 16
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


def random_salt() -> bytes:
    """16 random bytes for Scrypt."""
    return os.urandom(SALT_SIZE)


def random_nonce() -> bytes:
    """12 random bytes for AES-GCM (new for every message)."""
    return os.urandom(NONCE_SIZE)


def derive_key(password: str, salt: bytes) -> bytes:
    """Stretch ``password`` into a 256-bit key with Scrypt."""
    kdf = Scrypt(salt=salt, length=KEY_SIZE, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def encrypt(plaintext: bytes, password: str, salt: bytes, nonce: bytes, aad: bytes = b"") -> bytes:
    """Encrypt and authenticate. ``aad`` (the header) is authenticated but not encrypted."""
    return AESGCM(derive_key(password, salt)).encrypt(nonce, plaintext, aad)


def decrypt(ciphertext: bytes, password: str, salt: bytes, nonce: bytes, aad: bytes = b"") -> bytes:
    """Decrypt; raises :class:`WrongPasswordError` on a bad password or tampered data."""
    try:
        return AESGCM(derive_key(password, salt)).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise WrongPasswordError(
            "Wrong password, or the hidden data was modified/damaged."
        ) from exc


def seed_from_password(password: str, salt: bytes) -> np.ndarray:
    """Deterministic 256-bit seed (8 x uint32) for the random pixel order."""
    digest = hashlib.sha256(b"stego-pixel-order|" + salt + password.encode("utf-8")).digest()
    return np.frombuffer(digest, dtype=">u4").astype(np.uint32)
