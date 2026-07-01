"""Stage 9 — open-ended agentic refinement (E-2.12, ADR-0014 + ADR-0019).

The user types a free-text refinement ("insert more photos of Las Vegas", "don't
drop Vegas even if it's low quality", "make the beginning clips 50% longer and
shrink the photos around them", "increase photo duration with the song's rising
tempo"). A single richly-contextualised Tier-M/L planner call INTERPRETS the
request against the analysis already computed and emits a `RefinementOutcome` — a
combination of the shared levers:

  * `directive_patch`   — a partial PlanDirective (positional/tempo/band edits):
                          pure pacing, re-runs Stage 6 only (no re-judge).
  * `reserve_*`         — force-include destinations/refs via a ReservationSet
                          (re-runs Stage 4 → Stage 5 through the same mechanism
                          S-2.10.5 uses).
  * `brief_addendum`    — a content steer ("more landscape") → re-judge.
  * `explanation`       — when a request can't be honoured with this media.

`execute_refinement` reconstructs the job context from the persisted sidecars +
LLM cache (no re-ingest), applies the outcome through the normal pipeline
functions, and renders a **child snapshot** so an initial render and a refined
re-render run identical Stage-4/5/6 code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline import (
    stage1_ingest,
    stage2_bulk_ops,
    stage3_metadata,
    stage4_prefilter,
    stage5_judge,
    stage6_plan,
    stage6_title_card,
    stage7_render,
)
from impact_crater.pipeline.brief_intent import BriefIntent, NamedDestination, parse_brief
from impact_crater.pipeline.destinations import ReservationSet
from impact_crater.pipeline.plan_directive import PlanDirective, merge_directive
from impact_crater.pipeline.stage6_plan import RenderClip, RenderPlan, TitleCardSpec
from impact_crater.workers import WorkerPool

log = logging.getLogger(__name__)


# ---- Outcome model -----------------------------------------------------


class RefinementOutcome(BaseModel):
    """The planner's structured interpretation of a refinement request."""

    model_config = ConfigDict(extra="ignore")
    interpretation: str = ""
    # Pacing/duration lever (partial PlanDirective) — re-runs Stage 6 only.
    directive_patch: PlanDirective | None = None
    # Coverage lever — force-include named places / specific candidate refs.
    reserve_destinations: list[str] = Field(default_factory=list)
    reserve_refs: list[str] = Field(default_factory=list)
    # Content lever — a steer appended to the brief for a re-judge.
    brief_addendum: str | None = None
    # Title-card lever (S-2.12.4) — a partial TitleCardSpec: text / style (image) /
    # title_position / text_color / text_size_scale / show_year / show_faces.
    title_card_patch: dict[str, Any] | None = None
    # When the request can't be honoured with the current media.
    explanation: str | None = None

    @property
    def needs_rejudge(self) -> bool:
        return bool(self.reserve_destinations or self.reserve_refs or self.brief_addendum)

    @property
    def is_light(self) -> bool:
        """A cheap edit that re-runs Stage 6 only (pacing and/or title-card), no
        re-judge."""
        return (self.directive_patch is not None or bool(self.title_card_patch)) and not self.needs_rejudge

    @property
    def is_actionable(self) -> bool:
        return self.directive_patch is not None or bool(self.title_card_patch) or self.needs_rejudge


class RefinementResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    outcome: RefinementOutcome
    new_snapshot_id: str | None = None
    rendered: bool = False


_REFINE_SCHEMA = {
    "type": "object",
    "required": ["interpretation"],
    "properties": {
        "interpretation": {"type": "string"},
        "directive_patch": {
            "type": ["object", "null"],
            "properties": {
                "positional_rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                            "multiplier": {"type": "number"},
                            "delta_ms": {"type": "integer"},
                            "neighbor_multiplier": {"type": "number"},
                            "neighbor_delta_ms": {"type": "integer"},
                            "raises_band": {"type": "boolean"},
                            "label": {"type": "string"},
                        },
                    },
                },
                "tempo": {
                    "type": "object",
                    "properties": {
                        "bands": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "start_frac": {"type": "number"},
                                    "end_frac": {"type": "number"},
                                    "duration_multiplier": {"type": "number"},
                                    "density_multiplier": {"type": "number"},
                                },
                            },
                        },
                    },
                },
                "bands": {"type": "object"},
            },
        },
        "reserve_destinations": {"type": "array", "items": {"type": "string"}},
        "reserve_refs": {"type": "array", "items": {"type": "string"}},
        "brief_addendum": {"type": ["string", "null"]},
        "title_card_patch": {
            "type": ["object", "null"],
            "properties": {
                "title_text": {"type": ["string", "null"]},
                "style": {"type": ["string", "null"]},
                "title_position": {"enum": ["center", "lower-third", "upper-third", "top", "bottom"]},
                "text_color": {"type": "string"},
                "text_size_scale": {"type": "number"},
                "show_year": {"type": "boolean"},
                "show_faces": {"type": "boolean"},
            },
        },
        "explanation": {"type": ["string", "null"]},
    },
}


