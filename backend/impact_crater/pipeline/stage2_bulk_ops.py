"""Stage 2 — bulk per-asset ops per ADR-0011 §"Stage 2 — Bulk per-asset operations".

For each photo (and each video scene's representative frames), in parallel
on the worker pool's `network` class:

  - embed_image    → numpy embedding cached as .npy
  - caption_image  → 1-line caption cached as .json
  - score_image    (dimension="quality")             → quality score
  - score_image    (dimension="narrative_relevance") → brief-aware score

The narrative-relevance score's cache key includes a short hash of the
brief so re-running the same media against a different brief invalidates
only the brief-aware scores; quality + caption + embedding stay cached.

Stage 2 is the Tier-S workhorse — most of a job's LLM calls happen here
and most cache hits land here on a re-run.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Iterable
from pathlib import Path

from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.types import Stage2AssetOutputs
from impact_crater.workers import WorkerPool, default_pool

log = logging.getLogger(__name__)


# ---- Public API --------------------------------------------------------


async def run_stage2(
    *,
    router: LLMRouter,
    media: list[MediaRecord],
    brief: str,
    pool: WorkerPool | None = None,
) -> list[Stage2AssetOutputs]:
    """Run embed + caption + score over every photo + every scene.

    Returns one Stage2AssetOutputs per asset (photos: one per record;
    videos: one per scene).
    """
    pool = pool or default_pool()
    brief_hash = _short_hash(brief)
    work_items = list(_enumerate_assets(media))
    return await pool.submit_many(
        "network",
        work_items,
        lambda item: _run_for_asset(router, item, brief, brief_hash),
    )


# ---- Per-asset workhorse ----------------------------------------------


async def _run_for_asset(
    router: LLMRouter,
    asset: "_Asset",
    brief: str,
    brief_hash: str,
) -> Stage2AssetOutputs:
    image_bytes = await asyncio.to_thread(asset.path.read_bytes)
    cache_hash = asset.cache_hash

    # Run all four operations concurrently. Each is independently cached
    # by the router (cache hits become near-instant; misses go to the
    # provider in parallel).
    caption_task = router.caption_image(image_bytes, content_hash=cache_hash)
    quality_task = router.score_image(
        image_bytes, content_hash=cache_hash, dimension="quality"
    )
    narrative_task = router.score_image(
        image_bytes,
        content_hash=cache_hash,
        dimension="narrative_relevance",
        prompt_vars={"brief": brief},
        cache_extra={"brief_hash": brief_hash},
    )
    embed_task = router.embed_image(image_bytes, content_hash=cache_hash)

    results = await asyncio.gather(
        caption_task, quality_task, narrative_task, embed_task,
        return_exceptions=True,
    )
    # Surface the first real exception with its identity intact (avoid the
    # gather-cascade obscuring which call actually failed).
    for label, value in zip(
        ("caption_image", "score_image[quality]", "score_image[narrative]", "embed_image"),
        results,
    ):
        if isinstance(value, BaseException):
            log.error("stage2 %s failed for %s: %s", label, asset.cache_hash, value)
            raise value
    caption, quality, narrative, embedding = results  # type: ignore[misc]

    return Stage2AssetOutputs(
        content_hash=asset.content_hash,
        scene_index=asset.scene_index,
        caption=caption,
        quality_score=float(quality),
        narrative_relevance_score=float(narrative),
        embedding_dim=int(embedding.shape[0]) if embedding.ndim == 1 else 0,
    )


# ---- Asset enumeration ------------------------------------------------


class _Asset:
    """One scoring unit: a photo (whole file) or a single video scene."""

    __slots__ = ("content_hash", "scene_index", "path", "cache_hash")

    def __init__(
        self,
        *,
        content_hash: str,
        scene_index: int | None,
        path: Path,
        cache_hash: str,
    ) -> None:
        self.content_hash = content_hash
        self.scene_index = scene_index
        self.path = path
        self.cache_hash = cache_hash


def _enumerate_assets(media: list[MediaRecord]) -> Iterable[_Asset]:
    """Flatten media records into one _Asset per photo or per video scene.

    For videos, we score the **middle representative frame** as the scene's
    canonical asset — extending to a multi-frame aggregator is a Stage 2
    refinement when needed.
    """
    for rec in media:
        if rec.media_type == "photo":
            yield _Asset(
                content_hash=rec.content_hash,
                scene_index=None,
                path=Path(rec.source_path),
                cache_hash=rec.content_hash,
            )
        elif rec.media_type == "video" and rec.scenes:
            for scene in rec.scenes:
                # Pick the middle frame; fall back to the first frame.
                frame_paths = [Path(p) for p in scene.representative_frame_paths]
                if not frame_paths:
                    continue
                middle = frame_paths[len(frame_paths) // 2]
                yield _Asset(
                    content_hash=rec.content_hash,
                    scene_index=scene.index,
                    path=middle,
                    # Cache key for video scenes folds in the scene index so
                    # different scenes from the same video don't collide.
                    cache_hash=f"{rec.content_hash}#{scene.index}",
                )


# ---- Helpers ----------------------------------------------------------


def _short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
