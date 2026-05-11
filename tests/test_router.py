"""Unit tests for the LLMRouter + prompts loader + cache layer.

Covers:
  - YAML routing config parsing + override merging
  - Prompt template loading + sha256 versioning
  - Cache miss → client dispatch → write-through
  - Cache hit → no client dispatch
  - Different prompt versions / different schemas → different cache entries
  - Provider missing → LLMOperationFailed
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import numpy as np
import pytest
import yaml

from impact_crater.llm_clients import prompts
from impact_crater.llm_clients.base import (
    ArcJudgment,
    CallParams,
    CandidateRef,
    SelectedItem,
)
from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.llm_clients.router import LLMRouter, OperationRoute
from impact_crater.storage.migrations import run_pending_migrations


# ---- Fixtures ----------------------------------------------------------


@pytest.fixture
def routing_config(tmp_path: Path) -> Path:
    """A minimal in-test routing config the router can load."""
    cfg = {
        "defaults": {"max_tokens": 512, "temperature": 0.0},
        "operations": {
            "caption_image": {
                "provider": "google",
                "model": "gemini-2.5-flash",
                "model_version": "v1",
                "tier": "S",
                "max_tokens": 256,
            },
            "extract_metadata_image": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5",
                "model_version": "latest",
                "tier": "M",
                "max_tokens": 2048,
            },
            "judge_narrative_arc": {
                "provider": "anthropic",
                "model": "claude-opus-4-5",
                "model_version": "latest",
                "tier": "L",
                "max_tokens": 4096,
            },
            "embed_text": {
                "provider": "google",
                "model": "gemini-embedding-001",
                "model_version": "v1",
                "tier": "embedding",
            },
        },
    }
    path = tmp_path / "llm-routing.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


@pytest.fixture
def prompts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-test prompts root so we don't depend on the shipped templates."""
    root = tmp_path / "prompts"
    for op, provider, model, body in [
        ("caption_image", "google", "gemini-2.5-flash", "Describe this image: {{ extra or '' }}"),
        (
            "extract_metadata_image",
            "anthropic",
            "claude-sonnet-4-5",
            "Extract metadata. brief={{ context_brief or '' }}",
        ),
        (
            "judge_narrative_arc",
            "anthropic",
            "claude-opus-4-5",
            "Judge arc. brief={{ brief }} target={{ target_duration_seconds }}s "
            "mode={{ mode }} candidates={{ candidates|length }}",
        ),
    ]:
        op_dir = root / op
        op_dir.mkdir(parents=True, exist_ok=True)
        (op_dir / f"{provider}_{model}.jinja2").write_text(body, encoding="utf-8")

    monkeypatch.setenv("IMPACT_CRATER_PROMPTS_DIR", str(root))
    prompts.clear_cache()
    yield root
    prompts.clear_cache()


@pytest.fixture
async def db_initialized() -> None:
    """Run migrations against the (per-test) isolated_home SQLite."""
    await run_pending_migrations()


def _mock_client(provider: str) -> Any:
    """Build a SimpleNamespace-ish mock LLMClient with all methods stubbed."""
    client = AsyncMock()
    client.provider = provider
    return client


# ---- Routing config parsing -------------------------------------------


def test_router_loads_yaml_and_resolves_route(routing_config: Path) -> None:
    router = LLMRouter(clients={}, config_path=routing_config)
    route = router.route_for("caption_image")
    assert isinstance(route, OperationRoute)
    assert route.provider == "google"
    assert route.model == "gemini-2.5-flash"
    assert route.model_version == "v1"
    assert route.tier == "S"
    assert route.max_tokens == 256
    assert route.temperature == 0.0


def test_router_unknown_operation_raises(routing_config: Path) -> None:
    router = LLMRouter(clients={}, config_path=routing_config)
    with pytest.raises(KeyError):
        router.route_for("nonexistent_op")


def test_router_overrides_merge_per_operation(routing_config: Path) -> None:
    router = LLMRouter(
        clients={},
        config_path=routing_config,
        overrides={
            "caption_image": {"model": "gemini-2.5-pro", "max_tokens": 1024},
        },
    )
    route = router.route_for("caption_image")
    assert route.model == "gemini-2.5-pro"
    assert route.max_tokens == 1024
    # Untouched fields keep their YAML values.
    assert route.provider == "google"
    assert route.tier == "S"


def test_router_missing_provider_raises_on_dispatch(routing_config: Path) -> None:
    router = LLMRouter(clients={}, config_path=routing_config)
    with pytest.raises(LLMOperationFailed) as excinfo:
        router._client_for(router.route_for("caption_image"))
    assert "no LLMClient registered" in str(excinfo.value)


# ---- Prompts loader ---------------------------------------------------


