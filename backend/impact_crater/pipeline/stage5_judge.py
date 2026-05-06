"""Stage 5 — narrative-arc judgment per ADR-0011 + N-001.

Single Tier-L Opus call. Inputs: the `CandidateSet` from Stage 4 + the
user's brief + target_duration + (optional) music spec + mode +
(M4) optional `MusicAnalysis` for music-video mode.

Output: `ArcJudgment` — the structured plan the downstream stages execute
against. The router caches the call by full input signature, so re-running
an identical judgment is free.
"""

from __future__ import annotations

from typing import Any, Literal

from impact_crater.llm_clients.base import ArcJudgment, MusicSpec
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media.music import MusicAnalysis
from impact_crater.pipeline.stage4_prefilter import CandidateSet


async def judge_narrative_arc(
    *,
    router: LLMRouter,
    candidate_set: CandidateSet,
    brief: str,
    target_duration_seconds: int,
    mode: Literal["standard", "music_video"] = "standard",
    music_spec: MusicSpec | None = None,
    music_analysis: MusicAnalysis | None = None,
) -> ArcJudgment:
    """Run the Stage 5 judgment over `candidate_set`.

    `music_analysis` (M4 music-video mode) is forwarded to the prompt
    template via `extra_prompt_vars` so the Opus call sees the section
    structure + beats and can populate `ArcJudgment.section_mapping`.
    """
    extra: dict[str, Any] | None = None
    if music_analysis is not None:
        extra = {"music_analysis": music_analysis}
    return await router.judge_narrative_arc(
        candidates=candidate_set.items,
        brief=brief,
        target_duration=target_duration_seconds,
        mode=mode,
        music_spec=music_spec,
        extra_prompt_vars=extra,
    )
