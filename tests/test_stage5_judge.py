"""Stage 5 judge tests — thin wrapper around router.judge_narrative_arc."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from impact_crater.llm_clients.base import (
    ArcJudgment,
    CandidateRef,
    MusicSpec,
    SelectedItem,
)
from impact_crater.pipeline import stage5_judge
from impact_crater.pipeline.stage4_prefilter import CandidateSet


@pytest.fixture
def candidate_set() -> CandidateSet:
    return CandidateSet(
        items=[
            CandidateRef(content_hash="h1", caption="cap 1", quality_score=0.9, narrative_relevance=0.8),
            CandidateRef(content_hash="h2", caption="cap 2", quality_score=0.7, narrative_relevance=0.6),
        ],
        cluster_metadata={"input_count": 2},
        filter_log=[],
        target_size=2,
        floor=2,
        ceiling=2,
    )


async def test_judge_passes_through_to_router(candidate_set: CandidateSet) -> None:
    arc = ArcJudgment(
        selected_items=[
            SelectedItem(
                candidate_ref="h1",
                placement_position=0,
                intended_duration_ms=2500,
                role="opener",
            )
        ],
        arc_reasoning="strong opener",
        confidence=0.82,
    )
    router = AsyncMock()
    router.judge_narrative_arc = AsyncMock(return_value=arc)

    result = await stage5_judge.judge_narrative_arc(
        router=router,
        candidate_set=candidate_set,
        brief="family hike",
        target_duration_seconds=30,
    )
    assert result is arc
    call = router.judge_narrative_arc.await_args
    assert call.kwargs["brief"] == "family hike"
    assert call.kwargs["target_duration"] == 30
    assert call.kwargs["mode"] == "standard"
    assert call.kwargs["music_spec"] is None
    assert len(call.kwargs["candidates"]) == 2


async def test_judge_propagates_music_spec(candidate_set: CandidateSet) -> None:
    arc = ArcJudgment(selected_items=[], arc_reasoning="...", confidence=0.5)
    router = AsyncMock()
    router.judge_narrative_arc = AsyncMock(return_value=arc)
    music = MusicSpec(duration_ms=180_000, bpm=128.0, section_to_media_nl="verse: hike, chorus: summit")

    await stage5_judge.judge_narrative_arc(
        router=router,
        candidate_set=candidate_set,
        brief="trek",
        target_duration_seconds=60,
        mode="music_video",
        music_spec=music,
    )
    call = router.judge_narrative_arc.await_args
    assert call.kwargs["mode"] == "music_video"
    assert call.kwargs["music_spec"].bpm == 128.0
