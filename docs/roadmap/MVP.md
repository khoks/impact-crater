# MVP.md — Impact Crater MVP scope

> **Status: stub.** The MVP is **not yet locked.** It will be defined during the roadmap-grooming session (Epic `E-1.4`), after vision and architecture are groomed.

The MVP must be small. It must be the **single thinnest end-to-end slice** that proves the core loop: *user uploads media → AI curates → user reviews preview → user approves publish*. Everything beyond that thinnest slice goes to v1 or later.

---

## What the MVP must do (provisional)

These are the rough constraints the MVP definition will respect; they are not yet a feature list.

1. **One artifact type, end-to-end.** Pick one of: per-location reel, journey video with music, multi-photo album, montage. The MVP renders that one artifact type all the way to publish-ready.
2. **One platform connector, end-to-end.** Pick one of: Instagram, Facebook, YouTube, X. The MVP publishes to that one platform with the explicit-consent gate.
3. **One LLM routing path, end-to-end.** Either local-first or remote-first — but the routing abstraction must exist behind it so the second mode is a config flip in v1, not a rewrite.
4. **Project model.** A persistent unit of work. Closing the laptop and re-opening must restore state.
5. **Preview → approve → publish.** No silent publishes ever.

---

## What the MVP must explicitly NOT do (provisional)

- Multiple artifact types in one project.
- Auto photo / video editing (highlights / shadows / colors / etc.). Deferred to v1.
- Inspiration-link learning. Deferred to v1.
- Theme library. Deferred to v1.
- Multi-platform publish. Deferred to v1.
- Mobile UI. Deferred to v2.
- Voice / agentic-conversation editing. Deferred to v2.

---

## Open questions for the grooming session

(These will be answered with explicit decisions and recorded in `DECISIONS_LOG.md`.)

1. **Which single artifact type** is the MVP critical path?
2. **Which single platform** is the first connector?
3. **Local-first or remote-first** routing default?
4. **Which vision-LLM(s)** at the MVP capability tier?
5. **Which video / photo processing engine** does rendering use?
6. **Storage layout** — are projects directories on disk, rows in a DB, or both?
7. **How many photos / how long a video** must the MVP handle on a representative laptop without falling over?
8. **MVP success criterion** — what does "the MVP works" mean concretely? (E.g. "a user can take 100 photos, type a sentence, and post a curated artifact within N minutes.")

---

## Until this stub is filled

Anything that isn't in the (yet to be filled) MVP scope below is automatically v1 or later. The `work-tracker` skill enforces this by tagging out-of-MVP items with `phase: v1+` when it files them.
