"""Tests for `_fit_image_for_anthropic` — the size guard that keeps every
image-bearing Anthropic call under the 5 MB base64 cap.

Real failure mode caught by user run on 2026-05-06: a 9.5 MB Pixel photo
came back from the API as a 400 with the literal message:
    messages.0.content.0.image.source.base64: image exceeds 5 MB maximum
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from impact_crater.llm_clients.anthropic_client import _fit_image_for_anthropic

ANTHROPIC_BASE64_CAP = 5_242_880  # API hard limit, in base64 bytes


def _jpeg_bytes(*, size: tuple[int, int], quality: int = 95, noise: bool = False) -> bytes:
    """Build a JPEG of the requested pixel dimensions. `noise=True` fills
    the canvas with random pixels so JPEG entropy can't compress it down to
    a sliver — needed when the test wants a multi-MB output file."""
    if noise:
        rng = np.random.default_rng(seed=0)
        arr = rng.integers(0, 256, size=(size[1], size[0], 3), dtype=np.uint8)
        img = Image.fromarray(arr, mode="RGB")
    else:
        img = Image.new("RGB", size, color=(123, 200, 80))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def test_small_image_passes_through_unchanged() -> None:
    raw = _jpeg_bytes(size=(800, 600))
    assert len(raw) < 1_000_000

    fitted = _fit_image_for_anthropic(raw)

    # Pass-through avoids re-encoding artifacts + work on the happy path.
    assert fitted is raw


def test_large_image_is_downscaled_under_cap() -> None:
    # Generate a >5 MB-base64 JPEG via a high-entropy random canvas — flat
    # colors compress to <500 KB even at 6000×4000.
    raw = _jpeg_bytes(size=(6000, 4000), quality=98, noise=True)
    encoded_size = len(base64.b64encode(raw))
    assert encoded_size > ANTHROPIC_BASE64_CAP, (
        f"test fixture not big enough: {encoded_size} <= {ANTHROPIC_BASE64_CAP}"
    )

    fitted = _fit_image_for_anthropic(raw)
    assert fitted is not raw
    assert len(base64.b64encode(fitted)) <= ANTHROPIC_BASE64_CAP

    # And it should still be a valid JPEG that opens.
    img = Image.open(io.BytesIO(fitted))
    img.load()
    assert max(img.size) <= 1568  # the configured max edge


def test_oversized_rgba_png_round_trips_through_jpeg() -> None:
    # An RGBA PNG over the threshold must convert to RGB before JPEG-encoding,
    # otherwise PIL raises "cannot write mode RGBA as JPEG". Force >threshold
    # by using a noisy 4000×3000 RGBA canvas.
    rng = np.random.default_rng(seed=1)
    arr = rng.integers(0, 256, size=(3000, 4000, 4), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGBA")
    out = io.BytesIO()
    img.save(out, format="PNG", compress_level=1)  # low compression → big file
    raw = out.getvalue()
    assert len(raw) > 3_500_000, f"fixture too small: {len(raw)}"

    fitted = _fit_image_for_anthropic(raw)
    out_img = Image.open(io.BytesIO(fitted))
    out_img.load()
    assert out_img.mode == "RGB"
    assert len(base64.b64encode(fitted)) <= ANTHROPIC_BASE64_CAP
