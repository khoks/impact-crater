# ADR-0002 — Work tracking: four-level Initiative → Epic → Story → Task

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-25
**Phase:** scaffolding

## Context

The project needs a JIRA-like work-tracking system that:

- Lives **in the repo** (no external services), so a clone has the full picture.
- Survives across Claude Code sessions, since session memory is not durable.
- Maps cleanly onto the user's mental model — they specifically asked for "initiatives, epics, stories, and tasks within those stories."
- Lets a multi-quarter north-star ("Build the curation engine") sit above sprint-scale work ("Per-location reel generator") without the two getting confused.
- Is grep-friendly so that filtering by status, phase, or owner is a one-liner.

Two shapes were on the table: a **three-level** hierarchy (Epic → Story → Task), which is simpler but flattens long-horizon programs into the same level as sprint-scale epics, and a **four-level inline** hierarchy stored in a single markdown file, which is grep-resistant and merges poorly when multiple sessions edit the same file.

## Decision

Use a **four-level hierarchy**: Initiative → Epic → Story → Task, stored as **one markdown file per item** under `project/{initiatives,epics,stories,tasks}/`.

**ID convention** is hierarchical and monotonic per parent:

- Initiatives: `I-1`, `I-2`, …
- Epics: `E-{initiative}.{n}` — e.g. `E-1.2` is the second epic under Initiative 1.
- Stories: `S-{initiative}.{epic}.{n}` — e.g. `S-1.2.3`.
- Tasks: `T-{initiative}.{epic}.{story}.{n}` — e.g. `T-1.2.3.4`.

**IDs are never reused or renumbered**, even after deletion or reorganization.

**Filename pattern:** `{ID}-{kebab-case-slug}.md` (e.g. `T-1.1.1.4-write-tracking-templates.md`).

**Status values:** `todo`, `in-progress`, `review`, `done`, `blocked`, `canceled`. Each item has a frontmatter block with `id`, `title`, `type`, `status`, `priority`, `parent`, `phase`, `tags`, `created`, `updated`, plus an `## Activity log` at the bottom.

**`project/BOARD.md`** is a hand-maintained mirror of frontmatter statuses, sectioned into *In Progress / Up Next / Backlog / Recently Done* plus an *Initiative index*.

The `work-tracker` skill (under `.claude/skills/`) automates frontmatter / activity-log / board updates at end-of-session.

## Consequences

- **Pros:**
  - Hierarchical IDs are self-describing — `T-1.2.3.4` immediately tells you which initiative, epic, and story it belongs to.
  - File-per-item plays well with git: each item's history is independent, merges cleanly across sessions, and is greppable.
  - Four levels accommodate north-star initiatives without distorting the epic level.
- **Cons:**
  - When children move to a different parent (rare), their IDs become misleading. The mitigation is the never-renumber policy: the historical ID stays, and the move is recorded in the activity log.
  - Filename count grows over time. Mitigated by `phase` tagging and a future `archived/` folder for closed initiatives.
- **Implications:**
  - Templates in `project/TEMPLATES/` are required for each level (`INITIATIVE.md`, `EPIC.md`, `STORY.md`, `TASK.md`).
  - The `work-tracker` skill's ID-allocation rule is "monotonic per parent" — it must read the existing children of the parent to allocate the next ID.

## Alternatives considered

- **Three-level (Epic → Story → Task).** Simpler, but no clean home for multi-quarter programs. Rejected because the user explicitly named four levels.
- **Single-file inline.** Easier to read top-to-bottom, but merges poorly across parallel sessions and fights `git blame`. Rejected for a project that will see many short sessions.
- **GitHub Issues.** Ties the project to GitHub's UI and API; loses the offline / clone-and-go ethos; harder for Claude to manipulate without API rate limits. Rejected.

## Links

- Hierarchy spec: [`project/README.md`](../../project/README.md)
- Templates: [`project/TEMPLATES/`](../../project/TEMPLATES/)
- Live board: [`project/BOARD.md`](../../project/BOARD.md)
- Decision-log entry: D-003 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)
