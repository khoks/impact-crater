"""Auto-derived trip cast: unique-face inventory + group-vs-crowd (A-018 / N-012).

Before curation, scan the media set, cluster every detected face into
unique people, and infer which people are "the group" (the trip is about
them) versus incidental "crowd". The novel part (N-012) is the
group/crowd split by **recurrence breadth** — distinct time-windows ×
distinct locations, not raw appearance count: a tour guide who appears 40
times at one stop stays crowd, while a cousin who appears 6 times across
five days and three places is group.

The inventory feeds curation (Stage 5 sees which group members are in each
candidate) and the Stage 6 coverage report ("person X is in 0 selected
clips — add one?"). It also gives crowd removal (A-019) the identity of
who counts as a stranger.

Deterministic clustering + scoring here is fully unit-testable with
synthetic embeddings; the face detection + embedding upstream is what
needs a real model.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

log = logging.getLogger(__name__)

FaceVector = NDArray[np.float32]

# A person is "group" when they recur across enough distinct contexts.
# Breadth = distinct capture-days + distinct locations; a lone-but-frequent
# face at one place/time stays crowd.
_DEFAULT_GROUP_MIN_BREADTH = 3
# Breadth alone over-counts: a stranger photographed twice on two days at two
# places hits breadth=4 and a face-detection false positive that recurs slips
# in too. The travel party is photographed REPEATEDLY and on MULTIPLE DAYS, so
# also require a minimum total appearance count and recurrence across distinct
# days (not just distinct GPS cells within one day).
_DEFAULT_GROUP_MIN_APPEARANCES = 3
_DEFAULT_GROUP_MIN_DAYS = 2
# S-2.10.4: a centroid-level second pass fuses over-split identities. Tighter
# than the per-crop cluster threshold so only genuinely-close clusters merge.
_DEFAULT_CLUSTER_MERGE_THRESHOLD = 0.92
# Crop margin around the detected face box (fraction of box size) — gives
# the embedder hair/jaw context that improves identity matching.
_FACE_CROP_MARGIN = 0.4


# ---- Inputs / outputs --------------------------------------------------


@dataclass
class FaceObservation:
    """One detected face, ready for clustering."""

    content_hash: str
    embedding: FaceVector | None
    capture_timestamp: str | None
    location_key: str | None  # rounded GPS cell or location description
    bbox: tuple[float, float, float, float]  # normalized (x, y, w, h)


@dataclass
class Person:
    person_id: str
    appearance_count: int
    distinct_days: int
    distinct_locations: int
    recurrence_breadth: int
    is_group: bool
    content_hashes: list[str] = field(default_factory=list)


@dataclass
class CastInventory:
    persons: list[Person]
    # content_hash → person_ids present in that photo (group members only,
    # for the compact curation annotation).
    group_persons_by_hash: dict[str, list[str]] = field(default_factory=dict)

    @property
    def group(self) -> list[Person]:
        return [p for p in self.persons if p.is_group]

    @property
    def crowd(self) -> list[Person]:
        return [p for p in self.persons if not p.is_group]


# ---- Face detection + cropping -----------------------------------------


def detect_and_crop_faces(
    image_bytes: bytes, *, margin: float = _FACE_CROP_MARGIN
) -> list[tuple[bytes, tuple[float, float, float, float]]]:
    """Detect faces (mediapipe) and return (crop_jpeg_bytes, norm_bbox) each.

    Reuses the existing privacy-blur detector. Returns [] when mediapipe is
    unavailable or no face is found.
    """
    from impact_crater.media._face_detect import detect_face_boxes

    boxes = detect_face_boxes(image_bytes)
    if not boxes:
        return []
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    out: list[tuple[bytes, tuple[float, float, float, float]]] = []
    for box in boxes:
        bx, by, bw, bh = box
        # Expand by the margin and clamp to the image.
        mx, my = bw * margin, bh * margin
        x0 = max(0.0, bx - mx)
        y0 = max(0.0, by - my)
        x1 = min(1.0, bx + bw + mx)
        y1 = min(1.0, by + bh + my)
        px0, py0, px1, py1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
        if px1 - px0 < 8 or py1 - py0 < 8:
            continue
        crop = img.crop((px0, py0, px1, py1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=90)
        out.append((buf.getvalue(), box))
    return out


# ---- Clustering + group/crowd inference --------------------------------


def build_cast_inventory(
    observations: list[FaceObservation],
    *,
    cluster_threshold: float,
    group_min_breadth: int = _DEFAULT_GROUP_MIN_BREADTH,
    group_min_appearances: int = _DEFAULT_GROUP_MIN_APPEARANCES,
    group_min_days: int = _DEFAULT_GROUP_MIN_DAYS,
    merge_oversplit: bool = True,
    cluster_merge_threshold: float = _DEFAULT_CLUSTER_MERGE_THRESHOLD,
) -> CastInventory:
    """Cluster faces into persons and split group vs crowd by recurrence
    breadth (N-012). Pure/deterministic given the observations.

    "Group" (the travel party) demands all of: enough total appearances,
    recurrence across enough distinct DAYS, and enough overall breadth
    (days+locations). Breadth alone let strangers and face-detection false
    positives in — a person seen twice across two days at two places hit
    breadth 4 and was wrongly tagged group."""
    clusters = _cluster_faces(observations, cluster_threshold)
    if merge_oversplit:
        before = len(clusters)
        clusters = _merge_oversplit_clusters(clusters, cluster_merge_threshold)
        if len(clusters) != before:
            log.info("cast_merge before=%d after=%d", before, len(clusters))

    persons: list[Person] = []
    group_by_hash: dict[str, list[str]] = {}
    for idx, members in enumerate(clusters):
        person_id = f"P{idx + 1}"
        hashes = [m.content_hash for m in members]
        distinct_days = len({_day_key(m.capture_timestamp) for m in members if m.capture_timestamp})
        distinct_locs = len({m.location_key for m in members if m.location_key})
        breadth = distinct_days + distinct_locs
        # Group when recurrence is broad enough AND the person actually
        # recurs: enough appearances, across enough distinct days. A single
        # day/loc with many appearances is the tour-guide case (caught by
        # breadth); two stray appearances across two days is the
        # passing-stranger / false-positive case (caught by appearances+days).
        is_group = (
            len(members) >= group_min_appearances
            and distinct_days >= group_min_days
            and breadth >= group_min_breadth
        )
        persons.append(
            Person(
                person_id=person_id,
                appearance_count=len(members),
                distinct_days=distinct_days,
                distinct_locations=distinct_locs,
                recurrence_breadth=breadth,
                is_group=is_group,
                content_hashes=sorted(set(hashes)),
            )
        )
        if is_group:
            for h in set(hashes):
                group_by_hash.setdefault(h, []).append(person_id)

    # Stable, useful ordering: group first, then by appearance count.
    persons.sort(key=lambda p: (not p.is_group, -p.appearance_count, p.person_id))
    log.info(
        "cast_inventory persons=%d group=%d crowd=%d",
        len(persons),
        sum(1 for p in persons if p.is_group),
        sum(1 for p in persons if not p.is_group),
    )
    return CastInventory(persons=persons, group_persons_by_hash=group_by_hash)


def _cluster_faces(
    observations: list[FaceObservation], threshold: float
) -> list[list[FaceObservation]]:
    """Greedy single-pass cosine clustering. Faces without an embedding
    become their own singleton person (we can't identify them)."""
    clusters: list[list[FaceObservation]] = []
    centroids: list[FaceVector] = []
    for obs in observations:
        vec = obs.embedding
        if vec is None:
            clusters.append([obs])
            centroids.append(None)  # type: ignore[arg-type]
            continue
        best_ci = -1
        best_cos = threshold
        for ci, cen in enumerate(centroids):
            if cen is None:
                continue
            cos = float(np.dot(vec, cen))
            if cos >= best_cos:
                best_cos = cos
                best_ci = ci
        if best_ci >= 0:
            clusters[best_ci].append(obs)
            # Update centroid (running mean, re-normalized).
            members = clusters[best_ci]
            mean = np.mean([m.embedding for m in members if m.embedding is not None], axis=0)
            norm = float(np.linalg.norm(mean))
            centroids[best_ci] = mean / norm if norm else mean
        else:
            clusters.append([obs])
            centroids.append(vec)
    return clusters


def _cluster_centroid(members: list[FaceObservation]) -> "FaceVector | None":
    embs = [m.embedding for m in members if m.embedding is not None]
    if not embs:
        return None
    mean = np.mean(embs, axis=0)
    n = float(np.linalg.norm(mean))
    return mean / n if n else None


def _merge_oversplit_clusters(
    clusters: list[list[FaceObservation]], merge_threshold: float
) -> list[list[FaceObservation]]:
    """S-2.10.4: fuse clusters the greedy single-pass clusterer over-split.

    The order-dependent single pass in `_cluster_faces` can split one person into
    two clusters when their early crops are off-angle; a centroid-level second
    pass repairs that BEFORE the group/crowd recurrence math, so a split party
    member isn't wrongly demoted to crowd. Guards against false merges: clusters
    without embeddings never merge, and two clusters that share a photo are never
    merged (the same person rarely appears twice in one frame)."""
    clusters = [list(c) for c in clusters]
    centroids = [_cluster_centroid(c) for c in clusters]
    hashes = [{m.content_hash for m in c} for c in clusters]
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            if centroids[i] is None:
                continue
            for j in range(i + 1, len(clusters)):
                if centroids[j] is None or (hashes[i] & hashes[j]):
                    continue
                if float(np.dot(centroids[i], centroids[j])) >= merge_threshold:
                    clusters[i].extend(clusters[j])
                    hashes[i] |= hashes[j]
                    centroids[i] = _cluster_centroid(clusters[i])
                    del clusters[j], centroids[j], hashes[j]
                    merged = True
                    break
            if merged:
                break
    return clusters


def _day_key(iso_timestamp: str | None) -> str:
    if not iso_timestamp:
        return "?"
    try:
        return datetime.fromisoformat(iso_timestamp).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return iso_timestamp[:10]


def location_key(gps_lat: float | None, gps_lon: float | None, description: str | None) -> str | None:
    """A coarse location bucket for recurrence breadth — a ~1km GPS cell
    when coordinates exist, else the VLM location description."""
    if gps_lat is not None and gps_lon is not None:
        # ~0.01 degree ≈ 1.1 km — coarse enough that one stop is one cell.
        return f"{round(gps_lat, 2)},{round(gps_lon, 2)}"
    if description:
        return description.strip().lower()[:40]
    return None


# ---- Coverage ----------------------------------------------------------


@dataclass
class CoverageReport:
    """Which group members made it into the final selection (A-018)."""

    covered_person_ids: list[str]
    missing_person_ids: list[str]
    group_size: int

    @property
    def fully_covered(self) -> bool:
        return not self.missing_person_ids


def compute_coverage(
    inventory: CastInventory, selected_content_hashes: set[str]
) -> CoverageReport:
    """Group members present in vs absent from the selected clips.

    Answers the user's "is everyone being included, or did we leave someone
    behind?" — the absentees become a one-click "add a shot of X" repair."""
    covered: list[str] = []
    missing: list[str] = []
    for p in inventory.group:
        if any(h in selected_content_hashes for h in p.content_hashes):
            covered.append(p.person_id)
        else:
            missing.append(p.person_id)
    return CoverageReport(
        covered_person_ids=sorted(covered),
        missing_person_ids=sorted(missing),
        group_size=len(inventory.group),
    )


# Imported for typing only.
_ = Any
