"""Tests for the dual-cap (total + per-provider) quota check + spend recording."""

from __future__ import annotations

from datetime import date

import pytest

from impact_crater import quota
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


@pytest.mark.usefixtures("db_initialized")
async def test_check_quota_blocks_when_no_total_cap_configured() -> None:
    result = await quota.check_quota({"anthropic": 1.0})
    assert result.allowed is False
    assert result.reason == "no_total_cap_configured"


@pytest.mark.usefixtures("db_initialized")
async def test_check_quota_allows_when_under_total_cap() -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "10.00")
    result = await quota.check_quota({"anthropic": 2.0, "google": 1.0})
    assert result.allowed is True
    assert result.cap_total_usd == 10.0
    assert result.today_total_spent_usd == 0.0


@pytest.mark.usefixtures("db_initialized")
async def test_check_quota_blocks_when_total_would_be_exceeded() -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "5.00")
    await quota.record_spend("anthropic", 4.50)
    result = await quota.check_quota({"google": 1.00})
    assert result.allowed is False
    assert result.reason == "total_cap_would_be_exceeded"


@pytest.mark.usefixtures("db_initialized")
async def test_check_quota_blocks_when_per_provider_would_be_exceeded() -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")
    await settings_store.set_value(settings_store.KEY_ANTHROPIC_CAP_USD, "10.00")
    await quota.record_spend("anthropic", 9.00)
    result = await quota.check_quota({"anthropic": 2.00})
    assert result.allowed is False
    assert result.reason == "anthropic_cap_would_be_exceeded"


@pytest.mark.usefixtures("db_initialized")
async def test_record_spend_double_bumps_total_and_provider() -> None:
    await quota.record_spend("anthropic", 1.50)
    await quota.record_spend("google", 0.25)
    snap = await quota.get_today_spend()
    assert snap["anthropic"] == pytest.approx(1.50)
    assert snap["google"] == pytest.approx(0.25)
    assert snap["_total_"] == pytest.approx(1.75)


@pytest.mark.usefixtures("db_initialized")
async def test_record_spend_negative_or_zero_is_noop() -> None:
    await quota.record_spend("anthropic", 0.0)
    await quota.record_spend("google", -1.0)
    snap = await quota.get_today_spend()
    assert snap == {}


@pytest.mark.usefixtures("db_initialized")
async def test_check_quota_isolates_per_day() -> None:
    """Spend recorded yesterday must not count against today's caps."""
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "5.00")
    yesterday = date(2026, 5, 1)
    await quota.record_spend("anthropic", 4.99, today=yesterday)

    today = date(2026, 5, 4)
    result = await quota.check_quota({"anthropic": 4.00}, today=today)
    assert result.allowed is True
