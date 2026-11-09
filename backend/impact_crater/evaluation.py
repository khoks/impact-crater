"""Plan-quality metrics for the $0 eval harness (S-3.10.1, A-029, D-042).

`extract(snapshot_dir)` turns a finished snapshot into an `EvalInput` using only
files on disk and the LLM cache (no network, no API key, no media files);
`compute(eval_input)` turns that into eight metrics. Same input, same output.

The metric definitions live here and nowhere else, so the judge prompt's
coverage block (S-2.10.3 / S-2.10.5) and a later cap-violation report (S-3.10.3)
can import them instead of re-deriving them. Thresholds are provisional until
D-058 (the written quality gate) replaces them.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import ValidationError

from impact_crater import paths
from impact_crater.pipeline import destinations, stage4_prefilter
from impact_crater.pipeline.types import RichMetadataPhoto, RichMetadataVideoScene

SCHEMA_INPUT = "eval_input/1"
SCHEMA_RESULT = "eval/1"

_CONTENT_KINDS = frozenset({"photo", "video_scene", "burst_montage"})


@dataclass
class EvalClip:
    position: int
    ref: str
    kind: str
    role: str
    duration_ms: int
    capture_time: str | None = None
    viewpoint: str | None = None
    people_count: int | None = None
    cast: list[str] = field(default_factory=list)
    safety: str | None = None
    destinations: list[str] = field(default_factory=list)

    @property
    def has_people(self) -> bool:
        return bool(self.cast) or bool(self.people_count)


@dataclass
class EvalInput:
    snapshot_id: str
    clips: list[EvalClip]
    core_cast: list[str] = field(default_factory=list)
    destinations_named: list[str] = field(default_factory=list)
    # Named in the brief but matched by no media at all: an honest gap, not a miss.
    destinations_without_media: list[str] = field(default_factory=list)
    schema: str = SCHEMA_INPUT

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> EvalInput:
        clips = [EvalClip(**c) for c in data["clips"]]
        return cls(**{**data, "clips": clips})


Direction = Literal["higher", "lower", "band"]


@dataclass(frozen=True)
class Metric:
    name: str
    direction: Direction
    # Provisional pass line until D-058: a minimum ("higher"), a maximum
    # ("lower") or an inclusive (low, high) range ("band").
    threshold: float | tuple[float, float]
    # How far a metric may move the wrong way before --compare calls it a regression.
    tolerance: float
    description: str


METRICS: tuple[Metric, ...] = (
    Metric("motion_share", "higher", 0.10, 0.05, "video-scene clips / content clips"),
    Metric(
        "chronology_backsteps",
        "lower",
        3,
        0,
        "content clips (not callbacks) captured earlier than the clip before them",
    ),
    Metric(
        "destination_coverage",
        "higher",
        1.0,
        0.0,
        "brief-named destinations shown / those any media matches",
    ),
    Metric(
        "max_per_viewpoint",
        "lower",
        stage4_prefilter._DEFAULT_VIEWPOINT_CANDIDATE_CAP,
        0,
        "most content clips from one ~1 km GPS cell",
    ),
    Metric(
        "max_same_combo_run",
        "lower",
        3,
        0,
        "longest run of consecutive clips with the same day, GPS cell and people/no-people",
    ),
    Metric("people_share", "band", (0.15, 0.85), 0.05, "content clips with people / content clips"),
    Metric("cast_coverage", "higher", 0.5, 0.05, "core cast members seen in the cut / core cast"),
    Metric("safety_leaks", "lower", 0, 0, "clips whose metadata marks them explicit"),
)
METRICS_BY_NAME = {m.name: m for m in METRICS}


# ---- Metrics ---------------------------------------------------------------


def compute(data: EvalInput) -> dict[str, float]:
    content = [c for c in data.clips if c.kind in _CONTENT_KINDS]
    n = len(content)

    backsteps = 0
    previous: str | None = None
    for c in content:
        if c.capture_time is None:
            continue
        if previous is not None and c.capture_time < previous and c.role != "callback":
            backsteps += 1
        previous = c.capture_time

    required = [d for d in data.destinations_named if d not in data.destinations_without_media]
    shown = {d for c in content for d in c.destinations}
    per_cell: dict[str, int] = {}
    for c in content:
        if c.viewpoint is not None:
            per_cell[c.viewpoint] = per_cell.get(c.viewpoint, 0) + 1

    longest = run = 0
    last: tuple[str | None, str | None, bool] | None = None
    for c in content:
        combo = ((c.capture_time or "")[:10] or None, c.viewpoint, c.has_people)
        run = run + 1 if combo == last else 1
        longest = max(longest, run)
        last = combo

    seen = {p for c in content for p in c.cast}
    return {
        "motion_share": _ratio(sum(c.kind == "video_scene" for c in content), n),
        "chronology_backsteps": backsteps,
        "destination_coverage": _ratio(sum(d in shown for d in required), len(required), 1.0),
        "max_per_viewpoint": max(per_cell.values(), default=0),
        "max_same_combo_run": longest,
        "people_share": _ratio(sum(c.has_people for c in content), n),
        "cast_coverage": _ratio(sum(p in seen for p in data.core_cast), len(data.core_cast), 1.0),
        "safety_leaks": sum(c.safety == "explicit" for c in data.clips),
    }


def _ratio(num: int, den: int, empty: float = 0.0) -> float:
    return round(num / den, 4) if den else empty


def threshold_failures(metrics: dict[str, float]) -> list[str]:
    """Each metric outside its provisional pass line, as a readable line."""
    out = []
    for m in METRICS:
        value = metrics[m.name]
        if m.direction == "band":
            low, high = m.threshold  # type: ignore[misc]
            if not low <= value <= high:
                out.append(f"{m.name}={value} outside [{low}, {high}]")
        elif m.direction == "higher" and value < m.threshold:  # type: ignore[operator]
            out.append(f"{m.name}={value} below {m.threshold}")
        elif m.direction == "lower" and value > m.threshold:  # type: ignore[operator]
            out.append(f"{m.name}={value} above {m.threshold}")
    return out


def regressions(before: dict[str, float], after: dict[str, float]) -> list[str]:
    """Metrics that moved the wrong way by more than their tolerance."""
    out = []
    for m in METRICS:
        b, a = before[m.name], after[m.name]
        if m.direction == "higher":
            worse = b - a
        elif m.direction == "lower":
            worse = a - b
        else:
            low, high = m.threshold  # type: ignore[misc]
            worse = _band_distance(a, low, high) - _band_distance(b, low, high)
        if worse > m.tolerance:
            out.append(f"{m.name}: {b} -> {a}")
    return out


def _band_distance(value: float, low: float, high: float) -> float:
    return max(low - value, 0.0, value - high)


def result(data: EvalInput) -> dict[str, Any]:
    metrics = compute(data)
    return {
        "schema": SCHEMA_RESULT,
        "snapshot_id": data.snapshot_id,
        "metrics": metrics,
        "threshold_failures": threshold_failures(metrics),
    }


# ---- Extraction from a finished snapshot --------------------------------


def extract(snapshot_dir: Path) -> EvalInput:
    """Build an `EvalInput` from `projects/{project}/snapshots/{snapshot}/` plus the
    project's `sources/`, `cast.json`, the snapshot's `diagnostics.json` and the
    LLM cache. Raises FileNotFoundError when `plan.json` is missing."""
    plan = json.loads((snapshot_dir / "plan.json").read_text(encoding="utf-8"))
    project_dir = snapshot_dir.parent.parent
    db = sqlite3.connect(paths.db_path())
    db.row_factory = sqlite3.Row
    try:
        cast_by_hash, core_cast = _cast(project_dir / "cast.json")
        dest_names, dest_without_media, dest_by_ref = _destinations(
            db, plan["project_id"], snapshot_dir / "diagnostics.json", project_dir
        )
        clips = []
        for position, raw in enumerate(plan["clips"]):
            ref = raw["candidate_ref"]
            base = ref.split("#", 1)[0]
            source = _source(project_dir, base)
            metadata = _cached_metadata(db, ref) if raw["kind"] in _CONTENT_KINDS else {}
            clips.append(
                EvalClip(
                    position=position,
                    ref=ref,
                    kind=raw["kind"],
                    role=raw.get("role") or "",
                    duration_ms=int(raw.get("intended_duration_ms") or 0),
                    capture_time=source.get("capture_timestamp"),
                    viewpoint=_viewpoint(source.get("gps_lat"), source.get("gps_lon")),
                    people_count=(metadata.get("people") or {}).get("count"),
                    cast=sorted(cast_by_hash.get(base, [])),
                    safety=metadata.get("safety_level"),
                    destinations=sorted(dest_by_ref.get(ref, [])),
                )
            )
    finally:
        db.close()
    return EvalInput(
        snapshot_id=plan["snapshot_id"],
        clips=clips,
        core_cast=core_cast,
        destinations_named=dest_names,
        destinations_without_media=dest_without_media,
    )


def _viewpoint(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    dp = stage4_prefilter._VIEWPOINT_CELL_DP
    return f"{round(float(lat), dp)},{round(float(lon), dp)}"


def _source(project_dir: Path, content_hash: str) -> dict[str, Any]:
    path = project_dir / "sources" / f"{content_hash}.json"
    if not path.is_file():
        return {}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _cast(path: Path) -> tuple[dict[str, list[str]], list[str]]:
    if not path.is_file():
        return {}, []
    persons = json.loads(path.read_text(encoding="utf-8")).get("persons") or []
    by_hash: dict[str, list[str]] = {}
    for p in persons:
        for h in p.get("content_hashes") or []:
            by_hash.setdefault(h, []).append(p["person_id"])
    core = sorted(p["person_id"] for p in persons if p.get("is_group"))
    return by_hash, core


def _cached_payload(db: sqlite3.Connection, content_hash: str, operation: str) -> list[Any]:
    """Every cached result for (content_hash, operation), newest first."""
    rows = db.execute(
        "SELECT cache_path FROM cache_index WHERE content_hash = ? AND operation = ? "
        "ORDER BY computed_at DESC, cache_key",
        (content_hash, operation),
    ).fetchall()
    out = []
    for row in rows:
        path = Path(row["cache_path"])
        if path.suffix == ".json" and path.is_file():
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def _cached_metadata(db: sqlite3.Connection, ref: str) -> dict[str, Any]:
    """The newest cached Stage 3 result for `ref`, read through the same model
    Stage 3 validates it with (so a raw-shaped payload is normalised the same way)."""
    model = RichMetadataVideoScene if "#" in ref else RichMetadataPhoto
    for payload in _cached_payload(db, ref, "extract_metadata_image"):
        try:
            return model.model_validate(payload).model_dump()
        except ValidationError:
            continue
    return {}


def _destinations(
    db: sqlite3.Connection, project_id: str, diagnostics_path: Path, project_dir: Path
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """The brief's named destinations (from the cached brief-intent call), which of
    them no media matches, and which destinations each candidate ref matches,
    using the pipeline's own matcher over every Stage 4 candidate."""
    row = db.execute("SELECT brief FROM projects WHERE id = ?", (project_id,)).fetchone()
    brief = (row["brief"] if row else "") or ""
    intent: dict[str, Any] = {}
    if brief:
        key = hashlib.sha256(brief.encode("utf-8")).hexdigest()
        intent = next(
            (
                p
                for p in _cached_payload(db, key, "parse_user_brief")
                if isinstance(p, dict) and "named_destinations" in p
            ),
            {},
        )
    named = [
        SimpleNamespace(
            name=str(d.get("name") or "").strip(),
            aliases=[str(a).strip().lower() for a in d.get("aliases") or [] if str(a).strip()],
            chronological_hint=d.get("chronological_hint"),
        )
        for d in intent.get("named_destinations") or []
        if isinstance(d, dict) and str(d.get("name") or "").strip()
    ]
    if not named or not diagnostics_path.is_file():
        return [d.name for d in named], [], {}

    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    decisions: list[dict[str, Any]] = next(
        (p["decisions"] for p in diagnostics["phases"] if p["phase"] == "stage_4_prefilter"), []
    )
    assets = []
    for d in decisions:
        ref = d["ref"]
        metadata = _cached_metadata(db, ref)
        source = _source(project_dir, ref.split("#", 1)[0])
        assets.append(
            SimpleNamespace(
                key=ref,
                caption=d.get("caption"),
                location_description=(metadata.get("location") or {}).get("description"),
                metadata_summary=(
                    stage4_prefilter._summarize_metadata(metadata) if metadata else None
                ),
                specialness_score=metadata.get("specialness_score", 0.0),
                quality_score=d.get("quality_score") or 0.0,
                gps_lat=source.get("gps_lat"),
                gps_lon=source.get("gps_lon"),
            )
        )
    plan, _ = destinations.map_destinations(assets, named)
    by_ref: dict[str, list[str]] = {}
    for match in plan.named_destinations:
        for key in match.asset_keys:
            by_ref.setdefault(key, []).append(match.name)
    without = [m.name for m in plan.named_destinations if m.basis == "none"]
    return [d.name for d in named], without, by_ref
