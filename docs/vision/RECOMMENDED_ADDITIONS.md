# RECOMMENDED_ADDITIONS.md — Gaps the user didn't mention but the product likely needs

> **Status: stub.** Populated during grooming. The `knowledge-curator` skill appends to this file whenever a session surfaces a future-looking requirement or gap not already covered.

This file captures features, requirements, and capabilities that the **user has not explicitly asked for** in [`RAW_VISION.md`](./RAW_VISION.md), but which Claude (or the user, on reflection) thinks the product needs in order to be a credible product.

The point is to surface gaps early so they can be discussed and either accepted (moved into `GROOMED_FEATURES.md` with a phase tag), rejected (logged here as "considered and rejected" with the reason), or deferred (tagged with a phase and a rationale).

---

## Format

Each addition gets a heading with an `A-NNN` ID (monotonically incrementing, never reused), a one-paragraph description, and a discussion section.

```markdown
### A-001 — <short title> (YYYY-MM-DD)

**Status:** proposed | accepted | rejected | deferred

**Why this matters.** Short paragraph: why the product likely fails or is incomplete without this.

**What it would look like.** One paragraph or a short bullet list — the smallest credible version of the feature.

**Open questions.** Bullets — what we'd need to decide before building.

**Tradeoff against scope.** Honest cost: how much MVP time this would consume vs. the value delivered.
```

---

## Initial candidates (to be discussed in grooming)

The seed list — these are the kinds of gaps the curator skill will commonly file. None of these are accepted yet.

1. **Media library + project model.** A persistent, durable home for the user's source media, with a project (= one trip / shoot / event) being the unit a user works inside.
2. **Privacy posture for faces and locations.** A default policy on whether identifiable faces and geo-tagged locations get shared with remote LLMs, and a clear user-facing toggle.
3. **Publishing audit log.** A timestamped record of every artifact published, where, and from which version of the project — so a user can reverse course or prove provenance later.
4. **Cost / quota dashboard.** A live view of remote-LLM token spend and local-GPU time per project, with hard ceilings.
5. **Failure-recovery / resume.** A long curation pass on 5000 photos cannot lose its work if the laptop sleeps or the network blips.
6. **Multi-version artifact comparison.** When the user asks for an edit, hold both versions side-by-side rather than overwriting.
7. **Quality floor + user override.** A guard that refuses to publish artifacts below a quality threshold, with an explicit override.
8. **Watermark / brand-mark mode.** Optional consistent watermark or brand mark on outputs for the user's content brand.
9. **Accessibility metadata.** Auto-generated alt text and captions for accessibility, with user review before publish.
10. **Backup of source media identity.** Stable identifiers for source media so that re-running curation on the same project gives reproducible results.

(All of the above are *candidates only* until promoted via grooming.)
