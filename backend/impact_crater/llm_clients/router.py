"""LLMRouter — central dispatch per ADR-0007 + ADR-0009.

Reads `config/llm-routing.yaml` at construction time. For each operation,
resolves provider+model+model_version+max_tokens+temperature, loads the
matching prompt template, checks the read-through cache, dispatches to
the appropriate LLMClient on miss, and writes the result back.

Cache reuse is keyed on `content_hash` — caller must supply it for any
operation that consumes per-asset bytes (caption_image, score_image,
extract_metadata_image, embed_image). Operations that don't consume bytes
(parse_user_brief, judge_narrative_arc, recommend_*, explain_*) are
keyed on a deterministic hash of their input arguments.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from impact_crater.llm_clients import cache, prompts
from impact_crater.llm_clients.base import (
    ArcJudgment,
    CallParams,
    CandidateRef,
    Embedding,
    LLMClient,
    MusicSpec,
)
from impact_crater.llm_clients.exceptions import LLMOperationFailed

# Repo-root-relative `config/llm-routing.yaml`.
_CONFIG_PATH_DEFAULT = Path(__file__).resolve().parents[3] / "config" / "llm-routing.yaml"


@dataclass(frozen=True)
class OperationRoute:
    """Resolved routing entry for one operation."""

    operation: str
    provider: str
    model: str
    model_version: str
    tier: str
    max_tokens: int
    temperature: float


class LLMRouter:
    """Dispatches LLM operations through the cost-tiered provider lineup."""

    def __init__(
        self,
        clients: dict[str, LLMClient],
        *,
        config_path: Path | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        Args:
            clients: provider-name → LLMClient instance (e.g. {"anthropic": ...,
                     "google": ...}). The router never instantiates clients itself.
            config_path: explicit path to the YAML routing config; defaults to
                         repo-root config/llm-routing.yaml.
            overrides: per-operation overrides to merge over the YAML config
                       (e.g. effort-level per-job overrides per D-013).
        """
        self._clients = clients
        self._routes = _load_routes(config_path or _CONFIG_PATH_DEFAULT, overrides or {})

    # -- Introspection ---------------------------------------------------

    def route_for(self, operation: str) -> OperationRoute:
        """Return the resolved routing entry for `operation`.

        Raises KeyError if the operation isn't in the config.
        """
        if operation not in self._routes:
            raise KeyError(f"operation {operation!r} has no routing entry")
        return self._routes[operation]

    # -- Operation dispatch ----------------------------------------------

    async def caption_image(
        self,
        image_bytes: bytes,
        *,
        content_hash: str,
        prompt_vars: dict[str, Any] | None = None,
    ) -> str:
        op = "caption_image"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(prompt, **(prompt_vars or {}))
        params = self._params(route)

        params_canonical = cache.canonicalize_params({})
        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            return str(cached)

        result = await client.caption_image(image_bytes, prompt_template=rendered, params=params)
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        return result

    async def score_image(
        self,
        image_bytes: bytes,
        *,
        content_hash: str,
        dimension: str,
        prompt_vars: dict[str, Any] | None = None,
    ) -> float:
        op = "score_image"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(prompt, dimension=dimension, **(prompt_vars or {}))
        params = self._params(route)

        params_canonical = cache.canonicalize_params({"dimension": dimension})
        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            return float(cached)

        result = await client.score_image(
            image_bytes,
            prompt_template=rendered,
            dimension=dimension,
            params=params,
        )
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        return result

    async def extract_metadata_image(
        self,
        image_bytes: bytes,
        *,
        content_hash: str,
        schema: dict[str, Any],
        prompt_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        op = "extract_metadata_image"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(prompt, **(prompt_vars or {}))
        params = self._params(route)

        params_canonical = cache.canonicalize_params({"schema_hash": _hash_dict(schema)})
        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            assert isinstance(cached, dict)
            return cached

        result = await client.extract_metadata_image(
            image_bytes,
            prompt_template=rendered,
            schema=schema,
            params=params,
        )
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        return result

    async def embed_image(self, image_bytes: bytes, *, content_hash: str) -> Embedding:
        op = "embed_image"
        route = self.route_for(op)
        client = self._client_for(route)
        params = self._params(route)
        # Embedding ops have no prompt template — version is the model version itself.
        prompt_version = route.model_version
        params_canonical = cache.canonicalize_params({})
        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            return cached  # numpy ndarray

        result = await client.embed_image(image_bytes, params=params)
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt_version,
            params_canonical=params_canonical,
        )
        return result

    async def embed_text(self, text: str, *, cache_key_text: str | None = None) -> Embedding:
        """Embed text. The cache key uses sha256(text) unless `cache_key_text`
        is supplied (allows callers to canonicalize first — e.g. lowercase /
        strip whitespace).
        """
        op = "embed_text"
        route = self.route_for(op)
        client = self._client_for(route)
        params = self._params(route)
        keyed = cache_key_text if cache_key_text is not None else text
        content_hash = hashlib.sha256(keyed.encode("utf-8")).hexdigest()
        prompt_version = route.model_version
        params_canonical = cache.canonicalize_params({})

        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            return cached

        result = await client.embed_text(text, params=params)
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt_version,
            params_canonical=params_canonical,
        )
        return result

    async def judge_narrative_arc(
        self,
        candidates: list[CandidateRef],
        *,
        brief: str,
        target_duration: int,
        mode: Literal["standard", "music_video"] = "standard",
        music_spec: MusicSpec | None = None,
    ) -> ArcJudgment:
        """N-001 Stage-5 narrative judgment. Cache key includes the full input
        because brief / target_duration / candidate_set drive the result.
        """
        op = "judge_narrative_arc"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(
            prompt,
            brief=brief,
            target_duration_seconds=target_duration,
            mode=mode,
            music_spec=music_spec,
            candidates=candidates,
        )
        params = self._params(route)

        # Full-input cache key — repeating an identical judge call is rare but cheap to handle.
        input_signature = {
            "brief": brief,
            "target_duration": target_duration,
            "mode": mode,
            "music_spec": _music_spec_dict(music_spec),
            "candidates": [
                {
                    "ref": c.candidate_ref if hasattr(c, "candidate_ref") else None,
                    "ch": c.content_hash,
                    "si": c.scene_index,
                    "qs": c.quality_score,
                    "nr": c.narrative_relevance,
                }
                for c in candidates
            ],
        }
        content_hash = hashlib.sha256(
            cache.canonicalize_params(input_signature).encode("utf-8")
        ).hexdigest()
        params_canonical = cache.canonicalize_params({})

        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            assert isinstance(cached, ArcJudgment)
            return cached

        result = await client.judge_narrative_arc(
            candidates,
            prompt_template=rendered,
            brief=brief,
            target_duration=target_duration,
            mode=mode,
            music_spec=music_spec,
            params=params,
        )
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        return result

    async def parse_user_brief(
        self,
        text: str,
        *,
        schema: dict[str, Any],
        prompt_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        op = "parse_user_brief"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        merged_vars = {"user_brief": text, "hints": None}
        merged_vars.update(prompt_vars or {})
        rendered = prompts.render(prompt, **merged_vars)
        params = self._params(route)

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        params_canonical = cache.canonicalize_params({"schema_hash": _hash_dict(schema)})
        cached = await cache.get(
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        if cached is not None:
            assert isinstance(cached, dict)
            return cached

        result = await client.parse_user_brief(
            text,
            prompt_template=rendered,
            schema=schema,
            params=params,
        )
        await cache.put(
            result,
            content_hash=content_hash,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            operation=op,
            prompt_version=prompt.prompt_version,
            params_canonical=params_canonical,
        )
        return result

    # -- Internal helpers -----------------------------------------------

    def _client_for(self, route: OperationRoute) -> LLMClient:
        if route.provider not in self._clients:
            raise LLMOperationFailed(
                operation=route.operation,
                provider=route.provider,
                model=route.model,
                attempts=0,
                last_error=f"no LLMClient registered for provider {route.provider!r}",
            )
        return self._clients[route.provider]

    def _params(self, route: OperationRoute) -> CallParams:
        return CallParams(
            operation=route.operation,
            provider=route.provider,
            model=route.model,
            model_version=route.model_version,
            max_tokens=route.max_tokens,
            temperature=route.temperature,
        )


# ---- Module helpers ----------------------------------------------------


def _load_routes(
    config_path: Path,
    overrides: dict[str, dict[str, Any]],
) -> dict[str, OperationRoute]:
    """Parse the YAML config and merge overrides into the in-memory route table."""
    if not config_path.is_file():
        raise FileNotFoundError(f"llm routing config not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    defaults = raw.get("defaults", {}) or {}
    default_max_tokens = int(defaults.get("max_tokens", 1024))
    default_temperature = float(defaults.get("temperature", 0.0))

    out: dict[str, OperationRoute] = {}
    operations = raw.get("operations", {}) or {}
    for op_name, op_cfg in operations.items():
        merged = dict(op_cfg)
        if op_name in overrides:
            merged.update(overrides[op_name])
        out[op_name] = OperationRoute(
            operation=op_name,
            provider=str(merged["provider"]),
            model=str(merged["model"]),
            model_version=str(merged.get("model_version", "v1")),
            tier=str(merged.get("tier", "")),
            max_tokens=int(merged.get("max_tokens", default_max_tokens)),
            temperature=float(merged.get("temperature", default_temperature)),
        )
    return out


def _hash_dict(d: dict[str, Any]) -> str:
    return hashlib.sha256(
        cache.canonicalize_params(d).encode("utf-8")
    ).hexdigest()[:16]


def _music_spec_dict(ms: MusicSpec | None) -> dict[str, Any] | None:
    if ms is None:
        return None
    return {
        "duration_ms": ms.duration_ms,
        "bpm": ms.bpm,
        "section_to_media_nl": ms.section_to_media_nl,
    }
