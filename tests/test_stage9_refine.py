"""Tests for the open-ended agentic refinement planner (E-2.12)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from impact_crater.pipeline import stage9_refine as sr
from impact_crater.pipeline.stage6_plan import MontageMember, RenderClip, RenderPlan, TitleCardSpec
from impact_crater.pipeline.stage9_refine import (
    RefinementOutcome,
    _apply_title_patch,
    _arc_from_plan,
    _montage_groups_from_plan,
    _outcome_from_raw,
    _reservations_from_outcome,
    _title_patch_touches_image,
    plan_refinement,
)


def _plan() -> RenderPlan:
    return RenderPlan(
        project_id="p", snapshot_id="s0", target_duration_ms=10_000, brief="a zion trip",
        arc_reasoning="warm to cool", arc_confidence=0.8,
        clips=[
            RenderClip(candidate_ref="a", kind="photo", source_path="/tmp/a.jpg",
                       intended_duration_ms=2000, aspect_ratio_action="as_is", role="opener"),
            RenderClip(candidate_ref="b", kind="photo", source_path="/tmp/b.jpg",
                       intended_duration_ms=2000, aspect_ratio_action="as_is"),
        ],
    )


def test_outcome_pure_pacing_from_directive_patch() -> None:
    outcome = _outcome_from_raw({
        "interpretation": "hold the opener longer",
        "directive_patch": {"positional_rules": [{"region": [0.0, 0.2], "delta_ms": 2000, "raises_band": True}]},
    })
    assert outcome.directive_patch is not None
    assert outcome.is_light is True
    assert outcome.needs_rejudge is False
    assert outcome.directive_patch.positional_rules[0].delta_ms == 2000


def test_outcome_reserve_destination_needs_rejudge() -> None:
    outcome = _outcome_from_raw({"interpretation": "keep vegas", "reserve_destinations": ["Las Vegas"]})
    assert outcome.needs_rejudge is True
    assert outcome.is_light is False
    assert outcome.reserve_destinations == ["Las Vegas"]


def test_outcome_empty_directive_patch_is_ignored() -> None:
    outcome = _outcome_from_raw({"interpretation": "x", "directive_patch": {"positional_rules": []}})
    assert outcome.directive_patch is None
    assert outcome.is_actionable is False


def test_outcome_explanation_only() -> None:
    outcome = _outcome_from_raw({"interpretation": "can't", "explanation": "no snow in the media"})
    assert outcome.is_actionable is False
    assert outcome.explanation == "no snow in the media"


def test_outcome_title_card_patch_is_light() -> None:
    outcome = _outcome_from_raw({
        "interpretation": "rename the title + move it up",
        "title_card_patch": {"title_text": "Desert Wandering", "title_position": "top"},
    })
    assert outcome.title_card_patch == {"title_text": "Desert Wandering", "title_position": "top"}
    assert outcome.is_light is True  # title-only edit re-runs Stage 6 only, no re-judge
    assert outcome.needs_rejudge is False
    assert outcome.is_actionable is True


def test_apply_title_patch_sets_only_given_fields() -> None:
    base = TitleCardSpec(enabled=True, title_text="Old", text_color="white")
    out = _apply_title_patch(base, {"title_text": "New", "title_position": "top", "show_year": False})
    assert out.title_text == "New"
    assert out.title_position == "top"
    assert out.show_year is False
    assert out.text_color == "white"  # untouched
    assert out.enabled is True


def test_title_patch_touches_image() -> None:
    assert _title_patch_touches_image({"style": "painterly sunset"}) is True
    assert _title_patch_touches_image({"title_text": "X", "title_position": "top"}) is False
    assert _title_patch_touches_image({"spirit_prompt": "a desert at dawn"}) is True


async def test_plan_refinement_calls_router_and_parses() -> None:
    router = AsyncMock()
    router.parse_user_brief.return_value = {
        "interpretation": "shorten the intro",
        "directive_patch": {"positional_rules": [{"region": [0.0, 0.2], "multiplier": 0.7}]},
    }
    outcome = await plan_refinement(
        router, refinement_message="snappier intro", brief="b",
        plan_summary="2 clips", destinations_available="", music_summary="",
    )
    assert outcome.is_light
    assert router.parse_user_brief.await_count == 1
    sent_prompt = router.parse_user_brief.await_args.args[0]
    assert "snappier intro" in sent_prompt  # the request reached the prompt


def test_arc_from_plan_skips_title_card() -> None:
    plan = _plan()
    plan.clips.insert(0, RenderClip(candidate_ref="__title__", kind="title_card",
                                   source_path="/t.png", intended_duration_ms=3000, aspect_ratio_action="as_is"))
    arc = _arc_from_plan(plan)
    refs = [i.candidate_ref for i in arc.selected_items]
    assert "__title__" not in refs
    assert refs == ["a", "b"]


def test_reservations_from_outcome_refs() -> None:
    res = _reservations_from_outcome(RefinementOutcome(reserve_refs=["a", "b"]))
    assert res is not None
    assert res.keys == frozenset({"a", "b"})
    assert res.source == "refinement"
    assert _reservations_from_outcome(RefinementOutcome()) is None


def test_montage_groups_from_plan() -> None:
    plan = _plan()
    plan.clips.append(RenderClip(
        candidate_ref="m", kind="burst_montage", source_path="/m.jpg",
        intended_duration_ms=3000, aspect_ratio_action="as_is",
        members=[MontageMember(candidate_ref="m1", source_path="/m1.jpg", aspect_ratio_action="as_is", duration_ms=500),
                 MontageMember(candidate_ref="m2", source_path="/m2.jpg", aspect_ratio_action="as_is", duration_ms=500)],
    ))
    assert _montage_groups_from_plan(plan) == [["m1", "m2"]]


def test_summarize_plan_lists_clips() -> None:
    summary = sr._summarize_plan(_plan())
    assert "2 clips" in summary
    assert "ref=a" in summary
