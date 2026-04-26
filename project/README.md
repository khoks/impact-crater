# `project/` — In-repo work tracking (Initiative / Epic / Story / Task)

This folder is Impact Crater's **operational source of truth** for what's done, in progress, and pending. It replaces external tools like Jira, Linear, or GitHub Issues — every work item lives in the repo as one markdown file.

**Read [`BOARD.md`](./BOARD.md) at the start of every session.**

---

## Why in-repo tracking

- **Self-hosted ethos.** Clone the repo and you have everything — no separate accounts, no external services, no API rate limits.
- **Offline-friendly.** Works without an internet connection.
- **Diff-able.** `git log -- project/` is a real audit trail of how scope evolved.
- **AI-agent-friendly.** Future Claude Code sessions read items directly without API calls.
- **Migration path preserved.** A script can sync these markdown items to Linear / GitHub Issues / Jira later if needed.

---

## Hierarchy

Four levels, classic JIRA shape:

| Level | Folder | Spans | Example |
|---|---|---|---|
| **Initiative** | `initiatives/` | Multi-quarter north-star | "Curation engine," "Connector platform," "Adaptive style profile" |
| **Epic** | `epics/` | Weeks; multi-PR slice | "Per-location reel generator," "Instagram connector v1" |
| **Story** | `stories/` | Days to a week; single PR's worth | "Photo perceptual-hash dedup pass" |
| **Task** | `tasks/` | Hours; concrete implementation step | "Write FFmpeg crop filter wrapper" |

**Flat directory per level with hierarchical IDs** — easier to grep, link, and merge than nested folders.

---

## ID conventions

Hierarchical and monotonic per parent:

- Initiatives: `I-1`, `I-2`, `I-3`, …
- Epics: `E-{init}.{n}` — e.g. `E-1.2` is the second epic under Initiative 1.
- Stories: `S-{init}.{epic}.{n}` — e.g. `S-1.2.3`.
- Tasks: `T-{init}.{epic}.{story}.{n}` — e.g. `T-1.2.3.4`.

**IDs are never reused or renumbered**, even after deletion or reorganization. If an item moves to a different parent (rare), record the move in the activity log; the ID stays.

**Filename pattern:** `{ID}-{kebab-case-slug}.md` (e.g. `T-1.1.1.4-write-tracking-templates.md`).

To find the next free ID under a parent, list the children:
```bash
ls project/epics/ | grep '^E-1\.'    # epics under I-1
ls project/tasks/ | grep '^T-1\.2\.3\.'  # tasks under S-1.2.3
```

---

## Frontmatter format

Every item starts with a YAML frontmatter block:

```yaml
---
id: T-1.1.1.4                  # required
title: Write tracking templates
type: task                     # initiative | epic | story | task
status: todo                   # see status values below
priority: P0                   # P0 | P1 | P2 | P3
estimate: S                    # XS<1h | S<4h | M<1d | L<3d | XL>3d (omit for initiatives)
parent: S-1.1.1                # parent ID (omit for initiatives)
phase: scaffolding             # scaffolding | mvp | v1 | v2 | v3
tags: [project, scaffolding]
created: 2026-04-25
updated: 2026-04-25
---
```

**Status values:**
- `todo` — not yet started
- `in-progress` — actively being worked on
- `review` — work done, awaiting review / verification
- `done` — completed and verified
- `blocked` — cannot progress; reason in activity log
- `canceled` — abandoned; reason in activity log

**Priorities:**
- `P0` — critical / blocker for the current phase
- `P1` — important; should land in the current phase
- `P2` — nice-to-have for the current phase
- `P3` — low priority; usually shifts to a later phase

**Phases** match [`docs/roadmap/ROADMAP.md`](../docs/roadmap/ROADMAP.md):
- `scaffolding` — pre-MVP project setup
- `mvp` — single-thin-slice end-to-end
- `v1` — multi-artifact / multi-platform / basic editing
- `v2` — adaptive style + mobile
- `v3` — hosted-service mode + advanced agentic editing

---

## Body format

Below the frontmatter, every item has these sections (use the templates in [`TEMPLATES/`](./TEMPLATES/)):

```markdown
## Description
What this is and why it exists.

## Acceptance criteria
- [ ] Bullet list of testable conditions

## Dependencies
- Blocks: T-1.1.1.5
- Blocked by: T-1.1.1.3

## Activity log
- 2026-04-25 — created
- 2026-04-26 — picked up; status → in-progress
- 2026-04-26 — done
```

Initiatives and Epics also include a `## Children` section listing their immediate descendants. Initiatives include a `## North-star outcome` section in place of `## Acceptance criteria`.

---

## Lifecycle rules

1. **Creating an item:**
   - Copy the relevant template from `TEMPLATES/`.
   - Pick the next free ID under the parent (see above).
   - Save as `{ID}-{slug}.md` in the right folder.
   - Fill frontmatter and body.
   - Append a row to `BOARD.md` in the appropriate section.

2. **Status transitions:**
   - `todo → in-progress → review → done` (review is optional for solo work).
   - `blocked` from any state, with a one-line reason in the activity log.
   - `canceled` from any state, with a reason.
   - **Every status change appends a line to the item's activity log AND updates `BOARD.md`. Bumps the `updated:` field.**

3. **Commits:**
   - One commit per meaningful change so `git log -- project/` is a real audit trail.
   - Commit messages reference the item ID: `chore(project): mark T-1.1.1.4 done` or `feat(curator): scaffold narrative-arc planner [S-2.1.3]`.

4. **Scope changes from future discussions:**
   - New requirement → smallest level that fits (often a Story under an existing Epic).
   - Cancelled scope → set `status: canceled` with reason.
   - Plan documents in `docs/` are updated when meaningful scope shifts; `project/` is the operational truth for individual items.

The `work-tracker` skill (under `.claude/skills/`) automates most of this loop at end-of-session and opens a PR with the resulting board changes. It never auto-merges.

---

## How to find things fast

```bash
# All in-progress items
grep -l "status: in-progress" project/{initiatives,epics,stories,tasks}/*.md

# Everything tagged 'curator'
grep -l "tags:.*curator" project/{initiatives,epics,stories,tasks}/*.md

# All MVP work
grep -l "phase: mvp" project/{initiatives,epics,stories,tasks}/*.md

# All work under Initiative 1
ls project/{epics,stories,tasks}/ | grep -E '^[EST]-1\.'
```

---

## Templates

- [`TEMPLATES/INITIATIVE.md`](./TEMPLATES/INITIATIVE.md)
- [`TEMPLATES/EPIC.md`](./TEMPLATES/EPIC.md)
- [`TEMPLATES/STORY.md`](./TEMPLATES/STORY.md)
- [`TEMPLATES/TASK.md`](./TEMPLATES/TASK.md)
