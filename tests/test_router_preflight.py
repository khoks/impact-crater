"""Router pre-spend ping (A-028), `effort` plumbing and per-call rate-card pricing (S-2.10.9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from impact_crater import rate_cards
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.router import (
    LLMRouter,
    OperationRoute,
    _ballpark_cost,
    routed_models,
)

_OPS = {
    "caption_image": {
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "model_version": "2026-10-07",
        "tier": "S",
        "effort": "low",
    },
    "parse_user_brief": {
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "model_version": "2026-10-07",
        "tier": "M",
        "effort": "low",
    },
    "judge_narrative_arc": {
        "provider": "anthropic",
        "model": "claude-opus-5-5",
        "model_version": "2026-09-21",
        "tier": "L",
        "effort": "high",
        "max_tokens": 20000,
    },
    "embed_image": {
        "provider": "google",
        "model": "gemini-embedding-2",
        "model_version": "2026-04-22",
        "tier": "embedding",
    },
}


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "llm-routing.yaml"
    path.write_text(yaml.safe_dump({"defaults": {"max_tokens": 1024}, "operations": _OPS}))
    return path


def _client(served: dict[str, str] | None = None) -> AsyncMock:
    client = AsyncMock()
    client.verify_model = AsyncMock(side_effect=lambda m: (served or {}).get(m, m))
    return client


def test_effort_is_read_per_op_and_reaches_call_params(config_path: Path) -> None:
    router = LLMRouter(clients={}, config_path=config_path)
    assert router.route_for("judge_narrative_arc").effort == "high"
    assert router.route_for("embed_image").effort is None
    params = router._params(router.route_for("caption_image"))
    assert params.effort == "low"
    assert params.model_version == "2026-10-07"


async def test_verify_routes_pings_each_distinct_model_once(config_path: Path) -> None:
    anthropic_client = _client()
    google_client = _client({"gemini-embedding-2": "gemini-embedding-2 (002)"})
    router = LLMRouter(
        clients={"anthropic": anthropic_client, "google": google_client}, config_path=config_path
    )
    served = await router.verify_routes()
    assert served == {
        "claude-haiku-5-5": "claude-haiku-5-5",
        "claude-opus-5-5": "claude-opus-5-5",
        "gemini-embedding-2": "gemini-embedding-2 (002)",
    }
    assert anthropic_client.verify_model.await_count == 2
    assert google_client.verify_model.await_count == 1


async def test_verify_routes_raises_on_the_first_unavailable_model(config_path: Path) -> None:
    def _fail(model: str) -> str:
        if model == "claude-opus-5-5":
            raise LLMOperationFailed(
                operation="verify_model",
                provider="anthropic",
                model=model,
                attempts=1,
                last_error="model 'claude-opus-5-5' is not available to this Anthropic key",
            )
        return model

    anthropic_client = AsyncMock()
    anthropic_client.verify_model = AsyncMock(side_effect=_fail)
    router = LLMRouter(
        clients={"anthropic": anthropic_client, "google": _client()}, config_path=config_path
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await router.verify_routes()
    assert "claude-opus-5-5" in str(excinfo.value)


def test_routed_models_lists_the_distinct_models_per_provider(config_path: Path) -> None:
    assert routed_models("anthropic", config_path) == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert routed_models("google", config_path) == ["gemini-embedding-2"]


def test_shipped_config_routes_both_providers() -> None:
    assert routed_models("anthropic") == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert routed_models("google") == ["gemini-3.1-flash-lite-image", "gemini-embedding-2"]


def test_ballpark_cost_prefers_the_cards_per_call_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "google-gemini-embedding-2-2026-04-22.yaml").write_text(
        yaml.safe_dump(
            {
                "provider": "google",
                "model": "gemini-embedding-2",
                "model_version": "2026-04-22",
                "input_token_rate_usd_per_1k": 0.0002,
                "output_token_rate_usd_per_1k": 0.0,
                "per_call_rate_usd": 0.00012,
            }
        )
    )
    (cards / "anthropic-claude-haiku-5-5-2026-10-07.yaml").write_text(
        yaml.safe_dump(
            {
                "provider": "anthropic",
                "model": "claude-haiku-5-5",
                "model_version": "2026-10-07",
                "input_token_rate_usd_per_1k": 0.0001,
                "output_token_rate_usd_per_1k": 0.0005,
            }
        )
    )
    monkeypatch.setenv("IMPACT_CRATER_RATE_CARDS_DIR", str(cards))
    rate_cards.clear_cache()
    try:
        embed = OperationRoute(
            "embed_image", "google", "gemini-embedding-2", "2026-04-22", "embedding", 1024, 0.0
        )
        assert _ballpark_cost(embed) == pytest.approx(0.00012)
        haiku = OperationRoute(
            "caption_image", "anthropic", "claude-haiku-5-5", "2026-10-07", "S", 1024, 0.0
        )
        assert _ballpark_cost(haiku) == pytest.approx(0.001)
        missing = OperationRoute(
            "judge_narrative_arc", "anthropic", "claude-opus-5-5", "2026-09-21", "L", 1024, 0.0
        )
        assert _ballpark_cost(missing) == pytest.approx(0.50)
    finally:
        rate_cards.clear_cache()
