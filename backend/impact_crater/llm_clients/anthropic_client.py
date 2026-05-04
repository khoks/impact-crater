"""AnthropicLLMClient — implementation against the official `anthropic` SDK.

Uses the Messages API throughout; structured-output operations use Anthropic's
tool-use mode (the model is forced to invoke a single tool whose input_schema
is the desired JSON Schema, then we parse `tool_input` as the structured result).

Per ADR-0009, this client serves Tier-M Sonnet (extract_metadata_*, parse_user_brief,
recommend_*, explain_*, orchestrator_reasoning) and Tier-L Opus (judge_narrative_arc).
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import anthropic
import numpy as np
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


class AnthropicLLMClient:
    """Anthropic Claude implementation of the LLMClient Protocol."""

    provider: str = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    # -- Embeddings ---------------------------------------------------------

    async def embed_image(self, image_bytes: bytes, *, params: CallParams) -> Embedding:
        # Anthropic does not currently expose an embedding endpoint. Per
        # ADR-0009, embedding ops route to Google. If the router accidentally
        # picks Anthropic, fail loudly rather than silently degrade.
        raise LLMOperationFailed(
            operation=params.operation,
            provider=self.provider,
            model=params.model,
            attempts=0,
            last_error="anthropic provider does not support embed_image; route to google",
        )

    async def embed_text(self, text: str, *, params: CallParams) -> Embedding:
        raise LLMOperationFailed(
            operation=params.operation,
            provider=self.provider,
            model=params.model,
            attempts=0,
            last_error="anthropic provider does not support embed_text; route to google",
        )

    # -- Vision-language captioning + scoring ------------------------------

    async def caption_image(
        self, image_bytes: bytes, *, prompt_template: str, params: CallParams
    ) -> str:
        msg = await self._call_messages(
            params,
            messages=[
                {
                    "role": "user",
                    "content": [
                        _image_block(image_bytes),
                        {"type": "text", "text": prompt_template},
                    ],
                }
            ],
        )
        return _first_text(msg)

    async def caption_video_scene(
        self,
        scene_frames: list[bytes],
        *,
        prompt_template: str,
        params: CallParams,
    ) -> str:
        msg = await self._call_messages(
            params,
            messages=[
                {
                    "role": "user",
                    "content": [
                        *(_image_block(b) for b in scene_frames),
                        {"type": "text", "text": prompt_template},
                    ],
                }
            ],
        )
        return _first_text(msg)

    async def score_image(
        self,
        image_bytes: bytes,
        *,
        prompt_template: str,
        dimension: str,
        params: CallParams,
    ) -> float:
        # Forced-tool-use to get a single float in [0, 1].
        tool = {
            "name": "submit_score",
            "description": f"Submit a {dimension} score in [0.0, 1.0]",
            "input_schema": {
                "type": "object",
                "required": ["score"],
                "properties": {
                    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reasoning": {"type": "string"},
                },
            },
        }
        result = await self._call_tool_use(
            params,
            tools=[tool],
            messages=[
                {
                    "role": "user",
                    "content": [
                        _image_block(image_bytes),
                        {"type": "text", "text": prompt_template},
                    ],
                }
            ],
            tool_name="submit_score",
        )
        return float(result["score"])

    # -- Structured-output extraction --------------------------------------

    async def extract_metadata_image(
        self,
        image_bytes: bytes,
        *,
        prompt_template: str,
        schema: dict[str, Any],
        params: CallParams,
    ) -> dict[str, Any]:
        return await self._extract_via_tool(
            params,
            schema=schema,
            user_blocks=[
                _image_block(image_bytes),
                {"type": "text", "text": prompt_template},
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
        return await self._extract_via_tool(
            params,
            schema=schema,
            user_blocks=[
                *(_image_block(b) for b in scene_frames),
                {"type": "text", "text": prompt_template},
            ],
        )

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
        # The prompt_template is rendered upstream (by the router/prompts loader)
        # with brief + target_duration + music_spec + candidates already
        # interpolated. Here we just send it + force a tool that returns the
        # structured ArcJudgment.
        tool = {
            "name": "submit_arc_judgment",
            "description": "Submit the ordered, structured narrative-arc judgment.",
            "input_schema": {
                "type": "object",
                "required": ["selected_items", "arc_reasoning", "confidence"],
                "properties": {
                    "selected_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["candidate_ref", "placement_position",
                                          "intended_duration_ms", "role"],
                            "properties": {
                                "candidate_ref": {"type": "string"},
                                "placement_position": {"type": "integer", "minimum": 0},
                                "intended_duration_ms": {"type": "integer", "minimum": 100},
                                "role": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                        },
                    },
                    "arc_reasoning": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "open_questions": {"type": "array", "items": {"type": "string"}},
                    "section_mapping": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array", "items": {"type": "integer", "minimum": 0}
                        },
                    },
                },
            },
        }
        raw = await self._call_tool_use(
            params,
            tools=[tool],
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt_template}]}],
            tool_name="submit_arc_judgment",
        )
        return ArcJudgment(
            selected_items=[SelectedItem(**si) for si in raw["selected_items"]],
            arc_reasoning=raw["arc_reasoning"],
            confidence=float(raw["confidence"]),
            open_questions=raw.get("open_questions", []),
            section_mapping=raw.get("section_mapping"),
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
        return await self._extract_via_tool(
            params,
            schema=schema,
            user_blocks=[{"type": "text", "text": prompt_template}],
        )

    # -- Orchestrator tool-call loop ---------------------------------------

    async def tool_call(
        self,
        tools: list[ToolSpec],
        messages: list[Message],
        *,
        params: CallParams,
    ) -> ToolCall:
        anth_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        anth_messages = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        system = next((m.content for m in messages if m.role == "system"), "")
        msg = await self._call_messages(
            params,
            messages=anth_messages,
            system=system,
            tools=anth_tools,
        )
        for block in msg.content:
            if block.type == "tool_use":
                return ToolCall(
                    tool_name=block.name,
                    tool_input=dict(block.input),
                    raw_response_text=_first_text_safe(msg),
                )
        # Model returned text only — wrap as a synthetic "no tool" result.
        return ToolCall(
            tool_name="",
            tool_input={},
            raw_response_text=_first_text_safe(msg),
        )

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        params: CallParams,
    ) -> AsyncIterator[str]:
        anth_messages = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        system = next((m.content for m in messages if m.role == "system"), "")
        kwargs: dict[str, Any] = {
            "model": params.model,
            "max_tokens": params.max_tokens,
            "messages": anth_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        async with self._client.messages.stream(**kwargs) as stream:
            async for chunk in stream.text_stream:
                yield chunk

    # -- Internal helpers --------------------------------------------------

    async def _call_messages(
        self,
        params: CallParams,
        *,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> anthropic.types.Message:
        kwargs: dict[str, Any] = {
            "model": params.model,
            "max_tokens": params.max_tokens,
            "temperature": params.temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        return await _retry(params, lambda: self._client.messages.create(**kwargs))

    async def _call_tool_use(
        self,
        params: CallParams,
        *,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tool_name: str,
    ) -> dict[str, Any]:
        msg = await self._call_messages(
            params,
            messages=messages,
            tools=tools,
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == tool_name:
                return dict(block.input)
        raise LLMOperationFailed(
            operation=params.operation,
            provider=self.provider,
            model=params.model,
            attempts=1,
            last_error=f"model did not call expected tool {tool_name!r}",
        )

    async def _extract_via_tool(
        self,
        params: CallParams,
        *,
        schema: dict[str, Any],
        user_blocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        tool = {
            "name": "submit_metadata",
            "description": "Submit the structured metadata extraction.",
            "input_schema": schema,
        }
        return await self._call_tool_use(
            params,
            tools=[tool],
            messages=[{"role": "user", "content": user_blocks}],
            tool_name="submit_metadata",
        )


# -- Module-level helpers ------------------------------------------------


def _image_block(image_bytes: bytes, media_type: str = "image/jpeg") -> dict[str, Any]:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(image_bytes).decode("ascii"),
        },
    }


def _first_text(msg: anthropic.types.Message) -> str:
    for block in msg.content:
        if block.type == "text":
            return block.text
    raise LLMOperationFailed(
        operation="caption_or_text",
        provider="anthropic",
        model="(unknown)",
        attempts=1,
        last_error="response had no text block",
    )


def _first_text_safe(msg: anthropic.types.Message) -> str:
    for block in msg.content:
        if block.type == "text":
            return block.text
    return ""


def _is_transient(e: BaseException) -> bool:
    if isinstance(e, anthropic.APIStatusError):
        return e.status_code in (408, 425, 429, 500, 502, 503, 504)
    if isinstance(e, anthropic.APIConnectionError | anthropic.APITimeoutError):
        return True
    return False


async def _retry(params: CallParams, callable_: Any) -> Any:
    """Retry wrapper for transient Anthropic errors.

    `callable_` is a zero-arg awaitable factory so we can re-invoke on retry.
    """
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
    # Unreachable; tenacity reraise=True covers the loop exit.
    raise LLMOperationFailed(
        operation=params.operation,
        provider=params.provider,
        model=params.model,
        attempts=attempts,
        last_error=last_error or "unknown",
    )


# Use `json` import so ruff F401 doesn't flag it; structured output may need
# json.dumps in future for prompt-side serialization.
_ = json
