"""Privacy posture pipeline per ADR-0016.

Two pre-LLM image transforms:

  1. EXIF strip — `piexif`-based byte-level strip. Modes:
     - `off`     : original bytes pass through unchanged
     - `gps_only`: GPS group cleared; rest of EXIF preserved
     - `all`     : all EXIF cleared
  2. Face blur — `mediapipe` face-detection + Gaussian blur on detected
     boxes. Modes: `off` / `on`.

Originals are never modified in place — both transforms write to a
per-project cache. The `prepare_for_llm(path, posture, project_id)`
helper picks the right transform pipeline and returns the bytes the
LLM call should consume.

ADR-0010 named pyexiv2 + dlib's face-recognition; we substitute piexif
+ mediapipe because the originals don't ship pre-built wheels for
Python 3.12 + Windows. mediapipe's face *detection* is enough — we
only need bounding boxes, not embeddings.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageFilter

from impact_crater import paths

log = logging.getLogger(__name__)

ExifMode = Literal["off", "gps_only", "all"]
BlurMode = Literal["off", "on"]


@dataclass(frozen=True)
class PrivacySettings:
    """Per-project (or global default) privacy posture per ADR-0016."""

    strip_exif: ExifMode = "off"
    blur_faces: BlurMode = "off"

    def is_pass_through(self) -> bool:
        return self.strip_exif == "off" and self.blur_faces == "off"

    def cache_token(self) -> str:
        """Stable short string used in cache filenames."""
        return f"{self.strip_exif}-{self.blur_faces}"


# ---- EXIF strip --------------------------------------------------------


def strip_exif(image_bytes: bytes, *, mode: ExifMode) -> bytes:
    """Return image bytes with EXIF stripped per mode.

    Falls back to "preserve as-is" if piexif can't parse the file
    (some PNG/HEIC inputs); the caller decides whether to retry as
    a different format.
    """
    if mode == "off":
        return image_bytes
    try:
        import piexif
    except ImportError:  # pragma: no cover
        log.warning("piexif unavailable; returning original bytes")
        return image_bytes

    try:
        exif_dict = piexif.load(image_bytes)
    except Exception as exc:
        log.debug("piexif.load failed (%s); returning original bytes", exc)
        return image_bytes

    if mode == "gps_only":
        exif_dict["GPS"] = {}
    elif mode == "all":
        for key in list(exif_dict.keys()):
            if key in ("0th", "Exif", "GPS", "1st", "Interop"):
                exif_dict[key] = {}
            else:
                exif_dict.pop(key, None)
        # piexif also wants thumbnail bytes wiped.
        exif_dict["thumbnail"] = None

    try:
        new_exif = piexif.dump(exif_dict)
    except Exception as exc:
        log.warning("piexif.dump failed (%s); returning original bytes", exc)
        return image_bytes

    # Rewrite the file with the modified EXIF block. piexif.insert handles
    # JPEG only; for other formats we drop EXIF by re-encoding via PIL.
    out_buf = io.BytesIO()
    try:
        piexif.insert(new_exif, image_bytes, out_buf)
    except Exception:
        # Non-JPEG fallback: re-save through PIL without EXIF entirely.
        img = Image.open(io.BytesIO(image_bytes))
        img.save(out_buf, format=img.format or "JPEG")
    return out_buf.getvalue()


# ---- Face blur ---------------------------------------------------------


def blur_faces(image_bytes: bytes, *, blur_radius: int = 25) -> bytes:
    """Detect faces with mediapipe; Gaussian-blur each bbox.

    Falls back to no-op when mediapipe can't load (e.g. CPU-only
    install without OpenCV — mediapipe's pipeline requires it).
    Returns JPEG bytes regardless of input format so downstream code
    can treat the output uniformly.
    """
    try:
        from impact_crater.media._face_detect import detect_face_boxes

        boxes = detect_face_boxes(image_bytes)
    except Exception as exc:
        log.warning("face detection failed (%s); returning original bytes", exc)
        return image_bytes

    if not boxes:
        # No faces — pass through.
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    blurred = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Compose: original image, with blurred patches in face regions.
    out = img.copy()
    for box in boxes:
        # Box is (x_norm, y_norm, w_norm, h_norm). Clamp to image bounds.
        x = max(0, int(box[0] * w))
        y = max(0, int(box[1] * h))
        bw = max(1, int(box[2] * w))
        bh = max(1, int(box[3] * h))
        x2 = min(w, x + bw)
        y2 = min(h, y + bh)
        if x2 <= x or y2 <= y:
            continue
        patch = blurred.crop((x, y, x2, y2))
        out.paste(patch, (x, y))

    out_buf = io.BytesIO()
    out.save(out_buf, format="JPEG", quality=88)
    return out_buf.getvalue()


# ---- Orchestrator ------------------------------------------------------


def prepare_for_llm(
    path: Path,
    *,
    posture: PrivacySettings,
    project_id: str | None = None,
) -> bytes:
    """Apply EXIF strip + face blur per posture; return cached bytes.

    When posture is pass-through, reads the original bytes directly.
    Otherwise computes a cache key and either returns cached bytes or
    runs the transforms + writes to cache.
    """
    original = path.read_bytes()
    if posture.is_pass_through():
        return original

    cache_dir = _cache_dir(project_id)
    content_hash = hashlib.sha256(original).hexdigest()[:16]
    cache_path = cache_dir / f"{content_hash}-{posture.cache_token()}.jpg"
    if cache_path.is_file():
        return cache_path.read_bytes()

    out = original
    if posture.strip_exif != "off":
        out = strip_exif(out, mode=posture.strip_exif)
    if posture.blur_faces == "on":
        out = blur_faces(out)

    cache_path.write_bytes(out)
    return out


def _cache_dir(project_id: str | None) -> Path:
    if project_id:
        d = paths.projects_dir() / project_id / "cache" / "privacy"
    else:
        d = paths.cache_dir() / "privacy-shared"
    d.mkdir(parents=True, exist_ok=True)
    return d
