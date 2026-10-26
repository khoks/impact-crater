"""Integration smoke tests against the real Anthropic + Google APIs on the D-061 lineup.

Gated by `--integration` (per tests/conftest.py). Reads API keys from .env.test if
present, else from ANTHROPIC_API_KEY / GOOGLE_API_KEY. Each test makes the smallest
call that proves the request shape the pipeline sends: strict tool schemas, effort,
no temperature, image-byte embeddings, the 16:9 1K title image, and the judge on
Opus 5.5. Image inputs are tiny synthetic JPEGs; the whole module costs well under
a dollar (the Opus judge call is the bulk of it).
"""

from __future__ import annotations

import io
import os

import pytest
from impact_crater.llm_clients import prompts
from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import CallParams, CandidateRef
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.google_client import GoogleLLMClient
from impact_crater.llm_clients.router import routed_models
from impact_crater.pipeline.brief_intent import BRIEF_SCHEMA
from impact_crater.pipeline.types import RichMetadataPhoto
from PIL import Image

pytestmark = pytest.mark.integration

HAIKU = ("claude-haiku-5-5", "2026-10-07")
OPUS = ("claude-opus-5-5", "2026-09-21")
FLASH_LITE = ("gemini-3.5-flash-lite", "2026-07-21")
EMBED = ("gemini-embedding-2", "2026-04-22")
TITLE_IMAGE = ("gemini-3.1-flash-lite-image", "2026-06-30")


