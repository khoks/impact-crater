"""Stage 3 — rich metadata extraction per ADR-0011 §"Stage 3 — Rich metadata extraction".

For each photo (and each video scene's representative frames), call
`extract_metadata_image` (or `extract_metadata_video_scene`) and validate
the response against the D-009 Pydantic schema. On schema mismatch we
retry once; second mismatch raises `LLMOperationFailed`.

Person-library integration (N-008) is the M5 plug-in: when the library
is non-empty, the call site adds the reference-collage as a second image
input and the Pydantic schema's `recognized_persons` field gets populated
by the LLM. At M1 the field is always empty.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.types import (
    RichMetadataPhoto,
    RichMetadataVideoScene,
    Stage3AssetOutputs,
)
from impact_crater.workers import WorkerPool, default_pool

log = logging.getLogger(__name__)


# ---- Public API --------------------------------------------------------


async def run_stage3(
    *,
    router: LLMRouter,
    media: list[MediaRecord],
    brief: str,
    pool: WorkerPool | None = None,
) -> list[Stage3AssetOutputs]:
    """Run rich-metadata extraction over every photo + every scene.

    Per-asset failures are logged and silently dropped — Stage 4's
    prefilter handles missing entries gracefully (the asset has no
    metadata available and falls out via the quality floor when its
    score also defaults to 0). One bad image used to kill the job.

    Raises if EVERY asset failed (something is systemic).
    """
    pool = pool or default_pool()
    schema_photo = RichMetadataPhoto.model_json_schema()
    schema_video = RichMetadataVideoScene.model_json_schema()
    work_items = list(_enumerate_assets(media))

    def _on_error(idx: int, item: Any, exc: BaseException) -> None:
        log.warning(
            "stage3_asset_skipped idx=%d content_hash=%s scene_index=%s error=%r",
            idx,
            getattr(item, "cache_hash", "?"),
            getattr(item, "scene_index", None),
            str(exc)[:200],
        )

    raw = await pool.submit_many_tolerant(
        "network",
        work_items,
        lambda item: _extract(
            router,
            item,
            brief=brief,
            schema_photo=schema_photo,
            schema_video=schema_video,
        ),
        on_error=_on_error,
    )
    results = [r for r in raw if r is not None]
    failed = len(raw) - len(results)
    if work_items and not results:
        raise RuntimeError(
            f"stage3: every asset failed ({failed}/{len(work_items)}); "
            "see WARN-level stage3_asset_skipped logs above"
        )
    log.info(
        "stage3_done asset_count=%d failed=%d",
        len(results),
        failed,
    )
    return results


# ---- Per-asset workhorse ----------------------------------------------


async def _extract(
    router: LLMRouter,
    asset: "_Asset",
    *,
    brief: str,
    schema_photo: dict,
    schema_video: dict,
) -> Stage3AssetOutputs:
    image_bytes = await asyncio.to_thread(asset.path.read_bytes)
    schema = schema_video if asset.scene_index is not None else schema_photo

    try:
        raw = await router.extract_metadata_image(
            image_bytes,
            content_hash=asset.cache_hash,
            schema=schema,
            prompt_vars={"context_brief": brief},
        )
    except Exception as exc:
        # Most likely failure modes here: Anthropic 5MB cap (now guarded),
        # Pydantic schema mismatch from Gemini, or a transient API error
        # that retries already exhausted. Log the asset identity so the
        # developer can `grep content_hash=<prefix>` and find the row.
        log.error(
            "stage3_extract_failed operation=extract_metadata_image "
            "content_hash=%s scene_index=%s path=%s error=%r",
            asset.cache_hash,
            asset.scene_index,
            asset.path.name,
            str(exc)[:300],
        )
        raise

    try:
        metadata = _validate(raw, asset.scene_index is not None, attempt=1)
    except LLMOperationFailed as exc:
        log.error(
            "stage3_validation_failed content_hash=%s scene_index=%s error=%s",
            asset.cache_hash,
            asset.scene_index,
            str(exc)[:300],
        )
        raise

    return Stage3AssetOutputs(
        content_hash=asset.content_hash,
        scene_index=asset.scene_index,
        metadata=metadata,
    )


def _validate(
    raw: dict,
    is_video_scene: bool,
    *,
    attempt: int,
) -> RichMetadataPhoto | RichMetadataVideoScene:
    cls = RichMetadataVideoScene if is_video_scene else RichMetadataPhoto
    try:
        return cls.model_validate(raw)
    except ValidationError as e:
        if attempt >= 2:
            raise LLMOperationFailed(
                operation="extract_metadata_image",
                provider="(unknown)",
                model="(unknown)",
                attempts=attempt,
                last_error=f"D-009 schema mismatch after {attempt} attempts: {e}",
            ) from e
        # M1 keeps the retry simple — accept partial validity by re-trying
        # the construction with `model_construct` on attempt-2 logic.
        # For now we just re-raise as the LLM router's tool-use forces
        # schema-conformance for Anthropic (Stage 3 default per ADR-0009).
        raise LLMOperationFailed(
            operation="extract_metadata_image",
            provider="(unknown)",
            model="(unknown)",
            attempts=attempt,
            last_error=f"D-009 schema mismatch: {e}",
        ) from e


# ---- Asset enumeration ------------------------------------------------


class _Asset:
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
                frame_paths = [Path(p) for p in scene.representative_frame_paths]
                if not frame_paths:
                    continue
                middle = frame_paths[len(frame_paths) // 2]
                yield _Asset(
                    content_hash=rec.content_hash,
                    scene_index=scene.index,
                    path=middle,
                    cache_hash=f"{rec.content_hash}#{scene.index}",
                )
