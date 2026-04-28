# CLAUDE.md — Project context for Claude Code sessions

This file is the entry point for any Claude Code session working in this repo. Read it first. Read [`project/BOARD.md`](./project/BOARD.md) second.

---

## Mission (one paragraph)

Impact Crater is an AI-driven photo and video curator. The user feeds it a batch of media (often thousands of photos and videos from a trip, event, or shoot) plus a natural-language brief describing the artifacts they want — per-location reels, multi-photo albums, full-journey music-scored videos, montages — and the app analyzes the media with vision LLMs, picks the best moments, sequences them into a narrative, fits music, renders, previews in-app, and only after explicit user approval publishes to the connected platforms (Instagram, Facebook, YouTube, X, etc). It chooses between locally hosted models (≤ 32B parameters) and remote API LLMs at runtime based on the user's hardware (GPU class / VRAM) and any API quotas they've configured. Self-hosted-first; open-source under BSL 1.1; designed so any future hosted-service mode is a config flip rather than a rewrite.

---

## Decisions locked

| Decision | Choice | Reason |
|---|---|---|
| Project name | Impact Crater | Locked at project init |
| License | BSL 1.1 → Apache 2.0 (Change Date 2030-04-25) | Free for personal/family/team self-host; blocks hosted-service competitors until the Change Date |
| Repo visibility | GitHub public from day 1 | User chose openness over IP secrecy; novel ideas must be filed in `NOVEL_IDEAS.md` *before* the public commit if pre-publication priority matters |
| Work-tracking shape | 4-level Initiative → Epic → Story → Task, file-per-item, hierarchical IDs (`I-1`, `E-1.2`, `S-1.2.3`, `T-1.2.3.4`) | Mirrors what the user asked for; supports multi-quarter north-stars sitting above sprint-scale epics |
| Session housekeeping | Two project-local skills (`knowledge-curator`, `work-tracker`) auto-run via the `Stop` hook in `.claude/settings.json` | Persists session knowledge into the right docs and into `project/` without relying on conversation history |
| Skill git autonomy | Branch + commit + push + open a PR against `master` via `gh`, then **auto-merge with `--squash --delete-branch`** (per [ADR-0004](./docs/architecture/ADR-0004-skill-pr-auto-merge.md)) | Live in-session review is the authoritative review; merged PRs remain revertible via `gh pr revert`; branches don't accumulate. Applies to skill PRs *and* feature PRs. |
| Primary OS for dev | Windows 11 (WSL2 for any Docker work) | User's machine; macOS/Linux supported via OS adapter scripts later |

Tech stack, MVP scope, agent harness shape, vision-model choices, sandbox approach for media processing, storage layout, and connector strategy are **all deferred** to grooming sessions — and will be locked one-at-a-time as ADRs in `docs/architecture/`.

---

## Where to find things

- **The user's verbatim original vision:** [`docs/vision/RAW_VISION.md`](./docs/vision/RAW_VISION.md). Source-of-truth for *intent*. Never edit; addenda go below the rule.
- **Groomed feature catalog (MVP/v1/v2/v3-tagged):** [`docs/vision/GROOMED_FEATURES.md`](./docs/vision/GROOMED_FEATURES.md). Stub today; populated in the vision-grooming session.
- **Gaps the user didn't mention but the product needs:** [`docs/vision/RECOMMENDED_ADDITIONS.md`](./docs/vision/RECOMMENDED_ADDITIONS.md).
- **Novel-ideas / inventions log (N-NNN entries):** [`docs/vision/NOVEL_IDEAS.md`](./docs/vision/NOVEL_IDEAS.md). File ideas here *before* a public commit if you want pre-publication priority.
- **Architecture map:** [`docs/architecture/ARCHITECTURE.md`](./docs/architecture/ARCHITECTURE.md).
- **ADRs:** [`docs/architecture/ADR-*.md`](./docs/architecture/). Update or add an ADR for any architectural change.
- **Decision log:** [`docs/decisions/DECISIONS_LOG.md`](./docs/decisions/DECISIONS_LOG.md). Append-only D-NNN entries.
- **MVP scope:** [`docs/roadmap/MVP.md`](./docs/roadmap/MVP.md). Locked once chosen — anything outside it becomes a backlog Story.
- **Roadmap:** [`docs/roadmap/ROADMAP.md`](./docs/roadmap/ROADMAP.md).
- **Live work tracking:** [`project/BOARD.md`](./project/BOARD.md). **Read this every session before starting work.**

---

## The project tracking system is the source of truth

`project/` is a four-level Initiative → Epic → Story → Task hierarchy stored as one markdown file per item. Do not rely on conversation history to reconstruct what's done or pending. The board is the source of truth.

Every session that touches code or scope follows this loop:

1. Read [`project/BOARD.md`](./project/BOARD.md) — what's `in-progress`, what's `Up Next`?
2. Pick a Task (or get one from the user). Set `status: in-progress`. Append to its activity log: `YYYY-MM-DD — picked up`. Update `BOARD.md`.
3. Do the work.
4. When complete, set `status: done`. Append: `YYYY-MM-DD — done`. Update `BOARD.md`. Commit.
5. New requirement from a discussion? **Create the matching item** (Initiative / Epic / Story / Task — pick the smallest level that fits). Don't just remember it.
6. Cancelled scope? Set `status: canceled`, add the reason to the activity log.