# ---- The planner call --------------------------------------------------


async def plan_refinement(
    router: LLMRouter,
    *,
    refinement_message: str,
    brief: str,
    plan_summary: str,
    destinations_available: str,
    music_summary: str,
) -> RefinementOutcome:
    """One structured call: interpret the request → a RefinementOutcome."""
    prompt = _PLANNER_PROMPT.format(
        brief=brief or "(none recorded)",
        plan_summary=plan_summary,
        destinations_available=destinations_available or "(no named destinations detected)",
        music_summary=music_summary or "(no music analysis)",
        refinement_message=refinement_message,
    )
    raw = await router.parse_user_brief(prompt, schema=_REFINE_SCHEMA)
    return _outcome_from_raw(raw)


def _outcome_from_raw(raw: dict[str, Any]) -> RefinementOutcome:
    patch = raw.get("directive_patch")
    directive_patch: PlanDirective | None = None
    if isinstance(patch, dict) and any(patch.get(k) for k in ("positional_rules", "tempo", "bands")):
        try:
            directive_patch = PlanDirective.model_validate({**patch, "provenance": "refine"})
        except Exception as exc:
            log.warning("refine directive_patch invalid (ignored): %r", str(exc)[:200])
    tc_patch = raw.get("title_card_patch")
    if not isinstance(tc_patch, dict) or not tc_patch:
        tc_patch = None
    return RefinementOutcome(
        interpretation=str(raw.get("interpretation") or ""),
        directive_patch=directive_patch,
        reserve_destinations=[str(x) for x in (raw.get("reserve_destinations") or [])],
        reserve_refs=[str(x) for x in (raw.get("reserve_refs") or [])],
        brief_addendum=raw.get("brief_addendum") or None,
        title_card_patch=tc_patch,
        explanation=raw.get("explanation") or None,
    )


