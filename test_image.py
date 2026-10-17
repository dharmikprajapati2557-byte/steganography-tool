import hashlib
import os
import shutil

import numpy as np
import pytest
from PIL import Image

from stego import analysis
from stego.image_lsb import HEADER_BITS, decode_image, encode_image, image_capacity_bytes
from stego.utils import (
    CapacityError, CorruptedDataError, EmptyMessageError, NoHiddenDataError,
    PasswordRequiredError, StegoError, StegoFileNotFoundError, UnsupportedFormatError,
    WrongPasswordError, load_rgb,
)


def out(tmp_path, name="stego.png"):
    return tmp_path / name


@pytest.mark.parametrize("password,random_order", [(None, False), ("pw", False), ("pw", True)])
def test_text_roundtrip(cover_png, tmp_path, password, random_order):
    r = encode_image(cover_png, out(tmp_path), "héllo wörld ✓".encode(), password=password, random_order=random_order)
    got = decode_image(r.output_path, password=password)
    assert got.text() == "héllo wörld ✓" and not got.is_file


def test_bmp_roundtrip(cover_png, tmp_path):
    bmp = tmp_path / "c.bmp"
    Image.open(cover_png).save(bmp)
    r = encode_image(bmp, out(tmp_path, "s.bmp"), b"bmp works")
    assert decode_image(r.output_path).data == b"bmp works"


def test_file_roundtrip_keeps_name(cover_png, tmp_path):
    blob = os.urandom(3000)
    r = encode_image(cover_png, out(tmp_path), blob, filename="dir/secret.bin", password="pw")
    got = decode_image(r.output_path, password="pw")
    assert got.is_file and got.filename == "secret.bin" and got.data == blob


def test_large_file(big_cover, tmp_path):
    blob = os.urandom(100_000)
    r = encode_image(big_cover, out(tmp_path), blob, filename="big.bin", password="pw", random_order=True)
    assert r.used_percent > 70
    assert decode_image(r.output_path, password="pw").data == blob


def test_quality_report_and_original_untouched(cover_png, tmp_path):
    before = hashlib.sha256(cover_png.read_bytes()).hexdigest()
    r = encode_image(cover_png, out(tmp_path), b"x" * 500)
    assert hashlib.sha256(cover_png.read_bytes()).hexdigest() == before
    assert r.psnr > 50 and r.mse < 0.1 and 0 < r.used_percent < 100


def test_wrong_and_missing_password(cover_png, tmp_path):
    r = encode_image(cover_png, out(tmp_path), b"secret", password="right")
    with pytest.raises(WrongPasswordError):
        decode_image(r.output_path, password="wrong")
    with pytest.raises(PasswordRequiredError):
        decode_image(r.output_path)


def test_random_order_wrong_password(cover_png, tmp_path):
    r = encode_image(cover_png, out(tmp_path), b"secret", password="right", random_order=True)
    with pytest.raises(WrongPasswordError):
        decode_image(r.output_path, password="wrong")


def test_no_hidden_data(cover_png):
    with pytest.raises(NoHiddenDataError):
        decode_image(cover_png)


def test_capacity_overflow(cover_png, tmp_path):
    cap = image_capacity_bytes(cover_png)
    assert cap == 300 * 300 * 3 // 8 - 38
    with pytest.raises(CapacityError) as exc:
        encode_image(cover_png, out(tmp_path), os.urandom(cap + 100))
    assert exc.value.available == cap
    assert not out(tmp_path).exists()


def test_empty_message(cover_png, tmp_path):
    with pytest.raises(EmptyMessageError):
        encode_image(cover_png, out(tmp_path), b"")


def test_corrupted_data(cover_png, tmp_path):
    r = encode_image(cover_png, out(tmp_path), b"a" * 200, compress=False)
    arr = load_rgb(r.output_path)
    flat = arr.reshape(-1)
    flat[HEADER_BITS + 40] ^= 1
    Image.fromarray(flat.reshape(arr.shape), "RGB").save(tmp_path / "bad.png")
    with pytest.raises(CorruptedDataError):
        decode_image(tmp_path / "bad.png")


def test_format_and_path_errors(cover_png, tmp_path):
    jpg = tmp_path / "c.jpg"
    Image.open(cover_png).convert("RGB").save(jpg)
    with pytest.raises(UnsupportedFormatError, match="JPEG"):
        encode_image(jpg, out(tmp_path), b"x")
    fake = tmp_path / "fake.png"            # JPEG data with a .png name
    shutil.copy(jpg, fake)
    with pytest.raises(UnsupportedFormatError):
        decode_image(fake)
    with pytest.raises(UnsupportedFormatError):   # JPEG output refused
        encode_image(cover_png, tmp_path / "o.jpg", b"x")
    with pytest.raises(StegoFileNotFoundError):
        decode_image(tmp_path / "missing.png")
    with pytest.raises(StegoError, match="differ"):
        encode_image(cover_png, cover_png, b"x", overwrite=True)
    encode_image(cover_png, out(tmp_path), b"x")
    with pytest.raises(StegoError, match="exists"):
        encode_image(cover_png, out(tmp_path), b"x")


def test_random_order_needs_password(cover_png, tmp_path):
    with pytest.raises(StegoError, match="password"):
        encode_image(cover_png, out(tmp_path), b"x", random_order=True)


def test_chi_square_detects_full_lsb_embedding(tmp_path):
    rng = np.random.default_rng(7)
    arr = (rng.integers(0, 128, (400, 400, 3)) * 2 + (rng.random((400, 400, 3)) < 0.2)).astype(np.uint8)
    cover = tmp_path / "biased.png"
    Image.fromarray(arr, "RGB").save(cover)
    before = analysis.analyze_image(cover)
    assert before.level == "Low" and before.p_value < 0.01
    cap = image_capacity_bytes(cover)
    r = encode_image(cover, out(tmp_path), os.urandom(cap - 40), compress=False)
    after = analysis.analyze_image(r.output_path)
    assert after.p_value > 0.05 and after.level in {"Medium", "High"}


def test_psnr_helpers():
    a = np.zeros((4, 4, 3), np.uint8)
    assert analysis.psnr(analysis.mse(a, a)) == float("inf")
    assert analysis.mse(a, a + 1) == 1.0
