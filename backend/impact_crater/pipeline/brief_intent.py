"""Stage 0.5 — brief understanding (S-2.10.5).

Parses the free-text brief for the *named destinations* the user wants the video
to cover (e.g. "Las Vegas", "Hoover Dam") and whether they want chronological
sequencing, so Stage 4 can guarantee coverage (the reservation mechanism, see
`destinations.py`) and the judge can be told to represent each. Reuses the
existing Tier-M `parse_user_brief` op. Fully fail-soft: any error returns an empty
`BriefIntent`, so a brief-parse hiccup never regresses a job.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["named_destinations", "chronological"],
    "properties": {
        "theme": {"type": "string"},
        "named_destinations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "aliases"],
                "properties": {
                    "name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["place", "person", "subject", "event"]},
                    "chronological_hint": {"type": ["integer", "null"]},
                },
            },
        },
        "chronological": {"type": "boolean"},
    },
}


@dataclass
class NamedDestination:
    name: str
    aliases: list[str] = field(default_factory=list)
    kind: str = "place"
    chronological_hint: int | None = None


@dataclass
class BriefIntent:
    theme: str = ""
    named_destinations: list[NamedDestination] = field(default_factory=list)
    chronological: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.named_destinations and not self.chronological


async def parse_brief(
    router: Any, brief: str, *, media_count: int = 0, target_duration_seconds: int = 60
) -> BriefIntent:
    """Parse the brief into a `BriefIntent`. Fail-soft → empty intent."""
    if not brief or not brief.strip():
        return BriefIntent()
    try:
        raw = await router.parse_user_brief(
            brief,
            schema=BRIEF_SCHEMA,
            prompt_vars={"hints": {"media_count": media_count, "target_seconds": target_duration_seconds}},
        )
    except Exception as exc:  # noqa: BLE001 — never block a job on brief-parse
        log.warning("brief_intent parse failed (proceeding without): %r", str(exc)[:200])
        return BriefIntent()
    return _to_intent(raw)


def _to_intent(raw: dict[str, Any]) -> BriefIntent:
    dests: list[NamedDestination] = []
    for d in raw.get("named_destinations") or []:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "").strip()
        if not name:
            continue
        aliases = [str(a).strip().lower() for a in (d.get("aliases") or []) if str(a).strip()]
        hint = d.get("chronological_hint")
        dests.append(
            NamedDestination(
                name=name,
                aliases=aliases,
                kind=str(d.get("kind") or "place"),
                chronological_hint=int(hint) if isinstance(hint, int) else None,
            )
        )
    return BriefIntent(
        theme=str(raw.get("theme") or ""),
        named_destinations=dests,
        chronological=bool(raw.get("chronological", False)),
    )
