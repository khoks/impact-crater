"""Capture-time + GPS extraction for media chronology (A-021 / N-014).

The single source of truth for *when* and *where* a photo or video was
captured. Three sources, reconciled by reliability:

  1. EXIF DateTimeOriginal (photos) — embedded by the camera at capture.
     Most trustworthy.
  2. Filename-encoded timestamp — phones and apps stamp the real capture
     time into the filename (`PXL_20260405_223121903.jpg`,
     `IMG_20240101_123456.jpg`, `Screenshot_...`, WhatsApp, Signal, …).
     Reliable, occasionally the device clock was wrong.
  3. File mtime — survives some copies, but download/sync resets it.
     Last resort.

We record which source won (`source`) and a coarse `confidence` so the
planner and UI can decide how much to trust the ordering. GPS is read
from EXIF when present — the bytes are already in the file; before this
module the app only ever *stripped* GPS for privacy, never read it.

Reconciliation rationale (N-014): a real PXL file carries the same time
in EXIF and filename, so either is fine; but EXIF is canonical when the
two disagree because the filename can be renamed by sync tools while EXIF
travels with the pixels.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger(__name__)


CaptureSource = Literal["exif", "filename", "file_mtime", "none"]

# Plausibility window — anything outside this is a parse artifact, not a
# real capture time (e.g. a filename digit run that isn't a date).
_MIN_YEAR = 1990
_MAX_YEAR = 2100


@dataclass(frozen=True)
class CaptureTime:
    """Reconciled capture time for one media file."""

    timestamp: datetime | None
    source: CaptureSource
    confidence: float  # 1.0 exif, 0.8 filename, 0.4 mtime, 0.0 none

    @property
    def iso(self) -> str | None:
        return self.timestamp.isoformat() if self.timestamp else None


@dataclass(frozen=True)
class GpsCoord:
    lat: float
    lon: float


# ---- Public API --------------------------------------------------------


def extract_capture_time(path: Path, *, is_photo: bool) -> CaptureTime:
    """Best capture time for `path`, reconciled across sources.

    EXIF (photos only) > filename > file mtime. Returns a CaptureTime
    whose `source` names the winner so callers can weigh confidence.
    """
    if is_photo:
        exif_dt = _exif_datetime(path)
        if exif_dt is not None:
            return CaptureTime(exif_dt, "exif", 1.0)

    name_dt = _filename_datetime(path.name)
    if name_dt is not None:
        return CaptureTime(name_dt, "filename", 0.8)

    mtime_dt = _file_mtime(path)
    if mtime_dt is not None:
        return CaptureTime(mtime_dt, "file_mtime", 0.4)

    return CaptureTime(None, "none", 0.0)


def extract_gps(path: Path, *, is_photo: bool) -> GpsCoord | None:
    """Decimal (lat, lon) from EXIF GPS, or None.

    Photos only — video container GPS would need ffprobe and is deferred.
    """
    if not is_photo:
        return None
    return _exif_gps(path)


# ---- EXIF (photos) -----------------------------------------------------


def _load_exif(path: Path) -> Any:
    """Return the piexif EXIF dict (Any — piexif is untyped) or None."""
    try:
        import piexif
    except ImportError:  # pragma: no cover
        return None
    try:
        return piexif.load(str(path))
    except Exception as exc:
        log.debug("piexif.load failed for %s: %s", path.name, exc)
        return None


def _exif_datetime(path: Path) -> datetime | None:
    exif = _load_exif(path)
    if not exif:
        return None
    try:
        import piexif
    except ImportError:  # pragma: no cover
        return None

    # DateTimeOriginal (when the shutter fired) beats DateTime (last edit).
    candidates = [
        (exif.get("Exif", {}), piexif.ExifIFD.DateTimeOriginal),
        (exif.get("Exif", {}), piexif.ExifIFD.DateTimeDigitized),
        (exif.get("0th", {}), piexif.ImageIFD.DateTime),
    ]
    for group, tag in candidates:
        raw = group.get(tag)
        if not raw:
            continue
        text = raw.decode("ascii", "ignore") if isinstance(raw, bytes) else str(raw)
        dt = _parse_exif_datetime(text)
        if dt is not None:
            return dt
    return None


def _parse_exif_datetime(text: str) -> datetime | None:
    # EXIF format: "YYYY:MM:DD HH:MM:SS" (occasionally with sub-seconds dropped).
    text = text.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if _MIN_YEAR <= dt.year <= _MAX_YEAR:
            return dt
    return None


def _exif_gps(path: Path) -> GpsCoord | None:
    exif = _load_exif(path)
    if not exif:
        return None
    try:
        import piexif
    except ImportError:  # pragma: no cover
        return None
    gps = exif.get("GPS") or {}
    lat = _gps_to_decimal(
        gps.get(piexif.GPSIFD.GPSLatitude), gps.get(piexif.GPSIFD.GPSLatitudeRef)
    )
    lon = _gps_to_decimal(
        gps.get(piexif.GPSIFD.GPSLongitude), gps.get(piexif.GPSIFD.GPSLongitudeRef)
    )
    if lat is None or lon is None:
        return None
    return GpsCoord(lat=lat, lon=lon)


def _gps_to_decimal(dms: object, ref: object) -> float | None:
    """EXIF stores GPS as 3 (numerator, denominator) rationals + a hemisphere
    ref (b'N'/b'S'/b'E'/b'W'). Convert to signed decimal degrees."""
    if not dms or not isinstance(dms, (list, tuple)) or len(dms) != 3:
        return None
    try:
        degrees = _rational(dms[0])
        minutes = _rational(dms[1])
        seconds = _rational(dms[2])
    except (TypeError, ZeroDivisionError, IndexError):
        return None
    if degrees is None or minutes is None or seconds is None:
        return None
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    ref_str = ref.decode("ascii", "ignore") if isinstance(ref, bytes) else str(ref or "")
    if ref_str.upper() in ("S", "W"):
        decimal = -decimal
    return round(float(decimal), 6)


def _rational(value: object) -> float | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        num, den = value
        if den == 0:
            return None
        return float(num / den)
    if isinstance(value, (int, float)):
        return float(value)
    return None


# ---- Filename patterns -------------------------------------------------

# Ordered most-specific → most-generic. Each entry maps named groups
# (y, mo, d, h, mi, s, ms?) so one builder handles them all.
_FILENAME_PATTERNS: list[re.Pattern[str]] = [
    # Pixel: PXL_20260405_223121903.jpg / .MP.jpg / .mp4 (last 3 = millis)
    re.compile(r"PXL_(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})_(?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})(?P<ms>\d{3})"),
    # IMG_/VID_/generic: IMG_20240101_123456 , VID_20240101_123456
    re.compile(r"(?:IMG|VID|MVIMG|PANO)[_-](?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})[_-](?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})"),
    # WhatsApp: IMG-20240101-WA0001.jpg (date only)
    re.compile(r"(?:IMG|VID)-(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})-WA\d+"),
    # Screenshot_20240101-123456 / Screenshot_20240101_123456
    re.compile(r"(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})[-_](?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})"),
    # Signal / dashed date+time: 2024-01-01-12-34-56 or 2024-01-01_12.34.56
    re.compile(r"(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})[-_ ](?P<h>\d{2})[.:-](?P<mi>\d{2})[.:-](?P<s>\d{2})"),
    # "2024-01-01 12.34.56" (macOS screenshot-ish)
    re.compile(r"(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2}) (?P<h>\d{2})\.(?P<mi>\d{2})\.(?P<s>\d{2})"),
    # Date only: 20240101 or 2024-01-01 (time defaults to midnight)
    re.compile(r"(?<!\d)(?P<y>\d{4})[-_]?(?P<mo>\d{2})[-_]?(?P<d>\d{2})(?!\d)"),
]


def _filename_datetime(name: str) -> datetime | None:
    for pat in _FILENAME_PATTERNS:
        m = pat.search(name)
        if not m:
            continue
        g = m.groupdict()
        try:
            dt = datetime(
                year=int(g["y"]),
                month=int(g["mo"]),
                day=int(g["d"]),
                hour=int(g.get("h") or 0),
                minute=int(g.get("mi") or 0),
                second=int(g.get("s") or 0),
                microsecond=int(g["ms"]) * 1000 if g.get("ms") else 0,
            )
        except (ValueError, KeyError):
            continue
        if _MIN_YEAR <= dt.year <= _MAX_YEAR:
            return dt
    return None


# ---- File mtime --------------------------------------------------------


def _file_mtime(path: Path) -> datetime | None:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    try:
        dt = datetime.fromtimestamp(ts)
    except (OverflowError, OSError, ValueError):
        return None
    if _MIN_YEAR <= dt.year <= _MAX_YEAR:
        return dt
    return None


# Imported but unused at runtime — keep for callers that want UTC stamping.
_ = timezone
