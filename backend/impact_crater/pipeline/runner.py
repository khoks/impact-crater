"""Headless pipeline runner — sequences Stages 1-5 (M1) and Stages 1-7 (M2).

`run_headless_pipeline` (M1) returns the structured ArcJudgment.
`run_full_pipeline` (M2) takes the same inputs plus an `audio_path` and
runs through Stages 6-7 to produce a rendered MP4 + JobCostSummary.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from impact_crater import quota, telemetry
from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import ArcJudgment, MusicSpec
from impact_crater.llm_clients.google_client import GoogleLLMClient
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media import ffmpeg as ff
from impact_crater.pipeline import (
    stage1_ingest,
    stage2_bulk_ops,
    stage3_metadata,
    stage4_prefilter,
    stage5_judge,
    stage6_plan,
    stage7_render,
)
from impact_crater.pipeline.stage4_prefilter import CandidateSet, PreFilterOverrides
from impact_crater.pipeline.stage6_plan import RenderPlan, StandardMusicSpec
from impact_crater.pipeline.stage7_render import RenderResult
from impact_crater.storage import settings as settings_store
from impact_crater.workers import WorkerPool

log = logging.getLogger(__name__)


# ---- Public types ------------------------------------------------------


@dataclass
class HeadlessJobResult:
    project_id: str
    arc_judgment: ArcJudgment
    candidate_set: CandidateSet
    media_count: int
    correlation_id: str
    media: list[Any] = field(default_factory=list)  # MediaRecord; typed Any to avoid forward-ref dance
    quota_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadlessJobConfig:
    media_paths: list[Path]
    brief: str
    target_duration_seconds: int
    mode: Literal["standard", "music_video"] = "standard"
    music_spec: MusicSpec | None = None
    project_id: str | None = None  # auto-generated if not supplied
    overrides: PreFilterOverrides | None = None


class QuotaDeniedError(RuntimeError):
    """Raised when the pre-job dual-cap quota check denies the job."""

    def __init__(self, reason: str, snapshot: dict[str, Any]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.snapshot = snapshot


# ---- Public entry point -----------------------------------------------


async def run_headless_pipeline(
    config: HeadlessJobConfig,
    *,
    router: LLMRouter | None = None,
    pool: WorkerPool | None = None,
) -> HeadlessJobResult:
    """Run Stages 1-5 end-to-end and return the ArcJudgment.

    Steps:
      0. Pre-job dual-cap quota check (rough estimate from input size).
      1. Stage 1 ingest (cpu pool).
      2. Stage 2 bulk ops (network pool).
      3. Stage 3 rich metadata (network pool).
      4. Stage 4 deterministic pre-filter.
      5. Stage 5 narrative-arc judgment.

    Telemetry: emits JobLifecycleEvent at start + completion. Per-call
    LLMCallEvent emission lives at the LLMRouter layer (S-2.2.X follow-up
    if not already wired); the runner just bookends the job.
    """
    project_id = config.project_id or f"headless-{uuid.uuid4().hex[:12]}"
    correlation_id = uuid.uuid4().hex
    pool = pool or WorkerPool()
    router = router or _default_router_from_settings()

    # 0. Quota pre-check (rough estimate — pessimistic per ADR-0015).
    estimated = _estimate_cost_per_provider(len(config.media_paths))
    quota_check = await quota.check_quota(estimated)
    quota_snapshot = {
        "allowed": quota_check.allowed,
        "reason": quota_check.reason,
        "today_total_spent_usd": quota_check.today_total_spent_usd,
        "today_per_provider_spent_usd": quota_check.today_per_provider_spent_usd,
        "cap_total_usd": quota_check.cap_total_usd,
        "cap_per_provider_usd": quota_check.cap_per_provider_usd,
        "estimate_usd": sum(estimated.values()),
    }
    if not quota_check.allowed:
        raise QuotaDeniedError(quota_check.reason, quota_snapshot)

    telemetry.emit(
        telemetry.JobLifecycleEvent(
            project_id=project_id,
            snapshot_id=None,
            state="started",
            correlation_id=correlation_id,
            reason="headless",
        )
    )

    try:
        # Stage 1
        media = await stage1_ingest.ingest_media(
            project_id, config.media_paths, pool=pool
        )

        # Stage 2 + 3 — sequentially (3 needs the full media list); inside
        # each stage we parallelize per-asset.
        stage2 = await stage2_bulk_ops.run_stage2(
            router=router, media=media, brief=config.brief, pool=pool
        )
        stage3 = await stage3_metadata.run_stage3(
            router=router, media=media, brief=config.brief, pool=pool
        )

        # Stage 4
        candidate_set = stage4_prefilter.prefilter(
            media=media,
            stage2=stage2,
            stage3=stage3,
            target_duration_seconds=config.target_duration_seconds,
            overrides=config.overrides,
        )

        # Stage 5
        arc_judgment = await stage5_judge.judge_narrative_arc(
            router=router,
            candidate_set=candidate_set,
            brief=config.brief,
            target_duration_seconds=config.target_duration_seconds,
            mode=config.mode,
            music_spec=config.music_spec,
        )

        telemetry.emit(
            telemetry.JobLifecycleEvent(
                project_id=project_id,
                snapshot_id=None,
                state="completed",
                correlation_id=correlation_id,
            )
        )
        return HeadlessJobResult(
            project_id=project_id,
            arc_judgment=arc_judgment,
            candidate_set=candidate_set,
            media_count=len(media),
            correlation_id=correlation_id,
            media=media,
            quota_snapshot=quota_snapshot,
        )
    except Exception as exc:
        telemetry.emit(
            telemetry.JobLifecycleEvent(
                project_id=project_id,
                snapshot_id=None,
                state="failed",
                correlation_id=correlation_id,
                reason=str(exc)[:200],
            )
        )
        raise


# ---- M2 full pipeline (Stages 1-7) ------------------------------------


@dataclass
class FullJobConfig:
    """Configuration for `run_full_pipeline` (Stages 1-7)."""

    media_paths: list[Path]
    brief: str
    target_duration_seconds: int
    audio_path: Path
    mode: Literal["standard"] = "standard"  # music_video → M4
    project_id: str | None = None
    overrides: PreFilterOverrides | None = None


@dataclass
class FullJobResult:
    project_id: str
    snapshot_id: str
    render_path: str
    output_bytes: int
    render_duration_ms: int
    media_count: int
    correlation_id: str
    cost_summary_path: str
    quota_snapshot: dict[str, Any] = field(default_factory=dict)
    arc_judgment: ArcJudgment | None = None


# Tier-lookup mirrors ADR-0009; consumed by `telemetry.aggregate_summary`.
_TIER_BY_OPERATION = {
    "embed_image": "embedding",
    "embed_text": "embedding",
    "caption_image": "S",
    "caption_video_scene": "S",
    "score_image": "S",
    "extract_metadata_image": "M",
    "extract_metadata_video_scene": "M",
    "parse_user_brief": "M",
    "recommend_effort_level": "M",
    "explain_cost": "M",
    "explain_upgrade_path": "M",
    "orchestrator_reasoning": "M",
    "judge_narrative_arc": "L",
}


async def run_full_pipeline(
    config: FullJobConfig,
    *,
    router: LLMRouter | None = None,
    pool: WorkerPool | None = None,
) -> FullJobResult:
    """Run Stages 1-7 end-to-end → rendered MP4 + JobCostSummary.

    Sequences: ingest → bulk ops → metadata → pre-filter → narrative judge
    → plan compile → render. Pre-job dual-cap quota check; per-stage
    JobLifecycleEvent + RenderEvent telemetry; final aggregation persisted
    as `snapshots/{snapshot_id}/cost_summary.json`.
    """
    # Reuse the M1 runner for Stages 1-5; it already handles the quota
    # check + lifecycle telemetry.
    headless_config = HeadlessJobConfig(
        media_paths=config.media_paths,
        brief=config.brief,
        target_duration_seconds=config.target_duration_seconds,
        mode="standard",
        music_spec=None,
        project_id=config.project_id,
        overrides=config.overrides,
    )
    pool = pool or WorkerPool()
    headless = await run_headless_pipeline(headless_config, router=router, pool=pool)

    # Stage 6 — compile plan with the user's audio.
    audio_probe = ff.probe_audio(config.audio_path)
    music = StandardMusicSpec(
        audio_path=str(config.audio_path),
        audio_duration_ms=audio_probe.duration_ms,
    )
    # Reuse the media records the headless runner already produced
    # (idempotent ingest means re-running would be safe, but skipping the
    # work is faster).
    plan = await stage6_plan.compile_plan(
        arc_judgment=headless.arc_judgment,
        ingest_records=headless.media,
        project_id=headless.project_id,
        target_duration_seconds=config.target_duration_seconds,
        mode="standard",
        audio=music,
    )

    # Stage 7 — render.
    render_result = await stage7_render.render_plan(
        plan, correlation_id=headless.correlation_id, pool=pool
    )

    # Aggregate JobCostSummary across the entire correlation_id family
    # and persist alongside render.mp4.
    summary = telemetry.aggregate_summary(
        project_id=headless.project_id,
        snapshot_id=plan.snapshot_id,
        correlation_ids=[headless.correlation_id],
        tier_lookup=_TIER_BY_OPERATION,
    )
    summary_path = stage6_plan.snapshot_dir(headless.project_id, plan.snapshot_id) / "cost_summary.json"
    summary_path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")

    return FullJobResult(
        project_id=headless.project_id,
        snapshot_id=plan.snapshot_id,
        render_path=render_result.render_path,
        output_bytes=render_result.output_bytes,
        render_duration_ms=render_result.duration_ms,
        media_count=headless.media_count,
        correlation_id=headless.correlation_id,
        cost_summary_path=str(summary_path),
        quota_snapshot=headless.quota_snapshot,
        arc_judgment=headless.arc_judgment,
    )


# ---- Helpers ----------------------------------------------------------


def _estimate_cost_per_provider(media_count: int) -> dict[str, float]:
    """Pessimistic cost estimate per provider, used for the pre-job quota check.

    Mirrors the ADR-0009 per-job envelope ($7-$22 at ~1000 photos):
      Anthropic: ~$0.008 per asset (Tier-M metadata) + ~$1 fixed for Tier-L judge.
      Google: ~$0.0015 per asset (Tier-S caption + score + embedding).
    """
    n = max(media_count, 1)
    return {
        "anthropic": 0.008 * n + 1.0,
        "google": 0.0015 * n,
    }


def _default_router_from_settings() -> LLMRouter:
    """Build a router from settings (encrypted) or env vars (test fallback)."""
    # Settings reads are async, so we surface an informative error if the
    # caller forgets to plumb in their own router. The headless test-suite
    # path always passes its own router; production callers go through the
    # API layer which awaits settings_store.get_value first.
    raise RuntimeError(
        "default_router_from_settings is a placeholder — pass `router=` "
        "explicitly or use api.jobs.build_router_from_settings()"
    )


async def build_router_from_settings() -> LLMRouter:
    """Async factory the API layer calls to assemble the router.

    Reads the Fernet-decrypted API keys from settings; falls back to env
    vars when the wizard hasn't run yet (so the smoke-test harness can
    skip the wizard).
    """
    anthropic_key = await settings_store.get_value(
        settings_store.KEY_ANTHROPIC_API_KEY
    ) or os.environ.get("ANTHROPIC_API_KEY")
    google_key = await settings_store.get_value(
        settings_store.KEY_GOOGLE_API_KEY
    ) or os.environ.get("GOOGLE_API_KEY")
    if not anthropic_key or not google_key:
        raise RuntimeError(
            "Anthropic and Google API keys must be configured (run the "
            "first-time-setup wizard or set ANTHROPIC_API_KEY / "
            "GOOGLE_API_KEY in the environment)"
        )
    return LLMRouter(
        clients={
            "anthropic": AnthropicLLMClient(api_key=anthropic_key),
            "google": GoogleLLMClient(api_key=google_key),
        },
    )
