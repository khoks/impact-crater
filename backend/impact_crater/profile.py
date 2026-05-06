"""Cross-project user profile per N-010 + ADR-0014.

Two storage shapes:
  ~/.impact-crater/profile/feedback_log.jsonl  (append-only, authoritative)
  ~/.impact-crater/profile/profile.json        (derived, regenerated on demand)

MVP derivation is deterministic frequency-based: counts + averages over
the feedback events. LLM-driven derivation is post-launch. The schema is
the same — `derive_profile()` just populates it from event tallies.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from impact_crater import paths

_LOCK = threading.Lock()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- Feedback events --------------------------------------------------


EventType = Literal[
    "approve",
    "refine",
    "second_guess_accepted",
    "second_guess_rejected",
    "second_guess_modified",
    "refinement_succeeded",
    "refinement_failed",
    "pre_filter_overridden",
    "effort_level_overridden",
    "publish_succeeded",
    "publish_failed",
    "job_cancelled",
]


@dataclass
class FeedbackEvent:
    event_type: EventType
    project_id: str
    snapshot_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    timestamp: str = field(default_factory=_iso_now)


def _feedback_log_path() -> Path:
    p = paths.profile_dir() / "feedback_log.jsonl"
    return p


def _profile_path() -> Path:
    return paths.profile_dir() / "profile.json"


def emit(event: FeedbackEvent) -> None:
    """Append a feedback event to the log."""
    line = json.dumps(asdict(event), separators=(",", ":"))
    target = _feedback_log_path()
    with _LOCK:
        with target.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_events() -> Iterator[dict[str, Any]]:
    """Iterate every feedback event in stream order."""
    target = _feedback_log_path()
    if not target.is_file():
        return
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---- Profile schema ---------------------------------------------------


@dataclass
class StylePreferences:
    """User's revealed style preferences (frequency-derived)."""

    target_duration_seconds_avg: float | None = None
    target_duration_seconds_observed: list[int] = field(default_factory=list)
    mode_counts: dict[str, int] = field(default_factory=dict)  # standard | music_video
    visibility_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class OrchestratorPriors:
    """Priors for the orchestrator's decision points."""

    second_guess_acceptance_rate: float | None = None  # accepted / (accepted+rejected)
    refinement_success_rate: float | None = None
    effort_level_override_rate: float | None = None  # how often user adjusts beyond default


@dataclass
class NarrativePatterns:
    """Patterns in narrative-arc judgments the user accepts."""

    approved_count: int = 0
    refined_count: int = 0
    cancelled_count: int = 0


@dataclass
class Profile:
    style_preferences: StylePreferences = field(default_factory=StylePreferences)
    orchestrator_priors: OrchestratorPriors = field(default_factory=OrchestratorPriors)
    narrative_patterns: NarrativePatterns = field(default_factory=NarrativePatterns)
    schema_version: int = 1
    derived_at: str = field(default_factory=_iso_now)
    derived_from_n_events: int = 0

    def is_empty(self) -> bool:
        return self.derived_from_n_events == 0


def load_profile() -> Profile:
    """Read the persisted profile, or return a fresh empty one."""
    p = _profile_path()
    if not p.is_file():
        return Profile()
    raw = json.loads(p.read_text(encoding="utf-8"))
    return Profile(
        style_preferences=StylePreferences(**raw.get("style_preferences", {})),
        orchestrator_priors=OrchestratorPriors(**raw.get("orchestrator_priors", {})),
        narrative_patterns=NarrativePatterns(**raw.get("narrative_patterns", {})),
        schema_version=raw.get("schema_version", 1),
        derived_at=raw.get("derived_at", _iso_now()),
        derived_from_n_events=raw.get("derived_from_n_events", 0),
    )


def save_profile(profile: Profile) -> None:
    p = _profile_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


# ---- Derivation -------------------------------------------------------


