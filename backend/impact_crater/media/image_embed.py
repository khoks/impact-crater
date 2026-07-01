"""Pluggable image-embedder backends (S-2.10.8, ADR-0018).

Mirrors the cast face-embed cloud-default/local-optional pattern. The default
`RouterImageEmbedder` delegates to the existing caption-then-embed router op, so
the default path is byte-for-byte unchanged. A local CLIP/SigLIP backend can be
selected by the `image_embed_backend` setting; it is a STUB here (returns None →
the caller falls back to the router op) because loading weights requires GPU and
weights are never pulled into the repo/env.

Hard requirement for the future real backend: local vectors MUST be written under
a distinct cache namespace (the router cache key does not include the media-layer
backend), or caption-space and CLIP-space vectors would collide in the 0.93
cosine dedup and corrupt selection. The stub never populates the cache.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger(__name__)


@runtime_checkable
class ImageEmbedder(Protocol):
    backend: str

    async def embed_image(self, image_bytes: bytes, *, content_hash: str) -> Any | None: ...


class RouterImageEmbedder:
    """Default — delegates to the router's caption-then-embed op (today's path)."""

    backend = "router"

    def __init__(self, router: Any) -> None:
        self._router = router

    async def embed_image(self, image_bytes: bytes, *, content_hash: str) -> Any | None:
        return await self._router.embed_image(image_bytes, content_hash=content_hash)


class LocalClipImageEmbedder:
    """STUB — a local CLIP/SigLIP backend. Returns None until a real model is
    present (the caller then falls back to the router op). Lazy-imports and never
    downloads weights at import time (CLAUDE.md hard rule)."""

    backend = "local_clip"

    def __init__(self) -> None:
        self._model = None

    async def embed_image(self, image_bytes: bytes, *, content_hash: str) -> Any | None:
        # A real implementation would lazy-import open_clip / siglip, load weights
        # from the user's cache on first use, and return a unit vector under a
        # distinct cache namespace. Until then, signal "unavailable" so the caller
        # falls back to the routed op.
        return None


def build_image_embedder(backend: str | None, router: Any) -> ImageEmbedder:
    """Factory: 'router' (default) | 'local_clip' (opt-in, stub). Unknown → router."""
    chosen = (backend or "router").strip().lower()
    if chosen == "local_clip":
        return LocalClipImageEmbedder()
    if chosen not in ("router", ""):
        log.warning("unknown image_embed_backend %r — falling back to router", backend)
    return RouterImageEmbedder(router)


async def embed_with_fallback(
    embedder: ImageEmbedder | None, router: Any, image_bytes: bytes, *, content_hash: str
) -> Any:
    """Use the selected embedder; if it returns None (or is absent), fall back to
    the router op so a vector always lands."""
    if embedder is not None:
        v = await embedder.embed_image(image_bytes, content_hash=content_hash)
        if v is not None:
            return v
    return await router.embed_image(image_bytes, content_hash=content_hash)
