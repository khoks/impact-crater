"""Tests for the pluggable image embedder + fallback (S-2.10.8)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import numpy as np

from impact_crater.media.image_embed import (
    LocalClipImageEmbedder,
    RouterImageEmbedder,
    build_image_embedder,
    embed_with_fallback,
)


def test_build_defaults_to_router() -> None:
    e = build_image_embedder(None, router=object())
    assert isinstance(e, RouterImageEmbedder)
    assert e.backend == "router"


def test_build_local_clip_is_stub() -> None:
    e = build_image_embedder("local_clip", router=object())
    assert isinstance(e, LocalClipImageEmbedder)
    assert e.backend == "local_clip"


def test_unknown_backend_falls_back_to_router() -> None:
    assert isinstance(build_image_embedder("nonsense", router=object()), RouterImageEmbedder)


async def test_router_embedder_delegates() -> None:
    router = AsyncMock()
    vec = np.ones((8,), dtype=np.float32)
    router.embed_image.return_value = vec
    e = RouterImageEmbedder(router)
    out = await e.embed_image(b"x", content_hash="h")
    assert out is vec
    router.embed_image.assert_awaited_once()


async def test_local_clip_stub_returns_none() -> None:
    assert await LocalClipImageEmbedder().embed_image(b"x", content_hash="h") is None


async def test_fallback_uses_router_when_embedder_returns_none() -> None:
    router = AsyncMock()
    vec = np.ones((8,), dtype=np.float32)
    router.embed_image.return_value = vec
    out = await embed_with_fallback(LocalClipImageEmbedder(), router, b"x", content_hash="h")
    assert out is vec  # stub returned None → routed op used
    router.embed_image.assert_awaited_once()


async def test_fallback_uses_embedder_vector_without_calling_router() -> None:
    router = AsyncMock()
    local = AsyncMock()
    my_vec = np.arange(8, dtype=np.float32)
    local.embed_image.return_value = my_vec
    out = await embed_with_fallback(local, router, b"x", content_hash="h")
    assert out is my_vec
    router.embed_image.assert_not_awaited()  # local vector used verbatim
