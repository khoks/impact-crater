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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TimeOfDay = Literal[
    "morning", "midday", "golden_hour", "dusk", "night", "indoor", "ambiguous"
]


class PeopleObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    count: int = Field(default=0, ge=0)
    in_focus: list[str] = Field(default_factory=list)


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
