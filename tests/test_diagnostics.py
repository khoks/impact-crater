"""Tests for the per-phase diagnostics builder (A-023)."""

from __future__ import annotations

from dataclasses import dataclass, field

from impact_crater.pipeline.diagnostics import build_diagnostics


@dataclass
class _Item:
    content_hash: str
    scene_index: int | None
    caption: str
    quality_score: float
    narrative_relevance: float


@dataclass
class _CandidateSet:
    items: list
    filter_log: list
    cluster_metadata: dict
    target_size: int
    floor: int
    ceiling: int


@dataclass
class _Selected:
    candidate_ref: str
    placement_position: int
    intended_duration_ms: int
    role: str
    notes: str = ""


@dataclass
class _Arc:
    selected_items: list
    arc_reasoning: str
    confidence: float
    open_questions: list = field(default_factory=list)


@dataclass
class _Clip:
    candidate_ref: str
    kind: str
    role: str
    intended_duration_ms: int
    aspect_ratio_action: str


@dataclass
class _Plan:
    clips: list
    target_duration_ms: int
    mode: str


@dataclass
class _Media:
    content_hash: str
    thumb_256_path: str | None = "/tmp/x.256.jpg"


def _fixture():
    items = [
        _Item("kept1", None, "a sharp peak shot", 0.9, 0.8),
        _Item("kept2", None, "the summit selfie", 0.85, 0.7),
    ]
    cs = _CandidateSet(
        items=items,
        filter_log=[
            {"key": "kept1", "decision": "keep"},
            {"key": "kept2", "decision": "keep"},
            {"key": "drop1", "decision": "drop", "reason": "semantic_duplicate", "kept_key": "kept1", "cluster_size": 3},
            {"key": "drop2", "decision": "drop", "reason": "quality_below_threshold", "quality_score": 0.2, "threshold": 0.4},
            {"key": "drop3", "decision": "drop", "reason": "safety_explicit", "safety_level": "explicit"},
        ],
        cluster_metadata={"input_count": 5},
        target_size=2,
        floor=2,
        ceiling=4,
    )
    arc = _Arc(
        selected_items=[
            _Selected("kept1", 0, 4000, "opener"),
            _Selected("kept2", 1, 3000, "closer", notes="warm ending"),
        ],
        arc_reasoning="Climb to summit, end on the selfie.",
        confidence=0.85,
        open_questions=["Is the dog part of the group?"],
    )
    plan = _Plan(
        clips=[
            _Clip("kept1", "photo", "opener", 4000, "as_is"),
            _Clip("kept2", "photo", "closer", 3000, "smart_crop"),
        ],
        target_duration_ms=7000,
        mode="standard",
    )
    media = [_Media("kept1"), _Media("kept2"), _Media("drop1"), _Media("drop2"), _Media("drop3")]
    return cs, arc, plan, media


def test_diagnostics_has_all_phases() -> None:
    cs, arc, plan, media = _fixture()
    doc = build_diagnostics(
        project_id="proj", snapshot_id="snap",
        candidate_set=cs, arc_judgment=arc, plan=plan, cast=None, media=media,
    )
    phases = {p["phase"] for p in doc["phases"]}
    assert phases == {"stage_4_prefilter", "stage_5_judge", "stage_6_plan"}
    assert doc["snapshot_id"] == "snap"


def test_stage4_decisions_carry_reason_and_thumb() -> None:
    cs, arc, plan, media = _fixture()
    doc = build_diagnostics(
        project_id="proj", snapshot_id="snap",
        candidate_set=cs, arc_judgment=arc, plan=plan, cast=None, media=media,
    )
    s4 = next(p for p in doc["phases"] if p["phase"] == "stage_4_prefilter")
    assert s4["summary"]["input_count"] == 5
    assert s4["summary"]["kept"] == 2
    by_ref = {d["ref"]: d for d in s4["decisions"]}
    assert by_ref["drop2"]["reason"] == "quality_below_threshold"
    assert by_ref["drop2"]["quality_score"] == 0.2
    assert by_ref["drop3"]["reason"] == "safety_explicit"
    # Every decision has a thumbnail URL keyed on its content hash.
    assert by_ref["kept1"]["thumb_url"] == "/api/media/kept1/thumb.jpg"
    # Kept items carry their caption.
    assert by_ref["kept1"]["caption"] == "a sharp peak shot"


def test_stage5_selection_ordered_with_reasoning() -> None:
    cs, arc, plan, media = _fixture()
    doc = build_diagnostics(
        project_id="proj", snapshot_id="snap",
        candidate_set=cs, arc_judgment=arc, plan=plan, cast=None, media=media,
    )
    s5 = next(p for p in doc["phases"] if p["phase"] == "stage_5_judge")
    assert s5["summary"]["confidence"] == 0.85
    assert "summit" in s5["summary"]["arc_reasoning"]
    assert s5["summary"]["open_questions"] == ["Is the dog part of the group?"]
    assert [d["role"] for d in s5["decisions"]] == ["opener", "closer"]


def test_video_scene_ref_split() -> None:
    cs, arc, plan, media = _fixture()
    cs.filter_log.append({"key": "vid1#2", "decision": "keep"})
    doc = build_diagnostics(
        project_id="proj", snapshot_id="snap",
        candidate_set=cs, arc_judgment=arc, plan=plan, cast=None, media=media,
    )
    s4 = next(p for p in doc["phases"] if p["phase"] == "stage_4_prefilter")
    vid = next(d for d in s4["decisions"] if d["ref"] == "vid1#2")
    assert vid["content_hash"] == "vid1"
    assert vid["scene_index"] == 2
