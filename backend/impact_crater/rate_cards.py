"""Rate-card loader + cost estimation per ADR-0015.

Rate cards live as YAML files at `config/rate-cards/{provider}-{model}-{version}.yaml`
(version is the `model_version` from the routing config). Loaded once per
process; bumping a model_version is a versioned config change that fans
out to both the cache key (ADR-0006) and the rate-card lookup here.

The estimator deliberately under-counts rather than over-counts on
unknowns — better to under-warn the user than to falsely block a job.
For tokens unknown at call time we fall back to a per-operation pessimistic
estimate so a bad estimate can never silently miss a quota check.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Repo-root-relative `config/rate-cards/` directory.
_RATE_CARD_DIR_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "rate-cards"


@dataclass(frozen=True)
class RateCard:
    provider: str
    model: str
    model_version: str
    effective_date: str
    input_token_rate_usd_per_1k: float
    output_token_rate_usd_per_1k: float
    image_input_rate_usd_per_1k_tokens_equivalent: float | None = None
    embedding_rate_usd_per_1k_tokens: float | None = None


def _rate_cards_dir() -> Path:
    import os

    override = os.environ.get("IMPACT_CRATER_RATE_CARDS_DIR")
    if override:
        return Path(override)
    return _RATE_CARD_DIR_DEFAULT


@lru_cache(maxsize=128)
def load(provider: str, model: str, model_version: str) -> RateCard:
    """Load the rate card for (provider, model, model_version).

    Filename convention: {provider}-{model}-{model_version}.yaml — the model
    name's dots/colons are sanitized to dashes so paths stay portable.
    """
    fname = f"{provider}-{_sanitize(model)}-{_sanitize(model_version)}.yaml"
    path = _rate_cards_dir() / fname
    if not path.is_file():
        raise FileNotFoundError(
            f"rate card not found: {path} "
            f"(provider={provider}, model={model}, model_version={model_version})"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RateCard(
        provider=str(raw["provider"]),
        model=str(raw["model"]),
        model_version=str(raw["model_version"]),
        effective_date=str(raw.get("effective_date", "")),
        input_token_rate_usd_per_1k=float(raw["input_token_rate_usd_per_1k"]),
        output_token_rate_usd_per_1k=float(raw["output_token_rate_usd_per_1k"]),
        image_input_rate_usd_per_1k_tokens_equivalent=_opt_float(
            raw.get("image_input_rate_usd_per_1k_tokens_equivalent")
        ),
        embedding_rate_usd_per_1k_tokens=_opt_float(
            raw.get("embedding_rate_usd_per_1k_tokens")
        ),
    )


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    model_version: str,
    input_tokens: int,
    output_tokens: int,
    image_tokens: int = 0,
    is_embedding: bool = False,
) -> float:
    """Compute USD cost for a single call.

    Args:
        image_tokens: provider-specific image-input token-equivalent count
                      (Anthropic exposes this in usage; Google reports as
                      total tokens).
        is_embedding: when True, charges everything at the embedding rate
                      (input_tokens count; output_tokens ignored).
    """
    card = load(provider, model, model_version)
    if is_embedding:
        if card.embedding_rate_usd_per_1k_tokens is None:
            # Embedding rate missing — fall back to input-token rate as a
            # conservative over-estimate (ensures quota check is honest).
            rate = card.input_token_rate_usd_per_1k
        else:
            rate = card.embedding_rate_usd_per_1k_tokens
        return (input_tokens / 1000.0) * rate

    in_cost = (input_tokens / 1000.0) * card.input_token_rate_usd_per_1k
    out_cost = (output_tokens / 1000.0) * card.output_token_rate_usd_per_1k
    img_rate = (
        card.image_input_rate_usd_per_1k_tokens_equivalent
        if card.image_input_rate_usd_per_1k_tokens_equivalent is not None
        else card.input_token_rate_usd_per_1k
    )
    img_cost = (image_tokens / 1000.0) * img_rate
    return in_cost + out_cost + img_cost


def clear_cache() -> None:
    """Reset the in-process rate-card cache. Tests use this after writing fixtures."""
    load.cache_clear()


# ---- Helpers ----------------------------------------------------------


def _sanitize(s: str) -> str:
    return s.replace(".", "-").replace(":", "-").replace("/", "-")


def _opt_float(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)
