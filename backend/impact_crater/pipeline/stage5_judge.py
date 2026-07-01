"""Stage 5 — narrative-arc judgment per ADR-0011 + N-001.

Single Tier-L Opus call. Inputs: the `CandidateSet` from Stage 4 + the
user's brief + target_duration + (optional) music spec + mode +
(M4) optional `MusicAnalysis` for music-video mode.

Output: `ArcJudgment` — the structured plan the downstream stages execute
against. The router caches the call by full input signature, so re-running
an identical judgment is free.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from impact_crater.llm_clients.base import ArcJudgment, MusicSpec
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media.music import MusicAnalysis
from impact_crater.pipeline.stage4_prefilter import CandidateSet

log = logging.getLogger(__name__)


async def judge_narrative_arc(
    *,
    router: LLMRouter,
    candidate_set: CandidateSet,
    brief: str,
    target_duration_seconds: int,
    mode: Literal["standard", "music_video"] = "standard",
    music_spec: MusicSpec | None = None,
    music_analysis: MusicAnalysis | None = None,
    coverage_plan: Any = None,
    chronological: bool = False,
) -> ArcJudgment:
    """Run the Stage 5 judgment over `candidate_set`.

    `music_analysis` (M4 music-video mode) is forwarded to the prompt
    template via `extra_prompt_vars` so the Opus call sees the section
    structure + beats and can populate `ArcJudgment.section_mapping`.

    `coverage_plan` (S-2.10.5) names the brief's destinations so the prompt's
    HARD-coverage block asks the judge to represent each; `chronological` gates
    the strict-forward-after-opener guidance. Both flow into the judge cache key
    via extra_prompt_vars, so a coverage change correctly re-runs the judge.
    """
    extra: dict[str, Any] = {}
    if music_analysis is not None:
        extra["music_analysis"] = music_analysis
    if coverage_plan is not None and getattr(coverage_plan, "named_destinations", None):
        extra["named_destinations"] = coverage_plan.to_prompt_vars()
    if chronological:
        extra["chronological"] = True
    extra_arg = extra or None

    log.info(
        "stage5_judge_start mode=%s candidate_count=%d target_duration_s=%d "
        "music_video=%s",
        mode,
        len(candidate_set.items),
        target_duration_seconds,
        music_analysis is not None,
    )
    started = time.monotonic()
    try:
        result = await router.judge_narrative_arc(
            candidates=candidate_set.items,
            brief=brief,
            target_duration=target_duration_seconds,
            mode=mode,
            music_spec=music_spec,
            extra_prompt_vars=extra_arg,
        )
    except Exception as exc:
        log.error(
            "stage5_judge_failed mode=%s candidate_count=%d elapsed_s=%.1f error=%r",
            mode,
            len(candidate_set.items),
            time.monotonic() - started,
            str(exc)[:300],
        )
        raise

    log.info(
        "stage5_judge_done mode=%s selected=%d confidence=%.2f elapsed_s=%.1f",
        mode,
        len(result.selected_items),
        result.confidence,
        time.monotonic() - started,
    )
    return result
