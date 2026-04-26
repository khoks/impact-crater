# `docs/decisions/` — The decision log

This folder owns [`DECISIONS_LOG.md`](./DECISIONS_LOG.md), the project's append-only chronological record of choices made between two or more viable options.

## How decisions and ADRs differ

- **A decision** (entry in `DECISIONS_LOG.md` with a `D-NNN` ID) is a choice between known options at a specific point in time. Most decisions are small. The decision log captures them all.
- **An ADR** (file in `docs/architecture/`, e.g. `ADR-0001-license.md`) is an architecturally-significant decision that warrants a longer write-up — context, alternatives considered, consequences. Only some decisions are ADRs.
- A decision can reference an ADR (and vice versa). Big decisions usually have both: a short `D-NNN` entry and a long `ADR-NNNN` file.

## How decisions and inventions differ

- **A decision** is a choice between options that already exist. The decision log captures them.
- **An invention** is a *new mechanism* that may not exist in the public literature. Those go in [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md) with an `N-NNN` ID.
- If you can't tell, file both: a `D-NNN` for the choice and an `N-NNN` for the underlying mechanism.

## Entry format

```markdown
### D-NNN — <short title> (YYYY-MM-DD)

**Status:** accepted | proposed | superseded by D-MMM | rejected

**Context.** What was being decided and why it came up. One short paragraph.

**Decision.** What we chose. One sentence.

**Alternatives considered.** Bullet list — option + why it lost.

**Consequences.** What this commits us to. What it forecloses. Any follow-ups required.

**Linked items.** ADR / Initiative / Epic / Story / PR.
```

Number monotonically (`D-001`, `D-002`, …). Never renumber. If a decision is reversed, append a new entry that supersedes the old one and update the old entry's `Status:` line to `superseded by D-MMM`.

## Who writes here

The `knowledge-curator` skill auto-appends entries at end-of-session for any decisions surfaced in the conversation. Manual entries are also welcome — keep the format consistent.