Conventions and frontmatter schema live in [`project/README.md`](./project/README.md). Templates are in [`project/TEMPLATES/`](./project/TEMPLATES/).

The `work-tracker` skill (under `.claude/skills/`) automates this loop at end-of-session, opens a PR with the resulting board changes, and immediately auto-merges it with `--squash --delete-branch` per [ADR-0004](./docs/architecture/ADR-0004-skill-pr-auto-merge.md).

---

## Knowledge curation (auto-running)

The `knowledge-curator` skill (under `.claude/skills/`) runs on the `Stop` hook and routes anything new from the conversation into the right doc:

- Future-looking requirements / vision shifts → `docs/vision/RECOMMENDED_ADDITIONS.md`
- Architecture / scaling / tech-stack / infra discussion → `docs/architecture/ARCHITECTURE.md` (or a new ADR)
- Crucial decisions (option chosen, alternative rejected, scope deferred) → `docs/decisions/DECISIONS_LOG.md` as a new D-NNN entry
- Novel mechanism / non-obvious idea → `docs/vision/NOVEL_IDEAS.md` as a new N-NNN entry
- Long verbatim user dumps → `docs/vision/notes/YYYY-MM-DD-slug.md`

It commits on a fresh branch, pushes, opens a PR against `master` via `gh`, and immediately auto-merges it with `--squash --delete-branch` per [ADR-0004](./docs/architecture/ADR-0004-skill-pr-auto-merge.md). If the session contained nothing capture-worthy, it exits as an explicit no-op.

---

## Coding standards (apply once code lands)

Most coding standards are deferred until the first ADR locks the language(s) and frameworks. The few rules that apply already:

- **Comments are rare.** Default to none. Add one only when the *why* is non-obvious.
- **No dead code.** Delete; don't comment out. No `// removed` tombstones.
- **Validate at boundaries; trust internal code.** No defensive try/catch for impossible cases.
- **No premature abstraction.** Three similar lines beats a generic helper. Don't introduce adapters or interfaces beyond what the architecture explicitly calls for.

The full coding-standards section will be filled in once the language stack ADR lands.

---

## Commit style

[Conventional Commits](https://www.conventionalcommits.org/), with a work-item ID at the end of the subject:

```
feat(media): wire perceptual-hash dedup pass [T-2.1.3.4]
fix(curator): correct narrative-arc tie-break order [S-2.1.3]
chore(project): mark T-1.1.1.5 done
docs(architecture): add ADR-0004 for media analysis pipeline
```

Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `perf`, `ci`, `build`. Scope is the package or area.

**Always reference the lowest-level item ID that fits the change.** If there isn't one, create the item first (the `work-tracker` skill helps).

---

## OS notes

- Primary dev environment is Windows 11 with WSL2 for Docker / Linux containers.
- In code paths and shell snippets, **use forward slashes** and POSIX-style paths. `.gitattributes` normalizes line endings.
- OS-specific bootstrap scripts live under `scripts/{windows,mac,linux}/`. Windows is the implemented one; the others are stubs filled in over time.
- Default to bash syntax for shell snippets in docs unless the snippet is explicitly Windows-only.

---

## Always update an ADR for architectural decisions

If you change the tech stack, swap a library, change a security or sandboxing model, or alter how packages depend on each other — write an ADR in `docs/architecture/`. Format: `ADR-NNNN-short-slug.md`. Status (proposed / accepted / superseded), context, decision, consequences. Keep them short.

---

## The MVP gate

The MVP scope (which artifact types, which platforms, which model routing rules) is **not yet chosen**. It will be locked in [`docs/roadmap/MVP.md`](./docs/roadmap/MVP.md) during the roadmap-grooming session. Once locked, anything outside that scope:

- Goes into `project/` as a new Story or Epic with `status: backlog` and `phase: v1` (or v2/v3).
- Does **not** land in MVP code.

Every "while we're at it…" idea is a chance to bloat the MVP into oblivion. Resist.

---

## Things to never do (without explicit user approval)

- Force-push to `master` (or any branch the user is sharing)
- Commit directly to `master` — every change goes through a branch + PR, even if the PR is auto-merged immediately after opening (per [ADR-0004](./docs/architecture/ADR-0004-skill-pr-auto-merge.md))
- Use `--merge` or `--rebase` on the auto-merge step — it must be `--squash --delete-branch`
- Run `pnpm install` / `npm install` / `pip install` / `cargo build` and materialize dependency trees
- Pull large model weights or media samples into the repo
- Commit with `--no-verify` or any hook bypass
- Publish to any social platform without an explicit user approval prompt — the preview-then-approve gate is fundamental to the product
- Add code that scrapes a platform's web UI in violation of its Terms of Service when an official API exists for the same purpose

---

## When in doubt

1. Re-read this file.
2. Check [`project/BOARD.md`](./project/BOARD.md) for current state.
3. Check the relevant ADR.
4. Ask the user.
