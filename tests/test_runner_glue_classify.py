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


def test_preflight_runtime_error_is_readable() -> None:
    exc = RuntimeError(
        "AI model pre-flight failed: model 'gemini-embedding-2' is not available to this "
        "Google key (404 NOT_FOUND)"
    )
    assert _classify_failure(exc).startswith("Model not available")


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
