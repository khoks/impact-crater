"""Headless + render job API per S-2.2.8 + S-2.3.4.

`POST /api/jobs/headless` runs the M1 pipeline (Stages 1-5) and returns
the structured ArcJudgment as JSON.

`POST /api/jobs/render` runs the full M2 pipeline (Stages 1-7) and returns
the path to a rendered MP4 + JobCostSummary.

Both endpoints share the same pre-job dual-cap quota gate (402 on denial)
and the same router-from-settings factory (412 when keys missing).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from impact_crater.llm_clients.base import MusicSpec
from impact_crater.pipeline import runner
from impact_crater.pipeline.runner import (
    FullJobConfig,
    HeadlessJobConfig,
    QuotaDeniedError,
    run_full_pipeline,
    run_headless_pipeline,
)
from impact_crater.pipeline.stage4_prefilter import PreFilterOverrides
from impact_crater.pipeline.stage7_render import RenderError

router = APIRouter()


class MusicSpecPayload(BaseModel):
    duration_ms: int = Field(ge=0)
    bpm: float | None = None
    section_to_media_nl: str | None = None


class HeadlessJobRequest(BaseModel):
    media_paths: list[str] = Field(min_length=1)
    brief: str = Field(min_length=1)
    target_duration: int = Field(ge=1, description="seconds")
    mode: Literal["standard", "music_video"] = "standard"
    music_spec: MusicSpecPayload | None = None
    project_id: str | None = None
    quality_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    target_size: int | None = Field(default=None, ge=1)


class HeadlessJobResponse(BaseModel):
    project_id: str
    correlation_id: str
    media_count: int
    candidate_count: int
    arc_judgment: dict[str, Any]
    candidate_set: dict[str, Any]
    quota: dict[str, Any]


@router.post(
    "/headless",
    response_model=HeadlessJobResponse,
    status_code=status.HTTP_200_OK,
)
async def post_headless_job(req: HeadlessJobRequest) -> HeadlessJobResponse:
    """Run the M1 headless pipeline and return the structured ArcJudgment."""
    music_spec = (
        MusicSpec(
            duration_ms=req.music_spec.duration_ms,
            bpm=req.music_spec.bpm,
            section_to_media_nl=req.music_spec.section_to_media_nl,
        )
        if req.music_spec
        else None
    )

    overrides = None
    if req.quality_threshold is not None or req.target_size is not None:
        overrides = PreFilterOverrides(
            quality_threshold=req.quality_threshold,
            target_size=req.target_size,
        )

    config = HeadlessJobConfig(
        media_paths=[Path(p) for p in req.media_paths],
        brief=req.brief,
        target_duration_seconds=req.target_duration,
        mode=req.mode,
        music_spec=music_spec,
        project_id=req.project_id,
        overrides=overrides,
    )

    try:
        llm_router = await runner.build_router_from_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc

    try:
        result = await run_headless_pipeline(config, router=llm_router)
    except QuotaDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": exc.reason, "quota": exc.snapshot},
        ) from exc

    return HeadlessJobResponse(
        project_id=result.project_id,
        correlation_id=result.correlation_id,
        media_count=result.media_count,
        candidate_count=len(result.candidate_set.items),
        arc_judgment=asdict(result.arc_judgment),
        candidate_set={
            "items": [asdict(it) for it in result.candidate_set.items],
            "cluster_metadata": result.candidate_set.cluster_metadata,
            "target_size": result.candidate_set.target_size,
            "floor": result.candidate_set.floor,
            "ceiling": result.candidate_set.ceiling,
        },
        quota=result.quota_snapshot,
    )


# ---- Full render pipeline (M2) -----------------------------------------


class RenderJobRequest(BaseModel):
    media_paths: list[str] = Field(min_length=1)
    brief: str = Field(min_length=1)
    target_duration: int = Field(ge=1, description="seconds")
    audio_path: str = Field(min_length=1)
    mode: Literal["standard", "music_video"] = "standard"
    project_id: str | None = None
    quality_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    target_size: int | None = Field(default=None, ge=1)


class RenderJobResponse(BaseModel):
    project_id: str
    snapshot_id: str
    correlation_id: str
    render_path: str
    output_bytes: int
    render_duration_ms: int
    media_count: int
    cost_summary_path: str
    arc_judgment: dict[str, Any]
    quota: dict[str, Any]


@router.post(
    "/render",
    response_model=RenderJobResponse,
    status_code=status.HTTP_200_OK,
)
async def post_render_job(req: RenderJobRequest) -> RenderJobResponse:
    """Run the full M2 pipeline (Stages 1-7) and return the rendered MP4 path."""
    if req.mode == "music_video":
        # M2 = standard only; M4 lights up music_video.
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="music_video mode lands at M4; M2 supports standard mode only",
        )

    overrides = None
    if req.quality_threshold is not None or req.target_size is not None:
        overrides = PreFilterOverrides(
            quality_threshold=req.quality_threshold,
            target_size=req.target_size,
        )

    audio_path = Path(req.audio_path)
    if not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"audio_path not found: {audio_path}",
        )

    config = FullJobConfig(
        media_paths=[Path(p) for p in req.media_paths],
        brief=req.brief,
        target_duration_seconds=req.target_duration,
        audio_path=audio_path,
        mode="standard",
        project_id=req.project_id,
        overrides=overrides,
    )

    try:
        llm_router = await runner.build_router_from_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc

    try:
        result = await run_full_pipeline(config, router=llm_router)
    except QuotaDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": exc.reason, "quota": exc.snapshot},
        ) from exc
    except RenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "reason": "render_failed",
                "stage": exc.stage,
                "ffmpeg_exit_code": exc.ffmpeg_exit_code,
                "stderr_excerpt": exc.stderr_excerpt[:2048],
            },
        ) from exc

    return RenderJobResponse(
        project_id=result.project_id,
        snapshot_id=result.snapshot_id,
        correlation_id=result.correlation_id,
        render_path=result.render_path,
        output_bytes=result.output_bytes,
        render_duration_ms=result.render_duration_ms,
        media_count=result.media_count,
        cost_summary_path=result.cost_summary_path,
        arc_judgment=asdict(result.arc_judgment) if result.arc_judgment else {},
        quota=result.quota_snapshot,
    )
