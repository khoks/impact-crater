"""Read-through cache layer for LLM operations per ADR-0006 (cache_index)
+ ADR-0007 (LLM abstraction) + A-011 / N-007 (cross-job content-addressed
analysis cache).

Cache key:
    sha256(content_hash + provider + model + model_version + operation
           + prompt_version + params_canonical)

Cache path:
    ~/.impact-crater/cache/{content_hash}/{provider}_{model}_{model_version}/
        {operation}_{prompt_version}.{json|npy}

Embeddings (numpy ndarray) → .npy via numpy.save / numpy.load.
Everything else (str, dict, ArcJudgment) → .json (ArcJudgment serialized
through `dataclasses.asdict`).

Cache hits skip the LLM call entirely. Misses dispatch to the underlying
client and write-through on success.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from impact_crater import paths
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.storage.db import connection


def cache_key(
    *,
    content_hash: str,
    provider: str,
    model: str,
    model_version: str,
    operation: str,
    prompt_version: str,
    params_canonical: str,
) -> str:
    """Compute the deterministic cache key per ADR-0006."""
    raw = "\x1f".join(
        [content_hash, provider, model, model_version, operation, prompt_version, params_canonical]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonicalize_params(extra: dict[str, Any]) -> str:
    """Produce a deterministic JSON encoding of per-call params for the key.

    Sorted keys + compact separators ensure identical inputs hash identically.
    Only `extra` participates in the key — model + temperature + max_tokens
    are already in the routing key.
    """
    return json.dumps(extra, sort_keys=True, separators=(",", ":"))


def _payload_path(
    *,
    content_hash: str,
    provider: str,
    model: str,
    model_version: str,
    operation: str,
    prompt_version: str,
    suffix: str,
) -> Path:
    """Resolve the on-disk path for a cache payload."""
    base = paths.cache_dir() / content_hash / f"{provider}_{model}_{model_version}"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{operation}_{prompt_version[:16]}{suffix}"


# ---- Read --------------------------------------------------------------


async def get(
    *,
    content_hash: str,
    provider: str,
    model: str,
    model_version: str,
    operation: str,
    prompt_version: str,
    params_canonical: str,
) -> Any | None:
    """Return cached payload or None.

    Decoder is chosen by the file's suffix as recorded in cache_index.cache_path.
    """
    key = cache_key(
        content_hash=content_hash,
        provider=provider,
        model=model,
        model_version=model_version,
        operation=operation,
        prompt_version=prompt_version,
        params_canonical=params_canonical,
    )
    async with connection() as db:
        cursor = await db.execute(
            "SELECT cache_path FROM cache_index WHERE cache_key = ?", (key,)
        )
        row = await cursor.fetchone()
    if not row:
        return None
    cache_path = Path(row["cache_path"])
    if not cache_path.is_file():
        # Stale index entry; treat as miss. The next put() will overwrite.
        return None
    return _decode(cache_path, operation)


# ---- Write -------------------------------------------------------------


async def put(
    payload: Any,
    *,
    content_hash: str,
    provider: str,
    model: str,
    model_version: str,
    operation: str,
    prompt_version: str,
    params_canonical: str,
    privacy_class: str | None = None,
    library_version_hash: str | None = None,
) -> None:
    """Write payload to disk + record in cache_index. Idempotent on conflict."""
    key = cache_key(
        content_hash=content_hash,
        provider=provider,
        model=model,
        model_version=model_version,
        operation=operation,
        prompt_version=prompt_version,
        params_canonical=params_canonical,
    )
    suffix, encoded = _encode(payload, operation)
    cache_path = _payload_path(
        content_hash=content_hash,
        provider=provider,
        model=model,
        model_version=model_version,
        operation=operation,
        prompt_version=prompt_version,
        suffix=suffix,
    )
    if isinstance(encoded, bytes):
        cache_path.write_bytes(encoded)
    else:
        cache_path.write_text(encoded, encoding="utf-8")

    async with connection() as db:
        await db.execute(
            """
            INSERT INTO cache_index
                (cache_key, content_hash, provider, model, model_version,
                 operation, prompt_version, params_canonical, cache_path,
                 privacy_class, library_version_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                cache_path = excluded.cache_path,
                computed_at = CURRENT_TIMESTAMP
            """,
            (
                key,
                content_hash,
                provider,
                model,
                model_version,
                operation,
                prompt_version,
                params_canonical,
                str(cache_path),
                privacy_class,
                library_version_hash,
            ),
        )
        await db.commit()


# ---- Encoding helpers --------------------------------------------------


def _encode(payload: Any, operation: str) -> tuple[str, str | bytes]:
    """Pick encoder (.json text vs .npy bytes) and return (suffix, blob)."""
    if isinstance(payload, np.ndarray):
        import io

        buf = io.BytesIO()
        np.save(buf, payload, allow_pickle=False)
        return (".npy", buf.getvalue())
    if isinstance(payload, ArcJudgment):
        return (".json", json.dumps(asdict(payload), separators=(",", ":")))
    if is_dataclass(payload) and not isinstance(payload, type):
        return (".json", json.dumps(asdict(payload), separators=(",", ":")))
    if isinstance(payload, (dict, list)):
        return (".json", json.dumps(payload, separators=(",", ":")))
    if isinstance(payload, str):
        return (".json", json.dumps({"_str": payload}))
    if isinstance(payload, (int, float, bool)):
        return (".json", json.dumps({"_scalar": payload}))
    raise TypeError(f"unsupported cache payload type for {operation!r}: {type(payload).__name__}")


def _decode(path: Path, operation: str) -> Any:
    """Reverse of _encode. Returns the original Python type."""
    if path.suffix == ".npy":
        return np.load(path, allow_pickle=False)
    raw = path.read_text(encoding="utf-8")
    obj = json.loads(raw)
    if operation == "judge_narrative_arc":
        return ArcJudgment(
            selected_items=[SelectedItem(**si) for si in obj["selected_items"]],
            arc_reasoning=obj["arc_reasoning"],
            confidence=obj["confidence"],
            open_questions=obj.get("open_questions", []),
            section_mapping=obj.get("section_mapping"),
        )
    if isinstance(obj, dict) and "_str" in obj and len(obj) == 1:
        return obj["_str"]
    if isinstance(obj, dict) and "_scalar" in obj and len(obj) == 1:
        return obj["_scalar"]
    return obj
