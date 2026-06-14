"""In-process job registry with WS-friendly event fan-out.

State machine:

    queued → running → succeeded
                    ↘ failed
                    ↘ cancelled

The registry stores a `JobSnapshot` per job_id and an asyncio queue per
WS subscriber. Producers (the pipeline runner) call `update_state` /
`emit_event` to advance the state and push a structured event to every
subscriber. Subscribers iterate `subscribe(job_id)` to consume events
in order; the iterator terminates after the job's terminal event.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

log = logging.getLogger(__name__)


JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
TERMINAL_STATES: frozenset[JobState] = frozenset(
    {"succeeded", "failed", "cancelled"}
)


class StageId(str, Enum):
    """The 7 ADR-0011 pipeline stages exposed to the UI."""

    INGEST = "stage_1_ingest"
    BULK_OPS = "stage_2_bulk_ops"
    METADATA = "stage_3_metadata"
    PREFILTER = "stage_4_prefilter"
    JUDGE = "stage_5_judge"
    PLAN = "stage_6_plan"
    RENDER = "stage_7_render"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StageProgress:
    stage: str
    state: Literal["pending", "running", "completed", "failed"] = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    detail: str = ""


@dataclass
class JobProgressEvent:
    """One message pushed onto every WS subscriber's queue.

    Concrete event types via the `type` discriminator:
      - "state": job state transition
      - "stage": stage state transition
      - "llm_call": one LLM call resolved (cache hit or miss)
      - "render": render-stage status update
      - "log": free-form info line
    """

    type: Literal["state", "stage", "llm_call", "render", "log", "diagnostics"]
    job_id: str
    timestamp: str = field(default_factory=_iso_now)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobSnapshot:
    """Polled view of a job's progress for `GET /api/jobs/{id}`."""

    job_id: str
    project_id: str
    snapshot_id: str | None = None
    state: JobState = "queued"
    submitted_at: str = field(default_factory=_iso_now)
    started_at: str | None = None
    completed_at: str | None = None
    stages: list[StageProgress] = field(default_factory=list)
    cost_by_tier_usd: dict[str, float] = field(default_factory=dict)
    cost_by_provider_usd: dict[str, float] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    render_path: str | None = None
    failure_reason: str | None = None
    correlation_id: str = ""
    # Optional metadata so the UI can show "Alps trip — June" instead of
    # `project-195c12955192`. Populated by submit_full_pipeline_job.
    project_name: str = ""
    brief: str = ""
    media_count: int = 0
    target_duration_seconds: int = 0


