"""Guard: the real routing config resolves a prompt for every op that needs one.

A model-string bump (S-2.10.7) that forgets to rename an op's prompt file would
hard-fail at dispatch (Stage 5 judge aborting the job is the worst case). This
test catches it at CI time instead.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from impact_crater.llm_clients import prompts

_ROOT = Path(__file__).resolve().parents[1]
_ROUTING = _ROOT / "config" / "llm-routing.yaml"
_PROMPTS = _ROOT / "prompts"


def test_every_routed_op_with_a_prompt_dir_resolves() -> None:
    cfg = yaml.safe_load(_ROUTING.read_text(encoding="utf-8"))
    missing: list[str] = []
    for op, route in cfg["operations"].items():
        if not (_PROMPTS / op).is_dir():
            continue  # ops that build their prompt inline have no prompt dir
        try:
            prompts.load(op, route["provider"], route["model"])
        except FileNotFoundError:
            missing.append(f"{op} → {route['provider']}_{route['model']}")
    assert not missing, f"routing references models with no prompt file: {missing}"


def test_bumped_models_are_current() -> None:
    cfg = yaml.safe_load(_ROUTING.read_text(encoding="utf-8"))
    assert cfg["operations"]["judge_narrative_arc"]["model"] == "claude-opus-4-8"
    assert cfg["operations"]["parse_user_brief"]["model"] == "claude-sonnet-4-6"
    # No op should still point at a superseded 4-5 Anthropic model.
    stale = [op for op, r in cfg["operations"].items()
             if r.get("provider") == "anthropic" and str(r.get("model", "")).endswith("-4-5")]
    assert not stale, f"ops still on a -4-5 model: {stale}"
