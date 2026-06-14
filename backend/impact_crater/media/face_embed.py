"""Pluggable face-identity embedders (A-018 / N-012).

Per the 2026-06-11 decision (D-044): a lightweight cloud default plus an
optional local upgrade for capable machines, mirroring the project's
hardware-tier routing philosophy.

  - `gemini`  (default) — reuse the already-wired image-embedding route
    on each face crop. Zero new dependency; general-purpose embeddings are
    weaker for identity (may merge look-alikes or split one person across
    outfits), so clustering thresholds are conservative. Good rough cut.
  - `insightface` (optional) — real ArcFace face-recognition embeddings.
    Accurate person clustering. Lazy-imported so the dependency is only
    needed when the user selects it; the model auto-downloads on first use.

Every embedder takes face-crop JPEG bytes and returns one unit-normalized
embedding per crop (or None when it can't embed that crop).
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

log = logging.getLogger(__name__)

FaceVector = NDArray[np.float32]

# Cosine-similarity threshold for "same person", tuned per backend. ArcFace
# embeddings are far more identity-discriminative than general image
# embeddings, so insightface can use a tighter, more confident threshold.
CLUSTER_THRESHOLD: dict[str, float] = {
    "gemini": 0.82,
    "insightface": 0.45,
}

DEFAULT_BACKEND = "gemini"


class FaceEmbedder(Protocol):
    backend: str

    async def embed_face_crops(self, crops: list[bytes]) -> list[FaceVector | None]: ...


def _unit(vec: FaceVector | None) -> FaceVector | None:
    if vec is None:
        return None
    v = np.asarray(vec, dtype=np.float32).ravel()
    n = float(np.linalg.norm(v))
    if v.size == 0 or n == 0.0:
        return None
    return v / n


# ---- Default: reuse the general image embedder -------------------------


class GeminiFaceEmbedder:
    """Embed face crops via the already-wired `router.embed_image` route.

    Cheap (Tier-embedding) and cached by crop-content hash, so re-running a
    job re-uses the work. Identity accuracy is rough — see module docstring.
    """

    backend = "gemini"

    def __init__(self, router: object) -> None:
        self._router = router

    async def embed_face_crops(self, crops: list[bytes]) -> list[FaceVector | None]:
        out: list[FaceVector | None] = []
        for crop in crops:
            if not crop:
                out.append(None)
                continue
            content_hash = "face-" + hashlib.sha256(crop).hexdigest()[:24]
            try:
                vec = await self._router.embed_image(crop, content_hash=content_hash)  # type: ignore[attr-defined]
            except Exception as exc:
                log.warning("face embed failed (%s); skipping crop", str(exc)[:120])
                out.append(None)
                continue
            out.append(_unit(vec))
        return out


# ---- Optional: real ArcFace embeddings ---------------------------------


class InsightFaceEmbedder:
    """ArcFace embeddings via insightface. Optional, configurable backend.

    Lazy-loads the model once. If insightface isn't installed we degrade to
    returning all-None (the caller treats every face as its own person),
    rather than crashing — the dependency is opt-in.
    """

    backend = "insightface"

    def __init__(self) -> None:
        self._app = None

    def _ensure_app(self) -> Any:
        if self._app is not None:
            return self._app
        try:
            from insightface.app import FaceAnalysis
        except ImportError:
            log.warning(
                "insightface backend selected but the package is not installed; "
                "falling back to no-embedding (each face becomes its own person)"
            )
            return None
        app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"])
        app.prepare(ctx_id=-1)  # CPU; capable machines can switch to GPU later
        self._app = app
        return app

    async def embed_face_crops(self, crops: list[bytes]) -> list[FaceVector | None]:
        import asyncio

        app = self._ensure_app()
        if app is None:
            return [None] * len(crops)
        return await asyncio.to_thread(self._embed_sync, app, crops)

    def _embed_sync(self, app: Any, crops: list[bytes]) -> list[FaceVector | None]:
        from PIL import Image

        out: list[FaceVector | None] = []
        for crop in crops:
            try:
                img = np.array(Image.open(io.BytesIO(crop)).convert("RGB"))[:, :, ::-1]  # RGB→BGR
                faces = app.get(img)
            except Exception as exc:
                log.warning("insightface embed failed (%s); skipping crop", str(exc)[:120])
                out.append(None)
                continue
            if not faces:
                out.append(None)
                continue
            best = max(faces, key=lambda f: float(getattr(f, "det_score", 0.0)))
            out.append(_unit(np.asarray(best.normed_embedding, dtype=np.float32)))
        return out


# ---- Factory -----------------------------------------------------------


def build_face_embedder(backend: str | None, router: object) -> FaceEmbedder:
    """Resolve the configured backend to an embedder instance.

    Unknown / None → the default Gemini embedder.
    """
    chosen = (backend or DEFAULT_BACKEND).strip().lower()
    if chosen == "insightface":
        return InsightFaceEmbedder()
    return GeminiFaceEmbedder(router)