def _tiny_jpeg(color: tuple[int, int, int] = (180, 60, 120)) -> bytes:
    """A 64x64 solid-color JPEG. Vision LLMs return short generic captions."""
    img = Image.new("RGB", (64, 64), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _params(
    operation: str,
    provider: str,
    pin: tuple[str, str],
    *,
    max_tokens: int = 1024,
    effort: str | None = None,
) -> CallParams:
    return CallParams(
        operation=operation,
        provider=provider,
        model=pin[0],
        model_version=pin[1],
        max_tokens=max_tokens,
        effort=effort,
    )


@pytest.fixture
def anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture
def google_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY not set")
    return key


# ---- Pre-spend ping (free) ---------------------------------------------


async def test_anthropic_verify_model_resolves_every_routed_pin(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    for model in routed_models("anthropic"):
        assert await client.verify_model(model) == model


async def test_google_verify_model_resolves_every_routed_pin(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    for model in routed_models("google"):
        assert (await client.verify_model(model)).startswith(model)


# ---- Anthropic: Haiku 5.5 Tier-S / Tier-M, Opus 5.5 judge ---------------


async def test_anthropic_caption_image_smoke(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    out = await client.caption_image(
        _tiny_jpeg(),
        prompt_template="In one short sentence, describe what you see. Reply with the sentence only.",
        params=_params("caption_image", "anthropic", HAIKU, effort="low"),
    )
    assert isinstance(out, str) and out.strip()


async def test_anthropic_score_image_calls_the_strict_tool(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    score = await client.score_image(
        _tiny_jpeg(),
        prompt_template=(
            "Rate this image's technical quality from 0.0 to 1.0. Submit the number by calling "
            "the `submit_score` tool exactly once."
        ),
        dimension="quality",
        params=_params("score_image", "anthropic", HAIKU, effort="low"),
    )
    assert 0.0 <= score <= 1.0


async def test_anthropic_extract_metadata_with_the_real_stage3_schema(anthropic_key: str) -> None:
    """The RichMetadataPhoto schema (pydantic $defs, nullable anyOf, enums) goes out
    as-is on a non-strict tool; the API must accept it and the result must parse back
    into the model."""
    client = AnthropicLLMClient(api_key=anthropic_key)
    prompt = prompts.render(
        prompts.load("extract_metadata_image", "anthropic", HAIKU[0]),
        context_brief="a smoke test",
    )
    out = await client.extract_metadata_image(
        _tiny_jpeg(),
        prompt_template=prompt,
        schema=RichMetadataPhoto.model_json_schema(),
        params=_params("extract_metadata_image", "anthropic", HAIKU, max_tokens=4096, effort="low"),
    )
    parsed = RichMetadataPhoto(**out)
    assert 0.0 <= parsed.quality <= 1.0


async def test_anthropic_parse_user_brief_with_the_brief_schema(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    prompt = prompts.render(
        prompts.load("parse_user_brief", "anthropic", HAIKU[0]),
        user_brief="A calm chronological recap of our two days hiking in Zion for the family.",
        hints=None,
    )
    out = await client.parse_user_brief(
        "unused-by-client",
        prompt_template=prompt,
        schema=BRIEF_SCHEMA,
        params=_params("parse_user_brief", "anthropic", HAIKU, max_tokens=4096, effort="low"),
    )
    assert isinstance(out, dict)
    for key in BRIEF_SCHEMA["required"]:
        assert key in out


async def test_anthropic_opus_judge_smoke(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    candidates = [
        CandidateRef(
            content_hash=f"c{i}",
            caption=caption,
            quality_score=0.8,
            narrative_relevance=0.7,
            capture_timestamp=f"2026-06-0{i + 1}T10:00:00",
            capture_source="exif",
        )
        for i, caption in enumerate(
            ["arrival at the trailhead", "family on the canyon rim", "sunset over the river"]
        )
    ]
    prompt = prompts.render(
        prompts.load("judge_narrative_arc", "anthropic", OPUS[0]),
        brief="a short chronological recap of a canyon hike",
        target_duration_seconds=9,
        mode="standard",
        music_spec=None,
        candidates=candidates,
    )
    arc = await client.judge_narrative_arc(
        candidates,
        prompt_template=prompt,
        brief="a short chronological recap of a canyon hike",
        target_duration=9,
        mode="standard",
        music_spec=None,
        params=_params("judge_narrative_arc", "anthropic", OPUS, max_tokens=20000, effort="high"),
    )
    assert arc.selected_items
    assert 0.0 <= arc.confidence <= 1.0


# ---- Google: embeddings, title image, the Tier-S fallback ----------------


async def test_google_embed_image_and_text_land_in_the_same_space(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    image = await client.embed_image(_tiny_jpeg(), params=_params("embed_image", "google", EMBED))
    text = await client.embed_text(
        "a plain magenta square", params=_params("embed_text", "google", EMBED)
    )
    assert image.shape == (768,) and text.shape == (768,)
    assert image.dtype.name == "float32" and text.dtype.name == "float32"


async def test_google_title_background_is_a_16_9_1k_image(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    params = _params("generate_title_background", "google", TITLE_IMAGE)
    params.temperature = 0.6
    params.extra["aspect_ratio"] = "16:9"
    try:
        data = await client.generate_image(
            "A cinematic, painterly title-card background, widescreen, no text anywhere: "
            "red sandstone canyon at golden hour.",
            params=params,
        )
    except LLMOperationFailed as exc:
        text = str(exc)
        if "RESOURCE_EXHAUSTED" in text and "Free Tier" in text and "limit: 0" in text:
            pytest.skip("this Google key is on the Free Tier, which has no image-generation quota")
        raise
    with Image.open(io.BytesIO(data)) as img:
        w, h = img.size
    assert w > h, (w, h)
    assert abs(w / h - 16 / 9) < 0.05, (w, h)
    assert params.usage_output_tokens > 0


async def test_google_flash_lite_fallback_caption_and_metadata(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    caption = await client.caption_image(
        _tiny_jpeg(),
        prompt_template="Describe this image in one short sentence.",
        params=_params("caption_image", "google", FLASH_LITE, effort="minimal"),
    )
    assert caption.strip()
    out = await client.extract_metadata_image(
        _tiny_jpeg(),
        prompt_template="Extract the mood and primary color of this image.",
        schema={
            "type": "object",
            "required": ["mood", "primary_color"],
            "properties": {"mood": {"type": "string"}, "primary_color": {"type": "string"}},
        },
        params=_params("extract_metadata_image", "google", FLASH_LITE, effort="minimal"),
    )
    assert "mood" in out and "primary_color" in out
