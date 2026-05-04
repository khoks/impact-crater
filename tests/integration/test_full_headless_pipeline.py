"""End-to-end integration test for the M1 headless pipeline.

Hits real Anthropic + Google APIs through the LLMRouter. Gated behind
`--integration` (per tests/conftest.py). Uses 4 small synthetic JPEGs
to keep token usage tiny while still exercising the full Stage 1 → 5
flow: ingest → bulk ops → metadata → pre-filter → narrative judgment.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from PIL import Image

from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.base import ArcJudgment
from impact_crater.llm_clients.google_client import GoogleLLMClient
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.pipeline.runner import HeadlessJobConfig, run_headless_pipeline
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations

pytestmark = pytest.mark.integration


def _tiny_jpeg(color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (96, 96), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=78)
    return buf.getvalue()


@pytest.fixture
async def real_router_keys() -> tuple[str, str]:
    a = os.environ.get("ANTHROPIC_API_KEY")
    g = os.environ.get("GOOGLE_API_KEY")
    if not a or not g:
        pytest.skip("ANTHROPIC_API_KEY + GOOGLE_API_KEY required for full-pipeline integration")
    return (a, g)


async def test_full_headless_pipeline_real_apis(
    tmp_path: Path,
    real_router_keys: tuple[str, str],
) -> None:
    """End-to-end Stage 1-5 against real APIs, returning a structured ArcJudgment."""
    # 4 distinctly-colored 96×96 JPEGs — keeps token spend small but gives
    # the pipeline a few candidates to choose between.
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    paths: list[Path] = []
    for i, color in enumerate(
        [(200, 80, 30), (40, 200, 100), (60, 60, 220), (220, 220, 40)]
    ):
        p = media_dir / f"photo-{i}.jpg"
        p.write_bytes(_tiny_jpeg(color))
        paths.append(p)

    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")

    a_key, g_key = real_router_keys
    router = LLMRouter(
        clients={
            "anthropic": AnthropicLLMClient(api_key=a_key),
            "google": GoogleLLMClient(api_key=g_key),
        },
    )

    config = HeadlessJobConfig(
        media_paths=paths,
        brief="A short montage of colorful test patterns. Order from warm to cool tones.",
        target_duration_seconds=10,
    )
    result = await run_headless_pipeline(config, router=router)

    assert result.media_count == 4
    assert isinstance(result.arc_judgment, ArcJudgment)
    assert 0.0 <= result.arc_judgment.confidence <= 1.0
    assert len(result.arc_judgment.selected_items) >= 1
    for item in result.arc_judgment.selected_items:
        assert item.candidate_ref
        assert item.intended_duration_ms > 0
        assert item.role
    # Pre-filter envelope sanity:
    assert result.candidate_set.floor >= 1
    assert result.candidate_set.ceiling >= result.candidate_set.floor
    # Quota was honored.
    assert result.quota_snapshot["allowed"] is True
