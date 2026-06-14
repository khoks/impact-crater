"""Glue between `JobRegistry` and the M2 pipeline runner.

`submit_full_pipeline_job` registers a JobSnapshot, kicks off
`run_full_pipeline` as a background asyncio task, and wires:

  - `_RegistryReporter` (stage-boundary callbacks → registry.update_stage)
  - router progress sink (per-LLM-call cost → registry.record_llm_call)

so the in-progress UI can drive every panel from `WS /api/ws/jobs/{id}`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from impact_crater.jobs.registry import (
    JobRegistry,
    JobSnapshot,
    StageId,
    get_registry,
)
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline.runner import (
    FullJobConfig,
    QuotaDeniedError,
    run_full_pipeline,
)
from impact_crater.pipeline.stage4_prefilter import Stage4EmptyCandidateSet
from impact_crater.pipeline.stage7_render import RenderError
from impact_crater.workers import JobCancelled

log = logging.getLogger(__name__)


_STAGE_BY_NAME: dict[str, StageId] = {s.value: s for s in StageId}


class _RegistryReporter:
    """ProgressReporter that forwards stage callbacks to the registry."""

    def __init__(self, registry: JobRegistry, job_id: str) -> None:
        self._registry = registry
        self._job_id = job_id

    async def stage_started(self, stage: str, *, detail: str = "") -> None:
        sid = _STAGE_BY_NAME.get(stage)
        if sid is None:
            return
        await self._registry.update_stage(self._job_id, sid, state="running", detail=detail)

    async def stage_completed(self, stage: str, *, detail: str = "") -> None:
        sid = _STAGE_BY_NAME.get(stage)
        if sid is None:
            return
        await self._registry.update_stage(self._job_id, sid, state="completed", detail=detail)

    async def stage_failed(self, stage: str, *, detail: str = "") -> None:
        sid = _STAGE_BY_NAME.get(stage)
        if sid is None:
            return
        await self._registry.update_stage(self._job_id, sid, state="failed", detail=detail)

    async def phase_diagnostics(self, phase_doc: dict[str, Any]) -> None:
        await self._registry.emit_diagnostics(self._job_id, phase_doc)


def _make_router_sink(registry: JobRegistry, job_id: str):
    async def _sink(payload: dict[str, Any]) -> None:
        await registry.record_llm_call(
            job_id,
            operation=payload.get("operation", ""),
            provider=payload.get("provider", ""),
            tier=payload.get("tier", ""),
            cost_usd=float(payload.get("cost_usd", 0.0)),
            cache_hit=bool(payload.get("cache_hit", False)),
        )

    return _sink


def submit_full_pipeline_job(
    *,
    media_paths: list[Path],
    brief: str,
    target_duration_seconds: int,
    audio_path: Path,
    router: LLMRouter,
    project_id: str | None = None,
    mode: str = "standard",
    section_to_media_nl: str | None = None,
    project_name: str = "",
    enable_cast: bool = True,
    cast_backend: str | None = None,
) -> JobSnapshot:
    """Register a new job + spawn the background task. Returns immediately."""
    registry = get_registry()
    job_id = uuid.uuid4().hex
    final_project_id = project_id or f"project-{uuid.uuid4().hex[:12]}"
    snap = JobSnapshot(
        job_id=job_id,
        project_id=final_project_id,
        project_name=project_name,
        brief=brief,
        media_count=len(media_paths),
        target_duration_seconds=target_duration_seconds,
    )
    registry.register(snap)

    if mode not in ("standard", "music_video"):
        raise ValueError(f"unsupported mode {mode!r}")

    config = FullJobConfig(
        media_paths=media_paths,
        brief=brief,
        target_duration_seconds=target_duration_seconds,
        audio_path=audio_path,
        mode=mode,  # type: ignore[arg-type]
        section_to_media_nl=section_to_media_nl,
        project_id=final_project_id,
        enable_cast=enable_cast,
        cast_backend=cast_backend,
    )
    reporter = _RegistryReporter(registry, job_id)
    router.set_progress_sink(_make_router_sink(registry, job_id))

    task = asyncio.create_task(_run_and_capture(config, router, reporter, registry, job_id))
    registry.attach_task(job_id, task)
    return snap


async def _run_and_capture(
    config: FullJobConfig,
    router: LLMRouter,
    reporter: _RegistryReporter,
    registry: JobRegistry,
    job_id: str,
) -> None:
    """Drive the pipeline + translate exceptions into terminal job states."""
    log.info("job_running job_id=%s media_count=%d", job_id, len(config.media_paths))
    await registry.update_state(job_id, "running")
    try:
        result = await run_full_pipeline(
            config, router=router, progress=reporter
        )
        snap = registry.get(job_id)
        if snap is not None:
            snap.correlation_id = result.correlation_id
        await registry.emit_render_event(
            job_id,
            status="success",
            duration_ms=result.render_duration_ms,
            output_bytes=result.output_bytes,
        )
        log.info(
            "job_succeeded job_id=%s project_id=%s snapshot_id=%s "
            "correlation_id=%s output_bytes=%d render_duration_ms=%d",
            job_id,
            result.project_id,
            result.snapshot_id,
            result.correlation_id,
            result.output_bytes,
            result.render_duration_ms,
        )
        await registry.update_state(
            job_id,
            "succeeded",
            snapshot_id=result.snapshot_id,
            render_path=result.render_path,
        )
    except QuotaDeniedError as exc:
        log.warning(
            "job_quota_denied job_id=%s reason=%s estimate_usd=%.4f",
            job_id,
            exc.reason,
            exc.quota_snapshot.get("estimate_usd", 0.0),
        )
        await registry.update_state(
            job_id,
            "failed",
            failure_reason=f"quota_denied:{exc.reason}",
        )
    except Stage4EmptyCandidateSet as exc:
        # Stage 4 produced zero candidates after the quality floor /
        # dedup / location passes. Surface the funnel stats so the user
        # understands which filter dropped everything. Fails before the
        # expensive Stage 5 L-tier call runs.
        log.warning(
            "job_stage4_empty job_id=%s input=%d after_quality=%d "
            "after_dedup=%d after_location=%d quality_threshold=%.2f",
            job_id,
            exc.input_count,
            exc.after_quality_count,
            exc.after_dedup_count,
            exc.after_location_count,
            exc.quality_threshold,
        )
        await registry.update_state(
            job_id,
            "failed",
            failure_reason=str(exc)[:300],
        )
    except RenderError as exc:
        log.error(
            "job_render_failed job_id=%s stage=%s ffmpeg_exit_code=%s "
            "stderr_tail=%r",
            job_id,
            exc.stage,
            exc.ffmpeg_exit_code,
            (exc.stderr_excerpt or "")[-300:],
        )
        await registry.update_state(
            job_id,
            "failed",
            failure_reason=f"render_failed:{exc.stage}",
        )
    except (asyncio.CancelledError, JobCancelled) as exc:
        # `asyncio.CancelledError` fires when the task itself is cancelled
        # (e.g. user clicks Cancel → registry.cancel_job → task.cancel()).
        # `JobCancelled` fires when the cancel signal reaches the task
        # while it's inside `pool.submit(...)`, which wraps the inner
        # CancelledError to make the cause less ambiguous. Both must
        # result in state="cancelled" — real bug 2026-05-07: cancelling
        # mid-Stage-2 produced state="failed" with reason "task cancelled"
        # because JobCancelled fell through to the generic Exception
        # branch below.
        log.info("job_cancelled job_id=%s via=%s", job_id, type(exc).__name__)
        await registry.update_state(job_id, "cancelled", failure_reason="cancelled")
        # Re-raise only for asyncio.CancelledError (so the surrounding
        # event loop sees the cancellation). JobCancelled is a normal
        # Exception — swallowing it is correct because we've already
        # recorded the terminal state.
        if isinstance(exc, asyncio.CancelledError):
            raise
    except Exception as exc:
        log.exception(
            "job_failed_unexpected job_id=%s error=%r",
            job_id,
            str(exc)[:200],
        )
        await registry.update_state(
            job_id, "failed", failure_reason=str(exc)[:200]
        )
    finally:
        # Detach the per-job sink so subsequent jobs don't accidentally
        # share state through the singleton router.
        router.set_progress_sink(None)
