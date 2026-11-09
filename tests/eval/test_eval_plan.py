"""The $0 plan-quality eval harness (S-3.10.1).

The committed fixture is a synthetic trip whose metrics are worked out by hand
below; the real SW-US and Zion snapshots are evaluated locally only until the
owner decides whether trip-derived fixtures may go in the public repo.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from impact_crater import evaluation, paths
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations

pytestmark = pytest.mark.eval

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "eval" / "synthetic_trip.eval_input.json"
_spec = importlib.util.spec_from_file_location("eval_plan", ROOT / "scripts" / "eval_plan.py")
assert _spec is not None and _spec.loader is not None
eval_plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_plan)


def _synthetic() -> evaluation.EvalInput:
    return evaluation.EvalInput.from_json(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_every_metric_on_the_synthetic_trip() -> None:
    # 7 content clips (the title card is not one); 2 are video scenes.
    # Back-steps: a3 (08:00) after v1 (11:00) counts; a4 (07:00) is a callback.
    # Destinations: The Narrows has no media, so 2 of the other 3 are shown.
    # Cells: three clips at 37.2,-112.95. Runs of (day, cell, people): v1#0, v1#1.
    # People: a2, a3, a5. Core cast seen: P1, P2 of 3. a5 is explicit.
    assert evaluation.compute(_synthetic()) == {
        "motion_share": 0.2857,
        "chronology_backsteps": 1,
        "destination_coverage": 0.6667,
        "max_per_viewpoint": 3,
        "max_same_combo_run": 2,
        "people_share": 0.4286,
        "cast_coverage": 0.6667,
        "safety_leaks": 1,
    }


def test_threshold_failures_name_the_metric_and_the_line() -> None:
    metrics = evaluation.compute(_synthetic())
    assert evaluation.threshold_failures(metrics) == [
        "destination_coverage=0.6667 below 1.0",
        "safety_leaks=1 above 0",
    ]


def test_regressions_respect_direction_band_and_tolerance() -> None:
    before = evaluation.compute(_synthetic())
    same = dict(before)
    assert evaluation.regressions(before, same) == []

    worse = {
        **before,
        "motion_share": before["motion_share"] - 0.06,  # beyond the 0.05 tolerance
        "chronology_backsteps": 2,
        "people_share": 0.95,  # out of the band
        "cast_coverage": before["cast_coverage"] - 0.04,  # within tolerance
    }
    assert evaluation.regressions(before, worse) == [
        "motion_share: 0.2857 -> 0.2257",
        "chronology_backsteps: 1 -> 2",
        "people_share: 0.4286 -> 0.95",
    ]

    better = {**before, "safety_leaks": 0, "max_per_viewpoint": 2, "people_share": 0.5}
    assert evaluation.regressions(before, better) == []


def test_empty_inputs_do_not_divide_by_zero() -> None:
    metrics = evaluation.compute(evaluation.EvalInput(snapshot_id="empty", clips=[]))
    assert metrics["motion_share"] == 0.0
    assert metrics["destination_coverage"] == 1.0
    assert metrics["cast_coverage"] == 1.0


def test_input_round_trips_through_json() -> None:
    data = _synthetic()
    assert evaluation.EvalInput.from_json(json.loads(json.dumps(data.to_json()))) == data


async def _write_snapshot(home: Path) -> Path:
    """A tiny finished snapshot on disk: plan, sources, cast, diagnostics and
    cached Stage 3 / brief-intent results, laid out as the pipeline writes them."""
    await run_pending_migrations()
    project = paths.projects_dir() / "p-eval"
    snap = project / "snapshots" / "s-eval"
    (project / "sources").mkdir(parents=True)
    snap.mkdir(parents=True)
    brief = "Our trip to Zion and Angels Landing"
    (snap / "plan.json").write_text(
        json.dumps(
            {
                "project_id": "p-eval",
                "snapshot_id": "s-eval",
                "clips": [
                    {"candidate_ref": "__title__", "kind": "title_card", "role": "title"},
                    {
                        "candidate_ref": "h1",
                        "kind": "photo",
                        "role": "opener",
                        "intended_duration_ms": 4000,
                    },
                    {
                        "candidate_ref": "h2#3",
                        "kind": "video_scene",
                        "role": "peak",
                        "intended_duration_ms": 3000,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    for h, ts, lat, lon in [
        ("h1", "2026-04-03T09:00:00", 37.2149, -112.9516),
        ("h2", "2026-04-03T10:00:00", None, None),
        ("h3", "2026-04-03T11:00:00", None, None),
    ]:
        (project / "sources" / f"{h}.json").write_text(
            json.dumps({"capture_timestamp": ts, "gps_lat": lat, "gps_lon": lon}), "utf-8"
        )
    (project / "cast.json").write_text(
        json.dumps(
            {
                "persons": [
                    {"person_id": "P1", "is_group": True, "content_hashes": ["h1"]},
                    {"person_id": "P2", "is_group": True, "content_hashes": ["h3"]},
                    {"person_id": "P9", "is_group": False, "content_hashes": ["h2"]},
                ]
            }
        ),
        "utf-8",
    )
    decisions = [
        {"ref": "h1", "caption": "Canyon wall in Zion", "quality_score": 0.9},
        {"ref": "h2#3", "caption": "River walk", "quality_score": 0.8},
        {"ref": "h3", "caption": "Chains on Angels Landing", "quality_score": 0.7},
    ]
    (snap / "diagnostics.json").write_text(
        json.dumps({"phases": [{"phase": "stage_4_prefilter", "decisions": decisions}]}), "utf-8"
    )
    cache_dir = home / "eval-cache"
    cache_dir.mkdir()
    payloads = [
        ("h1", "extract_metadata_image", {"people": {"count": 2}, "safety_level": "safe"}),
        ("h2#3", "extract_metadata_image", {"people": {"count": 0}, "safety_level": "explicit"}),
        (
            hashlib.sha256(brief.encode("utf-8")).hexdigest(),
            "parse_user_brief",
            {
                "named_destinations": [
                    {"name": "Zion", "aliases": []},
                    {"name": "Angels Landing", "aliases": []},
                    {"name": "Bryce Canyon", "aliases": ["bryce"]},
                ],
                "chronological": False,
            },
        ),
    ]
    async with connection() as db:
        await db.execute(
            "INSERT INTO projects (id, name, brief) VALUES ('p-eval', 'Eval', ?)", (brief,)
        )
        for i, (content_hash, op, payload) in enumerate(payloads):
            path = cache_dir / f"{i}.json"
            path.write_text(json.dumps(payload), "utf-8")
            await db.execute(
                "INSERT INTO cache_index (cache_key, content_hash, provider, model, "
                "model_version, operation, cache_path) VALUES (?, ?, 'x', 'm', 'v', ?, ?)",
                (f"k{i}", content_hash, op, str(path)),
            )
        await db.commit()
    return snap


async def test_extract_reads_files_and_cache_only(isolated_home: Path) -> None:
    snap = await _write_snapshot(isolated_home)
    data = evaluation.extract(snap)

    assert data.snapshot_id == "s-eval"
    assert data.core_cast == ["P1", "P2"]
    assert data.destinations_named == ["Zion", "Angels Landing", "Bryce Canyon"]
    assert data.destinations_without_media == ["Bryce Canyon"]
    title, photo, scene = data.clips
    assert title.kind == "title_card"
    assert (photo.capture_time, photo.viewpoint) == ("2026-04-03T09:00:00", "37.21,-112.95")
    assert (photo.people_count, photo.cast, photo.safety) == (2, ["P1"], "safe")
    assert photo.destinations == ["Zion"]
    assert (scene.ref, scene.viewpoint, scene.safety) == ("h2#3", None, "explicit")
    assert scene.cast == ["P9"]

    metrics = evaluation.compute(data)
    assert metrics["destination_coverage"] == 0.5  # Zion shown, Angels Landing only in the pool
    assert metrics["cast_coverage"] == 0.5
    assert metrics["safety_leaks"] == 1
    assert evaluation.extract(snap) == data  # deterministic


async def test_cli_writes_eval_json_and_compare_exits_on_regression(
    isolated_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snap = await _write_snapshot(isolated_home)
    assert eval_plan.main([str(snap)]) == 0
    first = (snap / "eval.json").read_text("utf-8")
    assert eval_plan.main([str(snap / "plan.json")]) == 0
    assert (snap / "eval.json").read_text("utf-8") == first
    assert json.loads(first)["metrics"]["safety_leaks"] == 1

    after = tmp_path / "after.json"
    assert eval_plan.main([str(FIXTURE), "--out", str(after)]) == 0
    capsys.readouterr()
    assert eval_plan.main(["--compare", str(snap / "eval.json"), str(snap / "eval.json")]) == 0
    assert eval_plan.main(["--compare", str(after), str(snap / "eval.json")]) == 1
    out = capsys.readouterr().out
    assert "REGRESSION destination_coverage: 0.6667 -> 0.5" in out
    assert "motion_share" in out and "REGRESSION motion_share" not in out