def test_prompts_loader_versions_by_content_hash(prompts_dir: Path) -> None:
    p1 = prompts.load("caption_image", "google", "gemini-2.5-flash")
    expected = hashlib.sha256(p1.template_text.encode("utf-8")).hexdigest()
    assert p1.prompt_version == expected

    # Mutate the file → version must change after cache clear.
    target = prompts_dir / "caption_image" / "google_gemini-2.5-flash.jinja2"
    target.write_text("Different content {{ extra or '' }}", encoding="utf-8")
    prompts.clear_cache()
    p2 = prompts.load("caption_image", "google", "gemini-2.5-flash")
    assert p2.prompt_version != p1.prompt_version


def test_prompts_loader_renders_with_variables(prompts_dir: Path) -> None:
    p = prompts.load("caption_image", "google", "gemini-2.5-flash")
    out = prompts.render(p, extra="and be brief")
    assert "Describe this image: and be brief" == out


def test_prompts_loader_missing_template_raises(prompts_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        prompts.load("caption_image", "anthropic", "no-such-model")


# ---- Cache hit / miss flow --------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_caption_cache_miss_then_hit(
    routing_config: Path, prompts_dir: Path
) -> None:
    google = _mock_client("google")
    google.caption_image = AsyncMock(return_value="A red apple on a table.")
    router = LLMRouter(clients={"google": google}, config_path=routing_config)

    # First call → miss → client invoked once.
    out1 = await router.caption_image(b"\x00fake-jpg", content_hash="hash-A")
    assert out1 == "A red apple on a table."
    assert google.caption_image.await_count == 1

    # Second call (same content_hash, same prompt) → hit → no further calls.
    out2 = await router.caption_image(b"\x00fake-jpg", content_hash="hash-A")
    assert out2 == "A red apple on a table."
    assert google.caption_image.await_count == 1


@pytest.mark.usefixtures("db_initialized")
async def test_caption_different_content_hashes_dont_share_cache(
    routing_config: Path, prompts_dir: Path
) -> None:
    google = _mock_client("google")
    google.caption_image = AsyncMock(side_effect=["caption A", "caption B"])
    router = LLMRouter(clients={"google": google}, config_path=routing_config)

    out_a = await router.caption_image(b"\x00aaa", content_hash="hash-A")
    out_b = await router.caption_image(b"\x00bbb", content_hash="hash-B")
    assert out_a == "caption A"
    assert out_b == "caption B"
    assert google.caption_image.await_count == 2


@pytest.mark.usefixtures("db_initialized")
async def test_extract_metadata_schema_change_invalidates_cache(
    routing_config: Path, prompts_dir: Path
) -> None:
    anthropic = _mock_client("anthropic")
    anthropic.extract_metadata_image = AsyncMock(
        side_effect=[{"v": 1}, {"v": 2}]
    )
    router = LLMRouter(clients={"anthropic": anthropic}, config_path=routing_config)

    schema_v1 = {"type": "object", "required": ["v"], "properties": {"v": {"type": "integer"}}}
    schema_v2 = {
        "type": "object",
        "required": ["v", "x"],
        "properties": {"v": {"type": "integer"}, "x": {"type": "string"}},
    }
    out_v1 = await router.extract_metadata_image(
        b"\x00img", content_hash="hash-A", schema=schema_v1
    )
    out_v2 = await router.extract_metadata_image(
        b"\x00img", content_hash="hash-A", schema=schema_v2
    )
    assert out_v1 == {"v": 1}
    assert out_v2 == {"v": 2}
    assert anthropic.extract_metadata_image.await_count == 2


@pytest.mark.usefixtures("db_initialized")
async def test_prompt_version_change_invalidates_cache(
    routing_config: Path, prompts_dir: Path
) -> None:
    google = _mock_client("google")
    google.caption_image = AsyncMock(side_effect=["v1 caption", "v2 caption"])
    router = LLMRouter(clients={"google": google}, config_path=routing_config)

    out_v1 = await router.caption_image(b"\x00img", content_hash="hash-A")
    assert out_v1 == "v1 caption"

    # Edit the template + clear the prompt cache → next call should miss.
    target = prompts_dir / "caption_image" / "google_gemini-2.5-flash.jinja2"
    target.write_text("Now describe with style: {{ extra or '' }}", encoding="utf-8")
    prompts.clear_cache()

    out_v2 = await router.caption_image(b"\x00img", content_hash="hash-A")
    assert out_v2 == "v2 caption"
    assert google.caption_image.await_count == 2


@pytest.mark.usefixtures("db_initialized")
async def test_embed_text_caches_by_text_hash(routing_config: Path) -> None:
    google = _mock_client("google")
    vec = np.ones((4,), dtype=np.float32)
    google.embed_text = AsyncMock(return_value=vec)
    router = LLMRouter(clients={"google": google}, config_path=routing_config)

    out1 = await router.embed_text("hello world")
    out2 = await router.embed_text("hello world")
    out3 = await router.embed_text("different text")

    np.testing.assert_array_equal(out1, vec)
    np.testing.assert_array_equal(out2, vec)
    np.testing.assert_array_equal(out3, vec)
    # First + third are misses; second is a hit.
    assert google.embed_text.await_count == 2


