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
from typing import Any, cast

from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media import image_embed
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
    image_embedder: Any = None,
) -> list[Stage2AssetOutputs]:
    """Run embed + caption + score over every photo + every scene.

    Returns one Stage2AssetOutputs per asset that succeeded (photos: one
    per record; videos: one per scene). Per-asset failures are logged
    and silently dropped — Stage 4's prefilter handles missing entries
    gracefully (the asset gets a default 0.0 quality score and falls out
    via the quality floor). One bad image used to kill the whole job.

    Raises if EVERY asset failed (something is systemic).
    """
    pool = pool or default_pool()
    brief_hash = _short_hash(brief)
    work_items = list(_enumerate_assets(media))
    # A-016 telemetry: how much smaller is the analysis payload than the
    # originals? Renditions are sent to the VLM instead of source bytes.
    analysis_bytes = sum(
        p.stat().st_size for p in (Path(a.path) for a in work_items) if p.is_file()
    )
    source_bytes = sum(int(m.file_size or 0) for m in media)
    log.info(
        "stage2_start asset_count=%d media_count=%d brief_hash=%s "
        "analysis_payload_bytes=%d source_bytes=%d payload_ratio=%.3f",
        len(work_items),
        len(media),
        brief_hash,
        analysis_bytes,
        source_bytes,
        (analysis_bytes / source_bytes) if source_bytes else 1.0,
    )

    def _on_error(idx: int, item: Any, exc: BaseException) -> None:
        log.warning(
            "stage2_asset_skipped idx=%d content_hash=%s scene_index=%s error=%r",
            idx,
            getattr(item, "cache_hash", "?"),
            getattr(item, "scene_index", None),
            str(exc)[:200],
        )

    raw = await pool.submit_many_tolerant(
        "network",
        work_items,
        lambda item: _run_for_asset(router, item, brief, brief_hash, image_embedder),
        on_error=_on_error,
    )
    results = [r for r in raw if r is not None]
    failed = len(raw) - len(results)
    if work_items and not results:
        raise RuntimeError(
            f"stage2: every asset failed ({failed}/{len(work_items)}); "
            "see WARN-level stage2_asset_skipped logs above"
        )
    log.info(
        "stage2_done asset_count=%d failed=%d brief_hash=%s",
        len(results),
        failed,
        brief_hash,
    )
    return results


# ---- Per-asset workhorse ----------------------------------------------


async def _run_for_asset(
    router: LLMRouter,
    asset: _Asset,
    brief: str,
    brief_hash: str,
    image_embedder: Any = None,
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
    # S-2.10.8: the pluggable embedder (default None → router op, byte-identical).
    embed_task = image_embed.embed_with_fallback(
        image_embedder, router, image_bytes, content_hash=cache_hash
    )

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
    # The loop above raised on any BaseException, so each result is its
    # success type — cast so the type checker agrees.
    caption = cast(str, results[0])
    quality = cast(float, results[1])
    narrative = cast(float, results[2])
    embedding = cast(Any, results[3])

    return Stage2AssetOutputs(
        content_hash=asset.content_hash,
        scene_index=asset.scene_index,
        caption=caption,
        quality_score=float(quality),
        narrative_relevance_score=float(narrative),
        embedding_dim=int(embedding.shape[0]) if embedding.ndim == 1 else 0,
        embedding=embedding if embedding.ndim == 1 else None,
    )


# ---- Asset enumeration ------------------------------------------------


class _Asset:
    """One scoring unit: a photo (whole file) or a single video scene."""

    __slots__ = ("cache_hash", "content_hash", "path", "scene_index")

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
                # A-016: analyze the 1024px rendition, not the 9-12 MB
                # original. The cache keys on content_hash (the source
                # file), so the uploaded bytes changing doesn't invalidate
                # anything — it just sends ~10x less data per call.
                path=Path(rec.thumb_1024_path or rec.source_path),
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
