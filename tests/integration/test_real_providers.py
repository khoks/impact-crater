"""Integration smoke tests against real Anthropic + Google APIs.

Gated by `--integration` (per tests/conftest.py). Reads API keys from
.env.test if present, else from system env vars (ANTHROPIC_API_KEY +
GOOGLE_API_KEY).

Each test makes the smallest possible call to validate the SDK + auth
+ schema-handling work end-to-end. Image inputs are tiny synthetic JPEGs
to keep token usage minimal.
"""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import CallParams
from impact_crater.llm_clients.google_client import GoogleLLMClient


pytestmark = pytest.mark.integration


def _tiny_jpeg() -> bytes:
    """A 64×64 solid-color JPEG. Vision LLMs return short generic captions."""
    img = Image.new("RGB", (64, 64), (180, 60, 120))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


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


# ---- Anthropic ---------------------------------------------------------


async def test_anthropic_caption_image_smoke(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    out = await client.caption_image(
        _tiny_jpeg(),
        prompt_template="In one short sentence, describe what you see.",
        params=CallParams(
            operation="caption_image",
            provider="anthropic",
            model="claude-sonnet-4-5",
            model_version="latest",
            max_tokens=64,
        ),
    )
    assert isinstance(out, str)
    assert len(out) > 0


async def test_anthropic_extract_metadata_smoke(anthropic_key: str) -> None:
    client = AnthropicLLMClient(api_key=anthropic_key)
    schema = {
        "type": "object",
        "required": ["mood", "primary_color"],
        "properties": {
            "mood": {"type": "string"},
            "primary_color": {"type": "string"},
        },
    }
    out = await client.extract_metadata_image(
        _tiny_jpeg(),
        prompt_template="Extract the mood and primary color of this image.",
        schema=schema,
        params=CallParams(
            operation="extract_metadata_image",
            provider="anthropic",
            model="claude-sonnet-4-5",
            model_version="latest",
            max_tokens=256,
        ),
    )
    assert isinstance(out, dict)
    assert "mood" in out
    assert "primary_color" in out


# ---- Google ------------------------------------------------------------


async def test_google_embed_text_smoke(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    emb = await client.embed_text(
        "Impact Crater integration test.",
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


async def test_google_caption_image_smoke(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    out = await client.caption_image(
        _tiny_jpeg(),
        prompt_template="Describe this image in one short sentence.",
        params=CallParams(
            operation="caption_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
            max_tokens=64,
        ),
    )
    assert isinstance(out, str)
    assert len(out) > 0


async def test_google_extract_metadata_smoke(google_key: str) -> None:
    client = GoogleLLMClient(api_key=google_key)
    schema = {
        "type": "object",
        "required": ["mood", "primary_color"],
        "properties": {
            "mood": {"type": "string"},
            "primary_color": {"type": "string"},
        },
    }
    out = await client.extract_metadata_image(
        _tiny_jpeg(),
        prompt_template="Extract the mood and primary color of this image.",
        schema=schema,
        params=CallParams(
            operation="extract_metadata_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
            max_tokens=1024,
        ),
    )
    assert isinstance(out, dict)
    assert "mood" in out
    assert "primary_color" in out
