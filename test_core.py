import pytest

from stego import crypto, header
from stego.utils import (
    CorruptedDataError, EmptyMessageError, NoHiddenDataError, WrongPasswordError,
    bits_to_bytes, bytes_to_bits, pack_payload, unpack_payload,
)


def test_bits_roundtrip():
    data = bytes(range(256))
    assert bits_to_bytes(bytes_to_bits(data)) == data


def test_payload_envelope():
    assert unpack_payload(pack_payload(b"hi")).data == b"hi"
    r = unpack_payload(pack_payload(b"data", "../../evil.txt"))
    assert r.is_file and r.filename == "evil.txt" and r.data == b"data"
    with pytest.raises(EmptyMessageError):
        pack_payload(b"")


def test_crypto_roundtrip_and_wrong_password():
    salt, nonce = crypto.random_salt(), crypto.random_nonce()
    ct = crypto.encrypt(b"secret", "pw", salt, nonce, b"hdr")
    assert crypto.decrypt(ct, "pw", salt, nonce, b"hdr") == b"secret"
    with pytest.raises(WrongPasswordError):
        crypto.decrypt(ct, "nope", salt, nonce, b"hdr")
    with pytest.raises(WrongPasswordError):  # header is authenticated too
        crypto.decrypt(ct, "pw", salt, nonce, b"HDR")


def test_header_pack_unpack():
    raw = header.pack_header(header.FLAG_ENCRYPTED | header.FLAG_COMPRESSED, 1234, b"s" * 16, b"n" * 12)
    assert len(raw) == header.HEADER_SIZE == 38
    h = header.unpack_header(raw)
    assert (h.length, h.encrypted, h.compressed, h.random_order) == (1234, True, True, False)
    with pytest.raises(NoHiddenDataError):
        header.unpack_header(b"\x00" * 38)


@pytest.mark.parametrize("pw", [None, "pw"])
def test_blob_roundtrip(pw):
    blob = header.build_blob(b"hello" * 100, password=pw)
    h = header.unpack_header(blob[:38])
    out = header.open_blob(blob[:38], h, blob[38:], pw)
    assert out.data == b"hello" * 100


def test_blob_checksum_detects_corruption():
    blob = bytearray(header.build_blob(b"hello world"))
    blob[40] ^= 0xFF
    h = header.unpack_header(bytes(blob[:38]))
    with pytest.raises(CorruptedDataError):
        header.open_blob(bytes(blob[:38]), h, bytes(blob[38:]), None)