_PLANNER_PROMPT = """\
You are the refinement planner for an AI Story-Video creator. The user already
has a rendered video and wants to change it. Interpret their request and choose
the RIGHT levers — think from the request and the analysis you already have.

ORIGINAL BRIEF:
{brief}

CURRENT VIDEO PLAN (order → clip):
{plan_summary}

NAMED DESTINATIONS DETECTED IN THE MEDIA (name → how many candidates exist):
{destinations_available}

MUSIC:
{music_summary}

USER'S REFINEMENT REQUEST:
"{refinement_message}"

You have these levers — use any combination (or none + an explanation):

1. directive_patch (PACING / DURATION / EMPHASIS — re-times the SAME clips, no
   content change). Use for "beginning clips 50% longer", "hold the opener 2s
   longer and shrink the photos around it", "punchier ending", "slower intro",
   "photo duration/frequency should rise with the song's tempo in the later half".
   - positional_rules: each targets a timeline REGION as a fraction [start,end]
     in 0..1 ("the beginning" ≈ [0.0,0.2], "the ending" ≈ [0.8,1.0]). Set
     `multiplier` (1.5 = +50%) and/or `delta_ms` (2000 = +2s); set
     `raises_band: true` when the emphasis should exceed the normal 3s photo cap.
     Use `neighbor_multiplier`/`neighbor_delta_ms` (e.g. -500) to shrink clips
     around the emphasised region ("reduce the photos around them by 0.5s").
   - tempo.bands: slices of the song [start_frac,end_frac] with a
     `duration_multiplier` (<1 = snappier). For "increase photo duration with
     rising tempo, decrease with falling tempo", set each half's multiplier to
     track its energy.

2. reserve_destinations / reserve_refs (COVERAGE — force-include). Use for
   "insert more photos of Las Vegas", "make sure you don't drop Las Vegas even if
   its quality is low", "add the Hoover Dam". Put the destination NAME(s) in
   reserve_destinations (they'll be force-kept through the pre-filter and the
   judge told to include them). Use reserve_refs only if the user names specific
   already-listed clips.

3. brief_addendum (CONTENT — re-judge the story). Use for "more landscape, fewer
   faces", "focus on the kids", "less driving footage". A short (<=200 word)
   steer appended to the brief; the narrative is re-judged.

4. title_card_patch (TITLE / SPLASH CARD). Use ONLY when the video has an opening
   title card and the user wants to change IT — its wording, its background image,
   where the title sits, or how it looks. Set only the fields they mention:
   - title_text: the exact words ("call it 'Desert Wandering'").
   - style: how the background IMAGE should look ("a painterly sunset", "vintage
     film", "minimal dark", "watercolor") — this regenerates the image.
   - title_position: one of center | lower-third | upper-third | top | bottom
     ("put the title at the top").
   - text_color: a colour name ("white", "gold", "black") or #RRGGBB.
   - text_size_scale: >1 bigger, <1 smaller ("make the title bigger" → ~1.3).
   - show_year / show_faces: false to drop the year or the people ("no year").

5. explanation: if the request cannot be honoured with the available media (e.g.
   "add snow" when there is none), leave the levers empty and explain why.

Prefer the NARROWEST lever(s) that satisfy the request: pure timing → only
directive_patch (fast, no re-judge); coverage → reserve_*; taste/content →
brief_addendum. Combine them when the request spans more than one.

Output JSON matching the schema. Always fill `interpretation` with one sentence
on how you read the request and which levers you chose.
"""


# ---- Execution (reconstruct → apply → render child snapshot) -----------


