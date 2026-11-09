"""Mid-job spend guard (S-3.11.1): the router checks the daily caps before every
paid call, and a reached cap or an exhausted provider credit stops the job
instead of failing once per remaining asset."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import yaml
from impact_crater import quota
from impact_crater.llm_clients import prompts
from impact_crater.llm_clients.base import CallParams
from impact_crater.llm_clients.exceptions import (
    LLMOperationFailed,
    ProviderCreditExhausted,
    QuotaExceededMidJob,
)
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline import runner
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations
from impact_crater.workers import WorkerPool

CREDIT_ERROR = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API.'}}"
)


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    ops = {
        "extract_metadata_image": ("anthropic", "test-anthropic-model", "M"),
        "caption_image": ("google", "test-google-model", "S"),
    }
    root = tmp_path / "prompts"
    for op, (provider, model, _tier) in ops.items():
        (root / op).mkdir(parents=True)
        (root / op / f"{provider}_{model}.jinja2").write_text("Do it.", encoding="utf-8")
    monkeypatch.setenv("IMPACT_CRATER_PROMPTS_DIR", str(root))
    prompts.clear_cache()
    path = tmp_path / "llm-routing.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "operations": {
                    op: {"provider": provider, "model": model, "tier": tier}
                    for op, (provider, model, tier) in ops.items()
                }
            }
        ),
        encoding="utf-8",
    )
    yield path
    prompts.clear_cache()


async def _caps(total: float, anthropic: float | None = None) -> None:
    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, str(total))
    if anthropic is not None:
        await settings_store.set_value(settings_store.KEY_ANTHROPIC_CAP_USD, str(anthropic))


def _clients(extract: Any) -> dict[str, Any]:
    anthropic = AsyncMock()
    anthropic.extract_metadata_image = extract
    google = AsyncMock()
    google.caption_image = AsyncMock(return_value="a canyon")
    return {"anthropic": anthropic, "google": google}


def _billed_extract(calls: list[int], *, fail_on: int | None = None) -> Any:
    async def extract(
        _image: bytes, *, prompt_template: str, schema: dict[str, Any], params: CallParams
    ) -> dict[str, Any]:
        calls.append(1)
        if fail_on is not None and len(calls) == fail_on:
            raise LLMOperationFailed(
                operation="extract_metadata_image",
                provider="anthropic",
                model="test-anthropic-model",
                attempts=1,
                last_error=CREDIT_ERROR,
            )
        params.usage_input_tokens = 1000
        params.usage_output_tokens = 200
        return {"ok": True}

    return extract


async def _extract(router: LLMRouter, i: int) -> dict[str, Any]:
    return await router.extract_metadata_image(b"img", content_hash=f"h{i}", schema={})


async def test_a_reached_provider_cap_stops_every_later_call(config: Path) -> None:
    await _caps(total=50.0, anthropic=0.003)
    await quota.record_spend("anthropic", 0.001)
    calls: list[int] = []
    clients = _clients(_billed_extract(calls))
    router = LLMRouter(clients=clients, config_path=config)
    router.enable_quota_guard()

    with pytest.raises(QuotaExceededMidJob) as excinfo:
        await _extract(router, 0)
    halt = excinfo.value
    assert halt.provider == "anthropic"
    assert halt.reason == "anthropic_cap_would_be_exceeded"
    assert halt.cap_usd == pytest.approx(0.003)
    assert "anthropic-only cap" in str(halt)
    assert "re-run" in str(halt)
    assert calls == []

    # Latched: a Google call is refused too, without reaching the provider.
    with pytest.raises(QuotaExceededMidJob):
        await router.caption_image(b"img", content_hash="g0")
    clients["google"].caption_image.assert_not_awaited()


async def test_the_total_cap_is_checked_per_call(config: Path) -> None:
    await _caps(total=1.0)
    await quota.record_spend("google", 0.999)
    router = LLMRouter(clients=_clients(_billed_extract([])), config_path=config)
    router.enable_quota_guard()

    with pytest.raises(QuotaExceededMidJob) as excinfo:
        await _extract(router, 0)
    assert excinfo.value.reason == "total_cap_would_be_exceeded"
    assert "total cap" in str(excinfo.value)


async def test_without_a_cap_the_guard_refuses(config: Path) -> None:
    await run_pending_migrations()
    router = LLMRouter(clients=_clients(_billed_extract([])), config_path=config)
    router.enable_quota_guard()
    with pytest.raises(QuotaExceededMidJob, match="No daily spend cap is set"):
        await _extract(router, 0)


async def test_the_guard_is_off_unless_enabled(config: Path) -> None:
    await run_pending_migrations()
    calls: list[int] = []
    router = LLMRouter(clients=_clients(_billed_extract(calls)), config_path=config)
    assert await _extract(router, 0) == {"ok": True}
    assert calls == [1]


async def test_credit_exhaustion_mid_stage3_fails_fast_and_keeps_the_spend(
    config: Path,
) -> None:
    """The 2026-06-17 shape: the provider runs out of credit partway through the
    per-photo metadata calls. Stage 3 skips a failed photo and moves on, so
    without the halt every remaining photo would make the same doomed call."""
    await _caps(total=50.0)
    calls: list[int] = []
    router = LLMRouter(clients=_clients(_billed_extract(calls, fail_on=3)), config_path=config)
    router.enable_quota_guard()
    pool = WorkerPool(network_workers=1)

    with pytest.raises(ProviderCreditExhausted) as excinfo:
        await pool.submit_many_tolerant("network", list(range(20)), lambda i: _extract(router, i))
    assert "credits exhausted" in str(excinfo.value)
    assert len(calls) == 3  # two billed, the third refused; the other 17 never sent
    spent = await quota.get_today_spend()
    assert spent["anthropic"] > 0
    assert spent["_total_"] == pytest.approx(spent["anthropic"])


async def test_an_ordinary_failure_is_still_skipped_per_asset(config: Path) -> None:
    await _caps(total=50.0)

    async def flaky(
        _image: bytes, *, prompt_template: str, schema: dict[str, Any], params: CallParams
    ) -> dict[str, Any]:
        raise LLMOperationFailed(
            operation="extract_metadata_image",
            provider="anthropic",
            model="m",
            attempts=1,
            last_error="image too large",
        )

    router = LLMRouter(clients=_clients(flaky), config_path=config)
    router.enable_quota_guard()
    out = await WorkerPool(network_workers=1).submit_many_tolerant(
        "network", [0, 1, 2], lambda i: _extract(router, i)
    )
    assert out == [None, None, None]


async def test_the_quota_day_is_utc_across_local_midnight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """06:30Z and 08:30Z on 2026-11-09 straddle midnight in Los Angeles (PST, UTC-8)
    but are the same UTC day, so spend before local midnight still counts after it."""
    await _caps(total=6.0)
    monkeypatch.setattr(quota, "_now", lambda: datetime(2026, 11, 9, 6, 30, tzinfo=UTC))
    await quota.record_spend("anthropic", 5.0)

    monkeypatch.setattr(quota, "_now", lambda: datetime(2026, 11, 9, 8, 30, tzinfo=UTC))
    check = await quota.check_quota({"anthropic": 2.0})
    assert not check.allowed
    assert check.today_total_spent_usd == pytest.approx(5.0)

    monkeypatch.setattr(quota, "_now", lambda: datetime(2026, 11, 10, 0, 30, tzinfo=UTC))
    assert (await quota.check_quota({"anthropic": 2.0})).allowed


async def test_routers_built_for_jobs_have_the_guard_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await run_pending_migrations()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google")
    monkeypatch.setattr(LLMRouter, "verify_routes", AsyncMock(return_value={}))
    router = await runner.build_router_from_settings()
    assert router._quota_guard is True
