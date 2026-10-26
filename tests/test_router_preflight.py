"""Router pre-spend ping (A-028), `effort` plumbing and per-call rate-card pricing (S-2.10.9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from impact_crater import rate_cards
from impact_crater.llm_clients.base import CallParams
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.router import (
    LLMRouter,
    OperationRoute,
    _ballpark_cost,
    routed_models,
)
from impact_crater.storage.migrations import run_pending_migrations

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
    "generate_title_background": {
        "provider": "google",
        "model": "gemini-3.1-flash-lite-image",
        "model_version": "2026-06-30",
        "tier": "M",
    },
}


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "llm-routing.yaml"
    path.write_text(yaml.safe_dump({"defaults": {"max_tokens": 1024}, "operations": _OPS}))
    return path


def _unavailable(model: str) -> LLMOperationFailed:
    return LLMOperationFailed(
        operation="verify_model",
        provider="x",
        model=model,
        attempts=1,
        last_error=f"model {model!r} is not available to this key",
    )


def _client(served: dict[str, str] | None = None, failing: set[str] | None = None) -> AsyncMock:
    def verify(model: str) -> str:
        if model in (failing or set()):
            raise _unavailable(model)
        return (served or {}).get(model, model)

    client = AsyncMock()
    client.verify_model = AsyncMock(side_effect=verify)
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
        "gemini-3.1-flash-lite-image": "gemini-3.1-flash-lite-image",
    }
    assert anthropic_client.verify_model.await_count == 2
    assert google_client.verify_model.await_count == 2


async def test_verify_routes_raises_on_an_unavailable_required_model(config_path: Path) -> None:
    router = LLMRouter(
        clients={"anthropic": _client(failing={"claude-opus-5-5"}), "google": _client()},
        config_path=config_path,
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await router.verify_routes()
    assert "claude-opus-5-5" in str(excinfo.value)


async def test_verify_routes_only_warns_for_the_opt_in_title_image_model(
    config_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The title-card background is opt-in and fail-soft, so its model must never
    block a job submit or fail the wizard's Google key test."""
    router = LLMRouter(
        clients={
            "anthropic": _client(),
            "google": _client(failing={"gemini-3.1-flash-lite-image"}),
        },
        config_path=config_path,
    )
    with caplog.at_level("WARNING"):
        served = await router.verify_routes()
    assert "gemini-3.1-flash-lite-image" not in served
    assert served["gemini-embedding-2"] == "gemini-embedding-2"
    assert "llm_preflight_optional_unavailable" in caplog.text


def test_routed_models_lists_the_distinct_models_per_provider(config_path: Path) -> None:
    assert routed_models("anthropic", config_path) == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert routed_models("google", config_path) == [
        "gemini-3.1-flash-lite-image",
        "gemini-embedding-2",
    ]
    assert routed_models("google", config_path, include_optional=False) == ["gemini-embedding-2"]


def test_shipped_config_routes_both_providers() -> None:
    assert routed_models("anthropic") == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert routed_models("google") == ["gemini-3.1-flash-lite-image", "gemini-embedding-2"]
    assert routed_models("google", include_optional=False) == ["gemini-embedding-2"]


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


async def test_verify_routes_requires_a_prompt_template_for_each_routed_op(
    tmp_path: Path,
) -> None:
    """A configured-fallback flip must be caught at submit, not in Stage 3 after the
    Stage 2 spend: here caption_image is flipped to a model that has no template."""
    ops = {**_OPS, "caption_image": {**_OPS["caption_image"], "model": "claude-sonnet-5-5"}}
    path = tmp_path / "llm-routing.yaml"
    path.write_text(yaml.safe_dump({"defaults": {"max_tokens": 1024}, "operations": ops}))
    anthropic_client = _client()
    router = LLMRouter(
        clients={"anthropic": anthropic_client, "google": _client()}, config_path=path
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await router.verify_routes()
    assert "prompts/caption_image/anthropic_claude-sonnet-5-5.jinja2" in str(excinfo.value)
    assert anthropic_client.verify_model.await_count == 0


async def test_shipped_fallback_prompts_exist_for_the_documented_flips() -> None:
    from impact_crater.llm_clients import prompts

    for op in ("extract_metadata_image", "parse_user_brief", "generate_title_text"):
        prompts.load(op, "anthropic", "claude-sonnet-5-5")
    for op in ("caption_image", "score_image", "generate_title_text"):
        prompts.load(op, "google", "gemini-3.5-flash-lite")


async def test_failed_dispatch_still_meters_the_billed_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusal / max_tokens / retried-then-failed call was billed by the provider;
    the router must still record it against quota and telemetry."""
    monkeypatch.delenv("IMPACT_CRATER_RATE_CARDS_DIR", raising=False)
    rate_cards.clear_cache()
    await run_pending_migrations()

    class FailingClient:
        provider = "anthropic"

        async def caption_image(
            self, image_bytes: bytes, *, prompt_template: str, params: CallParams
        ) -> str:
            params.usage_input_tokens = 40000
            params.usage_output_tokens = 20000
            raise LLMOperationFailed(
                operation="caption_image",
                provider="anthropic",
                model=params.model,
                attempts=1,
                last_error="stop_reason=max_tokens",
            )

    events: list[dict[str, object]] = []

    async def sink(event: dict[str, object]) -> None:
        events.append(event)

    router = LLMRouter(clients={"anthropic": FailingClient()})
    router.set_progress_sink(sink)
    try:
        with pytest.raises(LLMOperationFailed):
            await router.caption_image(b"\xff\xd8\xff", content_hash="feedfacefeedface")
    finally:
        rate_cards.clear_cache()
    assert len(events) == 1
    assert events[0]["cache_hit"] is False
    # 40k input at $0.10/M + 20k output at $0.50/M on claude-haiku-5-5
    assert events[0]["cost_usd"] == pytest.approx(0.004 + 0.010)


async def test_a_parse_error_after_billing_is_metered_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """judge_narrative_arc builds SelectedItem(**item) after the usage is on params; a
    malformed reply raises TypeError, which must still reach quota and telemetry."""
    monkeypatch.delenv("IMPACT_CRATER_RATE_CARDS_DIR", raising=False)
    rate_cards.clear_cache()
    await run_pending_migrations()

    class MalformedClient:
        provider = "anthropic"

        async def caption_image(
            self, image_bytes: bytes, *, prompt_template: str, params: CallParams
        ) -> str:
            params.usage_input_tokens = 10000
            params.usage_output_tokens = 2000
            raise TypeError("SelectedItem.__init__() got an unexpected keyword argument 'reason'")

    events: list[dict[str, object]] = []

    async def sink(event: dict[str, object]) -> None:
        events.append(event)

    router = LLMRouter(clients={"anthropic": MalformedClient()})
    router.set_progress_sink(sink)
    try:
        with pytest.raises(TypeError):
            await router.caption_image(b"\xff\xd8\xff", content_hash="feedfacefeedfac2")
    finally:
        rate_cards.clear_cache()
    assert len(events) == 1
    # 10k input at $0.10/M + 2k output at $0.50/M on claude-haiku-5-5
    assert events[0]["cost_usd"] == pytest.approx(0.001 + 0.001)
