import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _save(arr, path):
    Image.fromarray(arr.astype(np.uint8), "RGB").save(path)
    return path


@pytest.fixture
def cover_png(tmp_path):
    """300x300 smooth gradient with mild noise (~33 KB capacity)."""
    rng = np.random.default_rng(1)
    y, x = np.mgrid[0:300, 0:300]
    base = np.stack([x * 255 // 299, y * 255 // 299, (x + y) * 255 // 598], axis=-1)
    return _save(np.clip(base + rng.integers(-12, 12, base.shape), 0, 255), tmp_path / "cover.png")


@pytest.fixture
def big_cover(tmp_path):
    """600x600 noise image (~135 KB capacity) for the large-file test."""
    rng = np.random.default_rng(2)
    return _save(rng.integers(0, 256, (600, 600, 3)), tmp_path / "big.png")
