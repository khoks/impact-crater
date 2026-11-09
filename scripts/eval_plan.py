"""$0 plan-quality eval (S-3.10.1): eight metrics from a finished snapshot.

    python scripts/eval_plan.py SNAPSHOT_DIR | plan.json | eval_input.json [--out eval.json]
                                [--save-input eval_input.json]
    python scripts/eval_plan.py --compare BEFORE.json AFTER.json

No network, no API key, no media files: a snapshot is read from its files and the
LLM cache (`impact_crater.evaluation`). The result goes to `eval.json` next to the
snapshot unless `--out` says otherwise. `--compare` takes two eval.json files,
prints a per-metric delta table and exits 1 when a metric regressed beyond its
tolerance. Thresholds are provisional until D-058. See docs/dev/eval.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from impact_crater import evaluation


def _load_input(target: Path) -> tuple[evaluation.EvalInput, Path]:
    if target.is_file() and target.name != "plan.json":
        return evaluation.EvalInput.from_json(json.loads(target.read_text("utf-8"))), target.parent
    snapshot_dir = target.parent if target.name == "plan.json" else target
    return evaluation.extract(snapshot_dir), snapshot_dir


def _dump(data: Any, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _evaluate(args: argparse.Namespace) -> int:
    data, folder = _load_input(Path(args.target))
    if args.save_input:
        _dump(data.to_json(), Path(args.save_input))
    out = evaluation.result(data)
    _dump(out, Path(args.out) if args.out else folder / "eval.json")
    width = max(len(m.name) for m in evaluation.METRICS)
    print(f"snapshot {out['snapshot_id']}")
    for m in evaluation.METRICS:
        print(f"  {m.name:<{width}}  {out['metrics'][m.name]:>8}   {m.description}")
    for line in out["threshold_failures"]:
        print(f"  below provisional threshold: {line}")
    return 0


def _compare(before_path: str, after_path: str) -> int:
    before = json.loads(Path(before_path).read_text("utf-8"))["metrics"]
    after = json.loads(Path(after_path).read_text("utf-8"))["metrics"]
    width = max(len(m.name) for m in evaluation.METRICS)
    print(f"  {'metric':<{width}}  {'before':>8}  {'after':>8}  {'delta':>8}  better")
    for m in evaluation.METRICS:
        b, a = before[m.name], after[m.name]
        better = {"higher": "up", "lower": "down", "band": "in band"}[m.direction]
        print(f"  {m.name:<{width}}  {b:>8}  {a:>8}  {round(a - b, 4):>+8}  {better}")
    regressed = evaluation.regressions(before, after)
    for line in regressed:
        print(f"REGRESSION {line}")
    return 1 if regressed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target", nargs="?", help="snapshot dir, its plan.json, or an eval_input.json"
    )
    parser.add_argument("--out", help="where to write eval.json (default: next to the snapshot)")
    parser.add_argument("--save-input", help="also write the extracted eval_input.json here")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args(argv)
    if args.compare:
        return _compare(*args.compare)
    if not args.target:
        parser.error("give a snapshot dir, plan.json or eval_input.json, or --compare")
    return _evaluate(args)


if __name__ == "__main__":
    sys.exit(main())
