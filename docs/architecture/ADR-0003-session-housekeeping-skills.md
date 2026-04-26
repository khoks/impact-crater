# ADR-0003 — Session housekeeping skills with branch-and-PR flow

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-25
**Phase:** scaffolding

## Context

Claude Code sessions generate two kinds of state that have to leave the conversation and land in the repo:

1. **Knowledge state** — vision shifts, architectural decisions, novel ideas, scope changes. If this stays only in the chat transcript, it is effectively lost the next session.
2. **Work state** — newly agreed work, status transitions, scope changes, dependency updates on Initiative / Epic / Story / Task items.

The user wants both kinds of state to be captured **automatically at the end of every session**, written into the right canonical doc, and committed to the repo. They also asked that the changes go through a **pull request to master** rather than landing on master directly, so the user retains a review checkpoint.

Two implementation patterns were considered: a **`Stop`-hook-driven nudge** that emits a JSON `decision: block` payload reminding Claude to run housekeeping skills before session end (with a per-session marker file to prevent re-entry loops), and **project-local skills** with explicit detection heuristics, no-op-friendly behavior, and a defined doc-ownership map. The two patterns combine cleanly — the hook drives invocation, the skills do the work.

## Decision

Adopt **two project-local Claude Code skills** under `.claude/skills/`:

1. **`knowledge-curator`** — owns `docs/vision/RECOMMENDED_ADDITIONS.md`, `docs/architecture/ARCHITECTURE.md` and ADRs, `docs/decisions/DECISIONS_LOG.md`, and `docs/vision/NOVEL_IDEAS.md`. Routes content from the conversation into the right doc.
2. **`work-tracker`** — owns the `project/` tree exclusively. Creates new items, transitions statuses, refreshes `project/BOARD.md`.

Both skills are **auto-invoked** by a `Stop` hook configured in `.claude/settings.json`. The hook is a portable bash script that prints a JSON `decision: block` reason instructing Claude to run both skills, with a per-session marker file at `.claude/state/housekept-{session_id}` to ensure the block fires at most once per session and exits silently when `stop_hook_active` is true.

Both skills follow a strict **branch-and-PR flow**:

- Each skill creates a fresh branch (`auto/knowledge-curator-{session_short_id}` or `auto/work-tracker-{session_short_id}`).
- Commits are made on the branch with Conventional Commits messages (`docs(...)`, `chore(project): ...`).
- The branch is pushed to `origin`.
- A pull request is opened against `master` via `gh pr create`, with a generated body summarizing what changed and why.
- The skills **never auto-merge.** The user reviews and merges manually.

If a session contained nothing capture-worthy, each skill exits as an explicit no-op with a one-line message saying so. No empty branches and no empty PRs.

## Consequences

- **Pros:**
  - Knowledge and work state are captured automatically; no chance of being forgotten between sessions.
  - The PR checkpoint means the user can audit any AI-authored doc change before it lands on master.
  - The two skills have clean, non-overlapping ownership, so they can run in parallel without conflicting.
  - The `Stop` hook is a single-script implementation with no external dependencies (no `jq`, no Python).
- **Cons / required dependencies:**
  - Depends on `gh` CLI being installed and authenticated on the user's machine.
  - Depends on `master` being the default branch on the GitHub remote.
  - PRs accumulate if the user does not review them — a future addition could be a periodic auto-close-stale rule.
  - Both skills must be **no-op-friendly**; running them on an empty tactical session must not produce noise.
- **Forks of this repo** will inherit the `.claude/` directory and may want to disable the auto-PR flow to avoid spam in their own remote. The hook is opt-in by virtue of `settings.json` being committed; users who disable the hook lose the auto-housekeeping but the skills remain runnable manually.

## Alternatives considered

- **Skills commit directly to master.** Faster, but loses the review checkpoint on a public repo where prose docs are the main artifact. Rejected.
- **Single combined skill** that handles both knowledge and work. Tempting for simplicity, but the two have very different doc surfaces and the combined skill ends up either too long or too generic. Rejected.
- **Manual invocation only**, no `Stop` hook. The user has to remember to run them every session, which is exactly the failure mode this ADR is trying to prevent. Rejected.

## Links

- Hook script: [`.claude/hooks/post-session-housekeeping.sh`](../../.claude/hooks/post-session-housekeeping.sh)
- Hook config: [`.claude/settings.json`](../../.claude/settings.json)
- Skills: [`.claude/skills/knowledge-curator/SKILL.md`](../../.claude/skills/knowledge-curator/SKILL.md), [`.claude/skills/work-tracker/SKILL.md`](../../.claude/skills/work-tracker/SKILL.md)
- Decision-log entry: D-004 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)
