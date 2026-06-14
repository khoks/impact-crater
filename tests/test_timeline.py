"""Tests for media capture-time + GPS extraction (A-021 / N-014)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from impact_crater.media.timeline import (
    extract_capture_time,
    extract_gps,
)
from PIL import Image

# ---- Filename parsing --------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("PXL_20260405_223121903.jpg", datetime(2026, 4, 5, 22, 31, 21, 903000)),
        ("PXL_20260405_223142877.MP.jpg", datetime(2026, 4, 5, 22, 31, 42, 877000)),
        ("IMG_20240101_123456.jpg", datetime(2024, 1, 1, 12, 34, 56)),
        ("VID_20231231_235959.mp4", datetime(2023, 12, 31, 23, 59, 59)),
        ("IMG-20240715-WA0003.jpg", datetime(2024, 7, 15, 0, 0, 0)),
        ("Screenshot_20240301-091500.png", datetime(2024, 3, 1, 9, 15, 0)),
        ("2024-06-11 14.23.05.jpg", datetime(2024, 6, 11, 14, 23, 5)),
        ("signal-2024-02-02_08-09-10.jpg", datetime(2024, 2, 2, 8, 9, 10)),
    ],
)
def test_filename_timestamp_parsing(tmp_path: Path, name: str, expected: datetime) -> None:
    # No EXIF (we never write any), so filename must win over mtime.
    p = tmp_path / name
    p.write_bytes(b"not-a-real-image")
    ct = extract_capture_time(p, is_photo=False)  # is_photo=False skips EXIF
    assert ct.source == "filename"
    assert ct.timestamp == expected
    assert ct.confidence == 0.8


def test_unparseable_filename_falls_back_to_mtime(tmp_path: Path) -> None:
    p = tmp_path / "vacation-photo.jpg"
    p.write_bytes(b"x")
    # Pin a known mtime so the assertion is deterministic.
    fixed = datetime(2022, 5, 4, 10, 0, 0).timestamp()
    os.utime(p, (fixed, fixed))
    ct = extract_capture_time(p, is_photo=False)
    assert ct.source == "file_mtime"
    assert ct.timestamp == datetime.fromtimestamp(fixed)
    assert ct.confidence == 0.4


def test_random_digits_in_name_do_not_false_match(tmp_path: Path) -> None:
    # "IMG_9999.jpg" has no date — must not parse 9999 as a year.
    p = tmp_path / "IMG_9999.jpg"
    p.write_bytes(b"x")
    fixed = datetime(2021, 1, 1, 0, 0, 0).timestamp()
    os.utime(p, (fixed, fixed))
    ct = extract_capture_time(p, is_photo=False)
    assert ct.source == "file_mtime"


# ---- EXIF datetime + GPS -----------------------------------------------


def _jpeg_with_exif(path: Path, *, dt: str | None, gps: dict | None) -> None:
    img = Image.new("RGB", (8, 8), (120, 120, 120))
    exif_dict: dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "Interop": {}}
    if dt is not None:
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt.encode("ascii")
    if gps is not None:
        exif_dict["GPS"] = gps
    img.save(path, format="JPEG", exif=piexif.dump(exif_dict))


def test_exif_datetime_wins_over_filename(tmp_path: Path) -> None:
    # Filename says 2024; EXIF says 2026 — EXIF must win for a photo.
    p = tmp_path / "IMG_20240101_000000.jpg"
    _jpeg_with_exif(p, dt="2026:04:05 22:31:21", gps=None)
    ct = extract_capture_time(p, is_photo=True)
    assert ct.source == "exif"
    assert ct.timestamp == datetime(2026, 4, 5, 22, 31, 21)
    assert ct.confidence == 1.0


def test_exif_gps_decoded_to_decimal(tmp_path: Path) -> None:
    # Zion-ish: 37.2982 N, 113.0263 W.
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((37, 1), (17, 1), (5352, 100)),
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: ((113, 1), (1, 1), (3468, 100)),
    }
    p = tmp_path / "geo.jpg"
    _jpeg_with_exif(p, dt=None, gps=gps)
    coord = extract_gps(p, is_photo=True)
    assert coord is not None
    assert coord.lat == pytest.approx(37.2982, abs=1e-3)
    assert coord.lon == pytest.approx(-113.0263, abs=1e-3)  # W → negative


def test_no_gps_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "nogeo.jpg"
    _jpeg_with_exif(p, dt="2024:01:01 00:00:00", gps=None)
    assert extract_gps(p, is_photo=True) is None


def test_video_skips_exif_gps(tmp_path: Path) -> None:
    p = tmp_path / "PXL_20260405_223121903.mp4"
    p.write_bytes(b"x")
    assert extract_gps(p, is_photo=False) is None
