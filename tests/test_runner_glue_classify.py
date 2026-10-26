"""`_classify_failure` turns provider exceptions into the one-line reason the job card shows."""

from __future__ import annotations

from impact_crater.jobs.runner_glue import _classify_failure
from impact_crater.llm_clients.exceptions import LLMOperationFailed


def _failed(last_error: str, model: str = "claude-haiku-5-5") -> LLMOperationFailed:
    return LLMOperationFailed(
        operation="extract_metadata_image",
        provider="anthropic",
        model=model,
        attempts=1,
        last_error=last_error,
    )


def test_anthropic_model_not_found_is_readable() -> None:
    raw = (
        "Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', "
        "'message': 'model: claude-retired-1'}}"
    )
    reason = _classify_failure(_failed(raw, model="claude-retired-1"))
    assert reason.startswith("Model not available")
    assert "config/llm-routing.yaml" in reason
    assert "claude-retired-1" in reason


def test_google_model_not_found_is_readable() -> None:
    raw = (
        "404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-old is not found for "
        "API version v1beta, or is not supported for generateContent.'}}"
    )
    assert _classify_failure(_failed(raw, model="gemini-old")).startswith("Model not available")


def test_refusal_and_context_window_are_readable() -> None:
    assert _classify_failure(
        _failed("stop_reason=refusal category=cyber explanation='x'")
    ).startswith("An AI provider declined")
    assert _classify_failure(_failed("stop_reason=model_context_window_exceeded")).startswith(
        "Request too large"
    )


def test_credits_rate_limit_and_unknown_errors_keep_their_branches() -> None:
    assert _classify_failure(_failed("Your credit balance is too low")).startswith(
        "Anthropic API credits"
    )
    assert _classify_failure(_failed("429 rate_limit_error")).startswith("Rate limited")
    assert _classify_failure(ValueError("something odd")) == "something odd"


def test_max_tokens_truncation_is_readable() -> None:
    reason = _classify_failure(
        _failed("stop_reason=max_tokens (thinking + answer exceeded max_tokens=4096; raise it ...)")
    )
    assert reason.startswith("An AI response was cut off")
    assert "config/llm-routing.yaml" in reason


def test_unrelated_404_is_not_reported_as_a_missing_model() -> None:
    raw = "HTTP 404 while fetching the model release notes page"
    assert _classify_failure(ValueError(raw)) == raw


def test_free_tier_quota_is_named_not_called_a_rate_limit() -> None:
    raw = (
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current "
        "quota ... Quota exceeded for metric: generativelanguage.googleapis.com/"
        "generate_content_free_tier_requests, limit: 0, model: gemini-3.1-flash-lite-image, "
        "description: Generate content requests per day limit exceeded on Free Tier.'}}"
    )
    reason = _classify_failure(_failed(raw, model="gemini-3.1-flash-lite-image"))
    assert reason.startswith("Google API quota exhausted")
    assert "Free Tier" in reason
    assert _classify_failure(_failed("429 rate_limit_error")).startswith("Rate limited")