@pytest.mark.usefixtures("db_initialized")
async def test_judge_narrative_arc_round_trips_through_cache(
    routing_config: Path, prompts_dir: Path
) -> None:
    anthropic = _mock_client("anthropic")
    judgment = ArcJudgment(
        selected_items=[
            SelectedItem(
                candidate_ref="hash1",
                placement_position=0,
                intended_duration_ms=1500,
                role="opener",
            ),
        ],
        arc_reasoning="strong opener",
        confidence=0.8,
        open_questions=[],
    )
    anthropic.judge_narrative_arc = AsyncMock(return_value=judgment)
    router = LLMRouter(clients={"anthropic": anthropic}, config_path=routing_config)

    candidates = [CandidateRef(content_hash="hash1", quality_score=0.9)]
    out1 = await router.judge_narrative_arc(
        candidates,
        brief="family hike",
        target_duration=10,
    )
    out2 = await router.judge_narrative_arc(
        candidates,
        brief="family hike",
        target_duration=10,
    )
    assert isinstance(out1, ArcJudgment)
    assert isinstance(out2, ArcJudgment)
    assert out1.confidence == 0.8
    assert out2.arc_reasoning == "strong opener"
    assert out2.selected_items[0].role == "opener"
    # Second call should be a cache hit.
    assert anthropic.judge_narrative_arc.await_count == 1


@pytest.mark.usefixtures("db_initialized")
async def test_judge_narrative_arc_different_brief_invalidates_cache(
    routing_config: Path, prompts_dir: Path
) -> None:
    anthropic = _mock_client("anthropic")
    j1 = ArcJudgment(selected_items=[], arc_reasoning="brief1", confidence=0.5)
    j2 = ArcJudgment(selected_items=[], arc_reasoning="brief2", confidence=0.5)
    anthropic.judge_narrative_arc = AsyncMock(side_effect=[j1, j2])
    router = LLMRouter(clients={"anthropic": anthropic}, config_path=routing_config)

    candidates = [CandidateRef(content_hash="hash1")]
    await router.judge_narrative_arc(candidates, brief="trip A", target_duration=10)
    await router.judge_narrative_arc(candidates, brief="trip B", target_duration=10)
    assert anthropic.judge_narrative_arc.await_count == 2


# ---- CallParams plumbing ---------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_call_params_pass_through_correctly(
    routing_config: Path, prompts_dir: Path
) -> None:
    google = _mock_client("google")
    google.caption_image = AsyncMock(return_value="ok")
    router = LLMRouter(clients={"google": google}, config_path=routing_config)
    await router.caption_image(b"\x00img", content_hash="hash-A")

    call = google.caption_image.await_args
    params: CallParams = call.kwargs["params"]
    assert params.operation == "caption_image"
    assert params.provider == "google"
    assert params.model == "gemini-2.5-flash"
    assert params.model_version == "v1"
    assert params.max_tokens == 256
    assert params.temperature == 0.0


# ---- Quota wiring (Bug 2 fix from 2026-05-07 UI test) -----------------


@pytest.mark.usefixtures("db_initialized")
async def test_cache_miss_bumps_daily_quota_spend(
    routing_config: Path, prompts_dir: Path
) -> None:
    """Every successful non-cached LLM dispatch must record the cost into
    the quota_state table so Settings → 'Today's spend' reflects reality.

    Real bug: quota.record_spend() was defined + documented as "every
    LLMCallEvent emit triggers exactly one record_spend" but no caller
    ever invoked it. Settings always read $0.00 today regardless of
    actual usage."""
    from impact_crater import quota
    from impact_crater.storage import settings as settings_store

    # Set a cap so check_quota is meaningful; not strictly needed for this test.
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "10.00")

    today_before = await quota.get_today_spend()
    assert today_before.get("_total_", 0.0) == 0.0
    assert today_before.get("google", 0.0) == 0.0

    google = _mock_client("google")
    google.caption_image = AsyncMock(return_value="A red apple.")
    router = LLMRouter(clients={"google": google}, config_path=routing_config)

    # First call is a cache miss → records spend.
    await router.caption_image(b"\x00fake-jpg", content_hash="hash-X")

    today_after_miss = await quota.get_today_spend()
    assert today_after_miss.get("_total_", 0.0) > 0.0
    assert today_after_miss.get("google", 0.0) > 0.0
    assert today_after_miss["_total_"] == pytest.approx(today_after_miss["google"])

    # Second call is a cache hit → NO additional spend recorded.
    miss_total = today_after_miss["_total_"]
    await router.caption_image(b"\x00fake-jpg", content_hash="hash-X")
    today_after_hit = await quota.get_today_spend()
    assert today_after_hit["_total_"] == pytest.approx(miss_total)
