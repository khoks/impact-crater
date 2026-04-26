# DECISIONS_LOG.md — Impact Crater chronological decision log

Append-only. Numbered monotonically. See [`README.md`](./README.md) for the format and the difference between decisions, ADRs, and inventions.

---

### D-001 — Project named "Impact Crater" (2026-04-25)

**Status:** accepted

**Context.** The user proposed an AI-driven photo/video curator that turns raw media plus a natural-language brief into ready-to-publish social-media artifacts. A name was needed for the repository, the license, the docs, and the GitHub project URL.

**Decision.** The product is named **Impact Crater**. The GitHub repository slug is `impact-crater`.

**Alternatives considered.** None — the user supplied the name in the original vision.

**Consequences.** Used in the LICENSE Additional Use Grant ("an Impact Crater Service"), in the README, in CLAUDE.md, and in every public artifact going forward. Renaming later is possible but expensive (license, repo URL, prose).

**Linked items.** ADR-0001 (license), GitHub repo `khoks/impact-crater`.

---

### D-002 — License: Business Source License 1.1, Change Date 2030-04-25 (2026-04-25)

**Status:** accepted

**Context.** The user wants free self-hosting for personal / family / team use, but wants to block hosted-service competitors during the early commercial window. They want the code to eventually become permissively open.

**Decision.** License under BSL 1.1 with the *Additional Use Grant* permitting personal / family / team self-hosting and prohibiting hosted-service competition. Change Date is 2030-04-25 (four years from project start). Change License is Apache License 2.0.

**Alternatives considered.**
- *Apache 2.0 from day 1.* Loses the commercial moat. Rejected.
- *All-rights-reserved.* Loses the open-source positioning. Rejected.
- *AGPL.* Doesn't actually block hosted competition. Rejected.

**Consequences.** Must include the LICENSE file at the repo root with the agreed parameters. Any contributor will be subject to BSL 1.1 terms until the Change Date. Forks cannot relicense. On 2030-04-25 (or four years after a specific version's first public release, whichever comes first), the code converts to Apache 2.0 automatically.

**Linked items.** ADR-0001-license.md, [`LICENSE`](../../LICENSE).

---

### D-003 — Work tracking: four-level hierarchy, file-per-item, hierarchical IDs (2026-04-25)

**Status:** accepted

**Context.** The user wants to track Initiatives, Epics, Stories, and Tasks in the repo (not in an external tool), with the ability for a north-star initiative to span multiple sprints' worth of epics. Two shapes were considered: a three-level file-per-item hierarchy and a four-level single-inline-file hierarchy.

**Decision.** Use a four-level hierarchy (Initiative → Epic → Story → Task) with **file-per-item** layout under `project/{initiatives,epics,stories,tasks}/` and **hierarchical IDs** (`I-1`, `E-1.2`, `S-1.2.3`, `T-1.2.3.4`) that never get renumbered.

**Alternatives considered.**
- *Three-level (Epic → Story → Task).* Flattens north-star programs. Rejected — user explicitly named four levels.
- *Four-level inline single file.* Bad for parallel-session merges. Rejected.
- *External tool (GitHub Issues / Jira / Linear).* Loses the offline / clone-and-go ethos. Rejected.

**Consequences.** Templates required for all four levels. The `work-tracker` skill has to scan the relevant subdirectory to allocate the next monotonic ID under a parent. `project/BOARD.md` is hand-maintained (or skill-maintained) as a mirror of frontmatter statuses.

**Linked items.** ADR-0002-work-tracking-hierarchy.md, [`project/README.md`](../../project/README.md).

---

### D-004 — Auto-running session-housekeeping skills with branch-and-PR flow (2026-04-25)

**Status:** accepted

**Context.** Knowledge state and work state generated during a Claude Code session must end up in the repo, not in the chat transcript. The user wants the capture step automated, but wants to retain a review checkpoint by having the changes flow through a pull request rather than land directly on master.

**Decision.** Two project-local skills under `.claude/skills/` — `knowledge-curator` and `work-tracker` — auto-invoked by a `Stop` hook configured in `.claude/settings.json`. Both skills use a strict branch-and-PR flow (branch → commit → push → `gh pr create` against `master`) and **never auto-merge**.

**Alternatives considered.**
- *Direct commits to master.* Faster but no review checkpoint. Rejected.
- *Single combined skill.* Mixes two unrelated concerns. Rejected.
- *Manual invocation only.* Defeats the "automatic" requirement. Rejected.

**Consequences.** Depends on `gh` being installed and authenticated. Depends on `master` being the default branch. PRs accumulate if the user does not review them. Both skills must be no-op-friendly (empty session → no branch, no PR, explicit no-op message).

**Linked items.** ADR-0003-session-housekeeping-skills.md, [`.claude/settings.json`](../../.claude/settings.json), [`.claude/hooks/post-session-housekeeping.sh`](../../.claude/hooks/post-session-housekeeping.sh).

---

### D-005 — GitHub repository public from day 1 (2026-04-25)

**Status:** accepted

**Context.** The user was offered a private-repo option but chose to make the GitHub repository public from the very first commit, prioritizing openness over IP secrecy.

**Decision.** Create the GitHub repo `khoks/impact-crater` with `--public` visibility. Open-source the project from the first commit.

**Alternatives considered.**
- *Private repo to start, public at MVP.* Safer for early-stage IP. Rejected.
- *No GitHub yet, local-only git.* Loses the auto-PR flow that the housekeeping skills require. Rejected.

**Consequences.** Anything committed becomes immediately publicly visible. **Therefore: novel ideas that the user wants to preserve patent options for must be filed in [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md) on a feature branch and discussed with counsel before merging to master.** The `knowledge-curator` skill's PR-only flow gives the user a chance to intercept such ideas before the public-disclosure event of the merge.

**Linked items.** [`README.md`](../../README.md), [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md), GitHub repo `khoks/impact-crater`.