class JobRegistry:
    """Process-wide job registry. Singleton via `get_registry()`."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobSnapshot] = {}
        self._subscribers: dict[str, list[asyncio.Queue[JobProgressEvent | None]]] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    # ---- Lifecycle ----

    def register(self, snapshot: JobSnapshot) -> None:
        self._jobs[snapshot.job_id] = snapshot
        self._subscribers.setdefault(snapshot.job_id, [])
        # Pre-populate the 7 stages as `pending`.
        snapshot.stages = [StageProgress(stage=s.value) for s in StageId]

    def attach_task(self, job_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks[job_id] = task

    def get(self, job_id: str) -> JobSnapshot | None:
        return self._jobs.get(job_id)

    def all(self) -> list[JobSnapshot]:
        return list(self._jobs.values())

    # ---- State transitions ----

    async def update_state(
        self,
        job_id: str,
        state: JobState,
        *,
        snapshot_id: str | None = None,
        failure_reason: str | None = None,
        render_path: str | None = None,
    ) -> None:
        snap = self._jobs.get(job_id)
        if snap is None:
            return
        snap.state = state
        if state == "running" and snap.started_at is None:
            snap.started_at = _iso_now()
        if state in TERMINAL_STATES and snap.completed_at is None:
            snap.completed_at = _iso_now()
        if snapshot_id is not None:
            snap.snapshot_id = snapshot_id
        if failure_reason is not None:
            snap.failure_reason = failure_reason
        if render_path is not None:
            snap.render_path = render_path
        await self._emit(
            JobProgressEvent(
                type="state",
                job_id=job_id,
                payload={
                    "state": state,
                    "snapshot_id": snap.snapshot_id,
                    "failure_reason": snap.failure_reason,
                    "render_path": snap.render_path,
                },
            )
        )
        if state in TERMINAL_STATES:
            await self._close_subscribers(job_id)

    async def update_stage(
        self,
        job_id: str,
        stage: StageId,
        *,
        state: Literal["running", "completed", "failed"],
        detail: str = "",
    ) -> None:
        snap = self._jobs.get(job_id)
        if snap is None:
            return
        target = next((s for s in snap.stages if s.stage == stage.value), None)
        if target is None:
            return
        target.state = state
        if state == "running" and target.started_at is None:
            target.started_at = _iso_now()
        if state in ("completed", "failed") and target.completed_at is None:
            target.completed_at = _iso_now()
        if detail:
            target.detail = detail
        await self._emit(
            JobProgressEvent(
                type="stage",
                job_id=job_id,
                payload={
                    "stage": stage.value,
                    "state": state,
                    "detail": detail,
                    "started_at": target.started_at,
                    "completed_at": target.completed_at,
                },
            )
        )

    async def record_llm_call(
        self,
        job_id: str,
        *,
        operation: str,
        provider: str,
        tier: str,
        cost_usd: float,
        cache_hit: bool,
    ) -> None:
        snap = self._jobs.get(job_id)
        if snap is None:
            return
        if cache_hit:
            snap.cache_hits += 1
        else:
            snap.cache_misses += 1
            snap.total_cost_usd += cost_usd
            snap.cost_by_tier_usd[tier] = snap.cost_by_tier_usd.get(tier, 0.0) + cost_usd
            snap.cost_by_provider_usd[provider] = (
                snap.cost_by_provider_usd.get(provider, 0.0) + cost_usd
            )
        await self._emit(
            JobProgressEvent(
                type="llm_call",
                job_id=job_id,
                payload={
                    "operation": operation,
                    "provider": provider,
                    "tier": tier,
                    "cost_usd": 0.0 if cache_hit else cost_usd,
                    "cache_hit": cache_hit,
                    "total_cost_usd": snap.total_cost_usd,
                    "cost_by_tier_usd": dict(snap.cost_by_tier_usd),
                    "cost_by_provider_usd": dict(snap.cost_by_provider_usd),
                },
            )
        )

    async def emit_render_event(
        self,
        job_id: str,
        *,
        status: str,
        duration_ms: int,
        output_bytes: int,
    ) -> None:
        await self._emit(
            JobProgressEvent(
                type="render",
                job_id=job_id,
                payload={
                    "status": status,
                    "duration_ms": duration_ms,
                    "output_bytes": output_bytes,
                },
            )
        )

    async def emit_log(self, job_id: str, message: str) -> None:
        await self._emit(
            JobProgressEvent(type="log", job_id=job_id, payload={"message": message})
        )

    async def emit_diagnostics(self, job_id: str, phase_doc: dict[str, Any]) -> None:
        """Push one phase's diagnostics to subscribers as the phase finishes,
        so the in-progress UI can show decisions live (A-023 live popups)."""
        await self._emit(
            JobProgressEvent(
                type="diagnostics",
                job_id=job_id,
                payload={"phase": phase_doc.get("phase", ""), "doc": phase_doc},
            )
        )

    # ---- Cancellation ----

    async def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a running job. Returns True if a task
        was found and cancellation was signalled, False otherwise.

        The cancel signal flows through asyncio.CancelledError: the
        runner_glue catch-block updates state to "cancelled" with
        failure_reason="cancelled" before re-raising. The WS stream
        closes naturally on the terminal state.
        """
        snap = self._jobs.get(job_id)
        if snap is None or snap.state in TERMINAL_STATES:
            return False
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        log.info("job_cancel_requested job_id=%s", job_id)
        task.cancel()
        return True

    # ---- WS subscription ----

    async def subscribe(self, job_id: str) -> asyncio.Queue[JobProgressEvent | None]:
        queue: asyncio.Queue[JobProgressEvent | None] = asyncio.Queue()
        async with self._lock:
            subs = self._subscribers.setdefault(job_id, [])
            subs.append(queue)
        # Replay the current state to the new subscriber so late joiners
        # don't miss a state-only update that happened before they connected.
        snap = self._jobs.get(job_id)
        if snap is not None:
            await queue.put(
                JobProgressEvent(
                    type="state",
                    job_id=job_id,
                    payload={
                        "state": snap.state,
                        "snapshot_id": snap.snapshot_id,
                        "failure_reason": snap.failure_reason,
                        "render_path": snap.render_path,
                    },
                )
            )
            for stage in snap.stages:
                if stage.state != "pending":
                    await queue.put(
                        JobProgressEvent(
                            type="stage",
                            job_id=job_id,
                            payload={
                                "stage": stage.stage,
                                "state": stage.state,
                                "detail": stage.detail,
                                "started_at": stage.started_at,
                                "completed_at": stage.completed_at,
                            },
                        )
                    )
            if snap.state in TERMINAL_STATES:
                await queue.put(None)  # close marker
        return queue

    async def unsubscribe(
        self, job_id: str, queue: asyncio.Queue[JobProgressEvent | None]
    ) -> None:
        async with self._lock:
            subs = self._subscribers.get(job_id, [])
            if queue in subs:
                subs.remove(queue)

    # ---- Internal ----

    async def _emit(self, event: JobProgressEvent) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(event.job_id, []))
        for q in subs:
            await q.put(event)

    async def _close_subscribers(self, job_id: str) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(job_id, []))
        for q in subs:
            await q.put(None)


# ---- Singleton ---------------------------------------------------------


_REGISTRY: JobRegistry | None = None


def get_registry() -> JobRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = JobRegistry()
    return _REGISTRY


def reset_registry_for_tests() -> None:
    """Drop the singleton — only use in pytest fixtures."""
    global _REGISTRY
    _REGISTRY = None


# Re-export imports kept silent for ruff:
_ = (time, log)
