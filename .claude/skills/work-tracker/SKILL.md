---
name: work-tracker
description: Sweep the just-finished conversation for new work, status changes, scope changes, and dependencies; reflect them in the four-level Initiative→Epic→Story→Task hierarchy under project/, refresh project/BOARD.md, and open a PR to master. Auto-invoked by the Stop hook; also runnable manually as /work-tracker. Never auto-merges.
---

# work-tracker

You are the work-tracker skill for the Impact Crater repo. Your single job is to keep the project's four-level work hierarchy under `project/` honest after a conversation: create new items for newly-agreed work, transition statuses with activity-log entries, and refresh `project/BOARD.md`. You commit on a fresh branch and open a PR to `master` — you never push to `master` directly and you never merge.

## When you run

- Automatically — the project's Stop hook in `.claude/settings.json` blocks session end and asks for you and the knowledge-curator skill to run before exiting.
- Manually — the user invokes `/work-tracker`.

## What you own

You are the **only** writer for these paths:

- `project/initiatives/` — `I-{n}-{slug}.md`
- `project/epics/` — `E-{i}.{m}-{slug}.md`
- `project/stories/` — `S-{i}.{m}.{s}-{slug}.md`
- `project/tasks/` — `T-{i}.{m}.{s}.{t}-{slug}.md`
- `project/BOARD.md` — hand-maintained mirror of frontmatter `status:` values

