"""Tests for the rate-card loader + cost estimator."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from impact_crater import rate_cards


@pytest.fixture
def card_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "rate-cards"
    root.mkdir()
    monkeypatch.setenv("IMPACT_CRATER_RATE_CARDS_DIR", str(root))
    rate_cards.clear_cache()
    yield root
    rate_cards.clear_cache()


def _write(card_dir: Path, fname: str, body: dict) -> None:
    (card_dir / fname).write_text(yaml.safe_dump(body), encoding="utf-8")


def test_load_returns_parsed_card(card_dir: Path) -> None:
    _write(
        card_dir,
        "anthropic-claude-sonnet-4-5-latest.yaml",
        {
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "model_version": "latest",
            "effective_date": "2026-03-01",
            "input_token_rate_usd_per_1k": 0.003,
            "output_token_rate_usd_per_1k": 0.015,
            "image_input_rate_usd_per_1k_tokens_equivalent": 0.003,
        },
    )
    c = rate_cards.load("anthropic", "claude-sonnet-4-5", "latest")
    assert c.provider == "anthropic"
    assert c.input_token_rate_usd_per_1k == 0.003
    assert c.image_input_rate_usd_per_1k_tokens_equivalent == 0.003


def test_load_missing_card_raises(card_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rate_cards.load("anthropic", "no-such-model", "v1")


def test_load_sanitizes_model_name_with_dots(card_dir: Path) -> None:
    """`gemini-2.5-flash` should resolve to filename with dashes."""
    _write(
        card_dir,
        "google-gemini-2-5-flash-v1.yaml",
        {
            "provider": "google",
            "model": "gemini-2-5-flash",
            "model_version": "v1",
            "input_token_rate_usd_per_1k": 0.0003,
            "output_token_rate_usd_per_1k": 0.0025,
        },
    )
    c = rate_cards.load("google", "gemini-2.5-flash", "v1")
    assert c.input_token_rate_usd_per_1k == 0.0003


def test_estimate_cost_sums_input_output_image(card_dir: Path) -> None:
    _write(
        card_dir,
        "anthropic-claude-sonnet-4-5-latest.yaml",
        {
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "model_version": "latest",
            "input_token_rate_usd_per_1k": 0.003,
            "output_token_rate_usd_per_1k": 0.015,
            "image_input_rate_usd_per_1k_tokens_equivalent": 0.003,
        },
    )
    cost = rate_cards.estimate_cost_usd(
        provider="anthropic",
        model="claude-sonnet-4-5",
        model_version="latest",
        input_tokens=1000,
        output_tokens=500,
        image_tokens=2000,
    )
    # 1.0 * 0.003 + 0.5 * 0.015 + 2.0 * 0.003 = 0.003 + 0.0075 + 0.006 = 0.0165
    assert cost == pytest.approx(0.0165)


def test_estimate_cost_uses_embedding_rate_when_flagged(card_dir: Path) -> None:
    _write(
        card_dir,
        "google-gemini-embedding-001-v1.yaml",
        {
            "provider": "google",
            "model": "gemini-embedding-001",
            "model_version": "v1",
            "input_token_rate_usd_per_1k": 0.0001,
            "output_token_rate_usd_per_1k": 0.0,
            "embedding_rate_usd_per_1k_tokens": 0.0001,
        },
    )
    cost = rate_cards.estimate_cost_usd(
        provider="google",
        model="gemini-embedding-001",
        model_version="v1",
        input_tokens=10_000,
        output_tokens=0,
        is_embedding=True,
    )
    # 10.0 * 0.0001 = 0.001
    assert cost == pytest.approx(0.001)


def test_shipped_rate_cards_load(project_root: Path) -> None:
    """The four MVP rate cards we ship under config/rate-cards/ load cleanly.

    Resets the env override so we hit the shipped path, not the per-test fixture.
    """
    import os

    os.environ.pop("IMPACT_CRATER_RATE_CARDS_DIR", None)
    rate_cards.clear_cache()
    for provider, model, version in [
        ("anthropic", "claude-sonnet-4-5", "latest"),
        ("anthropic", "claude-opus-4-5", "latest"),
        ("google", "gemini-2.5-flash", "v1"),
        ("google", "gemini-embedding-001", "v1"),
    ]:
        c = rate_cards.load(provider, model, version)
        assert c.input_token_rate_usd_per_1k > 0
