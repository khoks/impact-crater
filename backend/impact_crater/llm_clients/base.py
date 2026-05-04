"""LLMClient Protocol + supporting types per ADR-0007.

Every LLM call site uses `LLMClient`; concrete provider implementations
(`AnthropicLLMClient`, `GoogleLLMClient`, future `LocalLLMClient` per
ADR-0008) live behind it. Routing dispatch (ADR-0007 + ADR-0009) picks
the right implementation per operation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

# Numpy-backed embeddings; numpy ndarray of shape (D,) dtype float32 per ADR-0007.
Embedding = NDArray[np.float32]


# ---- Domain types --------------------------------------------------------


@dataclass
class CandidateRef:
    """A single candidate item the narrative-arc judge sees.

    For photos: just the content_hash. For video scenes: content_hash plus
    the scene index. The judge produces selected_items referencing these.
    """

    content_hash: str
    scene_index: int | None = None
    caption: str | None = None
    metadata_summary: str | None = None
    quality_score: float | None = None
    narrative_relevance: float | None = None


@dataclass
class SelectedItem:
    """One item the narrative-arc judge picked, with placement metadata."""

    candidate_ref: str  # "{content_hash}" or "{content_hash}#{scene_index}"
    placement_position: int
    intended_duration_ms: int
    role: str  # "opener" / "scene_set" / "peak" / "callback" / "closer" / ...
    notes: str = ""


@dataclass
class ArcJudgment:
    """Output of judge_narrative_arc — N-001 mechanism."""

    selected_items: list[SelectedItem]
    arc_reasoning: str
    confidence: float
    open_questions: list[str] = field(default_factory=list)
    section_mapping: dict[str, list[int]] | None = None  # music-video mode


@dataclass
class MusicSpec:
    """Minimal music spec for Stage 5. Full music analysis lands in M4."""

    duration_ms: int
    bpm: float | None = None
    section_to_media_nl: str | None = None  # A-013 free-text spec


@dataclass
class CallParams:
    """Provider-resolved call parameters passed to each LLMClient method.

    The router (ADR-0007) populates this with the resolved provider+model
    + any per-call overrides.
    """

    operation: str
    provider: str
    model: str
    model_version: str
    max_tokens: int = 1024
    temperature: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


# ---- Tool / message shapes for tool-call loops --------------------------


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass
class ToolCall:
    """Output of `tool_call()` — one tool the model wants to invoke."""

    tool_name: str
    tool_input: dict[str, Any]
    raw_response_text: str = ""


# ---- The Protocol --------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """The single contract every provider implementation satisfies.

    All methods are async. Embeddings are normalized to numpy ndarray
    (float32, shape (D,)). Structured-output operations (extract_metadata_*,
    parse_user_brief, recommend_effort_level) validate the response against
    the supplied JSON Schema and raise LLMOperationFailed on mismatch.

    Pricing / cost-estimation lives outside this Protocol — the LLMRouter
    layers it on top using rate cards (ADR-0015).
    """

    provider: str  # "anthropic" / "google" / "local" / etc.

    # Embeddings -----------------------------------------------------------
    async def embed_image(self, image_bytes: bytes, *, params: CallParams) -> Embedding: ...

    async def embed_text(self, text: str, *, params: CallParams) -> Embedding: ...

    # Vision-language captioning + scoring ---------------------------------
    async def caption_image(
        self, image_bytes: bytes, *, prompt_template: str, params: CallParams
    ) -> str: ...

    async def caption_video_scene(
        self,
        scene_frames: list[bytes],
        *,
        prompt_template: str,
        params: CallParams,
    ) -> str: ...

    async def score_image(
        self,
        image_bytes: bytes,
        *,
        prompt_template: str,
        dimension: str,
        params: CallParams,
    ) -> float: ...

    # Structured-output extraction (D-009 rich metadata) -------------------
    async def extract_metadata_image(
        self,
        image_bytes: bytes,
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]: ...

    async def extract_metadata_video_scene(
        self,
        scene_frames: list[bytes],
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]: ...

    # Narrative judgment (N-001) -------------------------------------------
    async def judge_narrative_arc(
        self,
        candidates: list[CandidateRef],
        *,
        prompt_template: str,
        brief: str,
        target_duration: int,
        mode: Literal["standard", "music_video"],
        music_spec: MusicSpec | None,
        params: CallParams,
    ) -> ArcJudgment: ...

    # Brief parsing + agentic UX -------------------------------------------
    async def parse_user_brief(
        self,
        text: str,
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]: ...

    # Orchestrator (D-017) — tool-call-driven loop -------------------------
    async def tool_call(
        self,
        tools: list[ToolSpec],
        messages: list[Message],
        *,
        params: CallParams,
    ) -> ToolCall: ...

    def stream_chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        params: CallParams,
    ) -> AsyncIterator[str]: ...
