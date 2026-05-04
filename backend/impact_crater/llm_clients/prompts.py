"""Prompt template loader + version hashing per ADR-0007.

Templates live at `prompts/{operation}/{provider}_{model}.jinja2` at the repo
root. Each template's `prompt_version` is `sha256(raw_template_text)` — this
participates in the cache key (ADR-0006 cache_index, A-011 / N-007), so
editing a template invalidates only the affected cache entries automatically.

Loading is cached in-process; bumping `prompt_version` requires either
restarting the process or calling `clear_cache()` (used by tests).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import ChainableUndefined, Template

# Repo-root-relative `prompts/` directory. The package lives at
# `backend/impact_crater/llm_clients/`, so go up four levels.
_PROMPTS_DIR_DEFAULT = Path(__file__).resolve().parents[3] / "prompts"


@dataclass(frozen=True)
class LoadedPrompt:
    """A loaded template + its content hash."""

    operation: str
    provider: str
    model: str
    template_text: str
    prompt_version: str  # sha256 of template_text


def _prompts_dir() -> Path:
    """Resolve the prompts directory.

    Override via `IMPACT_CRATER_PROMPTS_DIR` env var (used by tests).
    """
    import os

    override = os.environ.get("IMPACT_CRATER_PROMPTS_DIR")
    if override:
        return Path(override)
    return _PROMPTS_DIR_DEFAULT


@lru_cache(maxsize=128)
def load(operation: str, provider: str, model: str) -> LoadedPrompt:
    """Load a prompt template and compute its prompt_version.

    Raises FileNotFoundError if the template doesn't exist.
    """
    path = _prompts_dir() / operation / f"{provider}_{model}.jinja2"
    if not path.is_file():
        raise FileNotFoundError(
            f"prompt template not found: {path} "
            f"(operation={operation}, provider={provider}, model={model})"
        )
    text = path.read_text(encoding="utf-8")
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return LoadedPrompt(
        operation=operation,
        provider=provider,
        model=model,
        template_text=text,
        prompt_version=version,
    )


def render(prompt: LoadedPrompt, **vars: Any) -> str:
    """Render a loaded template with the given variables.

    Uses ChainableUndefined so optional template variables (e.g. `context_brief`
    in extract_metadata_image, `music_spec` in judge_narrative_arc) can be
    omitted and `{% if foo %}` evaluates them as falsy. Misspelled variable
    references in `{{ foo.bar }}` chains still raise loudly.
    """
    return Template(prompt.template_text, undefined=ChainableUndefined).render(**vars)


def clear_cache() -> None:
    """Clear the in-process load cache. Tests call this after writing fixtures."""
    load.cache_clear()
