# NOVEL_IDEAS.md — Inventions and novel-mechanism log

> **Status: empty.** No N-NNN entries filed yet.
>
> ⚠️ **Public-repo warning.** This repository is public from day 1 (decision D-005). A novel idea committed here is *publicly disclosed* the moment it lands on `master`. If you want to preserve patent options for an idea, **file an N-NNN entry in a feature branch first, talk to counsel, and only then merge the branch to master.** The `knowledge-curator` skill defers to this rule by opening a PR rather than auto-merging.

---

## What goes here

This file is the project's record of **novel mechanisms, non-obvious combinations, and potentially-patentable concepts**. Distinguish from the decision log:

- Decisions (in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)) are choices between known options.
- Inventions are *new mechanisms* — algorithms, system architectures, product shapes that may not exist in the public literature.

The skill's job is to flag candidates and preserve the chronology. **The skill does not assess legal patentability** — that is a follow-up the user does, possibly with counsel.

---

## Detection heuristic — when to file an `N-NNN`

Treat an idea as a candidate invention when **any** of the following hold:

- The user describes a mechanism that they cannot easily point to as already existing in a product they know.
- A combination of two or more techniques is being used together in a way the user thinks is unusual.
- An algorithm is being designed (not selected) — choosing how a quality score is computed, how a narrative arc is built, how the local/remote LLM router decides.
- The user explicitly says "this might be patentable" or "I don't think anyone is doing this."
- The discussion produces a rule, threshold, or training signal that is bespoke to this product and not lifted from a paper.

If you're unsure between a decision and an invention, file both: a `D-NNN` for the choice, and an `N-NNN` for the underlying mechanism.

---

## Entry format

```markdown
### N-001 — <short title> (YYYY-MM-DD)

**Status:** proposed | filed-internal | filed-external | published | abandoned

**Inventor(s):** Rahul Singh Khokhar (default)

**Background.** What problem this addresses, and what existing approaches do.

**The invention.** The new mechanism, in plain language. Be precise. Include the steps, the inputs and outputs, and any thresholds or learned components.

**Why we think it is novel.** What makes this non-obvious. Briefly compare to the closest existing approach you know of.

**Where it lives in the system.** Pointer to the doc / module / Story where the implementation will land.

**Disclosure trail.** Date of first session it appeared, link to the conversation if available, link to the merge commit that first made it public (if/when public).
```

Number monotonically (`N-001`, `N-002`, …). Never renumber. Never delete an entry — supersede it with a new entry instead.

---

## Entries

*(none yet)*
