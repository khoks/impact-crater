## Summary
<!-- What changed and why, with the work-item ID (e.g. S-3.10.1). -->

## Checks
- [ ] `pytest` (from the repo root)
- [ ] `ruff check backend/impact_crater tests scripts`, `ruff format --check`, `mypy`
- [ ] `npm run typecheck` and `npm test` (inside `frontend/`), if the frontend changed

## Eval delta
<!-- Required for any change to Stages 4–7 or to a prompt (docs/dev/eval.md):
     run scripts/eval_plan.py on the same snapshot before and after, then paste
     the output of `scripts/eval_plan.py --compare before/eval.json after/eval.json`.
     Write "n/a" for anything else. -->
