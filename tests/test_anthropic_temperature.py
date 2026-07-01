"""Guard: `temperature` is omitted for models that deprecated it (S-2.10.7 bug).

Opus 4.8 rejects any request that includes `temperature` (400
invalid_request_error), which broke the judge live after the model bump.
"""

from __future__ import annotations

from impact_crater.llm_clients.anthropic_client import _supports_temperature


def test_opus_4_8_does_not_support_temperature() -> None:
    assert _supports_temperature("claude-opus-4-8") is False


def test_sonnet_4_6_still_supports_temperature() -> None:
    assert _supports_temperature("claude-sonnet-4-6") is True
    assert _supports_temperature("claude-opus-4-5") is True
