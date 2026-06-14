"""Face detection helper — returns normalized bounding boxes.

Resilient across environments: prefers mediapipe's face-detection solution
when the installed build exposes it, and falls back to OpenCV's Haar
cascade (which ships with opencv, needs no model download, and works on
every platform) otherwise. mediapipe 0.10.35+ removed the legacy
`mp.solutions` API, so the OpenCV path is what runs on current installs —
without this fallback both the cast inventory (A-018) and the privacy
face-blur (M5) silently find zero faces.

Boxes are normalized `(x, y, w, h)` with values in [0, 1].
"""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

Box = tuple[float, float, float, float]


def detect_face_boxes(image_bytes: bytes) -> Sequence[Box]:
    """Return zero or more normalized face bounding boxes."""
    mp_boxes = _detect_mediapipe(image_bytes)
    if mp_boxes is not None:
        return mp_boxes
    return _detect_opencv(image_bytes)


def _detect_mediapipe(image_bytes: bytes) -> list[Box] | None:
    """Try the legacy mediapipe solutions API. Returns None (not []) when
    it's unavailable so the caller falls through to OpenCV; returns a
    (possibly empty) list when it ran."""
    try:
        import mediapipe as mp  # type: ignore[import-not-found]

        solutions = getattr(mp, "solutions", None)
        fd_module = getattr(solutions, "face_detection", None) if solutions else None
        if fd_module is None:
            return None
    except ImportError:
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        with fd_module.FaceDetection(model_selection=1, min_detection_confidence=0.5) as fd:
            results = fd.process(arr)
    except Exception as exc:  # noqa: BLE001 — degrade to OpenCV on any runtime error
        log.debug("mediapipe face detection failed (%s); falling back to OpenCV", exc)
        return None

    boxes: list[Box] = []
    for det in getattr(results, "detections", None) or []:
        rb = det.location_data.relative_bounding_box
        x = max(0.0, float(rb.xmin))
        y = max(0.0, float(rb.ymin))
        w = max(0.0, float(rb.width))
        h = max(0.0, float(rb.height))
        if w > 0 and h > 0:
            boxes.append((x, y, w, h))
    return boxes


def _detect_opencv(image_bytes: bytes) -> list[Box]:
    """OpenCV Haar-cascade frontal-face detection. Always available with
    opencv; no model download."""
    try:
        import cv2
    except ImportError:  # pragma: no cover
        log.info("opencv unavailable — face detection skipped")
        return []

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            log.warning("haar cascade failed to load from %s", cascade_path)
            return []
        detections = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("opencv face detection failed (%s)", str(exc)[:120])
        return []

    h, w = gray.shape[:2]
    if w == 0 or h == 0:
        return []
    return [
        (float(x) / w, float(y) / h, float(fw) / w, float(fh) / h)
        for (x, y, fw, fh) in detections
    ]
