import os

import pytest

from stego import text_zw
from stego.utils import (
    CapacityError, CorruptedDataError, EmptyMessageError, NoHiddenDataError,
    PasswordRequiredError, StegoError, WrongPasswordError,
)

COVER = "The quick brown fox jumps over the lazy dog. " * 6


@pytest.mark.parametrize("password", [None, "pw"])
@pytest.mark.parametrize("spread", [True, False])
def test_roundtrip_and_visible_text_preserved(password, spread):
    r = text_zw.encode_text(COVER, "héllo ✓".encode(), password=password, spread=spread)
    assert text_zw.visible_text(r.text) == COVER
    assert r.text != COVER and r.hidden_chars > 0
    assert text_zw.decode_text(r.text, password=password).text() == "héllo ✓"


def test_file_roundtrip():
    blob = os.urandom(500)
    r = text_zw.encode_text(COVER, blob, filename="a/b.bin", password="pw")
    got = text_zw.decode_text(r.text, password="pw")
    assert got.filename == "b.bin" and got.data == blob


def test_wrong_and_missing_password():
    r = text_zw.encode_text(COVER, b"secret", password="right")
    with pytest.raises(WrongPasswordError):
        text_zw.decode_text(r.text, password="wrong")
    with pytest.raises(PasswordRequiredError):
        text_zw.decode_text(r.text)


def test_no_hidden_data():
    with pytest.raises(NoHiddenDataError):
        text_zw.decode_text(COVER)


def test_capacity_overflow_and_empty():
    with pytest.raises(CapacityError):
        text_zw.encode_text("hi", os.urandom(500))
    with pytest.raises(EmptyMessageError):
        text_zw.encode_text(COVER, b"")
    with pytest.raises(StegoError):
        text_zw.encode_text("", b"x")


def test_large_secret():
    cover = "lorem ipsum dolor sit amet " * 1000       # ~27k chars
    blob = os.urandom(30_000)
    r = text_zw.encode_text(cover, blob, password="pw")
    assert text_zw.decode_text(r.text, password="pw").data == blob


def test_decoder_ignores_other_characters_and_detects_stripping():
    r = text_zw.encode_text(COVER, b"hello")
    noisy = r.text.replace(" ", " \ufeff")                     # extra invisible char not in our alphabet
    assert text_zw.decode_text(noisy).data == b"hello"
    stripped = r.text
    for _ in range(8):                                         # an app strips the last few hidden chars
        i = max(stripped.rfind(c) for c in text_zw.ZW_CHARS)
        stripped = stripped[:i] + stripped[i + 1:]
    with pytest.raises(CorruptedDataError):
        text_zw.decode_text(stripped)


def test_cover_with_zero_width_rejected():
    with pytest.raises(StegoError, match="zero-width"):
        text_zw.encode_text("a\u200db", b"x")


def test_combining_marks_not_split():
    cover = "cafe\u0301 au lait " * 20
    r = text_zw.encode_text(cover, b"hi")
    assert "\u0301" not in "".join(
        r.text[i - 1] for i in range(1, len(r.text)) if r.text[i] == "\u0301" and r.text[i - 1] in text_zw.ZW_CHARS
    )
    assert text_zw.visible_text(r.text) == cover
