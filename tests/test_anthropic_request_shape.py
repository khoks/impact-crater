"""Guards on the Anthropic request shape for the 5.x models (S-2.10.9 / D-061).

Haiku 5.5 / Sonnet 5.5 / Opus 5.5 reject non-default sampling parameters and
forced tool choice, think by default (controlled through `output_config.effort`)
and can stop with `refusal` / `model_context_window_exceeded`. The S-2.10.7 bump
broke the judge live on exactly this class of change (`temperature` on Opus 4.8).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import anthropic
import httpx
import pytest
from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient, _strict_schema
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


def _client(response: Any) -> tuple[AnthropicLLMClient, AsyncMock]:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    create = AsyncMock(return_value=response)
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


async def test_metadata_tool_is_strict_with_closed_objects() -> None:
    schema = {
        "type": "object",
        "title": "RichMetadataPhoto",
        "required": ["quality"],
        "properties": {
            "quality": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.5},
            "title": {"type": "string", "maxLength": 80},
            "people": {"$ref": "#/$defs/People"},
        },
        "$defs": {
            "People": {
                "type": "object",
                "title": "People",
                "properties": {"count": {"type": "integer", "minimum": 0}},
            }
        },
    }
    original = repr(schema)
    client, create = _client(
        SimpleNamespace(
            content=[
                SimpleNamespace(type="tool_use", name="submit_metadata", input={"quality": 0.7})
            ],
            stop_reason="tool_use",
        )
    )
    out = await client.extract_metadata_image(
        _jpeg(),
        prompt_template="extract",
        schema=schema,
        params=_params("extract_metadata_image", "low"),
    )
    assert out == {"quality": 0.7}
    assert repr(schema) == original, "the caller's schema must not be mutated"
    (tool,) = create.call_args.kwargs["tools"]
    assert tool["strict"] is True
    sent = tool["input_schema"]
    assert sent["additionalProperties"] is False
    assert sent["$defs"]["People"]["additionalProperties"] is False
    assert "title" in sent["properties"], "a property named `title` is a field, not a keyword"
    assert sent["properties"]["quality"] == {"type": "number"}
    assert sent["properties"]["title"] == {"type": "string"}
    assert sent["$defs"]["People"]["properties"]["count"] == {"type": "integer"}
    assert "title" not in sent and "title" not in sent["$defs"]["People"]


def test_strict_schema_accepts_the_real_stage3_schema() -> None:
    from impact_crater.pipeline.types import RichMetadataPhoto

    sent = _strict_schema(RichMetadataPhoto.model_json_schema())
    flat = repr(sent)
    for keyword in ("'minimum'", "'maximum'", "'minItems'", "'maxItems'", "'default'"):
        assert keyword not in flat, keyword
    for defn in sent["$defs"].values():
        assert defn["additionalProperties"] is False


async def test_score_tool_is_strict_and_result_is_clamped() -> None:
    client, create = _client(
        SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name="submit_score", input={"score": 1.4})],
            stop_reason="tool_use",
        )
    )
    score = await client.score_image(
        _jpeg(), prompt_template="rate", dimension="quality", params=_params("score_image", "low")
    )
    assert score == pytest.approx(1.0)
    (tool,) = create.call_args.kwargs["tools"]
    assert tool["strict"] is True
    assert tool["input_schema"]["additionalProperties"] is False
    assert "minimum" not in tool["input_schema"]["properties"]["score"]


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


async def test_context_window_stop_reason_raises() -> None:
    client, _ = _client(SimpleNamespace(content=[], stop_reason="model_context_window_exceeded"))
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.parse_user_brief(
            "brief",
            prompt_template="parse",
            schema={"type": "object"},
            params=_params("parse_user_brief"),
        )
    assert "model_context_window_exceeded" in str(excinfo.value)


async def test_missing_tool_call_error_names_the_stop_reason() -> None:
    client, _ = _client(
        SimpleNamespace(
            content=[SimpleNamespace(type="text", text="I ran out")], stop_reason="max_tokens"
        )
    )
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.extract_metadata_image(
            _jpeg(),
            prompt_template="extract",
            schema={"type": "object"},
            params=_params("extract_metadata_image"),
        )
    msg = str(excinfo.value)
    assert "submit_metadata" in msg and "max_tokens" in msg and "I ran out" in msg


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
