"""Tests for the Stage 9 N-009 agentic refinement loop."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from impact_crater.llm_clients.base import ArcJudgment, CandidateRef, SelectedItem
from impact_crater.pipeline.stage4_prefilter import CandidateSet
from impact_crater.pipeline.stage9_refine import refine, RefinementPlan


def _arc(reasoning: str = "warm to cool") -> ArcJudgment:
    return ArcJudgment(
        selected_items=[
            SelectedItem(candidate_ref="a", placement_position=0, intended_duration_ms=2000, role="opener")
        ],
        arc_reasoning=reasoning,
        confidence=0.7,
    )


def _candidate_set() -> CandidateSet:
    return CandidateSet(
        items=[CandidateRef(content_hash="a", quality_score=0.9, narrative_relevance=0.8)],
        cluster_metadata={"input_count": 1},
        filter_log=[],
        target_size=1,
        floor=1,
        ceiling=1,
    )


# ---- Tests -------------------------------------------------------------


async def test_refine_partial_fix_runs_stage_5_with_addendum() -> None:
    router = AsyncMock()
    # First call: thinking step picks partial_fix_via_plan_edit.
    # Second call: parse_user_brief is reused by stage5 (no — Stage 5
    # uses judge_narrative_arc which is router.judge_narrative_arc).
    router.parse_user_brief = AsyncMock(
        return_value={
            "strategy": "partial_fix_via_plan_edit",
            "rationale": "the candidate set has enough landscape items",
            "brief_addendum": "Add 30% more landscape shots; reduce face shots.",
        }
    )
    new_arc = _arc(reasoning="more landscape")
    router.judge_narrative_arc = AsyncMock(return_value=new_arc)

    result = await refine(
        router=router,
        prior_arc=_arc(),
        candidate_set=_candidate_set(),
        refinement_message="more landscape",
        brief="hike",
        target_duration_seconds=10,
    )
    assert result.plan.strategy == "partial_fix_via_plan_edit"
    assert result.arc_judgment is new_arc
    assert result.turns_used == 2

    # The new judge call should have received the addendum-extended brief.
    call = router.judge_narrative_arc.await_args
    assert "Refinement addendum" in call.kwargs["brief"]
    assert "30% more landscape" in call.kwargs["brief"]


async def test_refine_explain_when_thinking_picks_it() -> None:
    router = AsyncMock()
    router.parse_user_brief = AsyncMock(
        return_value={
            "strategy": "explain_why_not_possible",
            "rationale": "no landscape in candidate set",
            "explanation": "The pre-filter dropped all landscape shots because their quality scores were too low.",
        }
    )
    result = await refine(
        router=router,
        prior_arc=_arc(),
        candidate_set=_candidate_set(),
        refinement_message="more landscape",
        brief="hike",
        target_duration_seconds=10,
    )
    assert result.plan.strategy == "explain_why_not_possible"
    assert result.plan.explanation is not None
    assert result.arc_judgment is None
    assert router.judge_narrative_arc.await_count == 0


async def test_refine_v1_strategies_fall_back_to_explain() -> None:
    """M6 doesn't execute full_reprocess; falls back gracefully."""
    router = AsyncMock()
    router.parse_user_brief = AsyncMock(
        return_value={
            "strategy": "full_reprocess",
            "rationale": "needs a fresh look",
        }
    )
    result = await refine(
        router=router,
        prior_arc=_arc(),
        candidate_set=_candidate_set(),
        refinement_message="x",
        brief="b",
        target_duration_seconds=10,
    )
    assert result.plan.strategy == "explain_why_not_possible"
    assert "v1" in (result.plan.explanation or "")


async def test_refine_empty_message_raises() -> None:
    router = AsyncMock()
    with pytest.raises(ValueError, match="empty"):
        await refine(
            router=router,
            prior_arc=_arc(),
            candidate_set=_candidate_set(),
            refinement_message="   ",
            brief="b",
            target_duration_seconds=10,
        )
    # Thinking call never made.
    router.parse_user_brief.assert_not_called()


async def test_refine_returns_typed_plan() -> None:
    router = AsyncMock()
    router.parse_user_brief = AsyncMock(
        return_value={
            "strategy": "explain_why_not_possible",
            "rationale": "x",
            "explanation": "y",
        }
    )
    result = await refine(
        router=router,
        prior_arc=_arc(),
        candidate_set=_candidate_set(),
        refinement_message="x",
        brief="b",
        target_duration_seconds=10,
    )
    assert isinstance(result.plan, RefinementPlan)
