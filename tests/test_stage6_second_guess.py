"""Tests for the Stage 6 orchestrator second-guess."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.pipeline import stage6_second_guess
from impact_crater.pipeline.stage6_plan import RenderClip, RenderPlan, apply_overrides
from impact_crater.pipeline.stage6_second_guess import (
    Override,
    SecondGuessResult,
    second_guess,
)


def _arc(items: list[SelectedItem]) -> ArcJudgment:
    return ArcJudgment(selected_items=items, arc_reasoning="t", confidence=0.8)


def _plan(clips: list[RenderClip]) -> RenderPlan:
    return RenderPlan(
        project_id="p",
        snapshot_id="snap-1",
        target_duration_ms=8000,
        clips=clips,
        arc_reasoning="t",
        arc_confidence=0.8,
    )


def _clip(ref: str, idx: int) -> RenderClip:
    return RenderClip(
        candidate_ref=ref,
        kind="photo",
        source_path=f"/tmp/{ref}.jpg",
        intended_duration_ms=2000,
        aspect_ratio_action="as_is",
    )


# ---- Schema parse tests -----------------------------------------------


async def test_second_guess_returns_typed_result_when_router_returns_valid_json() -> None:
    router = AsyncMock()
    router.parse_user_brief = AsyncMock(
        return_value={
            "overrides": [
                {
                    "type": "drop_item",
                    "target_position": 2,
                    "proposed_change": {},
                    "why": "near-duplicate of position 1",
                }
            ],
            "overall_confidence": 0.75,
            "rationale": "one near-duplicate worth dropping",
        }
    )
    arc = _arc(
        [
            SelectedItem(candidate_ref="a", placement_position=0, intended_duration_ms=2000, role="opener"),
            SelectedItem(candidate_ref="b", placement_position=1, intended_duration_ms=2000, role="peak"),
        ]
    )
    plan = _plan([_clip("a", 0), _clip("b", 1)])
    result = await second_guess(
        router=router, arc_judgment=arc, plan=plan, music_spec=None, brief="hike"
    )
    assert isinstance(result, SecondGuessResult)
    assert len(result.overrides) == 1
    assert result.overrides[0].type == "drop_item"
    assert result.overall_confidence == 0.75


async def test_second_guess_empty_overrides_when_judge_was_solid() -> None:
    router = AsyncMock()
    router.parse_user_brief = AsyncMock(
        return_value={
            "overrides": [],
            "overall_confidence": 0.4,
            "rationale": "plan looks reasonable",
        }
    )
    arc = _arc([SelectedItem(candidate_ref="a", placement_position=0, intended_duration_ms=2000, role="opener")])
    plan = _plan([_clip("a", 0)])
    result = await second_guess(
        router=router, arc_judgment=arc, plan=plan, music_spec=None, brief="x"
    )
    assert result.overrides == []
    assert result.overall_confidence == 0.4


# ---- apply_overrides tests --------------------------------------------


def test_apply_overrides_drop_item_removes_clip() -> None:
    plan = _plan([_clip("a", 0), _clip("b", 1), _clip("c", 2)])
    overrides = [Override(type="drop_item", target_position=1, why="dup")]
    new_plan = apply_overrides(plan, overrides)
    assert [c.candidate_ref for c in new_plan.clips] == ["a", "c"]
    # Original is untouched.
    assert [c.candidate_ref for c in plan.clips] == ["a", "b", "c"]


def test_apply_overrides_reorder_moves_clip() -> None:
    plan = _plan([_clip("a", 0), _clip("b", 1), _clip("c", 2)])
    overrides = [
        Override(
            type="reorder",
            target_position=2,
            proposed_change={"new_position": 0},
            why="closer too early",
        )
    ]
    new_plan = apply_overrides(plan, overrides)
    assert [c.candidate_ref for c in new_plan.clips] == ["c", "a", "b"]


def test_apply_overrides_multiple_drops_descending() -> None:
    plan = _plan([_clip(c, i) for i, c in enumerate(["a", "b", "c", "d"])])
    overrides = [
        Override(type="drop_item", target_position=1, why="dup"),
        Override(type="drop_item", target_position=3, why="off-topic"),
    ]
    new_plan = apply_overrides(plan, overrides)
    assert [c.candidate_ref for c in new_plan.clips] == ["a", "c"]


def test_apply_overrides_empty_returns_same_plan() -> None:
    plan = _plan([_clip("a", 0)])
    new_plan = apply_overrides(plan, [])
    assert [c.candidate_ref for c in new_plan.clips] == ["a"]


def test_apply_overrides_unsupported_type_logged_and_skipped() -> None:
    plan = _plan([_clip("a", 0), _clip("b", 1)])
    overrides = [
        # `swap` is unsupported at MVP; drop_item is.
        Override(type="swap", target_position=0, why="x"),
        Override(type="drop_item", target_position=0, why="dup"),
    ]
    new_plan = apply_overrides(plan, overrides)
    # drop_item still applies.
    assert [c.candidate_ref for c in new_plan.clips] == ["b"]


def test_apply_overrides_out_of_bounds_drop_is_noop() -> None:
    plan = _plan([_clip("a", 0)])
    overrides = [Override(type="drop_item", target_position=99, why="bad index")]
    new_plan = apply_overrides(plan, overrides)
    assert [c.candidate_ref for c in new_plan.clips] == ["a"]


_ = pytest  # silence ruff F401 if no fixtures used directly
