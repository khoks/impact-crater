"""Stage 9 — N-009 agentic refinement per ADR-0011 + ADR-0014.

The user picks Refine → types a free-text refinement message
("more landscape, less faces"). The orchestrator picks one of 5
strategies and executes:

  partial_fix_via_plan_edit       — re-run Stage 5 with brief addendum (M6 default)
  partial_fix_via_stage_3_rerun   — re-extract metadata for items missed (v1)
  full_reprocess                  — re-run from Stage 4 (v1)
  request_user_input              — ask the user for more (M6: surface as failure-mode)
  explain_why_not_possible        — some refinements aren't realizable (M6 supports)

M6 baseline ships strategies 1 + 5. Strategies 2/3/4 are v1.

Bounded at 10 turns per ADR-0014 (single tool call here = 1 turn).
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from impact_crater.llm_clients.base import ArcJudgment, MusicSpec
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media.music import MusicAnalysis
from impact_crater.pipeline.stage4_prefilter import CandidateSet
from impact_crater.pipeline.stage5_judge import judge_narrative_arc

log = logging.getLogger(__name__)


Strategy = Literal[
    "partial_fix_via_plan_edit",
    "partial_fix_via_stage_3_rerun",
    "full_reprocess",
    "request_user_input",
    "explain_why_not_possible",
]


class RefinementPlan(BaseModel):
    """The orchestrator's chosen response to a user's refinement request."""

    model_config = ConfigDict(extra="ignore")
    strategy: Strategy
    rationale: str
    brief_addendum: str | None = None
    request_text: str | None = None  # for request_user_input
    explanation: str | None = None  # for explain_why_not_possible


class RefinementResult(BaseModel):
    """Output of `refine`: either a new ArcJudgment (for plan_edit) or a status."""

    model_config = ConfigDict(extra="ignore")
    plan: RefinementPlan
    arc_judgment: ArcJudgment | None = None
    turns_used: int = 1


_THINKING_SCHEMA = {
    "type": "object",
    "required": ["strategy", "rationale"],
    "properties": {
        "strategy": {
            "type": "string",
            "enum": [
                "partial_fix_via_plan_edit",
                "partial_fix_via_stage_3_rerun",
                "full_reprocess",
                "request_user_input",
                "explain_why_not_possible",
            ],
        },
        "rationale": {"type": "string"},
        "brief_addendum": {"type": ["string", "null"]},
        "request_text": {"type": ["string", "null"]},
        "explanation": {"type": ["string", "null"]},
    },
}


_PROMPT = """\
You are the orchestrator's thinking step for a Story Video refinement.

Original brief:
{brief}

Prior arc reasoning:
{prior_reasoning}

User's refinement message:
"{refinement_message}"

Available strategies (M6 supports 1 and 5; 2/3/4 land in v1):

  1. partial_fix_via_plan_edit       — re-run Stage 5 with a brief addendum.
                                       Produce `brief_addendum` (≤200 words).
                                       This is the right pick for most "more X, less Y"
                                       requests where the existing candidate set has
                                       enough variety to support the change.

  2. partial_fix_via_stage_3_rerun   — re-extract metadata for items missed (v1).
  3. full_reprocess                  — re-run from Stage 4 (v1).
  4. request_user_input              — ask for clarification (M6: surfaces as failure UX).

  5. explain_why_not_possible        — explain why this refinement can't be honored
                                       with the current media (`explanation` field;
                                       e.g. user asks for "more landscape" but the
                                       candidate set has zero landscape items).

Pick exactly one strategy. Output JSON matching the schema.
"""


async def refine(
    *,
    router: LLMRouter,
    prior_arc: ArcJudgment,
    candidate_set: CandidateSet,
    refinement_message: str,
    brief: str,
    target_duration_seconds: int,
    mode: Literal["standard", "music_video"] = "standard",
    music_spec: MusicSpec | None = None,
    music_analysis: MusicAnalysis | None = None,
) -> RefinementResult:
    """Run the M6 refinement loop.

    M6 baseline: one Tier-M thinking call → strategy choice → execute. The
    full N-turn tool-call loop with re_extract_metadata + re_run_pre_filter
    is v1.
    """
    if not refinement_message.strip():
        raise ValueError("refinement_message is empty")

    prompt = _PROMPT.format(
        brief=brief,
        prior_reasoning=prior_arc.arc_reasoning,
        refinement_message=refinement_message,
    )
    raw = await router.parse_user_brief(prompt, schema=_THINKING_SCHEMA)
    plan = RefinementPlan.model_validate(raw)
    log.info("refinement strategy: %s — %s", plan.strategy, plan.rationale)

    if plan.strategy == "partial_fix_via_plan_edit":
        addendum = plan.brief_addendum or refinement_message
        new_brief = f"{brief}\n\nRefinement addendum:\n{addendum}"
        new_arc = await judge_narrative_arc(
            router=router,
            candidate_set=candidate_set,
            brief=new_brief,
            target_duration_seconds=target_duration_seconds,
            mode=mode,
            music_spec=music_spec,
            music_analysis=music_analysis,
        )
        return RefinementResult(plan=plan, arc_judgment=new_arc, turns_used=2)

    if plan.strategy == "explain_why_not_possible":
        return RefinementResult(plan=plan, arc_judgment=None, turns_used=1)

    # M6 doesn't execute strategies 2/3/4 yet — surface as the v1-deferred
    # failure-mode UX described by ADR-0014.
    log.info(
        "refinement strategy %s is not implemented at M6; falling back to "
        "explain_why_not_possible",
        plan.strategy,
    )
    fallback_plan = RefinementPlan(
        strategy="explain_why_not_possible",
        rationale=plan.rationale,
        explanation=(
            f"Strategy '{plan.strategy}' lands at v1. At MVP I can do "
            "partial-fix-via-plan-edit (re-run Stage 5 with an addendum). "
            "Try rephrasing your refinement so a brief tweak is enough."
        ),
    )
    return RefinementResult(plan=fallback_plan, arc_judgment=None, turns_used=1)
