"""Image quality metrics (MSE / PSNR) and a simple chi-square LSB detector."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

from .utils import load_rgb

MIN_WINDOW = 8192      # smallest prefix (in channel values) tested
MIN_DOF = 10           # ignore windows with too few populated value pairs
MEDIUM_P = 0.05        # p below this -> "Low"
HIGH_P = 0.5           # p at/above this -> "High"


# --------------------------------------------------------------------------- quality
def mse(a: np.ndarray, b: np.ndarray) -> float:
    """Mean squared error between two same-shaped images."""
    if a.shape != b.shape:
        raise ValueError("Images must have the same shape.")
    diff = a.astype(np.float64) - b.astype(np.float64)
    return float(np.mean(diff * diff))


def psnr(mse_value: float, max_value: float = 255.0) -> float:
    """Peak signal-to-noise ratio in dB (``inf`` for identical images)."""
    if mse_value <= 0:
        return math.inf
    return 10.0 * math.log10((max_value**2) / mse_value)


def compare_images(original: np.ndarray, stego: np.ndarray) -> tuple[float, float]:
    """Return ``(mse, psnr)``."""
    m = mse(original, stego)
    return m, psnr(m)


# --------------------------------------------------------------------------- chi-square
def chi2_sf(x: float, k: int) -> float:
    """P(X >= x) for X ~ chi-square(k), via the Wilson-Hilferty approximation (no SciPy)."""
    if k <= 0:
        return 0.0
    if x <= 0:
        return 1.0
    mu = 1.0 - 2.0 / (9.0 * k)
    sigma = math.sqrt(2.0 / (9.0 * k))
    z = ((x / k) ** (1.0 / 3.0) - mu) / sigma
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def pair_chi_square(values: np.ndarray) -> tuple[float, int]:
    """Westfeld/Pfitzmann "pairs of values" statistic for a flat uint8 array.

    LSB embedding of random bits equalises the counts of 2k and 2k+1, so a small
    statistic (large p-value) means "consistent with LSB embedding".
    """
    hist = np.bincount(values, minlength=256).astype(np.float64)
    even, odd = hist[0::2], hist[1::2]
    expected = (even + odd) / 2.0
    mask = expected >= 5.0
    chi2 = float(np.sum((even[mask] - expected[mask]) ** 2 / expected[mask]))
    return chi2, int(mask.sum()) - 1


@dataclass(frozen=True)
class AnalysisResult:
    """Outcome of :func:`analyze_array`."""

    p_value: float
    chi2: float
    dof: int
    window_fraction: float   # share of the image (from the start) where the peak was found
    level: str               # "Low" | "Medium" | "High"
    conclusive: bool
    summary: str


def level_for(p_value: float) -> str:
    """Map a p-value to a suspicion level."""
    if p_value >= HIGH_P:
        return "High"
    if p_value >= MEDIUM_P:
        return "Medium"
    return "Low"


def analyze_array(rgb: np.ndarray) -> AnalysisResult:
    """Run the chi-square test on growing prefixes of the pixel data and keep the worst case.

    Sequential embedding only touches the start of the image, so prefixes of
    8192, 16384, ... values (and the full image) are all tested.
    """
    flat = np.ascontiguousarray(rgb).reshape(-1)
    n = flat.size
    sizes, s = [], MIN_WINDOW
    while s < n:
        sizes.append(s)
        s *= 2
    sizes.append(n)

    best: tuple[float, float, int, float] | None = None
    for size in sizes:
        chi2, dof = pair_chi_square(flat[:size])
        if dof < MIN_DOF:
            continue
        p = chi2_sf(chi2, dof)
        if best is None or p > best[0]:
            best = (p, chi2, dof, size / n)
    if best is None:
        return AnalysisResult(0.0, 0.0, 0, 1.0, "Low", False,
                              "Inconclusive: too few distinct pixel values for the test.")
    p, chi2, dof, frac = best
    level = level_for(p)
    summary = {
        "Low": "Pixel LSBs look natural. No sign of LSB embedding.",
        "Medium": "Some LSB-pair equalisation. Could be embedding or just a noisy image.",
        "High": "LSB pairs are strongly equalised - typical of LSB embedding "
                "(or of very noisy / synthetic images).",
    }[level]
    return AnalysisResult(p, chi2, dof, frac, level, True, summary)


def analyze_image(path: str | os.PathLike) -> AnalysisResult:
    """Load a PNG/BMP and analyse it."""
    return analyze_array(load_rgb(path))
