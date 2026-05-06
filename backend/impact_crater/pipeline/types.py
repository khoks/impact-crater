"""Pydantic models for the curation pipeline outputs per D-009 + ADR-0011.

Stage 3's `extract_metadata_image` returns the `RichMetadataPhoto` shape;
`extract_metadata_video_scene` returns the same plus per-scene fields.
The schema is the contract the LLM must satisfy — the router validates
against `model_json_schema()` and rejects on mismatch.

Field set follows D-009 + the Stage 3 description in ADR-0011. The
person-library `recognized_persons` field exists from M1 but is
always empty until N-008 lands at M5.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TimeOfDay = Literal[
    "morning", "midday", "golden_hour", "dusk", "night", "indoor", "ambiguous"
]


def _coerce_str_list(value: Any) -> Any:
    """Pydantic before-validator that tolerates the LLM occasionally
    emitting a stringified list for `list[str]` fields.

    Real Anthropic tool_use observation (Times Square smoke test):
        generic_tags = 'times square", "new york", "tourist destination"]'
    The model wrote a CSV-with-quotes string instead of a JSON array.
    Try to parse it back; fall through if the input is already a list.
    """
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return []
    # Try JSON-array parse (with or without the opening/closing bracket).
    candidates = [s, "[" + s, "[" + s + "]", s + "]"]
    for c in candidates:
        try:
            parsed = json.loads(c)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    # CSV-style fallback: split on `", "` then strip quotes + brackets
    # from both ends in one pass (so `'child left"]'` -> `'child left'`).
    parts = [p.strip().strip('"[]') for p in s.split('", "')]
    return [p for p in parts if p]


class PeopleObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    count: int = Field(default=0, ge=0)
    in_focus: list[str] = Field(default_factory=list)

    _coerce_in_focus = field_validator("in_focus", mode="before")(_coerce_str_list)


class LocationObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str | None = None
    lat_long: tuple[float, float] | None = None


class RecognizedPerson(BaseModel):
    """Output of N-008 person-library face recognition. Empty at M1."""

    model_config = ConfigDict(extra="ignore")
    person_id: str
    display_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_in_photo: tuple[float, float, float, float] | None = None  # (x, y, w, h)


class RichMetadataPhoto(BaseModel):
    """The D-009 per-photo rich-metadata schema."""

    model_config = ConfigDict(extra="ignore")

    time_of_day: TimeOfDay = "ambiguous"
    people: PeopleObservation = Field(default_factory=PeopleObservation)
    location: LocationObservation = Field(default_factory=LocationObservation)
    mood: str = ""
    lighting: str = ""
    quality: float = Field(default=0.5, ge=0.0, le=1.0)
    foreground_activity: str = ""
    background_activity: str = ""
    objects: list[str] = Field(default_factory=list)
    clothing: list[str] = Field(default_factory=list)
    pose_quality_scores: dict[str, float] | None = None
    generic_tags: list[str] = Field(default_factory=list)
    task_context_tags: list[str] = Field(default_factory=list)
    recognized_persons: list[RecognizedPerson] = Field(default_factory=list)

    # Stringified-list tolerance: Anthropic tool_use sometimes returns a
    # CSV-quoted string (`'a", "b", "c"]'`) instead of a JSON array for
    # these fields. Real-world failure mode caught by Times Square smoke
    # test on 50 photos. The before-validator parses it back to a list;
    # see _coerce_str_list above.
    _coerce_objects = field_validator("objects", mode="before")(_coerce_str_list)
    _coerce_clothing = field_validator("clothing", mode="before")(_coerce_str_list)
    _coerce_generic_tags = field_validator("generic_tags", mode="before")(_coerce_str_list)
    _coerce_task_context_tags = field_validator("task_context_tags", mode="before")(_coerce_str_list)


class RichMetadataVideoScene(RichMetadataPhoto):
    """Per-scene metadata: every photo field + scene-specific extras."""

    model_config = ConfigDict(extra="ignore")
    scene_summary: str = ""  # one-line aggregate of the 3 frame captions


class Stage2AssetOutputs(BaseModel):
    """Per-asset Stage 2 outputs (one per photo or per video scene).

    Embeddings are stored in the cache as .npy and loaded lazily — this
    model carries the path / shape, not the bytes, so the orchestrator
    can pass Stage2 results around cheaply.
    """

    model_config = ConfigDict(extra="ignore")
    content_hash: str
    scene_index: int | None = None
    caption: str = ""
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    narrative_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    embedding_dim: int = 0  # populated when the embedding is computed


class Stage3AssetOutputs(BaseModel):
    """Per-asset Stage 3 outputs."""

    model_config = ConfigDict(extra="ignore")
    content_hash: str
    scene_index: int | None = None
    metadata: RichMetadataPhoto | RichMetadataVideoScene