async def execute_refinement(
    router: LLMRouter,
    *,
    project_id: str,
    prior_plan: RenderPlan,
    refinement_message: str,
) -> RefinementResult:
    """Interpret + apply a refinement, rendering a child snapshot.

    Reconstructs the job context from the persisted sidecars (+ the LLM cache for
    Stage 2/3), so no re-ingest is needed. Fail-soft: if the request isn't
    actionable, returns the outcome (with an explanation) and no new snapshot.
    """
    if not refinement_message.strip():
        raise ValueError("refinement_message is empty")

    media = stage1_ingest.load_media_records(project_id)
    brief = prior_plan.brief or prior_plan.arc_reasoning or ""

    outcome = await plan_refinement(
        router,
        refinement_message=refinement_message,
        brief=brief,
        plan_summary=_summarize_plan(prior_plan),
        destinations_available=await _summarize_destinations(router, brief, media),
        music_summary=_summarize_music(prior_plan),
    )
    log.info("refine outcome: %s", outcome.interpretation)

    if not outcome.is_actionable or not media:
        return RefinementResult(outcome=outcome, new_snapshot_id=None, rendered=False)

    pool = WorkerPool()
    target_seconds = max(prior_plan.target_duration_ms // 1000, 1)

    if outcome.is_light:
        # SAME clips, new timing / title only — re-run Stage 6 from the prior arc,
        # no re-judge (pacing edits and/or title-card edits).
        arc = _arc_from_plan(prior_plan)
        merged = (
            merge_directive(prior_plan.directive, outcome.directive_patch)
            if outcome.directive_patch is not None
            else prior_plan.directive
        )
        montage_groups = _montage_groups_from_plan(prior_plan)
        new_plan = await stage6_plan.compile_plan(
            arc_judgment=arc,
            ingest_records=media,
            project_id=project_id,
            target_duration_seconds=target_seconds,
            mode=prior_plan.mode,
            audio=prior_plan.music,
            montage_groups=montage_groups,
            directive=merged,
            brief=brief,
            parent_snapshot_id=prior_plan.snapshot_id,
        )
    else:
        # Coverage/content edit — reconstruct Stage 2/3 (cache) and re-curate.
        s2 = await stage2_bulk_ops.run_stage2(router=router, media=media, brief=brief, pool=pool)
        s3 = await stage3_metadata.run_stage3(router=router, media=media, brief=brief, pool=pool)
        brief_intent = await _reserve_intent(router, brief, media, outcome)
        reservations = _reservations_from_outcome(outcome)
        candidate_set = stage4_prefilter.prefilter(
            media=media, stage2=s2, stage3=s3, target_duration_seconds=target_seconds,
            brief_intent=brief_intent, reservations=reservations,
        )
        judge_brief = brief
        if outcome.brief_addendum:
            judge_brief = f"{brief}\n\nRefinement addendum:\n{outcome.brief_addendum}"
        arc = await stage5_judge.judge_narrative_arc(
            router=router, candidate_set=candidate_set, brief=judge_brief,
            target_duration_seconds=target_seconds, mode=prior_plan.mode,
            coverage_plan=candidate_set.coverage_plan,
            chronological=brief_intent.chronological,
        )
        merged = (
            merge_directive(prior_plan.directive, outcome.directive_patch)
            if outcome.directive_patch is not None
            else prior_plan.directive
        )
        new_plan = await stage6_plan.compile_plan(
            arc_judgment=arc, ingest_records=media, project_id=project_id,
            target_duration_seconds=target_seconds, mode=prior_plan.mode,
            audio=prior_plan.music, montage_groups=candidate_set.montage_groups,
            directive=merged, brief=brief, parent_snapshot_id=prior_plan.snapshot_id,
        )

    # Re-inject the title card (S-2.12.4): refinement re-plans from the arc, which
    # drops the post-plan title card — preserve it, or rebuild it if the user
    # asked to change it.
    new_plan = await _reinject_title_card(router, project_id, prior_plan, new_plan, media, outcome, brief)

    await stage7_render.render_plan(new_plan, correlation_id=f"refine-{new_plan.snapshot_id}", pool=pool)
    return RefinementResult(outcome=outcome, new_snapshot_id=new_plan.snapshot_id, rendered=True)


async def _reinject_title_card(
    router: LLMRouter, project_id: str, prior_plan: RenderPlan, new_plan: RenderPlan,
    media: list[Any], outcome: RefinementOutcome, brief: str,
) -> RenderPlan:
    """Preserve (or rebuild, if patched) the opt-in title card as clip 0 of the
    refined plan. Fail-soft: on any error the plan is returned unchanged."""
    prior_had = (prior_plan.title_card_spec is not None and prior_plan.title_card_spec.enabled) or (
        bool(prior_plan.clips) and prior_plan.clips[0].kind == "title_card"
    )
    if not prior_had:
        return new_plan
    base_spec = prior_plan.title_card_spec or TitleCardSpec(enabled=True)
    patch = outcome.title_card_patch
    child_dir = stage6_plan.snapshot_dir(new_plan.project_id, new_plan.snapshot_id)
    parent_dir = stage6_plan.snapshot_dir(prior_plan.project_id, prior_plan.snapshot_id)
    try:
        if patch:
            spec = _apply_title_patch(base_spec, patch)
            reuse_bg = None if _title_patch_touches_image(patch) else str(parent_dir / "title_card_bg.png")
            if reuse_bg is not None and not Path(reuse_bg).is_file():
                reuse_bg = None
            title_clip = await stage6_title_card.build_title_clip(
                router=router, plan=new_plan, media=media, cast=_load_cast(project_id),
                brief=brief, spec=spec, snapshot_dir=child_dir, background_path=reuse_bg,
            )
            if title_clip is None:
                return new_plan
        else:
            # No title change — preserve the parent's rendered card.
            spec = base_spec
            parent_png = parent_dir / "title_card.png"
            prior_clip = prior_plan.clips[0] if prior_plan.clips and prior_plan.clips[0].kind == "title_card" else None
            src = str(parent_png) if parent_png.is_file() else (prior_clip.source_path if prior_clip else None)
            if not src or not Path(src).is_file():
                return new_plan
            title_clip = RenderClip(
                candidate_ref="__title__", kind="title_card", source_path=src,
                intended_duration_ms=prior_clip.intended_duration_ms if prior_clip else 3000,
                aspect_ratio_action="as_is", role="title", notes="title card (preserved on refine)",
            )
    except Exception as exc:
        log.warning("title_card_reinject_failed (proceeding without): %r", str(exc)[:200])
        return new_plan
    new_plan = new_plan.model_copy(update={"clips": [title_clip, *new_plan.clips], "title_card_spec": spec})
    (child_dir / "plan.json").write_text(new_plan.model_dump_json(indent=2), encoding="utf-8")
    return new_plan


def _apply_title_patch(base: TitleCardSpec, patch: dict[str, Any]) -> TitleCardSpec:
    out = base.model_copy(deep=True)
    for k, v in patch.items():
        if k in TitleCardSpec.model_fields and v is not None:
            setattr(out, k, v)
    return out


def _title_patch_touches_image(patch: dict[str, Any]) -> bool:
    return any(patch.get(k) for k in ("style", "spirit_prompt"))


def _load_cast(project_id: str) -> Any:
    """Reconstruct the CastInventory from the persisted cast.json (for face
    thumbnails when rebuilding the title card). None if absent."""
    from impact_crater import paths
    from impact_crater.media.cast import CastInventory, Person

    p = paths.projects_dir() / project_id / "cast.json"
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        persons = [Person(**pp) for pp in d.get("persons", [])]
        return CastInventory(persons=persons, group_persons_by_hash=d.get("group_persons_by_hash", {}))
    except Exception:
        return None


# ---- Reservation + context helpers -------------------------------------


def _reservations_from_outcome(outcome: RefinementOutcome) -> ReservationSet | None:
    """A direct ref reservation from the outcome (destinations flow via
    brief_intent so they resolve to real candidate keys)."""
    if not outcome.reserve_refs:
        return None
    reasons = dict.fromkeys(outcome.reserve_refs, "refine:forced")
    return ReservationSet(keys=frozenset(outcome.reserve_refs), reason_by_key=reasons, source="refinement")


async def _reserve_intent(
    router: LLMRouter, brief: str, media: list[Any], outcome: RefinementOutcome
) -> BriefIntent:
    """The BriefIntent Stage 4 uses: the original brief's destinations PLUS any
    the refinement asked to reserve (so 'don't drop Las Vegas' maps to real
    media keys through the same destination matcher)."""
    intent = await parse_brief(router, brief, media_count=len(media))
    existing = {d.name.lower() for d in intent.named_destinations}
    for name in outcome.reserve_destinations:
        if name.lower() not in existing:
            intent.named_destinations.append(NamedDestination(name=name, aliases=[name.lower()]))
    return intent


def _arc_from_plan(plan: RenderPlan) -> ArcJudgment:
    items = [
        SelectedItem(
            candidate_ref=c.candidate_ref, placement_position=i,
            intended_duration_ms=c.intended_duration_ms, role=c.role, notes=c.notes,
        )
        for i, c in enumerate(plan.clips)
        if c.candidate_ref != "__title__"
    ]
    return ArcJudgment(selected_items=items, arc_reasoning=plan.arc_reasoning, confidence=plan.arc_confidence)


def _montage_groups_from_plan(plan: RenderPlan) -> list[list[str]]:
    groups: list[list[str]] = []
    for c in plan.clips:
        if c.kind == "burst_montage" and c.members:
            groups.append([m.candidate_ref for m in c.members])
    return groups


def _summarize_plan(plan: RenderPlan) -> str:
    lines = []
    for i, c in enumerate(plan.clips):
        dest = ""
        lines.append(
            f"  {i}: {c.kind} ref={c.candidate_ref[:12]} {c.intended_duration_ms}ms role={c.role or '-'}{dest}"
        )
    total = sum(c.intended_duration_ms for c in plan.clips)
    return f"{len(plan.clips)} clips, {total/1000:.1f}s total:\n" + "\n".join(lines[:80])


async def _summarize_destinations(router: LLMRouter, brief: str, media: list[Any]) -> str:
    if not brief or not media:
        return ""
    try:
        intent = await parse_brief(router, brief, media_count=len(media))
    except Exception:
        return ""
    if not intent.named_destinations:
        return ""
    return ", ".join(d.name for d in intent.named_destinations)


def _summarize_music(plan: RenderPlan) -> str:
    music = plan.music
    if music is None or music.music_analysis is None:
        return ""
    a = music.music_analysis
    sections = ", ".join(f"{s.label}({s.mood})" for s in a.sections[:8])
    return f"bpm={a.bpm:.0f}, {len(a.sections)} sections: {sections}"
