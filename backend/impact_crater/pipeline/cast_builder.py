"""Cast-analysis orchestration (A-018) — runs between Stage 3 and Stage 4.

Detects faces on the analysis renditions, embeds each via the configured
backend, and builds the `CastInventory`. Fail-soft: if mediapipe or the
embedder is unavailable, or no faces are found, it returns an empty
inventory and the pipeline proceeds exactly as before.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from impact_crater.media.cast import (
    CastInventory,
    FaceObservation,
    build_cast_inventory,
    detect_and_crop_faces,
    location_key,
)
from impact_crater.media.face_embed import CLUSTER_THRESHOLD, build_face_embedder
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.types import Stage3AssetOutputs

log = logging.getLogger(__name__)


async def build_cast(
    *,
    media: list[MediaRecord],
    stage3: list[Stage3AssetOutputs],
    router: object,
    backend: str | None,
) -> CastInventory:
    """Detect + embed + cluster faces across the photo set."""
    embedder = build_face_embedder(backend, router)
    threshold = CLUSTER_THRESHOLD.get(embedder.backend, CLUSTER_THRESHOLD["gemini"])

    # location description per photo, for the recurrence-breadth bucket.
    desc_by_hash: dict[str, str | None] = {}
    for o in stage3:
        if o.scene_index is None:
            md = o.metadata.model_dump()
            desc_by_hash[o.content_hash] = (md.get("location") or {}).get("description")

    observations: list[FaceObservation] = []
    faces_total = 0
    for rec in media:
        if rec.media_type != "photo":
            continue
        path = Path(rec.thumb_1024_path or rec.source_path)
        try:
            image_bytes = await asyncio.to_thread(path.read_bytes)
            crops = await asyncio.to_thread(detect_and_crop_faces, image_bytes)
        except Exception as exc:
            log.warning("cast: face detect failed for %s: %s", rec.content_hash[:12], str(exc)[:120])
            continue
        if not crops:
            continue
        faces_total += len(crops)
        embeddings = await embedder.embed_face_crops([c for c, _ in crops])
        loc = location_key(rec.gps_lat, rec.gps_lon, desc_by_hash.get(rec.content_hash))
        for (_, bbox), emb in zip(crops, embeddings):
            observations.append(
                FaceObservation(
                    content_hash=rec.content_hash,
                    embedding=emb,
                    capture_timestamp=rec.capture_timestamp,
                    location_key=loc,
                    bbox=bbox,
                )
            )

    log.info(
        "cast_build backend=%s photos=%d faces_detected=%d",
        embedder.backend,
        sum(1 for r in media if r.media_type == "photo"),
        faces_total,
    )
    return build_cast_inventory(observations, cluster_threshold=threshold)


# Imported for typing only.
_ = Any
