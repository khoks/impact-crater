"""Guards on the Anthropic request shape for the 5.x models (S-2.10.9 / D-061).

Haiku 5.5 / Sonnet 5.5 / Opus 5.5 reject non-default sampling parameters and
forced tool choice, think by default (controlled through `output_config.effort`)
and can stop with `refusal`, `model_context_window_exceeded` or `max_tokens`
before the tool call lands. The S-2.10.7 bump broke the judge live on exactly
this class of change (`temperature` on Opus 4.8).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import anthropic
import httpx
import pytest
from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import CallParams
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from PIL import Image


def _jpeg() -> bytes:
    img = Image.new("RGB", (16, 16), color=(80, 120, 160))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=70)
    return out.getvalue()


def _params(
    operation: str, effort: str | None = None, model: str = "claude-haiku-5-5"
) -> CallParams:
    return CallParams(
        operation=operation,
        provider="anthropic",
        model=model,
        model_version="2026-10-07",
        max_tokens=1024,
        temperature=0.0,
        effort=effort,
    )


def _client(*responses: Any) -> tuple[AnthropicLLMClient, AsyncMock]:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    create = AsyncMock(side_effect=list(responses))
    client._client.messages.create = create  # type: ignore[method-assign]
    return client, create


def _text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        stop_reason="end_turn",
    )


def _tool_response(name: str, payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name=name, input=payload)],
        stop_reason="tool_use",
    )


async def test_temperature_is_never_sent_and_effort_goes_to_output_config() -> None:
    client, create = _client(_text_response("A lake."))
    out = await client.caption_image(
        _jpeg(), prompt_template="caption", params=_params("caption_image", "low")
    )
    assert out == "A lake."
    kwargs = create.call_args.kwargs
    assert "temperature" not in kwargs
    assert "tool_choice" not in kwargs
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["model"] == "claude-haiku-5-5"


async def test_no_output_config_without_an_effort() -> None:
    client, create = _client(_text_response("A lake."))
    await client.caption_image(_jpeg(), prompt_template="caption", params=_params("caption_image"))
    assert "output_config" not in create.call_args.kwargs
    assert "temperature" not in create.call_args.kwargs


async def test_metadata_tool_sends_the_callers_schema_unstrict() -> None:
    """The D-009 schema exceeds Anthropic's strict-tool limits (map-typed field, > 24
    optional parameters, tuple fields), so submit_metadata must go out as-is and
    without `strict` — strict mode would 400 every Stage 3 call."""
    from impact_crater.pipeline.types import RichMetadataPhoto

    schema = RichMetadataPhoto.model_json_schema()
    client, create = _client(_tool_response("submit_metadata", {"quality": 0.7}))
    out = await client.extract_metadata_image(
        _jpeg(),
        prompt_template="extract",
        schema=schema,
        params=_params("extract_metadata_image", "low"),
    )
    assert out == {"quality": 0.7}
    (tool,) = create.call_args.kwargs["tools"]
    assert "strict" not in tool
    assert tool["input_schema"] is schema


async def test_score_tool_is_strict_and_result_is_clamped() -> None:
    client, create = _client(_tool_response("submit_score", {"score": 1.4}))
    score = await client.score_image(
        _jpeg(), prompt_template="rate", dimension="quality", params=_params("score_image", "low")
    )
    assert score == pytest.approx(1.0)
    (tool,) = create.call_args.kwargs["tools"]
    assert tool["strict"] is True
    assert tool["input_schema"]["additionalProperties"] is False
    assert tool["input_schema"]["required"] == ["score"]
    assert "minimum" not in tool["input_schema"]["properties"]["score"]


async def test_text_only_reply_is_retried_once_then_fails() -> None:
    client, create = _client(
        _text_response("Sure, here is the metadata: ..."),
        _tool_response("submit_metadata", {"mood": "calm"}),
    )
    out = await client.parse_user_brief(
        "brief",
        prompt_template="parse",
        schema={"type": "object"},
        params=_params("parse_user_brief", "low"),
    )
    assert out == {"mood": "calm"}
    assert create.await_count == 2

    client, create = _client(_text_response("no tool"), _text_response("still no tool"))
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.extract_metadata_image(
            _jpeg(),
            prompt_template="extract",
            schema={"type": "object"},
            params=_params("extract_metadata_image"),
        )
    msg = str(excinfo.value)
    assert create.await_count == 2
    assert "submit_metadata" in msg and "end_turn" in msg and "still no tool" in msg


async def test_refusal_stop_reason_raises_a_readable_failure() -> None:
    client, _ = _client(
        SimpleNamespace(
            content=[],
            stop_reason="refusal",
            stop_details=SimpleNamespace(category="cyber", explanation="declined"),
        )
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.caption_image(
            _jpeg(), prompt_template="caption", params=_params("caption_image")
        )
    assert "stop_reason=refusal" in str(excinfo.value)
    assert "cyber" in str(excinfo.value)


async def test_context_window_and_max_tokens_stops_raise_without_retry() -> None:
    client, create = _client(
        SimpleNamespace(content=[], stop_reason="model_context_window_exceeded")
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.parse_user_brief(
            "brief",
            prompt_template="parse",
            schema={"type": "object"},
            params=_params("parse_user_brief"),
        )
    assert "model_context_window_exceeded" in str(excinfo.value)
    assert create.await_count == 1

    truncated = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="submit_metadata", input={"quality": 0.2})],
        stop_reason="max_tokens",
    )
    client, create = _client(truncated)
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.extract_metadata_image(
            _jpeg(),
            prompt_template="extract",
            schema={"type": "object"},
            params=_params("extract_metadata_image"),
        )
    assert "stop_reason=max_tokens" in str(excinfo.value)
    assert "max_tokens=1024" in str(excinfo.value)
    assert create.await_count == 1


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    request = httpx.Request("GET", "https://api.anthropic.com/v1/models/x")
    return cls("nope", response=httpx.Response(status, request=request), body=None)


async def test_verify_model_returns_the_served_id() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    client._client.models.retrieve = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(id="claude-haiku-5-5")
    )
    assert await client.verify_model("claude-haiku-5-5") == "claude-haiku-5-5"


async def test_verify_model_maps_404_and_401_to_readable_failures() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    client._client.models.retrieve = AsyncMock(  # type: ignore[method-assign]
        side_effect=_status_error(anthropic.NotFoundError, 404)
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.verify_model("claude-retired-1")
    assert "not available" in str(excinfo.value) and "not_found_error" in str(excinfo.value)

    client._client.models.retrieve = AsyncMock(  # type: ignore[method-assign]
        side_effect=_status_error(anthropic.AuthenticationError, 401)
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.verify_model("claude-haiku-5-5")
    assert "rejected the API key" in str(excinfo.value)


def _usage(input_tokens: int, output_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


async def test_usage_accumulates_across_the_tool_retry_and_survives_a_failure() -> None:
    first = _text_response("prose instead of the tool")
    first.usage = _usage(1000, 50)
    second = _tool_response("submit_metadata", {"mood": "calm"})
    second.usage = _usage(1000, 300)
    client, _ = _client(first, second)
    params = _params("parse_user_brief", "low")
    await client.parse_user_brief(
        "brief", prompt_template="parse", schema={"type": "object"}, params=params
    )
    assert (params.usage_input_tokens, params.usage_output_tokens) == (2000, 350)

    truncated = SimpleNamespace(content=[], stop_reason="max_tokens", usage=_usage(40000, 20000))
    client, _ = _client(truncated)
    params = _params("judge_narrative_arc", "high", model="claude-opus-5-5")
    with pytest.raises(LLMOperationFailed):
        await client.parse_user_brief(
            "brief", prompt_template="judge", schema={"type": "object"}, params=params
        )
    assert (params.usage_input_tokens, params.usage_output_tokens) == (40000, 20000)


async def test_anthropic_retry_exhaustion_is_an_operation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from impact_crater.llm_clients import anthropic_client
    from tenacity import wait_none

    monkeypatch.setattr(anthropic_client, "_RETRY_WAIT", wait_none())
    client = AnthropicLLMClient(api_key="sk-ant-test")
    overloaded = _status_error(anthropic.InternalServerError, 503)
    client._client.messages.create = AsyncMock(side_effect=overloaded)  # type: ignore[method-assign]
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.caption_image(
            _jpeg(), prompt_template="caption", params=_params("caption_image")
        )
    assert excinfo.value.attempts == 4
    assert client._client.messages.create.await_count == 4


async def test_overloaded_529_is_retried_as_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    from impact_crater.llm_clients import anthropic_client
    from tenacity import wait_none

    monkeypatch.setattr(anthropic_client, "_RETRY_WAIT", wait_none())
    client = AnthropicLLMClient(api_key="sk-ant-test")
    overloaded = _status_error(anthropic.APIStatusError, 529)
    client._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=[overloaded, _text_response("A lake.")]
    )
    out = await client.caption_image(
        _jpeg(), prompt_template="caption", params=_params("caption_image")
    )
    assert out == "A lake."
    assert client._client.messages.create.await_count == 2
