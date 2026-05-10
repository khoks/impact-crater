"""Headless + render + async job API per S-2.2.8 + S-2.3.4 + S-2.4.1.

  - `POST /api/jobs/headless` (M1) — synchronous Stages 1-5 → ArcJudgment.
  - `POST /api/jobs/render`   (M2) — synchronous Stages 1-7 → MP4 path.
  - `POST /api/jobs/submit`   (M3) — async Stages 1-7 → 202 + job_id.
  - `GET  /api/jobs/{job_id}` (M3) — poll snapshot.
  - `WS   /api/ws/jobs/{job_id}` (M3 — defined in api/ws.py) — event stream.

Quota gate (402) and router factory (412) shared by all sync endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

from impact_crater.jobs import get_registry
from impact_crater.jobs.runner_glue import submit_full_pipeline_job
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
    section_to_media_nl: str | None = None
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
    """Run the full M2 pipeline (Stages 1-7) and return the rendered MP4 path.

    Both `standard` and `music_video` modes are supported as of M4 (E-2.5).
    """
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
        mode=req.mode,
        section_to_media_nl=req.section_to_media_nl,
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


# ---- Async job submission (M3) -----------------------------------------


class SubmitJobRequest(BaseModel):
    media_paths: list[str] = Field(min_length=1)
    brief: str = Field(min_length=1)
    target_duration: int = Field(ge=1)
    audio_path: str = Field(min_length=1)
    mode: Literal["standard", "music_video"] = "standard"
    section_to_media_nl: str | None = None
    project_id: str | None = None
    project_name: str = ""


class SubmitJobResponse(BaseModel):
    job_id: str
    project_id: str
    state: str
    submitted_at: str
    websocket_url: str


@router.post(
    "/submit",
    response_model=SubmitJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_submit_job(req: SubmitJobRequest) -> SubmitJobResponse:
    """Kick off the M2 pipeline as a background task. Returns 202 immediately.

    Use `GET /api/jobs/{job_id}` to poll, or subscribe to
    `WS /api/ws/jobs/{job_id}` for live progress events.
    """
    audio_path = Path(req.audio_path)
    if not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"audio_path not found: {audio_path}",
        )

    try:
        llm_router = await runner.build_router_from_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc

    snap = submit_full_pipeline_job(
        media_paths=[Path(p) for p in req.media_paths],
        brief=req.brief,
        target_duration_seconds=req.target_duration,
        audio_path=audio_path,
        router=llm_router,
        project_id=req.project_id,
        mode=req.mode,
        section_to_media_nl=req.section_to_media_nl,
        project_name=req.project_name,
    )
    return SubmitJobResponse(
        job_id=snap.job_id,
        project_id=snap.project_id,
        state=snap.state,
        submitted_at=snap.submitted_at,
        websocket_url=f"/api/jobs/ws/{snap.job_id}",
    )


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Snapshot of the job's current state for polling fallbacks."""
    snap = get_registry().get(job_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
    return asdict(snap)


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def post_cancel_job(job_id: str) -> dict[str, Any]:
    """Request cancellation of a running job. The cancel signal flows
    through asyncio.CancelledError → runner_glue catches it → sets state
    to "cancelled". Returns 404 if the job doesn't exist; 409 if it's
    already in a terminal state."""
    registry = get_registry()
    snap = registry.get(job_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
    if snap.state in ("succeeded", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"job is already in terminal state: {snap.state}",
        )
    cancelled = await registry.cancel_job(job_id)
    return {"cancellation_requested": cancelled, "current_state": snap.state}


# ---- WebSocket (M3) ----------------------------------------------------


@router.websocket("/ws/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: str) -> None:
    """Stream JobProgressEvent messages until the job terminates.

    The registry replays the current state on subscribe so late joiners
    don't miss the transitions that already happened.
    """
    await websocket.accept()
    registry = get_registry()
    if registry.get(job_id) is None:
        log.warning("ws_unknown_job job_id=%s", job_id)
        await websocket.send_json({"type": "error", "detail": "unknown job"})
        await websocket.close(code=4404)
        return

    log.info("ws_connected job_id=%s", job_id)
    queue = await registry.subscribe(job_id)
    disconnected = False
    try:
        while True:
            event = await queue.get()
            if event is None:
                break  # terminal — close cleanly
            await websocket.send_json(
                {
                    "type": event.type,
                    "job_id": event.job_id,
                    "timestamp": event.timestamp,
                    "payload": event.payload,
                }
            )
    except WebSocketDisconnect:
        disconnected = True
        log.info("ws_disconnected_early job_id=%s", job_id)
    finally:
        await registry.unsubscribe(job_id, queue)
        try:
            await websocket.close()
        except Exception:
            pass
        if not disconnected:
            log.info("ws_closed job_id=%s", job_id)


# Suppress ruff F401 for stdlib helpers used by error formatting only.
_ = (asyncio, json)
