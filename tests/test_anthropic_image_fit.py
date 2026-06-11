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

from impact_crater.llm_clients.anthropic_client import (
    _fit_image_for_anthropic,
    _image_block,
)

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


def test_under_budget_png_is_re_encoded_to_jpeg() -> None:
    """Real failure 2026-05-07: stage1 writes video-scene representative
    frames as PNG (`scene-N-middle.png`, cv2.imwrite). Even when the PNG is
    tiny (well under 3.5 MB) Anthropic 400'd because we declared the
    media_type as image/jpeg. The fix: always re-encode non-JPEG inputs
    to JPEG so the declared media_type is honest."""
    img = Image.new("RGB", (640, 480), color=(50, 100, 200))
    out = io.BytesIO()
    img.save(out, format="PNG")
    png_bytes = out.getvalue()
    assert len(png_bytes) < 3_500_000  # comfortably under the budget
    assert png_bytes.startswith(b"\x89PNG")

    fitted = _fit_image_for_anthropic(png_bytes)
    # Must NOT pass through unchanged — that's the exact bug.
    assert fitted is not png_bytes
    # Output must be a real JPEG (magic bytes + decodable as JPEG).
    assert fitted.startswith(b"\xff\xd8\xff"), "fitted output isn't a JPEG"
    out_img = Image.open(io.BytesIO(fitted))
    out_img.load()
    assert out_img.format == "JPEG"


def test_under_budget_jpeg_passes_through_unchanged() -> None:
    """Regression guard: don't accidentally re-encode every JPEG just
    because we now re-encode PNGs. JPEG inputs that already fit the
    budget should round-trip identically (no quality loss, no work)."""
    raw = _jpeg_bytes(size=(800, 600))
    assert raw.startswith(b"\xff\xd8\xff")
    fitted = _fit_image_for_anthropic(raw)
    assert fitted is raw  # identity check, not equality


def test_reencode_applies_exif_orientation() -> None:
    """Re-encoding strips EXIF, so the orientation must be baked into the
    pixels first. A landscape-stored Orientation=6 JPEG big enough to hit
    the re-encode path must come out portrait — not sideways with no tag.
    Real failure 2026-06-11: 3 Zion portrait photos reached Stage 3
    metadata extraction lying on their side."""
    rng = np.random.default_rng(seed=2)
    arr = rng.integers(0, 256, size=(4000, 6000, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    exif = Image.Exif()
    exif[274] = 6  # rotate 90° CW to display
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=98, exif=exif)
    raw = out.getvalue()
    assert len(base64.b64encode(raw)) > ANTHROPIC_BASE64_CAP  # forces re-encode

    fitted = _fit_image_for_anthropic(raw)
    assert fitted is not raw
    with Image.open(io.BytesIO(fitted)) as out_img:
        w, h = out_img.size
    assert h > w, f"orientation not applied: {w}x{h} still landscape"


def test_image_block_always_declares_jpeg_for_png_input() -> None:
    """The `_image_block` wrapper must declare image/jpeg unconditionally
    because `_fit_image_for_anthropic` always returns JPEG bytes."""
    img = Image.new("RGB", (320, 240), color=(10, 20, 30))
    out = io.BytesIO()
    img.save(out, format="PNG")
    png_bytes = out.getvalue()

    block = _image_block(png_bytes)
    assert block["type"] == "image"
    assert block["source"]["media_type"] == "image/jpeg"
    decoded = base64.b64decode(block["source"]["data"])
    assert decoded.startswith(b"\xff\xd8\xff")


def test_under_byte_budget_but_oversized_dimension_is_resized() -> None:
    """Real failure 2026-05-07: a Pixel NIGHT mode photo
    `PXL_20260405_030656922.NIGHT.jpg` had a long edge >8000px but a
    small file size (well under 3.5 MB). It slipped the byte check and
    Anthropic 400'd: `At least one of the image dimensions exceed max
    allowed size: 8000 pixels`. The fast path now also enforces the
    pixel-dimension cap; oversized dims trigger the full re-encode."""
    # Build a 9000×500 JPEG. Flat color compresses tiny — file size will
    # be well under 3.5 MB but the long edge exceeds the 8000px API cap.
    img = Image.new("RGB", (9000, 500), color=(50, 100, 200))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=70)
    raw = out.getvalue()
    assert len(raw) < 3_500_000, f"fixture too big: {len(raw)}"
    # Sanity: the fixture really does have a >8000px long edge.
    with Image.open(io.BytesIO(raw)) as probe:
        assert max(probe.size) > 8000

    fitted = _fit_image_for_anthropic(raw)
    # Must NOT pass through unchanged — exact bug shape.
    assert fitted is not raw
    # Output must be JPEG and within both caps.
    assert fitted.startswith(b"\xff\xd8\xff")
    assert len(base64.b64encode(fitted)) <= ANTHROPIC_BASE64_CAP
    with Image.open(io.BytesIO(fitted)) as out_img:
        assert max(out_img.size) <= 7900  # the configured dim cap
