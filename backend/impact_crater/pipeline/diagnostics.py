"""Per-phase job diagnostics (A-023 feedback loop).

Turns the pipeline's internal decision records into a single
`diagnostics.json` per snapshot that the UI can render as inspectable
per-phase panels — every keep/drop with its reason, the narrative
selection with roles, the final clip plan, and the trip cast. Each
media-bearing decision carries a thumbnail URL so the user can SEE what
was decided and give targeted feedback on it.

This is read-only reporting built from artifacts the pipeline already
produces (Stage 4 `filter_log`, the `ArcJudgment`, the `RenderPlan`, the
`CastInventory`); it adds no LLM calls.
"""

from __future__ import annotations

from typing import Any


def _ref_parts(ref: str) -> tuple[str, int | None]:
    head, _, tail = ref.partition("#")
    if not tail:
        return head, None
    try:
        return head, int(tail)
    except ValueError:
        return head, None


def _thumb_url(content_hash: str, scene_index: int | None = None) -> str:
    base = f"/api/media/{content_hash}/thumb.jpg"
    # Video scenes have no photo thumbnail; ?scene=N serves the Stage-1
    # representative frame so video keep/drop/select cards are reviewable (F8b).
    return f"{base}?scene={scene_index}" if scene_index is not None else base


# Stable phase order for both the persisted doc and the live stream.
PHASE_ORDER = ["stage_4_prefilter", "cast", "stage_5_judge", "stage_6_plan"]


def build_diagnostics(
    *,
    project_id: str,
    snapshot_id: str,
    candidate_set: Any,
    arc_judgment: Any,
    plan: Any,
    cast: Any,
    media: list[Any],
) -> dict[str, Any]:
    """Assemble the per-phase diagnostics document for one render."""
    phases: list[dict[str, Any]] = [
        phase_stage4(candidate_set),
        phase_stage5(arc_judgment),
        phase_stage6(plan),
    ]
    if cast is not None:
        phases.append(phase_cast(cast))
    # Order consistently with the live stream.
    phases.sort(key=lambda p: PHASE_ORDER.index(p["phase"]) if p["phase"] in PHASE_ORDER else 99)

    return {
        "schema_version": 1,
        "project_id": project_id,
        "snapshot_id": snapshot_id,
        "phases": phases,
    }


def phase_stage4(candidate_set: Any) -> dict[str, Any]:
    item_by_key: dict[str, Any] = {}
    for it in candidate_set.items:
        key = it.content_hash + (f"#{it.scene_index}" if it.scene_index is not None else "")
        item_by_key[key] = it
    return _stage4_phase(candidate_set, item_by_key)


def phase_stage5(arc_judgment: Any) -> dict[str, Any]:
    return _stage5_phase(arc_judgment)


def phase_stage6(plan: Any) -> dict[str, Any]:
    return _stage6_phase(plan)


def phase_cast(cast: Any) -> dict[str, Any]:
    return _cast_phase(cast)


def _stage4_phase(candidate_set: Any, item_by_key: dict[str, Any]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for entry in candidate_set.filter_log:
        key = entry.get("key", "")
        ch, scene = _ref_parts(key)
        it = item_by_key.get(key)
        decisions.append(
            {
                "content_hash": ch,
                "scene_index": scene,
                "ref": key,
                "decision": entry.get("decision"),
                "reason": entry.get("reason"),
                "caption": getattr(it, "caption", None) if it else None,
                "quality_score": entry.get("quality_score")
                if "quality_score" in entry
                else (getattr(it, "quality_score", None) if it else None),
                "narrative_relevance": entry.get("narrative_relevance")
                if "narrative_relevance" in entry
                else (getattr(it, "narrative_relevance", None) if it else None),
                "specialness_score": entry.get("specialness_score"),
                "extra": {
                    k: v
                    for k, v in entry.items()
                    if k
                    not in (
                        "key",
                        "decision",
                        "reason",
                        "quality_score",
                        "narrative_relevance",
                        "specialness_score",
                    )
                },
                "thumb_url": _thumb_url(ch, scene),
            }
        )
    # Stable, useful ordering: drops grouped by reason, then keeps.
    decisions.sort(key=lambda d: (d["decision"] != "drop", d.get("reason") or "", d["ref"]))
    return {
        "phase": "stage_4_prefilter",
        "title": "Pre-filter",
        "description": "Deterministic quality floor, safety floor, pHash + semantic best-of-burst dedup, location clustering, ranking.",
        "summary": {
            "input_count": candidate_set.cluster_metadata.get("input_count"),
            "kept": len(candidate_set.items),
            "floor": candidate_set.floor,
            "ceiling": candidate_set.ceiling,
            "target_size": candidate_set.target_size,
        },
        "decisions": decisions,
    }


def _stage5_phase(arc_judgment: Any) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for si in sorted(arc_judgment.selected_items, key=lambda s: s.placement_position):
        ch, scene = _ref_parts(si.candidate_ref)
        decisions.append(
            {
                "content_hash": ch,
                "scene_index": scene,
                "ref": si.candidate_ref,
                "decision": "select",
                "role": si.role,
                "placement_position": si.placement_position,
                "intended_duration_ms": si.intended_duration_ms,
                "notes": si.notes,
                "thumb_url": _thumb_url(ch, scene),
            }
        )
    return {
        "phase": "stage_5_judge",
        "title": "Narrative judge",
        "description": "Tier-L Opus picks the ordered narrative arc, defaulting to forward-in-time with deliberate openers.",
        "summary": {
            "confidence": arc_judgment.confidence,
            "selected": len(arc_judgment.selected_items),
            "arc_reasoning": arc_judgment.arc_reasoning,
            "open_questions": list(arc_judgment.open_questions or []),
        },
        "decisions": decisions,
    }


def _stage6_phase(plan: Any) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for i, c in enumerate(plan.clips):
        ch, scene = _ref_parts(c.candidate_ref)
        decisions.append(
            {
                "content_hash": ch,
                "scene_index": scene,
                "ref": c.candidate_ref,
                "decision": "clip",
                "position": i,
                "kind": c.kind,
                "role": c.role,
                "intended_duration_ms": c.intended_duration_ms,
                "aspect_ratio_action": c.aspect_ratio_action,
                "thumb_url": _thumb_url(ch, scene),
            }
        )
    return {
        "phase": "stage_6_plan",
        "title": "Plan",
        "description": "The arc compiled into a timeline: clip durations (linear or beat-snapped) and aspect-ratio handling.",
        "summary": {
            "clips": len(plan.clips),
            "target_duration_ms": plan.target_duration_ms,
            "mode": plan.mode,
        },
        "decisions": decisions,
    }


def _cast_phase(cast: Any) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for p in cast.persons:
        rep = p.content_hashes[0] if p.content_hashes else None
        decisions.append(
            {
                "person_id": p.person_id,
                "decision": "group" if p.is_group else "crowd",
                "appearance_count": p.appearance_count,
                "distinct_days": p.distinct_days,
                "distinct_locations": p.distinct_locations,
                "recurrence_breadth": p.recurrence_breadth,
                "content_hash": rep,
                "thumb_url": _thumb_url(rep) if rep else None,
            }
        )
    return {
        "phase": "cast",
        "title": "Trip cast",
        "description": "Unique faces clustered, split into group (recurs across days/places) vs incidental crowd.",
        "summary": {
            "persons": len(cast.persons),
            "group": len(cast.group),
            "crowd": len(cast.crowd),
        },
        "decisions": decisions,
    }
