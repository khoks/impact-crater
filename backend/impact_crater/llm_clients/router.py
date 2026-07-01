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

Per-call telemetry: every dispatch (cache hit or miss) emits an
`LLMCallEvent` so `JobCostSummary` can aggregate cost. The router can
also be given a `ProgressSink` (the M3 JobRegistry) for live UI updates.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from impact_crater import quota, rate_cards, telemetry
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

log = logging.getLogger(__name__)


# Async callback the router invokes on every dispatch. Receives a dict
# `{operation, provider, tier, cost_usd, cache_hit}`. The M3 JobRegistry
# is the production sink; tests pass their own.
ProgressSink = Callable[[dict[str, Any]], Awaitable[None]]

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
        self._progress_sink: ProgressSink | None = None
        self._telemetry_context: dict[str, Any] = {
            "project_id": "",
            "snapshot_id": None,
            "correlation_id": "",
        }

    def set_progress_sink(self, sink: ProgressSink | None) -> None:
        """Attach (or detach) a per-call progress callback."""
        self._progress_sink = sink

    def set_telemetry_context(
        self,
        *,
        project_id: str,
        snapshot_id: str | None,
        correlation_id: str,
    ) -> None:
        """Stamp project + correlation IDs on every emitted LLMCallEvent."""
        self._telemetry_context = {
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "correlation_id": correlation_id,
        }

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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
        return result

    async def generate_title_background(
        self, *, spirit_prompt: str, aspect: str = "16:9"
    ) -> bytes:
        """Generate a title-card background image from a spirit prompt (S-2.11.5).
        Not cached (image bytes; one call per job)."""
        op = "generate_title_background"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(prompt, spirit=spirit_prompt, aspect=aspect)
        params = self._params(route)
        result = await client.generate_image(rendered, params=params)
        await self._record_call(
            route,
            cache_hit=False,
            params=params,
            result_bytes_hash=hashlib.sha256(result).hexdigest(),
        )
        return result

    async def score_image(
        self,
        image_bytes: bytes,
        *,
        content_hash: str,
        dimension: str,
        prompt_vars: dict[str, Any] | None = None,
        cache_extra: dict[str, Any] | None = None,
    ) -> float:
        """Score the image on `dimension` (e.g. "quality", "narrative_relevance").

        For brief-aware scoring (narrative-relevance), pass
        `cache_extra={"brief_hash": sha256(brief)[:16]}` so the cache
        invalidates when the brief changes per ADR-0011 Stage 2.
        """
        op = "score_image"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(prompt, dimension=dimension, **(prompt_vars or {}))
        params = self._params(route)

        params_dict: dict[str, Any] = {"dimension": dimension}
        if cache_extra:
            params_dict.update(cache_extra)
        params_canonical = cache.canonicalize_params(params_dict)
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
        return result

    async def judge_narrative_arc(
        self,
        candidates: list[CandidateRef],
        *,
        brief: str,
        target_duration: int,
        mode: Literal["standard", "music_video"] = "standard",
        music_spec: MusicSpec | None = None,
        extra_prompt_vars: dict[str, Any] | None = None,
    ) -> ArcJudgment:
        """N-001 Stage-5 narrative judgment. Cache key includes the full input
        because brief / target_duration / candidate_set drive the result.

        `extra_prompt_vars` lets callers (e.g. M4 music-video mode) inject
        additional template context (`music_analysis`, etc.) without
        widening this method's surface for every variant.
        """
        op = "judge_narrative_arc"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        render_vars: dict[str, Any] = {
            "brief": brief,
            "target_duration_seconds": target_duration,
            "mode": mode,
            "music_spec": music_spec,
            "candidates": candidates,
        }
        if extra_prompt_vars:
            render_vars.update(extra_prompt_vars)
        rendered = prompts.render(prompt, **render_vars)
        params = self._params(route)

        # Full-input cache key — repeating an identical judge call is rare but cheap to handle.
        input_signature = {
            "brief": brief,
            "target_duration": target_duration,
            "mode": mode,
            "music_spec": _music_spec_dict(music_spec),
            "extra_prompt_vars": _stable_repr(extra_prompt_vars),
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
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
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
        return result

    async def generate_title_text(self, *, brief: str, year: str = "") -> str:
        """A short, human title for the splash card from the brief + year (S-2.11.7).

        Cheap Tier-S text call reusing the structured-text primitive
        (`parse_user_brief` → JSON `{title}`). Keyed on (brief, year); callers
        fall back to a heuristic if this raises or returns empty. Returns the
        stripped title string ("" if the model gave nothing usable)."""
        op = "generate_title_text"
        route = self.route_for(op)
        client = self._client_for(route)
        prompt = prompts.load(op, route.provider, route.model)
        rendered = prompts.render(prompt, brief=brief, year=year)
        params = self._params(route)
        schema = {
            "type": "object",
            "required": ["title"],
            "properties": {"title": {"type": "string"}},
        }

        content_hash = hashlib.sha256(f"{brief}\n{year}".encode()).hexdigest()
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
            await self._record_call(route, cache_hit=True, result_bytes_hash=content_hash)
            return str(cached)

        result = await client.parse_user_brief(
            brief, prompt_template=rendered, schema=schema, params=params
        )
        title = str(result.get("title", "")).strip()
        # Only cache a usable title — an empty result should re-try next run
        # rather than pin the heuristic fallback forever.
        if title:
            await cache.put(
                title,
                content_hash=content_hash,
                provider=route.provider,
                model=route.model,
                model_version=route.model_version,
                operation=op,
                prompt_version=prompt.prompt_version,
                params_canonical=params_canonical,
            )
        await self._record_call(route, cache_hit=False, params=params, result_bytes_hash=content_hash)
        return title

    # -- Internal helpers -----------------------------------------------

    async def _record_call(
        self,
        route: OperationRoute,
        *,
        cache_hit: bool,
        params: CallParams | None = None,
        latency_ms: int = 0,
        result_bytes_hash: str = "",
    ) -> None:
        """Emit LLMCallEvent telemetry + invoke progress sink (if any).

        Cost is computed from the provider's REAL token usage (written onto
        `params` by the client after the API responds) priced against the rate
        card (ADR-0015). When usage isn't available — a cache hit, an embedding
        op, or a fake client in tests — we fall back to the per-tier ballpark.
        Cache hits report cost=0.
        """
        cost = 0.0
        in_tok = 0
        out_tok = 0
        if not cache_hit:
            in_tok = params.usage_input_tokens if params is not None else 0
            out_tok = params.usage_output_tokens if params is not None else 0
            img_tok = params.usage_image_tokens if params is not None else 0
            if in_tok or out_tok or img_tok:
                try:
                    cost = rate_cards.estimate_cost_usd(
                        provider=route.provider,
                        model=route.model,
                        model_version=route.model_version,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        image_tokens=img_tok,
                        is_embedding=route.operation in ("embed_image", "embed_text"),
                    )
                except Exception as exc:  # pragma: no cover — best-effort
                    log.debug("rate-card cost calc failed for %s/%s: %s",
                              route.provider, route.model, exc)
                    cost = _ballpark_cost(route)
            else:
                # No usage reported (embeddings don't surface tokens here, and
                # test fakes never set them) — fall back to the ballpark so a
                # quota check is never silently skipped.
                try:
                    cost = _ballpark_cost(route)
                except Exception as exc:  # pragma: no cover — best-effort
                    log.debug("rate-card lookup failed for %s/%s: %s",
                              route.provider, route.model, exc)
                    cost = 0.0

        ctx = self._telemetry_context
        # Single structured log line on EVERY dispatch (cache hit or miss).
        # Lets a developer grep for `operation=extract_metadata_image
        # cache_hit=False` and see exactly which calls hit the network +
        # which were served from cache. correlation_id ties this back to
        # the owning job (set via `set_telemetry_context` from runner.py).
        log.debug(
            "llm_call operation=%s provider=%s tier=%s model=%s cache_hit=%s "
            "cost_usd=%.6f result_hash=%s correlation_id=%s project_id=%s snapshot_id=%s",
            route.operation,
            route.provider,
            route.tier,
            route.model,
            cache_hit,
            cost,
            result_bytes_hash[:12] if result_bytes_hash else "",
            ctx.get("correlation_id", ""),
            ctx.get("project_id", ""),
            ctx.get("snapshot_id") or "",
        )
        try:
            telemetry.emit(
                telemetry.LLMCallEvent(
                    operation=route.operation,
                    provider=route.provider,
                    model=route.model,
                    model_version=route.model_version,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=latency_ms,
                    cost_estimate_usd=cost,
                    result_bytes_hash=result_bytes_hash,
                    project_id=ctx.get("project_id", ""),
                    snapshot_id=ctx.get("snapshot_id"),
                    cache_hit=cache_hit,
                    correlation_id=ctx.get("correlation_id", ""),
                )
            )
        except Exception as exc:  # pragma: no cover
            log.debug("telemetry emit failed: %s", exc)

        # Bump the daily quota_state table so Settings → "Today's spend"
        # and the next job's pre-flight quota check see this spend. Real
        # bug 2026-05-07: this call was missing; quota.record_spend was
        # defined + documented but no caller existed, so Settings always
        # showed $0.00 today regardless of what the user had spent.
        # record_spend short-circuits on cost<=0 so cache hits are free.
        if not cache_hit and cost > 0:
            try:
                await quota.record_spend(route.provider, cost)
            except Exception as exc:  # pragma: no cover
                log.warning(
                    "quota_record_spend_failed provider=%s cost=%.6f error=%r",
                    route.provider,
                    cost,
                    str(exc)[:200],
                )

        if self._progress_sink is not None:
            try:
                await self._progress_sink(
                    {
                        "operation": route.operation,
                        "provider": route.provider,
                        "tier": route.tier,
                        "cost_usd": cost,
                        "cache_hit": cache_hit,
                    }
                )
            except Exception as exc:  # pragma: no cover
                log.debug("progress sink failed: %s", exc)

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


# Per-tier ballpark cost in USD per call. Pulled from ADR-0009's per-job
# envelope (~$7-22 for 1000 photos = ~3500 Tier-S + ~1500 Tier-M + 1 Tier-L).
# These are placeholders until per-provider clients pass back actual token
# counts from their usage objects (v1 enhancement).
_TIER_COST_FALLBACK = {
    "S": 0.001,
    "M": 0.005,
    "L": 0.50,
    "embedding": 0.0001,
}


def _ballpark_cost(route: OperationRoute) -> float:
    """Best-effort per-call cost without real token counts.

    Tries to read the rate card to validate it exists; falls back to the
    per-tier envelope from ADR-0009 if the rate card has no per-call
    figure. Real token-aware costing arrives when each provider client
    surfaces `usage` from its responses (v1).
    """
    try:
        rate_cards.load(route.provider, route.model, route.model_version)
    except FileNotFoundError:
        pass
    return _TIER_COST_FALLBACK.get(route.tier, 0.001)


def _music_spec_dict(ms: MusicSpec | None) -> dict[str, Any] | None:
    if ms is None:
        return None
    return {
        "duration_ms": ms.duration_ms,
        "bpm": ms.bpm,
        "section_to_media_nl": ms.section_to_media_nl,
    }


def _stable_repr(obj: Any) -> str:
    """Stable string for cache-key inclusion. Handles None + Pydantic models."""
    if obj is None:
        return ""
    try:
        from pydantic import BaseModel

        def _coerce(o: Any) -> Any:
            if isinstance(o, BaseModel):
                return o.model_dump()
            if isinstance(o, dict):
                return {k: _coerce(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_coerce(v) for v in o]
            return o

        return cache.canonicalize_params({"v": _coerce(obj)})
    except Exception:  # pragma: no cover
        return str(obj)
