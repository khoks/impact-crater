"""mediapipe face-detection helper.

Wrapped in its own module so the heavy import is only triggered when
face-blur is actually requested. Returns normalized bounding boxes
`(x_norm, y_norm, w_norm, h_norm)` with values in [0, 1].
"""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


def detect_face_boxes(image_bytes: bytes) -> Sequence[tuple[float, float, float, float]]:
    """Return zero or more normalized face bounding boxes."""
    try:
        import mediapipe as mp  # type: ignore[import-not-found]
    except ImportError:
        log.info("mediapipe unavailable — face detection skipped")
        return []

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)

    fd_module = mp.solutions.face_detection
    with fd_module.FaceDetection(model_selection=1, min_detection_confidence=0.5) as fd:
        results = fd.process(arr)

    boxes: list[tuple[float, float, float, float]] = []
    detections = getattr(results, "detections", None) or []
    for det in detections:
        rb = det.location_data.relative_bounding_box
        # mediapipe returns negative xmin/ymin sometimes for boxes that
        # extend past the image edge — clamp.
        x = max(0.0, float(rb.xmin))
        y = max(0.0, float(rb.ymin))
        w = max(0.0, float(rb.width))
        h = max(0.0, float(rb.height))
        if w == 0 or h == 0:
            continue
        boxes.append((x, y, w, h))
    return boxes
