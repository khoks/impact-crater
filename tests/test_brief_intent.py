"""Tests for Stage-0.5 brief intent parsing (S-2.10.5)."""

from __future__ import annotations

from impact_crater.pipeline import brief_intent as bi
from impact_crater.pipeline.brief_intent import BriefIntent, parse_brief


class _OkRouter:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def parse_user_brief(self, text, *, schema, prompt_vars=None):
        return self._payload


class _FailRouter:
    async def parse_user_brief(self, text, *, schema, prompt_vars=None):
        raise RuntimeError("model down")


def test_to_intent_parses_destinations_and_chronological() -> None:
    raw = {
        "theme": "road trip",
        "chronological": True,
        "named_destinations": [
            {"name": "Las Vegas", "aliases": ["Vegas", "Hoover Dam"], "kind": "place", "chronological_hint": 4},
            {"name": "Zion", "aliases": []},
            {"name": "", "aliases": ["skip"]},  # dropped — no name
        ],
    }
    intent = bi._to_intent(raw)
    assert intent.chronological is True
    names = [d.name for d in intent.named_destinations]
    assert names == ["Las Vegas", "Zion"]
    vegas = intent.named_destinations[0]
    assert vegas.aliases == ["vegas", "hoover dam"]  # lowercased
    assert vegas.chronological_hint == 4


async def test_parse_brief_ok() -> None:
    router = _OkRouter({"named_destinations": [{"name": "Bryce", "aliases": []}], "chronological": False})
    intent = await parse_brief(router, "a trip to bryce", media_count=10)
    assert [d.name for d in intent.named_destinations] == ["Bryce"]


async def test_parse_brief_fail_soft() -> None:
    intent = await parse_brief(_FailRouter(), "anything")
    assert intent == BriefIntent()
    assert intent.is_empty


async def test_parse_brief_empty_text() -> None:
    intent = await parse_brief(_OkRouter({}), "   ")
    assert intent.is_empty
