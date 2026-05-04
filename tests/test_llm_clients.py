"""Unit tests for AnthropicLLMClient + GoogleLLMClient with mocked SDKs.

Real-API smoke is in tests/integration/test_real_providers.py (gated by
--integration).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import CallParams, LLMClient
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.google_client import GoogleLLMClient


def _params(operation: str, model: str = "claude-sonnet-4-7") -> CallParams:
    return CallParams(
        operation=operation,
        provider="anthropic",
        model=model,
        model_version="v20260301",
    )


def test_anthropic_satisfies_protocol() -> None:
    """Structural check: AnthropicLLMClient is an LLMClient at runtime."""
    client = AnthropicLLMClient(api_key="sk-ant-test")
    assert isinstance(client, LLMClient)


def test_google_satisfies_protocol() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    assert isinstance(client, LLMClient)


async def test_anthropic_caption_returns_first_text_block(mocker: pytest.FixtureRequest) -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="A cat on a windowsill.")]
    )
    client._client.messages.create = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

    out = await client.caption_image(
        b"\x00\x00\x00fake-jpg",
        prompt_template="caption this",
        params=_params("caption_image"),
    )
    assert out == "A cat on a windowsill."


async def test_anthropic_extract_metadata_uses_tool_use() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    payload = {"people": {"count": 2}, "mood": "warm"}
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="submit_metadata", input=payload)]
    )
    client._client.messages.create = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

    out = await client.extract_metadata_image(
        b"\x00\x00\x00fake-jpg",
        prompt_template="extract",
        schema={"type": "object"},
        params=_params("extract_metadata_image"),
    )
    assert out == payload


async def test_anthropic_extract_metadata_raises_when_tool_not_called() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="I'd rather not")]
    )
    client._client.messages.create = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.extract_metadata_image(
            b"\x00\x00\x00fake-jpg",
            prompt_template="extract",
            schema={"type": "object"},
            params=_params("extract_metadata_image"),
        )
    assert "submit_metadata" in str(excinfo.value)


async def test_anthropic_judge_narrative_arc_parses_arc_judgment() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    raw = {
        "selected_items": [
            {
                "candidate_ref": "abc#0",
                "placement_position": 0,
                "intended_duration_ms": 2000,
                "role": "opener",
                "notes": "wide shot",
            },
            {
                "candidate_ref": "def",
                "placement_position": 1,
                "intended_duration_ms": 1500,
                "role": "scene_set",
            },
        ],
        "arc_reasoning": "Builds from wide to close.",
        "confidence": 0.78,
        "open_questions": ["consider including #47?"],
    }
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="submit_arc_judgment", input=raw)]
    )
    client._client.messages.create = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

    arc = await client.judge_narrative_arc(
        candidates=[],
        prompt_template="judge",
        brief="family vacation",
        target_duration=60,
        mode="standard",
        music_spec=None,
        params=_params("judge_narrative_arc", model="claude-opus-4-7"),
    )
    assert arc.confidence == pytest.approx(0.78)
    assert len(arc.selected_items) == 2
    assert arc.selected_items[0].role == "opener"
    assert arc.selected_items[1].notes == ""  # default for missing field
    assert arc.open_questions == ["consider including #47?"]


async def test_anthropic_score_image_clamps_via_tool_use() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="submit_score", input={"score": 0.42})]
    )
    client._client.messages.create = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

    score = await client.score_image(
        b"\x00\x00\x00fake-jpg",
        prompt_template="rate quality",
        dimension="quality",
        params=_params("score_image"),
    )
    assert score == pytest.approx(0.42)


async def test_anthropic_embed_image_raises_misroute() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.embed_image(b"x", params=_params("embed_image"))
    assert "does not support" in str(excinfo.value)


async def test_google_embed_text_returns_numpy_array() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    fake_embedding = SimpleNamespace(values=[0.1] * 768)
    fake_response = SimpleNamespace(embeddings=[fake_embedding])
    client._client.models.embed_content = MagicMock(return_value=fake_response)  # type: ignore[method-assign]

    emb = await client.embed_text(
        "hello world",
        params=CallParams(
            operation="embed_text",
            provider="google",
            model="gemini-embedding-001",
            model_version="v1",
        ),
    )
    assert emb.ndim == 1
    assert emb.dtype.name == "float32"
    assert emb.shape[0] > 0


async def test_google_caption_image_extracts_text() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    fake_response = SimpleNamespace(text="A serene lake at dusk.", candidates=[])
    client._client.models.generate_content = MagicMock(return_value=fake_response)  # type: ignore[method-assign]

    out = await client.caption_image(
        b"\x00\x00\x00fake-jpg",
        prompt_template="caption",
        params=CallParams(
            operation="caption_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
        ),
    )
    assert out == "A serene lake at dusk."


async def test_google_extract_metadata_returns_parsed_json() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    payload_text = '{"people": {"count": 1}, "mood": "calm"}'
    fake_response = SimpleNamespace(text=payload_text, candidates=[])
    client._client.models.generate_content = MagicMock(return_value=fake_response)  # type: ignore[method-assign]

    out = await client.extract_metadata_image(
        b"\x00\x00\x00fake-jpg",
        prompt_template="extract",
        schema={"type": "object"},
        params=CallParams(
            operation="extract_metadata_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
        ),
    )
    assert out == {"people": {"count": 1}, "mood": "calm"}


async def test_google_extract_metadata_raises_on_non_json() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    fake_response = SimpleNamespace(text="not json at all", candidates=[])
    client._client.models.generate_content = MagicMock(return_value=fake_response)  # type: ignore[method-assign]

    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.extract_metadata_image(
            b"\x00\x00\x00fake-jpg",
            prompt_template="extract",
            schema={"type": "object"},
            params=CallParams(
                operation="extract_metadata_image",
                provider="google",
                model="gemini-2.5-flash",
                model_version="v1",
            ),
        )
    assert "non-JSON" in str(excinfo.value)
