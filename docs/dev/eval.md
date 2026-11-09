# Plan-quality eval harness

`scripts/eval_plan.py` scores a finished video's plan on eight metrics at $0. It reads only files on disk and the LLM cache: no network, no API key, no media files. Use it to put before/after numbers on any change to Stages 4–7 or to a prompt.

The metric definitions, their provisional pass lines and their regression tolerances live in one place, `backend/impact_crater/evaluation.py` (`METRICS`). The pass lines are provisional until decision D-058, the written quality gate, replaces them.

## Score a snapshot

```bash
PYTHONPATH=backend python scripts/eval_plan.py ~/.impact-crater/projects/<project>/snapshots/<snapshot>
```

This prints the eight metrics and writes `eval.json` next to the snapshot. Options:

- `--out path`: write the result somewhere else.
- `--save-input path`: also write the extracted `eval_input.json`, the compact per-clip facts the metrics are computed from.

The target can also be the snapshot's `plan.json`, or a saved `eval_input.json`.

## Compare two runs

```bash
PYTHONPATH=backend python scripts/eval_plan.py --compare before/eval.json after/eval.json
```

This prints a per-metric table (before, after, delta, which way is better). It exits 1 when any metric moved the wrong way by more than its tolerance, printing `REGRESSION <metric>: <before> -> <after>`.

## The metrics

| Metric | Better | Provisional line | What it counts |
|---|---|---|---|
| `motion_share` | higher | ≥ 0.10 | video-scene clips / content clips (the title card is not content) |
| `chronology_backsteps` | lower | ≤ 3 | clips captured earlier than the clip before them, callbacks excepted |
| `destination_coverage` | higher | = 1.0 | brief-named destinations shown / named destinations any media matches; one no media matches is an honest gap, not a miss |
| `max_per_viewpoint` | lower | ≤ 4 (the Stage 4 per-cell cap) | most clips from one ~1 km GPS cell |
| `max_same_combo_run` | lower | ≤ 3 | longest run of consecutive clips with the same capture day, GPS cell and people/no-people |
| `people_share` | in band | 0.15–0.85 | clips with people (cast match or a people count) / content clips |
| `cast_coverage` | higher | ≥ 0.5 | core cast members seen in the cut / core cast |
| `safety_leaks` | lower | = 0 | clips whose Stage 3 metadata marks them explicit |

Where each fact comes from:

- **Clip list:** `plan.json`.
- **Capture times and GPS:** the project's `sources/*.json`.
- **Cast:** the project's `cast.json`.
- **People count and safety:** the newest cached Stage 3 result, read through the same model Stage 3 validates it with.
- **Named destinations:** the cached brief-intent call for the project's brief, matched against every Stage 4 candidate with the pipeline's own `destinations.map_destinations`.

A snapshot made before brief intent existed (late June 2026) has no named destinations, so its coverage is 1.0 by definition.

## Tests and fixtures

`pytest -m eval` runs `tests/eval/`; the tests also run in the normal suite and in CI. The committed fixture, `tests/fixtures/eval/synthetic_trip.eval_input.json`, is a synthetic trip whose metrics are worked out by hand in the test.

Fixtures taken from real trips (the SW-US reference snapshot `b4b73c7b1fe044b7` and a Zion snapshot) are evaluated locally only, for now. Their `eval_input.json` carries capture times, GPS cells and person ids from a real trip, and whether those may go into the public repository is the owner's decision.
