"""Unit tests for AnthropicLLMClient + GoogleLLMClient with mocked SDKs.

Real-API smoke is in tests/integration/test_real_providers.py (gated by
--integration).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import CallParams, LLMClient
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.google_client import GoogleLLMClient
from PIL import Image


def _real_jpeg_bytes() -> bytes:
    """Minimum valid JPEG. Anthropic client now decodes non-JPEG inputs and
    re-encodes to JPEG (fix for stage1 PNG scene frames being sent as
    image/jpeg) — so tests must pass real magic-byte JPEGs through, not
    `b"\\x00\\x00fake"` placeholders."""
    img = Image.new("RGB", (16, 16), color=(80, 120, 160))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=70)
    return out.getvalue()


_FAKE_JPEG = _real_jpeg_bytes()


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
        _FAKE_JPEG,
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
        _FAKE_JPEG,
        prompt_template="extract",
        schema={"type": "object"},
        params=_params("extract_metadata_image"),
    )
    assert out == payload


async def test_anthropic_extract_metadata_raises_when_tool_not_called() -> None:
    client = AnthropicLLMClient(api_key="sk-ant-test")
    fake_response = SimpleNamespace(content=[SimpleNamespace(type="text", text="I'd rather not")])
    client._client.messages.create = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.extract_metadata_image(
            _FAKE_JPEG,
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
        _FAKE_JPEG,
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
            model="gemini-embedding-2",
            model_version="2026-04-22",
        ),
    )
    assert emb.ndim == 1
    assert emb.dtype.name == "float32"
    assert emb.shape[0] > 0
    kwargs = client._client.models.embed_content.call_args.kwargs
    assert kwargs["model"] == "gemini-embedding-2"
    assert kwargs["contents"] == ["hello world"]
    assert kwargs["config"].output_dimensionality == 768


async def test_google_embed_text_substitutes_fallback_for_empty_input() -> None:
    """Real failure mode caught 2026-05-06: Gemini Flash returned an empty
    caption for one image of a 545-asset job, that empty string flowed
    into embed_content, and Google's API 400'd with `EmbedContentRequest.
    content contains an empty Part`. embed_text now substitutes a benign
    placeholder so a single problem image can't kill the whole job."""
    client = GoogleLLMClient(api_key="AIza-test")
    fake_embedding = SimpleNamespace(values=[0.1] * 768)
    fake_response = SimpleNamespace(embeddings=[fake_embedding])
    captured: dict[str, str] = {}

    def _capture(*, model: str, contents: list[str], config: object) -> SimpleNamespace:
        captured["contents"] = contents[0]
        return fake_response

    client._client.models.embed_content = MagicMock(side_effect=_capture)  # type: ignore[method-assign]

    for empty_in in ("", "   ", "\n\t  \n"):
        captured.clear()
        emb = await client.embed_text(
            empty_in,
            params=CallParams(
                operation="embed_text",
                provider="google",
                model="gemini-embedding-001",
                model_version="v1",
            ),
        )
        assert emb.shape == (768,)
        # The empty-string was replaced with a non-empty placeholder
        # before the network call.
        assert captured["contents"], f"empty input {empty_in!r} reached the API"
        assert captured["contents"].strip(), "fallback was whitespace-only"


