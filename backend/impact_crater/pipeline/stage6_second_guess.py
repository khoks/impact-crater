"""Stage 6 orchestrator second-guess per ADR-0011 + ADR-0014.

After Stage 6's deterministic plan-compile produces a `RenderPlan`, the
orchestrator runs a Tier-M sanity-check call:

    orchestrator_second_guess(arc_judgment, plan, music_spec, brief)
        → SecondGuessResult { overrides, confidence, rationale }

Overrides are typed: `drop_item`, `reorder`, `shorten`, `lengthen`, `swap`.
Per ADR-0011, when overrides are non-empty AND confidence > 0.6, the
runner pauses for user reconfirm. M6 baseline auto-applies high-confidence
overrides (>0.85) and surfaces the rest as "suggested but skipped" in
the snapshot's metadata; the per-override Apply/Skip/Modify UI is v1.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from impact_crater.llm_clients.base import ArcJudgment, MusicSpec
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline.stage6_plan import RenderPlan

log = logging.getLogger(__name__)


OverrideType = Literal["drop_item", "reorder", "shorten", "lengthen", "swap"]


class Override(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: OverrideType
    target_position: int
    proposed_change: dict[str, Any] = Field(default_factory=dict)
    why: str


class SecondGuessResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overrides: list[Override]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


_SCHEMA = {
    "type": "object",
    "required": ["overrides", "overall_confidence", "rationale"],
    "properties": {
        "overrides": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "target_position", "why"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["drop_item", "reorder", "shorten", "lengthen", "swap"],
                    },
                    "target_position": {"type": "integer", "minimum": 0},
                    "proposed_change": {"type": "object"},
                    "why": {"type": "string"},
                },
            },
        },
        "overall_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "rationale": {"type": "string"},
    },
}


_PROMPT = """\
You are the orchestrator's sanity check on a Story Video render plan.

User brief:
{brief}

Target duration: {target_duration_seconds} seconds.

Selected items (after Stage 5 narrative judgment):
{selected_items_text}

Plan-compiled clips (after Stage 6 first pass):
{clips_text}

Your job: spot obvious issues the judge let through. Examples:
- 3+ near-identical shots in the timeline (drop_item)
- "closer" item placed before half the "scene_set" items (reorder)
- A 90s target with only 12 clips averaging 7.5s each → too slow (lengthen / shorten)
- A clip with metadata that contradicts the brief (swap)

Be conservative — most plans don't need overrides. If you're not confident
about a proposed change, leave it out and lower `overall_confidence`. The
user sees your overrides only if `overall_confidence > 0.6`.

Output JSON matching this schema:
{{
  "overrides": [
    {{"type": "drop_item|reorder|shorten|lengthen|swap",
      "target_position": <int>,
      "proposed_change": {{}},
      "why": "<short reason>"}}
  ],
  "overall_confidence": <float 0..1>,
  "rationale": "<one paragraph explaining your overall confidence>"
}}
"""


async def second_guess(
    *,
    router: LLMRouter,
    arc_judgment: ArcJudgment,
    plan: RenderPlan,
    music_spec: MusicSpec | None,
    brief: str,
) -> SecondGuessResult:
    """Tier-M check on the M2/M4 plan."""
    selected_items_text = "\n".join(
        f"  [{i.placement_position}] role={i.role} dur={i.intended_duration_ms}ms ref={i.candidate_ref} notes={i.notes!r}"
        for i in arc_judgment.selected_items
    ) or "  (empty)"
    clips_text = "\n".join(
        f"  [{i}] {c.kind} dur={c.intended_duration_ms}ms aspect={c.aspect_ratio_action} ref={c.candidate_ref}"
        for i, c in enumerate(plan.clips)
    ) or "  (empty)"

    prompt = _PROMPT.format(
        brief=brief,
        target_duration_seconds=plan.target_duration_ms // 1000,
        selected_items_text=selected_items_text,
        clips_text=clips_text,
    )

    # The router doesn't have a generic "structured output" entry point;
    # parse_user_brief is the closest fit (Tier-M Sonnet, schema-validated
    # output) so we reuse it. The cache key includes the schema_hash and
    # text content so identical inputs hit cache.
    raw = await router.parse_user_brief(prompt, schema=_SCHEMA)
    return SecondGuessResult.model_validate(raw)


# Suppress F401 for music_spec — kept in the API for future routing
# decisions (e.g. tempo-aware overrides) but unused at MVP.
_ = MusicSpec
