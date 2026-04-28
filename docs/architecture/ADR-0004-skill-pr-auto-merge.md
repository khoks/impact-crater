# ADR-0004 — Auto-merge for skill-generated and feature PRs

**Status:** Accepted (supersedes the "never auto-merge" clause of ADR-0003)
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-26
**Phase:** scaffolding

## Context

ADR-0003 established the branch-and-PR flow for both `knowledge-curator` and `work-tracker` skills, with a hard rule that **neither skill auto-merges**. The user reviewed and merged each PR by hand. The intent was to retain a human review checkpoint over every AI-authored doc / project change before it landed on master.

After running the flow once end-to-end (E-1.2 round 1 closure, session a974bff1, 2026-04-26), the user concluded that the manual-merge step adds friction without adding value at this phase of the project:

- The PR diff is reviewable inside the session as the changes are made (the user sees every Edit / Write tool call live).
- The PR description and the per-commit messages already capture the "what and why" needed for auditability after the fact.
- A merged PR is still fully revertible via `gh pr revert` or a direct `git revert`, so the lossy-vs-lossless distinction is small.
- Branches accumulate when PRs sit waiting for human merges, polluting `gh pr list` and the GitHub web UI.

The user explicitly directed (verbatim, 2026-04-26): **"PRs should be automerged be it the work tracker or knowledge curator or actual work PRs."**

## Decision

**All Claude-generated PRs auto-merge by default.** This applies to:

1. `knowledge-curator` PRs (docs).
2. `work-tracker` PRs (project tracking).
3. **Feature PRs** opened from any future development session.

Concretely:

- The merge strategy is **`gh pr merge <N> --squash --delete-branch --admin`** by default. Squash keeps `master` history linear and one-commit-per-PR; delete-branch keeps `gh pr list` and the GitHub branches view clean. `--admin` invokes the admin-override path so existing branch-protection rules on `master` (e.g., "Require pull-request review before merging") do not block the merge — see the **Branch-protection compatibility** section below for the rationale and the revisit conditions. The PR title becomes the squashed commit subject; the PR body and the per-commit narrative remain visible on the closed PR for after-the-fact review.
- The PR is opened, then immediately merged in the same session.
- The PR is **not held open for asynchronous review** — review happens inside the session, in the conversation transcript.
- This decision **does not relax** any other ADR-0003 rule: the branch-and-PR flow itself stays (no direct commits to master), Conventional Commits messages still required, hooks still run, no `--no-verify`.

## Branch-protection compatibility

The `--admin` flag on the merge command is **not optional**. It is the documented way to make the auto-merge work under the project's current branch-protection settings on `master`.

**Why it is needed.** GitHub branch-protection rules on `master` currently require a pull-request review before merging. Because Impact Crater is, at this phase, a single-contributor project — Rahul is the only human reviewer and is also the PR author for every Claude-generated PR — there is no second human who can satisfy the review requirement. Without `--admin`, every auto-merge attempt fails with `mergeStateStatus: BLOCKED, reviewDecision: REVIEW_REQUIRED`, which would force the user back to the manual-merge step that this ADR explicitly removes. With `--admin`, the merge succeeds because the user's GitHub token has admin rights on the repo.

**Why this is acceptable.** The "review" requirement does not buy anything at this phase: every Edit / Write tool call is visible to the user live during the session (this is the authoritative review per the **Decision** section above). Re-asking for a separate "approve" click on a static GitHub diff after the fact adds no information that the live session did not already surface. The `--admin` path is the explicit-use API for exactly this kind of solo-author workflow.

**What `--admin` does *not* relax.** It does not bypass:

- The branch-and-PR flow itself (the change still goes through a PR; no direct commits to `master`).
- Conventional Commits messages on the constituent commits and the PR title.
- Pre-commit hooks (`--no-verify` is still forbidden).
- The squash-and-delete-branch merge strategy (`--merge` and `--rebase` remain forbidden).

**Revisit triggers.** Drop `--admin` from the skill scripts when *any* of the following is true:

1. A second human contributor (or a CI bot) is reliably available to review and approve PRs without significant latency. At that point, `--auto` (waiting for required reviews) becomes the right flag and the live-session-review claim weakens.
2. CI is configured on `master` and the project decides the CI gate is the authoritative pre-merge check. At that point, branch-protection rules should be reformulated as "require status checks to pass" instead of "require pull-request review", and the merge command can drop `--admin` in favor of `--auto`.
3. The user changes their mind about the live-session-review-is-authoritative stance — at which point this ADR itself is revisited.

Until any of those triggers, `--admin` stays in the merge command. Skills must use it; the hook block-reason must mention it; CLAUDE.md's "Decisions locked" row must reflect it.

## Audit trail

