# Contributing to Impact Crater

Impact Crater is a single-maintainer project that is public from day one (see [`README.md`](./README.md) for what it is and where it stands). Contributions are welcome; this file is the short version of how they land. The long version of the project's working rules is [`CLAUDE.md`](./CLAUDE.md) — written for AI coding sessions, but every rule in it applies to humans too.

## Licence and sign-off (DCO)

The code is licensed under the [Business Source License 1.1](./LICENSE), converting to Apache License 2.0 on 2030-04-25 ([ADR-0001](./docs/architecture/ADR-0001-license.md)). By contributing you agree that your contribution is licensed under the same terms and converts with the project on the Change Date.

Every commit must carry a [Developer Certificate of Origin](https://developercertificate.org/) sign-off, which `git commit -s` adds for you:

```
Signed-off-by: Your Name <you@example.com>
```

The sign-off certifies that you wrote the change or have the right to submit it under the project licence. It is required on external contributions; the maintainer's own commits and the two housekeeping skills' commits do not carry the trailer today (recorded honestly, 2026-10-25).

## The flow: branch → PR → squash

1. Branch from `master`. Nothing is committed to `master` directly — not even one-line fixes.
2. Make the change. One logical change per PR; keep the diff reviewable.
3. Run the checks below locally (there is no test CI yet — that is tracked as S-3.11.2).
4. Open a pull request against `master`. Merges are always `--squash --delete-branch`, so the PR title becomes the commit subject; write it as a Conventional Commit with the work-item ID (see below).
5. The maintainer reviews and merges. The maintainer's own AI-assisted PRs auto-merge per [ADR-0004](./docs/architecture/ADR-0004-skill-pr-auto-merge.md); external PRs do not.

## Commit and PR titles

[Conventional Commits](https://www.conventionalcommits.org/) with the tracker item ID at the end of the subject:

```
feat(media): wire perceptual-hash dedup pass [T-2.1.3.4]
fix(curator): correct narrative-arc tie-break order [S-2.1.3]
docs(architecture): amend ADR-0013 for env-var credentials [S-2.13.5]
```

Work is tracked in-repo under [`project/`](./project/README.md) (Initiative → Epic → Story → Task, one markdown file per item; [`project/BOARD.md`](./project/BOARD.md) is generated — never hand-edit it). If no item fits your change, say so in the PR and the maintainer will file one; do not invent IDs.

## Checks to run before opening a PR

Backend, from the repo root with the project virtualenv (the lock file pins the tool versions):

```bash
python -m pytest -q
```

```bash
ruff check backend/impact_crater tests scripts
```

```bash
mypy --strict
```

Frontend, inside `frontend/`:

```bash
npm run typecheck && npm test
```

Expectations: `pytest` and the frontend checks must be green. `ruff` and `mypy --strict` are configured but the tree still carries a known baseline of violations (tracked as S-3.11.6), so the rule until that sweep lands is: **a PR adds zero new violations in the files it touches, and formats the files it touches with `ruff format`.** Tests marked `integration` call the real Anthropic / Google APIs and cost money; they are skipped unless `--integration` is passed — do not run them without the maintainer's go-ahead.

If you touch `project/`, run `python scripts/tracker_board.py` and then `python scripts/tracker_board.py --check` before opening the PR.

## Style, in one paragraph

Comments are rare and explain *why*, never *what*. No dead code and no commented-out code. Validate at boundaries, trust internal code. No premature abstraction — three similar lines beat a generic helper. Forward-slash paths everywhere. Python 3.12 (3.11 is the declared floor) with FastAPI; the frontend is React 18 + TypeScript + Vite + Tailwind; Node 20+ (24 in use); ffmpeg + ffprobe on PATH — setup per README → Quick start (`pip install -e ".[dev]"` or the lock-file path). Architectural changes (a new dependency class, a swapped library, a changed security or storage model) need an ADR in `docs/architecture/` — short, dated, with status / context / decision / consequences.

## Dependencies and third-party assets

- Do not add a dependency, model download or media sample casually. Model weights and large media never enter the repo (`.gitignore` already blocks the common extensions).
- Any new third-party ML asset (a model, a weight file, a cascade, a hosted generative model) needs a row in [`NOTICE.md`](./NOTICE.md) with its licence and whether the app ships, downloads or merely references it. Non-commercial-only assets stay opt-in ([D-059](./docs/decisions/DECISIONS_LOG.md)).
- Never add code that scrapes a platform's web UI where an official API exists.
- Publishing to a social platform always goes through the preview-then-approve gate; nothing bypasses it.

## Security issues

Do not open a public issue for a vulnerability. See [`SECURITY.md`](./SECURITY.md).

## Code of conduct

Participation is governed by the [Code of Conduct](./CODE_OF_CONDUCT.md).