def test_google_sniff_mime_type_recognizes_real_formats() -> None:
    """Real failure 2026-05-07 motivated this: stage1's video-scene PNG
    frames were sent to Google with `mime_type="image/jpeg"`. Google was
    lenient (Stage 2 succeeded) but Anthropic 400'd in Stage 3. Fix is to
    sniff the actual mime type from magic bytes."""
    from impact_crater.llm_clients.google_client import _sniff_mime_type

    assert _sniff_mime_type(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"
    assert _sniff_mime_type(b"\x89PNG\r\n\x1a\n\x00\x00") == "image/png"
    assert _sniff_mime_type(b"GIF87a\x00\x00") == "image/gif"
    assert _sniff_mime_type(b"GIF89a\x00\x00") == "image/gif"
    assert _sniff_mime_type(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"
    assert _sniff_mime_type(b"BM\x00\x00") == "image/bmp"
    # Default (and sanity check that the WEBP guard doesn't false-positive
    # on RIFF chunks that aren't WEBP — e.g. RIFF/WAVE audio).
    assert _sniff_mime_type(b"RIFF\x00\x00\x00\x00WAVE") == "image/jpeg"
    # Default for unrecognized bytes.
    assert _sniff_mime_type(b"\x00\x00\x00\x00") == "image/jpeg"


async def test_google_embed_image_sends_the_image_part_not_a_caption() -> None:
    """D-061: gemini-embedding-2 embeds the image bytes directly; the old
    caption-then-embed round trip (and its generate_content call) is gone."""
    client = GoogleLLMClient(api_key="AIza-test")
    client._client.models.generate_content = MagicMock(  # type: ignore[method-assign]
        side_effect=AssertionError("embed_image must not caption")
    )
    fake_embedding = SimpleNamespace(values=[0.2] * 768)
    client._client.models.embed_content = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(embeddings=[fake_embedding])
    )

    emb = await client.embed_image(
        _FAKE_JPEG,
        params=CallParams(
            operation="embed_image",
            provider="google",
            model="gemini-embedding-2",
            model_version="2026-04-22",
        ),
    )
    assert emb.shape == (768,)
    kwargs = client._client.models.embed_content.call_args.kwargs
    assert kwargs["model"] == "gemini-embedding-2"
    (part,) = kwargs["contents"]
    assert part.inline_data.mime_type == "image/jpeg"
    assert part.inline_data.data == _FAKE_JPEG
    assert kwargs["config"].output_dimensionality == 768


def test_google_fit_image_for_embedding_reencodes_webp_and_large_inputs() -> None:
    from impact_crater.llm_clients.google_client import _fit_image_for_embedding

    big = Image.new("RGB", (3000, 2000), (10, 20, 30))
    buf = io.BytesIO()
    big.save(buf, format="WEBP")
    out = _fit_image_for_embedding(buf.getvalue())
    assert out.startswith(b"\xff\xd8\xff")
    with Image.open(io.BytesIO(out)) as img:
        assert max(img.size) == 1024
    assert _fit_image_for_embedding(_FAKE_JPEG) == _FAKE_JPEG


def test_google_usage_splits_image_tokens_and_counts_thoughts() -> None:
    from impact_crater.llm_clients.google_client import _apply_usage

    params = CallParams(
        operation="caption_image",
        provider="google",
        model="gemini-3.5-flash-lite",
        model_version="2026-07-21",
    )
    usage = SimpleNamespace(
        prompt_token_count=1300,
        candidates_token_count=40,
        thoughts_token_count=25,
        prompt_tokens_details=[
            SimpleNamespace(modality="TEXT", token_count=270),
            SimpleNamespace(modality="IMAGE", token_count=1030),
        ],
    )
    _apply_usage(params, SimpleNamespace(usage_metadata=usage))
    assert (params.usage_input_tokens, params.usage_image_tokens, params.usage_output_tokens) == (
        270,
        1030,
        65,
    )


async def test_google_effort_becomes_thinking_level() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    client._client.models.generate_content = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(text="A lake.", candidates=[])
    )
    await client.caption_image(
        _FAKE_JPEG,
        prompt_template="caption",
        params=CallParams(
            operation="caption_image",
            provider="google",
            model="gemini-3.5-flash-lite",
            model_version="2026-07-21",
            effort="minimal",
        ),
    )
    config = client._client.models.generate_content.call_args.kwargs["config"]
    level = config.thinking_config.thinking_level
    assert getattr(level, "value", level) == "MINIMAL"


async def test_google_caption_image_extracts_text() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    fake_response = SimpleNamespace(text="A serene lake at dusk.", candidates=[])
    client._client.models.generate_content = MagicMock(return_value=fake_response)  # type: ignore[method-assign]

    out = await client.caption_image(
        _FAKE_JPEG,
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
        _FAKE_JPEG,
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
            _FAKE_JPEG,
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


async def test_google_verify_model_returns_the_served_version() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    client._client.models.get = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(name="models/gemini-embedding-2", version="002")
    )
    assert await client.verify_model("gemini-embedding-2") == "gemini-embedding-2 (002)"
    assert client._client.models.get.call_args.kwargs == {"model": "gemini-embedding-2"}


async def test_google_verify_model_maps_not_found_and_bad_key() -> None:
    client = GoogleLLMClient(api_key="AIza-test")
    missing = Exception("404 NOT_FOUND. models/gemini-old is not found for API version v1beta")
    missing.code = 404  # type: ignore[attr-defined]
    client._client.models.get = MagicMock(side_effect=missing)  # type: ignore[method-assign]
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.verify_model("gemini-old")
    assert "not available to this Google key" in str(excinfo.value)

    bad_key = Exception("400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key.")
    bad_key.code = 400  # type: ignore[attr-defined]
    client._client.models.get = MagicMock(side_effect=bad_key)  # type: ignore[method-assign]
    with pytest.raises(LLMOperationFailed) as excinfo:
        await client.verify_model("gemini-embedding-2")
    assert "rejected the API key" in str(excinfo.value)