A merged PR is still a permanent record:

- The PR remains visible on GitHub with its full description, per-commit history, and diff.
- The squashed commit on master references the PR number (`(#N)`) so any commit on master is traceable to its originating PR.
- The user can revert any merged change with `gh pr revert <N>` or `git revert <sha>` followed by a fresh PR.
- The conversation transcript that produced the PR is the upstream "review log" — it contains the user's directives, the model's reasoning, and the user's accept / redirect responses to plan-mode proposals.

## Consequences

- **Pros:**
  - Removes a manual step that the user had concluded was redundant given live-in-session review.
  - Master becomes the canonical state at the end of every session — no "in-flight" PRs to remember.
  - `gh pr list` stays clean; mental model is "PRs are work-in-progress only inside a session, then they are merged."
  - Branches don't accumulate.
- **Cons / mitigations:**
  - **No second-pass async review.** Mitigation: the user can always revert. If for a specific high-stakes change the user wants async review, they say so explicitly during the session and the model holds the PR open without merging.
  - **A bad change lands immediately.** Mitigation: the same was true even with manual merge if the user clicked "merge" without re-reading the diff; this ADR formalizes that the in-session review is the authoritative one.
  - **Branch protection on master cannot require external code review** under this model. Acceptable at this phase; revisit when the project has more than one human contributor.
- **Forks of this repo** that prefer the original "never auto-merge" behavior can pin ADR-0003's clause by editing the two SKILL.md files; the auto-merge step is the last action of each skill and is trivially removable.

## Alternatives considered

- **Auto-merge only for housekeeping skills; manual merge for feature PRs.** Splits the model: contributors have to learn which PRs auto-merge and which don't. Rejected — the user explicitly named feature PRs in the directive.
- **Auto-merge with a CI gate.** Sound long-term, but no CI is configured at this phase. Rejected for now; revisit when CI lands (likely E-1.3 or first feature work).
- **Use `--merge` (preserve per-commit history on master) instead of `--squash`.** Preserves more context but bloats master history with "WIP" / "fix typo" commits as sessions evolve. Rejected — squash is cleaner for one-PR-per-coherent-change flow.
- **Use `--rebase` for linear no-merge-commits history.** Equivalent to squash for single-commit PRs but worse for multi-commit PRs (preserves intermediate commits without the squash hygiene). Rejected.

## Implementation

The following files were updated to land this ADR:

**Initial PR (PR #3, squashed commit `a9642bd`, 2026-04-26):**
- `.claude/skills/work-tracker/SKILL.md` — git-flow section: add the `gh pr merge --squash --delete-branch` step; remove the "never merge" admonition.
- `.claude/skills/knowledge-curator/SKILL.md` — same as above.
- `.claude/hooks/post-session-housekeeping.sh` — block-reason text: replace "never auto-merges" with the squash-merge-and-delete-branch instruction.
- `CLAUDE.md` — "Things to never do" list: remove the "Merge an auto-generated PR" line; the new behavior is "merge them after opening" rather than "never merge."
- `docs/decisions/DECISIONS_LOG.md` — append `D-021` recording this policy change with cross-link to this ADR.
- `docs/architecture/ADR-0003-session-housekeeping-skills.md` — Status header updated to reflect the partial supersession.

**Same-day refinement PR (after PR #3 itself required `--admin` to merge under existing branch-protection rules):**
- This ADR — added the **Branch-protection compatibility** section above; updated the **Decision** section's merge-command spec to include `--admin`.
- `.claude/skills/work-tracker/SKILL.md` and `.claude/skills/knowledge-curator/SKILL.md` — merge step in the git-flow section now includes `--admin`; hard-rules list updated.
- `.claude/hooks/post-session-housekeeping.sh` — block-reason text now explicitly mentions `--admin`.
- `CLAUDE.md` — "Decisions locked" skill-git-autonomy row mentions `--admin`.
- Activity logs on `T-1.5.1.1`, `S-1.5.1`, `E-1.5`, `I-1` — same-day refinement noted; statuses unchanged (the original story is still done; this is a tighter spec, not new scope).

## Links

- Decision-log entry: D-021 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)
- Superseded clause: ADR-0003 [`Decision`](./ADR-0003-session-housekeeping-skills.md#decision) — the "never auto-merge" line.
- Skills: [`work-tracker/SKILL.md`](../../.claude/skills/work-tracker/SKILL.md), [`knowledge-curator/SKILL.md`](../../.claude/skills/knowledge-curator/SKILL.md).
- Hook: [`.claude/hooks/post-session-housekeeping.sh`](../../.claude/hooks/post-session-housekeeping.sh).
- Project work item: E-1.5 / S-1.5.1 / T-1.5.1.1.
