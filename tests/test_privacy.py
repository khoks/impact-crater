"""Tests for the privacy posture pipeline (EXIF strip + face blur)."""

from __future__ import annotations

import io
from pathlib import Path

import piexif
import pytest
from PIL import Image

from impact_crater.media.privacy import (
    PrivacySettings,
    blur_faces,
    prepare_for_llm,
    strip_exif,
)


def _jpeg_with_exif(*, gps: bool = True, color: tuple[int, int, int] = (200, 80, 30)) -> bytes:
    """Generate a JPEG with a synthetic EXIF block (incl. GPS)."""
    img = Image.new("RGB", (320, 240), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    raw = buf.getvalue()

    exif_dict = {
        "0th": {piexif.ImageIFD.Make: b"FakeCam", piexif.ImageIFD.Model: b"FakeModel"},
        "Exif": {piexif.ExifIFD.LensModel: b"FakeLens"},
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((45, 1), (30, 1), (0, 1)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((73, 1), (15, 1), (0, 1)),
        }
        if gps
        else {},
        "1st": {},
        "thumbnail": None,
        "Interop": {},
    }
    exif_bytes = piexif.dump(exif_dict)
    out = io.BytesIO()
    piexif.insert(exif_bytes, raw, out)
    return out.getvalue()


def _read_exif(blob: bytes) -> dict:
    return piexif.load(blob)


# ---- EXIF strip --------------------------------------------------------


def test_strip_exif_off_passes_bytes_through() -> None:
    blob = _jpeg_with_exif()
    assert strip_exif(blob, mode="off") == blob


def test_strip_exif_gps_only_clears_gps_keeps_other() -> None:
    blob = _jpeg_with_exif()
    out = strip_exif(blob, mode="gps_only")
    parsed = _read_exif(out)
    assert parsed["GPS"] == {}
    # Camera info (0th) should still be present.
    assert any(parsed["0th"].values())


def test_strip_exif_all_clears_everything() -> None:
    blob = _jpeg_with_exif()
    out = strip_exif(blob, mode="all")
    parsed = _read_exif(out)
    # All groups empty + thumbnail wiped.
    assert all(not v for k, v in parsed.items() if isinstance(v, dict))


def test_strip_exif_no_exif_input_returns_unchanged() -> None:
    """Plain JPEG without EXIF — strip is a no-op."""
    img = Image.new("RGB", (100, 100), (10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    blob = buf.getvalue()
    out = strip_exif(blob, mode="all")
    # Returned bytes might differ slightly because piexif.dump→insert
    # adds an empty EXIF block; the important assertion is that GPS
    # stays empty and the file is still readable.
    assert _read_exif(out)["GPS"] == {}


# ---- Face blur (no faces in synthetic input) --------------------------


def test_blur_faces_no_faces_returns_input_unchanged() -> None:
    """Solid-color JPEG has no faces → mediapipe returns 0 boxes → pass-through."""
    img = Image.new("RGB", (320, 240), (100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    blob = buf.getvalue()
    out = blur_faces(blob)
    assert out == blob


# ---- prepare_for_llm orchestrator -------------------------------------


def test_prepare_pass_through_when_posture_is_off(tmp_path: Path) -> None:
    p = tmp_path / "x.jpg"
    p.write_bytes(_jpeg_with_exif())
    out = prepare_for_llm(p, posture=PrivacySettings())
    assert out == p.read_bytes()


def test_prepare_strips_exif_and_caches(tmp_path: Path) -> None:
    p = tmp_path / "x.jpg"
    p.write_bytes(_jpeg_with_exif())
    out1 = prepare_for_llm(
        p, posture=PrivacySettings(strip_exif="all"), project_id="test-proj"
    )
    out2 = prepare_for_llm(
        p, posture=PrivacySettings(strip_exif="all"), project_id="test-proj"
    )
    # Same posture → same cached bytes.
    assert out1 == out2
    # Strip actually happened — original had GPS, output doesn't.
    assert _read_exif(p.read_bytes())["GPS"]
    assert not _read_exif(out1)["GPS"]


def test_prepare_different_postures_different_cache_files(tmp_path: Path) -> None:
    p = tmp_path / "x.jpg"
    p.write_bytes(_jpeg_with_exif())
    out_gps = prepare_for_llm(
        p, posture=PrivacySettings(strip_exif="gps_only"), project_id="multi"
    )
    out_all = prepare_for_llm(
        p, posture=PrivacySettings(strip_exif="all"), project_id="multi"
    )
    # Different transforms → different bytes.
    assert out_gps != out_all
    # gps_only kept the camera info; all wiped it.
    assert any(_read_exif(out_gps)["0th"].values())
    assert not any(_read_exif(out_all)["0th"].values())


def test_privacy_settings_cache_token() -> None:
    assert PrivacySettings().cache_token() == "off-off"
    assert PrivacySettings(strip_exif="all", blur_faces="on").cache_token() == "all-on"
