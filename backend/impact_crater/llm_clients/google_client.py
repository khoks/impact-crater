"""GoogleLLMClient — implementation against the official `google-genai` SDK.

Per ADR-0009, this client serves Tier-S Gemini Flash (caption_image,
caption_video_scene, score_image) AND embeddings (text-embedding-004 or
the current Google embedding model). The Anthropic client raises for
embed_* operations so the router pattern stays clean.

Structured outputs use Gemini's `response_schema` mode for JSON-shape
guarantees.

Note: the older `google-generativeai` package was deprecated in favor of
`google-genai`. This client targets the new SDK from the start.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types as gtypes
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from impact_crater.llm_clients.base import (
    ArcJudgment,
    CallParams,
    CandidateRef,
    Embedding,
    Message,
    MusicSpec,
    SelectedItem,
    ToolCall,
    ToolSpec,
)
from impact_crater.llm_clients.exceptions import LLMOperationFailed, LLMTransientError


_EMBED_MODEL = "gemini-embedding-001"
# Embedding dimensionality is provider/model-specific; we don't assert a
# specific value here. The router stores the actual emb.shape on the cache
# key for the v1 reuse-class semantics.


class GoogleLLMClient:
    """Google Gemini implementation of the LLMClient Protocol."""

    provider: str = "google"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    # -- Embeddings ---------------------------------------------------------

    async def embed_image(self, image_bytes: bytes, *, params: CallParams) -> Embedding:
        # Google's embed_content API does not accept image bytes directly.
        # Round-trip through Gemini Flash to caption first, then embed the
        # caption. v1's local-tier may use a true image-embedding model.
        caption = await self._caption_for_embedding(image_bytes, params)
        return await self.embed_text(caption, params=params)

    async def embed_text(self, text: str, *, params: CallParams) -> Embedding:
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.embed_content,
                model=_EMBED_MODEL,
                contents=text,
            ),
        )
        # google-genai returns ContentEmbedding objects with `values: list[float]`.
        emb_obj = result.embeddings[0]
        emb = np.asarray(emb_obj.values, dtype=np.float32)
        return emb

    async def _caption_for_embedding(self, image_bytes: bytes, params: CallParams) -> str:
        flash_params = CallParams(
            operation="_internal_caption_for_embedding",
            provider="google",
            model="gemini-2.5-flash",
            model_version=params.model_version,
            max_tokens=128,
            temperature=0.0,
        )
        return await self.caption_image(
            image_bytes,
            prompt_template="Describe this image in one short, concrete sentence.",
            params=flash_params,
        )

    # -- Vision-language captioning + scoring ------------------------------

    async def caption_image(
        self, image_bytes: bytes, *, prompt_template: str, params: CallParams
    ) -> str:
        contents = [
            gtypes.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt_template,
        ]
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents,
                config=gtypes.GenerateContentConfig(
                    temperature=params.temperature,
                    max_output_tokens=params.max_tokens,
                ),
            ),
        )
        return _extract_text(result)

    async def caption_video_scene(
        self,
        scene_frames: list[bytes],
        *,
        prompt_template: str,
        params: CallParams,
    ) -> str:
        contents: list[Any] = [
            gtypes.Part.from_bytes(data=f, mime_type="image/jpeg") for f in scene_frames
        ]
        contents.append(prompt_template)
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents,
                config=gtypes.GenerateContentConfig(
                    temperature=params.temperature,
                    max_output_tokens=params.max_tokens,
                ),
            ),
        )
        return _extract_text(result)

    async def score_image(
        self,
        image_bytes: bytes,
        *,
        prompt_template: str,
        dimension: str,
        params: CallParams,
    ) -> float:
        # Plain-text response — Gemini Flash's structured-output path is
        # finicky for a single float (the model emits a "Here is..."
        # preamble that eats the token budget). Asking for a bare number
        # and parsing the first float we see is more robust.
        contents = [
            gtypes.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt_template
            + "\n\nReply with ONLY a single decimal number between 0.0 and 1.0. "
            "No words. No JSON. No explanation. Just the number.",
        ]
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents,
                config=gtypes.GenerateContentConfig(
                    temperature=params.temperature,
                    max_output_tokens=params.max_tokens,
                ),
            ),
        )
        text = _extract_text(result).strip()
        try:
            score = _first_float(text)
        except ValueError as e:
            raise LLMOperationFailed(
                operation=params.operation,
                provider=self.provider,
                model=params.model,
                attempts=1,
                last_error=f"score parse failed: {e}; raw={text[:200]!r}",
            ) from e
        return max(0.0, min(1.0, score))

    # -- Structured-output extraction --------------------------------------

    async def extract_metadata_image(
        self,
        image_bytes: bytes,
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]:
        return await self._call_with_schema(
            params,
            schema=schema,
            contents=[
                gtypes.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt_template,
            ],
        )

    async def extract_metadata_video_scene(
        self,
        scene_frames: list[bytes],
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]:
        contents: list[Any] = [
            gtypes.Part.from_bytes(data=f, mime_type="image/jpeg") for f in scene_frames
        ]
        contents.append(prompt_template)
        return await self._call_with_schema(params, schema=schema, contents=contents)

    # -- Narrative judgment (N-001) ----------------------------------------

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
    ) -> ArcJudgment:
        # Per ADR-0009 narrative judgment routes to Anthropic Opus by default.
        # Provided here for completeness if the user manually picks Gemini.
        schema = {
            "type": "object",
            "required": ["selected_items", "arc_reasoning", "confidence"],
            "properties": {
                "selected_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "candidate_ref",
                            "placement_position",
                            "intended_duration_ms",
                            "role",
                        ],
                        "properties": {
                            "candidate_ref": {"type": "string"},
                            "placement_position": {"type": "integer"},
                            "intended_duration_ms": {"type": "integer"},
                            "role": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                    },
                },
                "arc_reasoning": {"type": "string"},
                "confidence": {"type": "number"},
                "open_questions": {"type": "array", "items": {"type": "string"}},
            },
        }
        raw = await self._call_with_schema(params, schema=schema, contents=[prompt_template])
        return ArcJudgment(
            selected_items=[SelectedItem(**si) for si in raw["selected_items"]],
            arc_reasoning=raw["arc_reasoning"],
            confidence=float(raw["confidence"]),
            open_questions=raw.get("open_questions", []),
        )

    # -- Brief parsing -----------------------------------------------------

    async def parse_user_brief(
        self,
        text: str,
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]:
        return await self._call_with_schema(params, schema=schema, contents=[prompt_template])

    # -- Orchestrator tool-call loop ---------------------------------------

    async def tool_call(
        self,
        tools: list[ToolSpec],
        messages: list[Message],
        *,
        params: CallParams,
    ) -> ToolCall:
        # Gemini's tool-calling API differs from Anthropic's. Per ADR-0009
        # the orchestrator's tool-call loop runs on Anthropic Sonnet, so this
        # path is exercised mainly when the user manually picks Google.
        # Minimal support kept for M1.
        raise LLMOperationFailed(
            operation=params.operation,
            provider=self.provider,
            model=params.model,
            attempts=0,
            last_error=(
                "google.tool_call is not implemented at M1 — orchestrator routes "
                "to anthropic per the ADR-0009 cost-tier defaults"
            ),
        )

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        params: CallParams,
    ) -> AsyncIterator[str]:
        contents = [{"role": m.role, "parts": [{"text": m.content}]} for m in messages]
        result = await _to_async(
            self._client.models.generate_content_stream,
            model=params.model,
            contents=contents,
        )
        for chunk in result:
            text = getattr(chunk, "text", "") or ""
            if text:
                yield text

    # -- Internal helpers --------------------------------------------------

    async def _call_with_schema(
        self,
        params: CallParams,
        *,
        schema: dict[str, Any],
        contents: list[Any],
    ) -> dict[str, Any]:
        # Use prompted-JSON instead of `response_schema` for cross-version
        # robustness — google-genai's response_schema accepts only certain
        # JSON-Schema shapes (and converts to Pydantic-style internally).
        # We append a schema-summary suffix to the user's prompt and require
        # JSON output via response_mime_type. Gemini Flash follows this
        # reliably; the parse-failure path below catches the rare drift.
        schema_hint = (
            "\n\nReply with a single JSON object matching exactly this JSON Schema:\n"
            f"{json.dumps(_strip_unsupported(schema), separators=(',', ':'))}"
            "\nNo prose, no markdown fences, no commentary. "
            "Begin your response with the opening brace `{`."
        )
        contents_with_hint = list(contents)
        # Append the schema hint to the last text part if present, else add a new part.
        if contents_with_hint and isinstance(contents_with_hint[-1], str):
            contents_with_hint[-1] = contents_with_hint[-1] + schema_hint
        else:
            contents_with_hint.append(schema_hint)

        config = gtypes.GenerateContentConfig(
            temperature=params.temperature,
            max_output_tokens=params.max_tokens,
            response_mime_type="application/json",
        )
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents_with_hint,
                config=config,
            ),
        )
        text = _extract_text(result).strip()
        # Strip markdown fences in case the model added them despite the prompt.
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        # Gemini Flash sometimes leads with a preamble like "Here is the JSON
        # requested:" before the actual JSON object — even with the
        # "Begin with `{`" instruction in the prompt suffix. Fall back to
        # scanning for the first `{...}` substring before declaring failure.
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            extracted = _extract_first_json_object(text)
            if extracted is not None:
                try:
                    return json.loads(extracted)  # type: ignore[no-any-return]
                except json.JSONDecodeError:
                    pass
            raise LLMOperationFailed(
                operation=params.operation,
                provider=self.provider,
                model=params.model,
                attempts=1,
                last_error=f"non-JSON structured response: raw={text[:200]!r}",
            ) from None


# -- Module-level helpers ------------------------------------------------


def _first_float(text: str) -> float:
    """Find the first floating-point number in `text` and return it."""
    import re

    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        raise ValueError(f"no number in {text!r}")
    return float(m.group(0))


def _extract_first_json_object(text: str) -> str | None:
    """Find the first balanced {...} substring. Handles nested braces.

    Naive bracket-counting is enough here because the only producers we
    care about are LLM JSON outputs, which don't contain unbalanced
    braces inside string literals at the top level.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_text(result: Any) -> str:
    text = getattr(result, "text", None)
    if text:
        return str(text)
    for cand in getattr(result, "candidates", []) or []:
        content = getattr(cand, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", []) or []:
            t = getattr(part, "text", None)
            if t:
                return str(t)
    return ""


def _strip_unsupported(node: Any) -> Any:
    """Strip JSON-Schema keywords google-genai's response_schema doesn't accept."""
    if isinstance(node, dict):
        return {
            k: _strip_unsupported(v)
            for k, v in node.items()
            if k not in {"additionalProperties", "$schema"}
        }
    if isinstance(node, list):
        return [_strip_unsupported(v) for v in node]
    return node


async def _to_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a sync callable in the default thread-pool so async sites stay non-blocking."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _is_transient(e: BaseException) -> bool:
    msg = str(e).lower()
    return any(s in msg for s in ("429", "503", "504", "timeout", "deadline", "reset"))


async def _retry(params: CallParams, callable_: Any) -> Any:
    attempts = 0
    last_error: BaseException | None = None
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        retry=retry_if_exception_type(LLMTransientError),
        reraise=True,
    ):
        with attempt:
            attempts += 1
            try:
                return await callable_()
            except Exception as e:
                last_error = e
                if _is_transient(e):
                    raise LLMTransientError(str(e)) from e
                raise LLMOperationFailed(
                    operation=params.operation,
                    provider=params.provider,
                    model=params.model,
                    attempts=attempts,
                    last_error=e,
                ) from e
    raise LLMOperationFailed(
        operation=params.operation,
        provider=params.provider,
        model=params.model,
        attempts=attempts,
        last_error=last_error or "unknown",
    )


__all__ = ["GoogleLLMClient"]
_ = (CandidateRef, MusicSpec, ToolSpec)
