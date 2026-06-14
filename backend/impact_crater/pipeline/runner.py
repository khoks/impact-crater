"""Headless pipeline runner — sequences Stages 1-5 (M1) and Stages 1-7 (M2).

`run_headless_pipeline` (M1) returns the structured ArcJudgment.
`run_full_pipeline` (M2) takes the same inputs plus an `audio_path` and
runs through Stages 6-7 to produce a rendered MP4 + JobCostSummary.

Both runners accept an optional `progress` ProgressReporter (M3) that
receives stage-boundary callbacks. The router separately accepts a
ProgressSink for per-call cost telemetry; the API layer wires both to
the JobRegistry.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from impact_crater import quota, telemetry
from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import ArcJudgment, MusicSpec
from impact_crater.llm_clients.google_client import GoogleLLMClient
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media import ffmpeg as ff
from impact_crater.media.music import (
    LibrosaMusicAnalyzer,
    MusicAnalysis,
    MusicAnalyzer,
    generate_cut_grid,
)
from impact_crater.pipeline import (
    cast_builder,
    diagnostics,
    stage1_ingest,
    stage2_bulk_ops,
    stage3_metadata,
    stage4_prefilter,
    stage5_judge,
    stage6_plan,
    stage6_second_guess,
    stage7_render,
)
from impact_crater.pipeline.stage4_prefilter import CandidateSet, PreFilterOverrides
from impact_crater.pipeline.stage6_plan import StandardMusicSpec
from impact_crater.storage import settings as settings_store
from impact_crater.workers import WorkerPool

log = logging.getLogger(__name__)


# ---- Public types ------------------------------------------------------


@runtime_checkable
class ProgressReporter(Protocol):
    """Optional sink for stage-boundary callbacks. The M3 API layer
    binds this to the JobRegistry; tests can pass their own."""

    async def stage_started(self, stage: str, *, detail: str = "") -> None: ...

    async def stage_completed(self, stage: str, *, detail: str = "") -> None: ...

    async def stage_failed(self, stage: str, *, detail: str = "") -> None: ...

    async def phase_diagnostics(self, phase_doc: dict[str, Any]) -> None: ...


class _NoopReporter:
    """Default reporter — silence."""

    async def stage_started(self, stage: str, *, detail: str = "") -> None:
        return None

    async def stage_completed(self, stage: str, *, detail: str = "") -> None:
        return None

    async def stage_failed(self, stage: str, *, detail: str = "") -> None:
        return None

    async def phase_diagnostics(self, phase_doc: dict[str, Any]) -> None:
        return None


@dataclass
class HeadlessJobResult:
    project_id: str
    arc_judgment: ArcJudgment
    candidate_set: CandidateSet
    media_count: int
    correlation_id: str
    media: list[Any] = field(default_factory=list)  # MediaRecord; typed Any to avoid forward-ref dance
    quota_snapshot: dict[str, Any] = field(default_factory=dict)
    cast: Any = None  # A-018 CastInventory (or None when disabled)


@dataclass
class HeadlessJobConfig:
    media_paths: list[Path]
    brief: str
    target_duration_seconds: int
    mode: Literal["standard", "music_video"] = "standard"
    music_spec: MusicSpec | None = None
    project_id: str | None = None  # auto-generated if not supplied
    overrides: PreFilterOverrides | None = None
    # A-018 auto trip cast. Enabled by default; backend resolved from
    # settings (gemini cloud default / insightface optional local).
    enable_cast: bool = True
    cast_backend: str | None = None


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
    progress: ProgressReporter | None = None,
    music_analysis: MusicAnalysis | None = None,
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
    LLMCallEvent emission happens inside the LLMRouter (M3 wired); the
    runner additionally emits stage-boundary events via `progress` if
    supplied — the M3 API layer wires this to the JobRegistry.
    """
    project_id = config.project_id or f"headless-{uuid.uuid4().hex[:12]}"
    correlation_id = uuid.uuid4().hex
    pool = pool or WorkerPool()
    router = router or _default_router_from_settings()
    reporter: ProgressReporter = progress or _NoopReporter()

    # Stamp telemetry context so LLMCallEvent rows carry the correlation_id.
    router.set_telemetry_context(
        project_id=project_id,
        snapshot_id=None,
        correlation_id=correlation_id,
    )

    log.info(
        "headless_pipeline_start project_id=%s correlation_id=%s "
        "media_count=%d target_duration_s=%d mode=%s",
        project_id,
        correlation_id,
        len(config.media_paths),
        config.target_duration_seconds,
        config.mode,
    )

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
        log.warning(
            "quota_denied project_id=%s correlation_id=%s reason=%s "
            "estimate_usd=%.4f today_total_spent_usd=%.4f cap_total_usd=%s",
            project_id,
            correlation_id,
            quota_check.reason,
            sum(estimated.values()),
            quota_check.today_total_spent_usd,
            quota_check.cap_total_usd,
        )
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
        await reporter.stage_started("stage_1_ingest")
        media = await stage1_ingest.ingest_media(
            project_id, config.media_paths, pool=pool
        )
        await reporter.stage_completed(
            "stage_1_ingest", detail=f"{len(media)} media records"
        )

        # Stage 2 + 3 — sequentially (3 needs the full media list); inside
        # each stage we parallelize per-asset.
        await reporter.stage_started("stage_2_bulk_ops")
        stage2 = await stage2_bulk_ops.run_stage2(
            router=router, media=media, brief=config.brief, pool=pool
        )
        await reporter.stage_completed(
            "stage_2_bulk_ops", detail=f"{len(stage2)} assets"
        )

        await reporter.stage_started("stage_3_metadata")
        stage3 = await stage3_metadata.run_stage3(
            router=router, media=media, brief=config.brief, pool=pool
        )
        await reporter.stage_completed(
            "stage_3_metadata", detail=f"{len(stage3)} extracted"
        )

        # Stage 3.5 — auto trip cast (A-018). Fail-soft: any error or a
        # missing face model yields an empty inventory and the pipeline
        # proceeds unchanged.
        cast_inventory = None
        if config.enable_cast:
            try:
                cast_inventory = await cast_builder.build_cast(
                    media=media,
                    stage3=stage3,
                    router=router,
                    backend=config.cast_backend,
                )
                _persist_cast(project_id, cast_inventory)
                await _emit_phase_diag(reporter, diagnostics.phase_cast, cast_inventory)
            except Exception as exc:
                log.warning(
                    "cast_analysis_failed project_id=%s error=%r — proceeding without cast",
                    project_id,
                    str(exc)[:200],
                )
                cast_inventory = None

        # Stage 4
        await reporter.stage_started("stage_4_prefilter")
        candidate_set = stage4_prefilter.prefilter(
            media=media,
            stage2=stage2,
            stage3=stage3,
            target_duration_seconds=config.target_duration_seconds,
            overrides=config.overrides,
            cast=cast_inventory,
        )
        await reporter.stage_completed(
            "stage_4_prefilter",
            detail=f"{len(candidate_set.items)}/{candidate_set.cluster_metadata.get('input_count', '?')} candidates",
        )
        await _emit_phase_diag(reporter, diagnostics.phase_stage4, candidate_set)

        # Stage 5
        await reporter.stage_started("stage_5_judge")
        arc_judgment = await stage5_judge.judge_narrative_arc(
            router=router,
            candidate_set=candidate_set,
            brief=config.brief,
            target_duration_seconds=config.target_duration_seconds,
            mode=config.mode,
            music_spec=config.music_spec,
            music_analysis=music_analysis,
        )
        await reporter.stage_completed(
            "stage_5_judge",
            detail=f"confidence={arc_judgment.confidence:.2f}",
        )
        await _emit_phase_diag(reporter, diagnostics.phase_stage5, arc_judgment)

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
            cast=cast_inventory,
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
    mode: Literal["standard", "music_video"] = "standard"
    section_to_media_nl: str | None = None  # M4: optional NL spec
    project_id: str | None = None
    overrides: PreFilterOverrides | None = None
    enable_cast: bool = True
    cast_backend: str | None = None


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
    progress: ProgressReporter | None = None,
    music_analyzer: MusicAnalyzer | None = None,
) -> FullJobResult:
    """Run Stages 1-7 end-to-end → rendered MP4 + JobCostSummary.

    Sequences: ingest → bulk ops → metadata → pre-filter → narrative judge
    → plan compile → render. Pre-job dual-cap quota check; per-stage
    JobLifecycleEvent + RenderEvent telemetry; final aggregation persisted
    as `snapshots/{snapshot_id}/cost_summary.json`.
    """
    pool = pool or WorkerPool()
    reporter: ProgressReporter = progress or _NoopReporter()

    # When mode=music_video, run MusicAnalyzer up-front so Stage 5 sees
    # the analysis + section-to-media NL spec. Sync mode skips this.
    music_analysis = None
    cut_grid = None
    if config.mode == "music_video":
        await reporter.stage_started("stage_0_music_analysis", detail="(M4)")
        analyzer = music_analyzer or LibrosaMusicAnalyzer()
        music_analysis = await analyzer.analyze(config.audio_path)
        cut_grid = generate_cut_grid(music_analysis)
        await reporter.stage_completed(
            "stage_0_music_analysis",
            detail=f"bpm={music_analysis.bpm:.0f}, {len(cut_grid.cut_points_ms)} cuts",
        )

    # Reuse the M1 runner for Stages 1-5; it already handles the quota
    # check + lifecycle telemetry. Pass the MusicSpec for music_video mode
    # so Stage 5's prompt sees the section structure.
    music_spec_for_judge = None
    if config.mode == "music_video" and music_analysis is not None:
        music_spec_for_judge = MusicSpec(
            duration_ms=music_analysis.duration_ms,
            bpm=music_analysis.bpm,
            section_to_media_nl=config.section_to_media_nl,
        )

    headless_config = HeadlessJobConfig(
        media_paths=config.media_paths,
        brief=config.brief,
        target_duration_seconds=config.target_duration_seconds,
        mode=config.mode,
        music_spec=music_spec_for_judge,
        project_id=config.project_id,
        overrides=config.overrides,
        enable_cast=config.enable_cast,
        cast_backend=config.cast_backend,
    )
    headless = await run_headless_pipeline(
        headless_config,
        router=router,
        pool=pool,
        progress=reporter,
        music_analysis=music_analysis,
    )

    # Stage 6 — compile plan with the user's audio.
    await reporter.stage_started("stage_6_plan")
    audio_probe = ff.probe_audio(config.audio_path)
    music = StandardMusicSpec(
        audio_path=str(config.audio_path),
        audio_duration_ms=audio_probe.duration_ms,
        music_analysis=music_analysis,
        cut_grid=cut_grid,
        section_to_media_nl=config.section_to_media_nl,
    )
    # Reuse the media records the headless runner already produced
    # (idempotent ingest means re-running would be safe, but skipping the
    # work is faster).
    # The candidate_refs list mirrors the order Stage 5's prompt rendered
    # the candidates in. compile_plan uses it to recover from Opus
    # occasionally emitting a `[index]` integer instead of the ref hash.
    candidate_refs = [
        c.content_hash + (f"#{c.scene_index}" if c.scene_index is not None else "")
        for c in headless.candidate_set.items
    ]
    plan = await stage6_plan.compile_plan(
        arc_judgment=headless.arc_judgment,
        ingest_records=headless.media,
        project_id=headless.project_id,
        target_duration_seconds=config.target_duration_seconds,
        mode=config.mode,
        audio=music,
        candidate_refs=candidate_refs,
    )

    # M6 — orchestrator second-guess. Auto-applies high-confidence
    # overrides; everything else is logged on the snapshot for the
    # v1 user-reconfirm UI.
    # Update telemetry context now that we have a snapshot_id, so any
    # remaining LLM calls (second-guess, refine) tag their LLMCallEvent
    # rows with the snapshot they belong to.
    sg_router = router or _default_router_from_settings()
    sg_router.set_telemetry_context(
        project_id=headless.project_id,
        snapshot_id=plan.snapshot_id,
        correlation_id=headless.correlation_id,
    )
    log.info(
        "stage6_plan_compiled project_id=%s snapshot_id=%s correlation_id=%s "
        "clip_count=%d",
        headless.project_id,
        plan.snapshot_id,
        headless.correlation_id,
        len(plan.clips),
    )

    try:
        sg_result = await stage6_second_guess.second_guess(
            router=sg_router,
            arc_judgment=headless.arc_judgment,
            plan=plan,
            music_spec=music_spec_for_judge,
            brief=config.brief,
        )
    except Exception as exc:
        log.warning(
            "second_guess_failed project_id=%s snapshot_id=%s correlation_id=%s "
            "error=%r — proceeding with plan as-is",
            headless.project_id,
            plan.snapshot_id,
            headless.correlation_id,
            str(exc)[:200],
        )
        sg_result = None

    if sg_result is not None and sg_result.overrides:
        # Persist the full second-guess result for the v1 UI.
        sg_path = stage6_plan.snapshot_dir(headless.project_id, plan.snapshot_id) / "second_guess.json"
        sg_path.write_text(sg_result.model_dump_json(indent=2), encoding="utf-8")
        if sg_result.overall_confidence > 0.85:
            plan = stage6_plan.apply_overrides(plan, sg_result.overrides)
            log.info(
                "second_guess_overrides_applied project_id=%s snapshot_id=%s "
                "correlation_id=%s overrides=%d confidence=%.2f",
                headless.project_id,
                plan.snapshot_id,
                headless.correlation_id,
                len(sg_result.overrides),
                sg_result.overall_confidence,
            )

    # A-018 coverage report: are all group members represented in the cut?
    if headless.cast is not None:
        _write_coverage(headless.project_id, plan.snapshot_id, headless.cast, plan)

    # A-023 per-phase diagnostics for the in-app feedback loop.
    _write_diagnostics(
        headless.project_id,
        plan.snapshot_id,
        candidate_set=headless.candidate_set,
        arc_judgment=headless.arc_judgment,
        plan=plan,
        cast=headless.cast,
        media=headless.media,
    )
    await _emit_phase_diag(reporter, diagnostics.phase_stage6, plan)

    await reporter.stage_completed(
        "stage_6_plan", detail=f"{len(plan.clips)} clips"
    )

    # Stage 7 — render.
    await reporter.stage_started("stage_7_render")
    render_result = await stage7_render.render_plan(
        plan, correlation_id=headless.correlation_id, pool=pool
    )
    await reporter.stage_completed(
        "stage_7_render", detail=f"{render_result.output_bytes} bytes"
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

    log.info(
        "full_pipeline_done project_id=%s snapshot_id=%s correlation_id=%s "
        "media_count=%d clip_count=%d output_bytes=%d render_duration_ms=%d "
        "total_cost_usd=%.4f cache_hits=%d cache_misses=%d",
        headless.project_id,
        plan.snapshot_id,
        headless.correlation_id,
        headless.media_count,
        len(plan.clips),
        render_result.output_bytes,
        render_result.duration_ms,
        summary.total_cost_usd,
        summary.cache_hits,
        summary.cache_misses,
    )

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


def _persist_cast(project_id: str, cast: Any) -> None:
    """Write the cast inventory to `{project}/cast.json` (A-018) — the
    reusable 'standard set of unique faces' the user asked for."""
    from dataclasses import asdict

    from impact_crater import paths

    try:
        proj_dir = paths.projects_dir() / project_id
        proj_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "persons": [asdict(p) for p in cast.persons],
            "group_persons_by_hash": cast.group_persons_by_hash,
        }
        (proj_dir / "cast.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("cast_persist_failed project_id=%s error=%r", project_id, str(exc)[:200])


def _write_coverage(project_id: str, snapshot_id: str, cast: Any, plan: Any) -> None:
    """Compute + persist the group-coverage report for this render (A-018):
    which group members are present in / missing from the selected clips."""
    from dataclasses import asdict

    from impact_crater.media.cast import compute_coverage

    try:
        selected = {c.candidate_ref.split("#")[0] for c in plan.clips}
        report = compute_coverage(cast, selected)
        snap_dir = stage6_plan.snapshot_dir(project_id, snapshot_id)
        (snap_dir / "coverage.json").write_text(
            json.dumps(asdict(report), indent=2), encoding="utf-8"
        )
        if report.missing_person_ids:
            log.info(
                "coverage_gap project_id=%s snapshot_id=%s group_size=%d missing=%s",
                project_id,
                snapshot_id,
                report.group_size,
                report.missing_person_ids,
            )
    except Exception as exc:
        log.warning("coverage_failed project_id=%s error=%r", project_id, str(exc)[:200])


async def _emit_phase_diag(reporter: Any, builder: Any, *args: Any) -> None:
    """Build one phase's diagnostics and stream it to the in-progress UI.
    Best-effort: a diagnostics failure must never break the job."""
    try:
        await reporter.phase_diagnostics(builder(*args))
    except Exception as exc:
        log.debug("phase_diagnostics emit failed: %s", str(exc)[:160])


def _write_diagnostics(
    project_id: str,
    snapshot_id: str,
    *,
    candidate_set: Any,
    arc_judgment: Any,
    plan: Any,
    cast: Any,
    media: list[Any],
) -> None:
    """Persist the per-phase diagnostics document (A-023) next to the plan."""
    from impact_crater.pipeline import diagnostics as diag

    try:
        doc = diag.build_diagnostics(
            project_id=project_id,
            snapshot_id=snapshot_id,
            candidate_set=candidate_set,
            arc_judgment=arc_judgment,
            plan=plan,
            cast=cast,
            media=media,
        )
        snap_dir = stage6_plan.snapshot_dir(project_id, snapshot_id)
        (snap_dir / "diagnostics.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("diagnostics_failed project_id=%s error=%r", project_id, str(exc)[:200])


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