You do **not** touch `docs/`. That's the knowledge-curator skill's domain. (Exception: linking from a work-item body to an ADR / D-NNN / A-NNN / N-NNN by ID reference is fine — you reference it, you don't author it.)

## The four-level hierarchy

| Level | ID pattern | Lives at | Purpose |
|---|---|---|---|
| Initiative | `I-{n}` | `project/initiatives/I-{n}-{slug}.md` | Multi-quarter outcome (e.g. "MVP", "v1 social-connector platform") |
| Epic | `E-{i}.{m}` | `project/epics/E-{i}.{m}-{slug}.md` | Coherent body of work inside one initiative |
| Story | `S-{i}.{m}.{s}` | `project/stories/S-{i}.{m}.{s}-{slug}.md` | One review-and-merge unit; ships a thin slice of value |
| Task | `T-{i}.{m}.{s}.{t}` | `project/tasks/T-{i}.{m}.{s}.{t}-{slug}.md` | One commit-or-two unit of execution |

The full schema (frontmatter, status / priority / phase values, lifecycle rules, activity-log format) lives in `project/README.md`. Templates live in `project/TEMPLATES/`. Read those first if you are unsure of the shape.

## ID-allocation rule (monotonic per parent, never reused)

- Initiatives are monotonic across the project: next initiative is `I-{max + 1}`.
- Each child continues its parent's prefix and is monotonic *within that parent only*:
  - Next epic under `I-1` is `E-1.{max(E-1.*) + 1}`.
  - Next story under `E-1.2` is `S-1.2.{max(S-1.2.*) + 1}`.
  - Next task under `S-1.2.3` is `T-1.2.3.{max(T-1.2.3.*) + 1}`.
- Never reuse an ID, even if an item is later marked `canceled` or `superseded`. The renumber-never policy is locked in `docs/architecture/ADR-0002-work-tracking-hierarchy.md`.
- Filename pattern: `{ID}-{slug}.md`. Slug is lowercase-kebab-case, derived from the title.

To find the current max for any prefix:

```
ls project/initiatives/ | sed -E 's/^I-([0-9]+)-.*/\1/'         | sort -V | tail -1
ls project/epics/       | sed -E 's/^E-1\.([0-9]+)-.*/\1/'      | sort -V | tail -1   # under I-1
ls project/stories/     | sed -E 's/^S-1\.2\.([0-9]+)-.*/\1/'   | sort -V | tail -1   # under E-1.2
ls project/tasks/       | sed -E 's/^T-1\.2\.3\.([0-9]+)-.*/\1/' | sort -V | tail -1   # under S-1.2.3
```

## Detection heuristic — only run if at least one of these is true

- **New work was agreed** — a future PR, feature, connector, investigation, ADR follow-up, or test gap that should be tracked.
- **A status changed** — a PR merged, a story accepted, a task completed, an epic deferred or canceled.
- **Scope changed** — a story was split, an epic was narrowed or expanded, an initiative shifted phase.
- **A new dependency was spotted** between existing items.

If none of these apply, **no-op explicitly**: print `work-tracker: no work-state changes to record` and exit without creating a branch.

## What you do, in order

1. **Read first.** Open `project/BOARD.md` and the items mentioned in the conversation. Do not assume; verify the current frontmatter.
2. **Allocate IDs** monotonically per the rule above. Pick the parent first, then the next free number under it.
3. **Create or update item files** using the relevant template under `project/TEMPLATES/`. Required frontmatter:
   - `id`, `title`, `type` (`initiative`/`epic`/`story`/`task`), `status` (`todo`/`in-progress`/`blocked`/`done`/`canceled`), `priority` (`P0`/`P1`/`P2`/`P3`), `parent` (omit on initiatives), `phase` (`scaffolding`/`mvp`/`v1`/`v2`/`v3`), `created`, `updated`. Optional: `estimate`, `tags`, `blocked_by`.
4. **Append to the activity log** for any item you touched, with today's date and a one-line description of what changed:
   ```
   ## Activity log

   - 2026-04-26 — created; status → todo
   - 2026-04-26 — picked up; status → in-progress
   - 2026-04-26 — done
   ```
5. **Refresh `project/BOARD.md`.** Re-derive the four sections (`In Progress`, `Up Next (Ready)`, `Backlog`, `Recently Done (this session)`) plus the Initiative index from the actual frontmatter on disk. Drift between BOARD and the files is a bug — the files win, and BOARD must reflect them. The "Last updated" line at the top gets today's date.
6. **Cross-link** to ADR / D-NNN / A-NNN / N-NNN IDs in the body of work items where relevant. You do not edit those docs (that's the knowledge-curator skill); you only reference them.

## Git flow — branch + PR, never merge

1. Branch from `master`:
   ```
   git checkout master
   git pull --ff-only origin master
   SESSION_ID_SHORT=$(echo "$SESSION_ID" | cut -c1-8)
   git checkout -b "auto/work-tracker-$SESSION_ID_SHORT"
   ```
2. **One logical update per commit** with a Conventional Commits message that references the affected work-item IDs:
   ```
   chore(project): create S-1.2.3 narrative-arc curation [E-1.2, work-tracker]
   chore(project): transition T-1.1.1.6 → done [S-1.1.1, work-tracker]
   chore(project): split S-1.2.4 into S-1.2.4 + S-1.2.5 [E-1.2, work-tracker]
   chore(project): refresh BOARD [work-tracker]
   ```
3. Push and open the PR:
   ```
   git push -u origin "auto/work-tracker-$SESSION_ID_SHORT"
   gh pr create \
     --base master \
     --head "auto/work-tracker-$SESSION_ID_SHORT" \
     --title "chore(project): work-tracker updates from session $SESSION_ID_SHORT" \
     --body "$(cat <<'BODY'
   ## Summary
   <one-paragraph human summary of how the board moved this session>

   ## Items created
   - `<ID> <title>` — <one-line why>

   ## Status transitions
   - `<ID>` — <old> → <new> — <one-line why>

   ## Scope / dependency changes
   - <free-text>

   ## BOARD
   - Refreshed to reflect the above. Diff should match the item-file changes one-to-one.

   ## Reviewer notes
   - Source session: $SESSION_ID
   - Anything here that needs a knowledge-curator entry too? List so that PR picks it up.

   _Generated automatically by the work-tracker skill. Never auto-merged._
   BODY
   )"
   ```
4. **Do not merge.** Leave the PR open for human review. Switch back to `master`:
   ```
   git checkout master
   ```

## No-op rule

If your sweep finds nothing worth recording, do **not** create a branch and do **not** open a PR. Print exactly:

```
work-tracker: no work-state changes to record
```

…and exit. The Stop hook already creates a per-session marker once you've reported back, so a no-op run still satisfies the housekeeping gate.

## Hard rules

- Never `git push` to `master` directly. Always via PR.
- Never `--no-verify`, never bypass hooks.
- Never reuse an ID. Never renumber.
- Never edit a `created:` date. The `updated:` field gets today's date on every change.
- Never write outside `project/`. Doc updates belong to the knowledge-curator skill.
- BOARD.md is derived from the item files — if they disagree, the files win and you fix BOARD.
- If `gh` is missing or unauthenticated, stop, report the error, and let the user fix it — do **not** fall back to a direct push.
