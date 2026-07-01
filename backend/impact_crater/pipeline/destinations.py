"""Destination→media mapping + the shared reservation primitive (S-2.10.5).

`ReservationSet` is THE source-agnostic "must-keep" lever through Stage 4 — the
Vegas fix. Three consumers build the same object: S-2.10.5 from named
destinations, the refinement layer's `reserve_destination`/`force_include` tools
(`source="refinement"`), and A-023 feedback (`source="feedback"`). Stage 4 has
exactly one reservation-merge path.

Deterministic, no-LLM. Assets are duck-typed (anything with `.key`, `.caption`,
`.location_description`, `.metadata_summary`, `.specialness_score`,
`.quality_score`, `.gps_lat`, `.gps_lon`) so this module does not import Stage 4's
`_Asset` (which imports this) — no cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

log = logging.getLogger(__name__)


@dataclass
class DestMatch:
    name: str
    aliases: list[str] = field(default_factory=list)
    asset_keys: set[str] = field(default_factory=set)  # all matched _Asset.key
    best_keys: list[str] = field(default_factory=list)  # top per_dest, ranked
    basis: Literal["matched", "none"] = "none"
    chronological_hint: int | None = None


@dataclass
class CoveragePlan:
    """The single coverage object Stage 4 populates, Stage 5 reads, diagnostics
    renders."""

    named_destinations: list[DestMatch] = field(default_factory=list)

    def to_prompt_vars(self) -> list[dict[str, Any]]:
        return [
            {"name": d.name, "matched": len(d.asset_keys), "basis": d.basis,
             "chronological_hint": d.chronological_hint}
            for d in self.named_destinations
        ]


@dataclass(frozen=True)
class ReservationSet:
    """Inviolable "must-keep" _Asset.key set threaded through Stage 4."""

    keys: frozenset[str] = frozenset()
    reason_by_key: dict[str, str] = field(default_factory=dict)
    source: Literal["destination", "refinement", "feedback"] = "destination"

    @classmethod
    def from_dest_matches(cls, matches: list[DestMatch]) -> "ReservationSet":
        keys: set[str] = set()
        reasons: dict[str, str] = {}
        for m in matches:
            for k in m.best_keys:
                keys.add(k)
                reasons[k] = f"dest:{m.name}"
        return cls(keys=frozenset(keys), reason_by_key=reasons, source="destination")

    def merged_with(self, other: "ReservationSet | None") -> "ReservationSet":
        if other is None:
            return self
        reasons = dict(self.reason_by_key)
        for k, r in other.reason_by_key.items():
            reasons.setdefault(k, r)  # destination (self) wins a tie
        return ReservationSet(
            keys=self.keys | other.keys,
            reason_by_key=reasons,
            source=self.source,
        )


def _search_text(asset: Any) -> str:
    parts = [
        getattr(asset, "caption", None) or "",
        getattr(asset, "location_description", None) or "",
        getattr(asset, "metadata_summary", None) or "",
    ]
    return " ".join(parts).lower()


def _rank_score(asset: Any) -> float:
    return max(
        float(getattr(asset, "specialness_score", 0.0) or 0.0),
        float(getattr(asset, "quality_score", 0.0) or 0.0),
    )


def map_destinations(
    assets: list[Any],
    named_destinations: list[Any],
    *,
    per_dest: int = 2,
    reverse_geocode: bool = True,
) -> tuple[CoveragePlan, ReservationSet]:
    """Map each named destination to matching media and reserve its best `per_dest`.

    `named_destinations` is a list of objects with `.name`, `.aliases`,
    `.chronological_hint` (BriefIntent.NamedDestination). Layered matching:
    (1) case-insensitive name/alias text match over caption + location +
    metadata; (2) optional offline GPS reverse-geocode (fail-soft — absent dep
    degrades to text-only).
    """
    matches: list[DestMatch] = []
    geo_labels = _reverse_geocode_labels(assets) if reverse_geocode else {}

    for dest in named_destinations:
        name = str(getattr(dest, "name", "")).strip()
        if not name:
            continue
        needles = {name.lower(), *[a for a in (getattr(dest, "aliases", []) or [])]}
        needles = {n for n in needles if n}
        matched: list[Any] = []
        for a in assets:
            text = _search_text(a)
            label = geo_labels.get(getattr(a, "key", None), "")
            hay = f"{text} {label}".strip()
            if any(n in hay for n in needles):
                matched.append(a)
        matched.sort(key=lambda a: (-_rank_score(a), getattr(a, "key", "")))
        best = [getattr(a, "key") for a in matched[:per_dest]]
        matches.append(
            DestMatch(
                name=name,
                aliases=sorted(needles),
                asset_keys={getattr(a, "key") for a in matched},
                best_keys=best,
                basis="matched" if matched else "none",
                chronological_hint=getattr(dest, "chronological_hint", None),
            )
        )
        if not matched:
            log.info("destination_no_media name=%s (basis=none)", name)

    plan = CoveragePlan(named_destinations=matches)
    reservations = ReservationSet.from_dest_matches(matches)
    return plan, reservations


def _reverse_geocode_labels(assets: list[Any]) -> dict[str, str]:
    """Best-effort offline reverse-geocode of each GPS'd asset to a place label.
    Fail-soft: absent `reverse_geocoder` dep → empty map (text matching carries)."""
    try:
        import reverse_geocoder as rg  # type: ignore
    except Exception:
        return {}
    coords: list[tuple[float, float]] = []
    keys: list[str] = []
    for a in assets:
        lat = getattr(a, "gps_lat", None)
        lon = getattr(a, "gps_lon", None)
        k = getattr(a, "key", None)
        if lat is not None and lon is not None and k is not None:
            coords.append((float(lat), float(lon)))
            keys.append(k)
    if not coords:
        return {}
    try:
        results = rg.search(coords)  # offline KD-tree over cities1000
    except Exception as exc:  # noqa: BLE001
        log.info("reverse_geocode failed (text-only): %r", str(exc)[:120])
        return {}
    out: dict[str, str] = {}
    for k, r in zip(keys, results):
        out[k] = f"{r.get('name', '')} {r.get('admin1', '')}".strip().lower()
    return out
