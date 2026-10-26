"""Guards on the shipped routing config (S-2.10.7 / S-2.10.9).

A model bump that forgets a prompt file or a rate card would hard-fail at dispatch
(the Stage 5 judge aborting a job after the Stage 2 spend is the worst case).
These tests catch it at test time instead, and pin the D-061 lineup so a drive-by
edit cannot quietly route an op back to a retired generation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from impact_crater import rate_cards
from impact_crater.llm_clients import prompts

_ROOT = Path(__file__).resolve().parents[1]
_ROUTING = _ROOT / "config" / "llm-routing.yaml"
_PROMPTS = _ROOT / "prompts"
_RATE_CARDS = _ROOT / "config" / "rate-cards"

_HAIKU = ("anthropic", "claude-haiku-5-5", "2026-10-07", "low")


def _ops() -> dict[str, dict[str, Any]]:
    cfg = yaml.safe_load(_ROUTING.read_text(encoding="utf-8"))
    ops: dict[str, dict[str, Any]] = cfg["operations"]
    return ops


@pytest.fixture
def shipped_rate_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMPACT_CRATER_RATE_CARDS_DIR", raising=False)
    rate_cards.clear_cache()
    yield
    rate_cards.clear_cache()


def test_every_routed_op_with_a_prompt_dir_resolves() -> None:
    missing: list[str] = []
    for op, route in _ops().items():
        if not (_PROMPTS / op).is_dir():
            continue  # ops that build their prompt inline have no prompt dir
        try:
            prompts.load(op, route["provider"], route["model"])
        except FileNotFoundError:
            missing.append(f"{op} → {route['provider']}_{route['model']}")
    assert not missing, f"routing references models with no prompt file: {missing}"


def test_every_prompt_file_belongs_to_a_priced_model() -> None:
    """Fallback prompts (the Google Tier-S lineup) stay flip-ready: each prompt's
    model has at least one rate card, so routing to it never prices at the ballpark."""
    cards = {p.name for p in _RATE_CARDS.glob("*.yaml")}
    orphans: list[str] = []
    for path in _PROMPTS.glob("*/*.jinja2"):
        provider, model = path.stem.split("_", 1)
        prefix = f"{provider}-{model.replace('.', '-')}-"
        card = re.compile(re.escape(prefix) + r"(\d{4}-\d{2}-\d{2}|latest|v\d+)\.yaml")
        if not any(card.fullmatch(c) for c in cards):
            orphans.append(str(path.relative_to(_ROOT)))
    assert not orphans, f"prompt files for models without a rate card: {orphans}"


def test_tier_lookup_mirrors_routing_yaml() -> None:
    """Every routed op has a tier entry for JobCostSummary and nothing dead lingers (S-2.13.7)."""
    from impact_crater.pipeline.runner import _TIER_BY_OPERATION

    routed = {op: route["tier"] for op, route in _ops().items()}
    assert len(routed) == 9
    assert routed == _TIER_BY_OPERATION


def test_every_routed_model_has_a_rate_card(shipped_rate_cards: None) -> None:
    for op, route in _ops().items():
        card = rate_cards.load(route["provider"], route["model"], str(route["model_version"]))
        assert card.input_token_rate_usd_per_1k >= 0, op


def test_pins_are_the_d061_lineup() -> None:
    ops = _ops()

    def pin(op: str) -> tuple[str, str, str, str | None]:
        r = ops[op]
        return (r["provider"], r["model"], str(r["model_version"]), r.get("effort"))

    for op in (
        "caption_image",
        "score_image",
        "generate_title_text",
        "extract_metadata_image",
        "parse_user_brief",
    ):
        assert pin(op) == _HAIKU, op
    assert pin("judge_narrative_arc") == ("anthropic", "claude-opus-5-5", "2026-09-21", "high")
    assert pin("embed_image") == ("google", "gemini-embedding-2", "2026-04-22", None)
    assert pin("embed_text") == pin("embed_image")
    assert pin("generate_title_background") == (
        "google",
        "gemini-3.1-flash-lite-image",
        "2026-06-30",
        None,
    )
    # Opus 5.5 cannot stop thinking; the cap must stay under the SDK's non-streaming
    # ceiling while leaving room for thinking above the ~4k-token judgment.
    assert 12000 <= ops["judge_narrative_arc"]["max_tokens"] <= 21000


def test_no_retired_generation_and_versions_are_release_dates() -> None:
    stale: list[str] = []
    unpinned: list[str] = []
    for op, r in _ops().items():
        model = str(r["model"])
        if r["provider"] == "anthropic" and re.search(r"-4-\d$", model):
            stale.append(f"{op}: {model}")
        if r["provider"] == "google" and model.startswith("gemini-2."):
            stale.append(f"{op}: {model}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r["model_version"])):
            unpinned.append(f"{op}: {r['model_version']}")
    assert not stale, f"ops still on a retired generation: {stale}"
    assert not unpinned, f"model_version must be the release date, not an alias: {unpinned}"
