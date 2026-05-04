"""Headless job API per S-2.2.8.

`POST /api/jobs/headless` runs the M1 pipeline (Stages 1-5) end-to-end
and returns the structured ArcJudgment as JSON. Pre-job dual-cap quota
check returns 402 (Payment Required) when denied.

Render (Stage 7) and the live UI surface land in later milestones; this
endpoint is the smoke-test harness for the M1 LLM stack and is also how
the CLI's headless run will exercise the pipeline.
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
    HeadlessJobConfig,
    QuotaDeniedError,
    run_headless_pipeline,
)
from impact_crater.pipeline.stage4_prefilter import PreFilterOverrides

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