def derive_profile() -> Profile:
    """Frequency-based deterministic derivation.

    LLM-driven derivation is post-launch (per ADR-0014 + the epic file).
    """
    events = list(read_events())
    style = StylePreferences()
    priors = OrchestratorPriors()
    patterns = NarrativePatterns()

    durations: list[int] = []
    second_guess_accept = 0
    second_guess_reject = 0
    refinement_succ = 0
    refinement_fail = 0
    effort_override = 0
    job_started = 0  # used as denominator for effort-override rate

    for ev in events:
        et = ev.get("event_type")
        payload = ev.get("payload", {})
        if et == "approve":
            patterns.approved_count += 1
        elif et == "refine":
            patterns.refined_count += 1
        elif et == "job_cancelled":
            patterns.cancelled_count += 1
        elif et == "second_guess_accepted":
            second_guess_accept += 1
        elif et == "second_guess_rejected":
            second_guess_reject += 1
        elif et == "refinement_succeeded":
            refinement_succ += 1
        elif et == "refinement_failed":
            refinement_fail += 1
        elif et == "effort_level_overridden":
            effort_override += 1
            job_started += 1
        elif et == "publish_succeeded":
            visibility = payload.get("visibility")
            if isinstance(visibility, str):
                style.visibility_counts[visibility] = (
                    style.visibility_counts.get(visibility, 0) + 1
                )

        # Side-channel: target_duration may be on multiple events.
        td = payload.get("target_duration_seconds")
        if isinstance(td, int):
            durations.append(td)
        mode = payload.get("mode")
        if isinstance(mode, str):
            style.mode_counts[mode] = style.mode_counts.get(mode, 0) + 1

    if durations:
        style.target_duration_seconds_avg = sum(durations) / len(durations)
        style.target_duration_seconds_observed = durations[-50:]  # cap

    sg_total = second_guess_accept + second_guess_reject
    if sg_total > 0:
        priors.second_guess_acceptance_rate = second_guess_accept / sg_total
    rf_total = refinement_succ + refinement_fail
    if rf_total > 0:
        priors.refinement_success_rate = refinement_succ / rf_total
    if job_started > 0:
        priors.effort_level_override_rate = effort_override / max(job_started, 1)

    return Profile(
        style_preferences=style,
        orchestrator_priors=priors,
        narrative_patterns=patterns,
        derived_from_n_events=len(events),
    )


def reset() -> None:
    """Wipe the feedback log + profile per the user's reset button."""
    fp = _feedback_log_path()
    if fp.is_file():
        fp.unlink()
    pp = _profile_path()
    if pp.is_file():
        pp.unlink()


# ---- Suggestions surface ----------------------------------------------


@dataclass
class JobSuggestions:
    """What the new-project UI shows when the profile is non-empty."""

    suggested_target_duration_seconds: int | None = None
    suggested_mode: Literal["standard", "music_video"] | None = None
    suggested_visibility: Literal["public", "unlisted", "private"] | None = None
    rationale: str = ""


def suggestions_for_new_job(profile: Profile | None = None) -> JobSuggestions:
    """Populate suggestions from the derived profile."""
    p = profile or load_profile()
    if p.is_empty():
        return JobSuggestions()

    rationale_bits: list[str] = []
    suggestion = JobSuggestions()

    avg = p.style_preferences.target_duration_seconds_avg
    if avg is not None:
        suggestion.suggested_target_duration_seconds = int(round(avg))
        rationale_bits.append(
            f"avg target duration across past jobs: {int(round(avg))}s"
        )

    if p.style_preferences.mode_counts:
        top_mode = max(p.style_preferences.mode_counts.items(), key=lambda kv: kv[1])[0]
        if top_mode in ("standard", "music_video"):
            suggestion.suggested_mode = top_mode  # type: ignore[assignment]
            rationale_bits.append(f"you usually pick {top_mode} mode")

    if p.style_preferences.visibility_counts:
        top_vis = max(
            p.style_preferences.visibility_counts.items(), key=lambda kv: kv[1]
        )[0]
        if top_vis in ("public", "unlisted", "private"):
            suggestion.suggested_visibility = top_vis  # type: ignore[assignment]
            rationale_bits.append(f"you usually publish as {top_vis}")

    suggestion.rationale = "; ".join(rationale_bits) if rationale_bits else ""
    return suggestion
