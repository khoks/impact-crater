"""GoogleLLMClient — implementation against the official `google-genai` SDK.

Per D-061 this client serves the embeddings (`gemini-embedding-2`, which embeds
the image bytes directly into a space shared with text) and the title-card image
model (`gemini-3.1-flash-lite-image`). The text ops are implemented too, so the
configured Tier-S fallback (`gemini-3.5-flash-lite`) is a yaml flip. The Anthropic
client raises for embed_* / generate_image so the router pattern stays clean.

Structured outputs are prompted JSON with a schema-keyword scrub
(`_call_with_schema`) rather than `response_schema`, for cross-version
robustness of the SDK.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types as gtypes
from PIL import Image, ImageOps
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
    MusicSpec,
    SelectedItem,
)
from impact_crater.llm_clients.exceptions import LLMOperationFailed, LLMTransientError

log = logging.getLogger(__name__)

# gemini-embedding-2 MRL output size (API-normalized at non-default sizes).
# Changing it changes the vector space: bump the op's model_version so cached
# vectors are never mixed in the Stage 4 cosine dedup.
_EMBED_DIM = 768

# embed_content rejects an empty text Part with a 400 (real failure 2026-05-06);
# embed_text substitutes this placeholder so one blank input cannot kill a job.
_EMPTY_TEXT_FALLBACK = "an image"

# embed_content accepts PNG / JPEG only, and a 768-d vector needs no more than
# ~1 MP, so other formats and oversized inputs are re-encoded first.
_EMBED_MAX_EDGE_PX = 1024


class GoogleLLMClient:
    """Google Gemini implementation of the LLMClient Protocol."""

    provider: str = "google"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    # -- Embeddings ---------------------------------------------------------

    async def embed_image(self, image_bytes: bytes, *, params: CallParams) -> Embedding:
        fitted = _fit_image_for_embedding(image_bytes)
        part = gtypes.Part.from_bytes(data=fitted, mime_type=_sniff_mime_type(fitted))
        return await self._embed(params, [part])

    async def embed_text(self, text: str, *, params: CallParams) -> Embedding:
        if not text or not text.strip():
            text = _EMPTY_TEXT_FALLBACK
        return await self._embed(params, [text])

    async def _embed(self, params: CallParams, contents: list[Any]) -> Embedding:
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.embed_content,
                model=params.model,
                contents=contents,
                config=gtypes.EmbedContentConfig(output_dimensionality=_EMBED_DIM),
            ),
        )
        return np.asarray(result.embeddings[0].values, dtype=np.float32)

    async def verify_model(self, model: str) -> str:
        params = CallParams(
            operation="verify_model", provider=self.provider, model=model, model_version=""
        )
        try:
            info = await _retry(params, lambda: _to_async(self._client.models.get, model=model))
        except LLMOperationFailed as exc:
            raise LLMOperationFailed(
                operation="verify_model",
                provider=self.provider,
                model=model,
                attempts=exc.attempts,
                last_error=_verify_reason(model, exc.last_error),
            ) from exc
        version = getattr(info, "version", None)
        return f"{model} ({version})" if version else model

    # -- Vision-language captioning + scoring ------------------------------

    async def generate_image(self, prompt: str, *, params: CallParams) -> bytes:
        """Generate an image from a text prompt (S-2.11.5). Returns raw PNG/JPEG
        bytes from the first inline image part; raises if none came back."""
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=[prompt],
                config=gtypes.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=params.temperature,
                    image_config=gtypes.ImageConfig(
                        aspect_ratio=str(params.extra.get("aspect_ratio", "16:9")),
                        image_size="1K",
                    ),
                ),
            ),
        )
        _apply_usage(params, result)
        for cand in getattr(result, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                data = getattr(inline, "data", None) if inline is not None else None
                if data:
                    return bytes(data)
        raise LLMOperationFailed(
            operation=params.operation,
            provider=self.provider,
            model=params.model,
            attempts=1,
            last_error="no inline image part in generate_content response",
        )

    async def caption_image(
        self, image_bytes: bytes, *, prompt_template: str, params: CallParams
    ) -> str:
        contents = [
            gtypes.Part.from_bytes(data=image_bytes, mime_type=_sniff_mime_type(image_bytes)),
            prompt_template,
        ]
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents,
                config=_gen_config(params),
            ),
        )
        _apply_usage(params, result)
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
            gtypes.Part.from_bytes(data=image_bytes, mime_type=_sniff_mime_type(image_bytes)),
            prompt_template + "\n\nReply with ONLY a single decimal number between 0.0 and 1.0. "
            "No words. No JSON. No explanation. Just the number.",
        ]
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents,
                config=_gen_config(params),
            ),
        )
        _apply_usage(params, result)
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
                gtypes.Part.from_bytes(data=image_bytes, mime_type=_sniff_mime_type(image_bytes)),
                prompt_template,
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

        config = _gen_config(params, response_mime_type="application/json")
        result = await _retry(
            params,
            lambda: _to_async(
                self._client.models.generate_content,
                model=params.model,
                contents=contents_with_hint,
                config=config,
            ),
        )
        _apply_usage(params, result)
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
            log.warning(
                "google_non_json_response operation=%s model=%s raw_prefix=%r",
                params.operation,
                params.model,
                text[:200],
            )
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


def _verify_reason(model: str, error: Exception | str) -> str:
    code = getattr(error, "code", None)
    text = str(error)
    if code == 404 or "NOT_FOUND" in text:
        return f"model {model!r} is not available to this Google key (404 NOT_FOUND)"
    if code in (401, 403) or (code == 400 and "api key" in text.lower()):
        return f"Google rejected the API key (HTTP {code}, permission denied)"
    return f"Google models.get failed: {text[:200]}"


def _gen_config(params: CallParams, **kwargs: Any) -> gtypes.GenerateContentConfig:
    if params.effort:
        kwargs["thinking_config"] = gtypes.ThinkingConfig(
            thinking_level=gtypes.ThinkingLevel(params.effort.upper())
        )
    return gtypes.GenerateContentConfig(
        temperature=params.temperature,
        max_output_tokens=params.max_tokens,
        **kwargs,
    )


def _fit_image_for_embedding(image_bytes: bytes) -> bytes:
    if image_bytes.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
        with Image.open(io.BytesIO(image_bytes)) as probe:
            w, h = probe.size
        if max(w, h) <= _EMBED_MAX_EDGE_PX:
            return image_bytes
    src = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(src) or src
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    scale = _EMBED_MAX_EDGE_PX / max(img.size)
    if scale < 1:
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.Resampling.LANCZOS,
        )
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def _apply_usage(params: CallParams, result: Any) -> None:
    """Write the Gemini response's real token usage back onto `params`.

    `prompt_token_count` includes the image tokens; `prompt_tokens_details` splits
    them out per modality, so the router can price image input separately.
    Thinking tokens are billed as output and arrive in `thoughts_token_count`.
    """
    um = getattr(result, "usage_metadata", None)
    if um is None:
        return
    prompt = int(getattr(um, "prompt_token_count", 0) or 0)
    image = sum(
        int(getattr(d, "token_count", 0) or 0)
        for d in (getattr(um, "prompt_tokens_details", None) or [])
        if str(getattr(d, "modality", "")).upper().endswith("IMAGE")
    )
    params.usage_input_tokens = max(prompt - image, 0)
    params.usage_image_tokens = image
    params.usage_output_tokens = int(getattr(um, "candidates_token_count", 0) or 0) + int(
        getattr(um, "thoughts_token_count", 0) or 0
    )


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


# Magic-byte prefixes for the image formats Gemini accepts. We sniff the
# first few bytes rather than trusting the file extension or hardcoding
# image/jpeg, because stage1's video-scene representative frames are PNG
# (cv2.imwrite scene-N-middle.png) and historically those went out with a
# false "image/jpeg" claim. Google was lenient (Stage 2 accepted them);
# Anthropic was strict (Stage 3 400'd, real failure 2026-05-07).
_IMAGE_MAGIC_PREFIXES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    # WebP: "RIFF" .... "WEBP"
    (
        b"RIFF",
        "image/webp",
    ),  # not perfect — WEBP has WEBP at offset 8, but RIFF alone is sufficiently rare for our inputs
    (b"BM", "image/bmp"),
)


def _sniff_mime_type(image_bytes: bytes) -> str:
    """Return the IANA mime type from magic bytes; default image/jpeg."""
    for prefix, mime in _IMAGE_MAGIC_PREFIXES:
        if image_bytes.startswith(prefix):
            # Tighten WEBP detection by also checking the WEBP signature at offset 8
            if mime == "image/webp" and image_bytes[8:12] != b"WEBP":
                continue
            return mime
    return "image/jpeg"


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
                    log.warning(
                        "google_transient operation=%s model=%s attempt=%d/4 error=%r",
                        params.operation,
                        params.model,
                        attempts,
                        str(e)[:200],
                    )
                    raise LLMTransientError(str(e)) from e
                log.error(
                    "google_failed operation=%s model=%s attempts=%d error=%r",
                    params.operation,
                    params.model,
                    attempts,
                    str(e)[:300],
                )
                raise LLMOperationFailed(
                    operation=params.operation,
                    provider=params.provider,
                    model=params.model,
                    attempts=attempts,
                    last_error=e,
                ) from e
    log.error(
        "google_retries_exhausted operation=%s model=%s attempts=%d last_error=%r",
        params.operation,
        params.model,
        attempts,
        str(last_error)[:300] if last_error else "unknown",
    )
    raise LLMOperationFailed(
        operation=params.operation,
        provider=params.provider,
        model=params.model,
        attempts=attempts,
        last_error=last_error or "unknown",
    )


__all__ = ["GoogleLLMClient"]
