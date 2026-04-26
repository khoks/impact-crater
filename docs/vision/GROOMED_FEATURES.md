# GROOMED_FEATURES.md — Impact Crater feature catalog

> **Status: stub.** Populated during the vision-grooming session (Epic `E-1.2`). Until then, every feature lives implicitly in [`RAW_VISION.md`](./RAW_VISION.md) and is unsorted.

This document is the groomed, phase-tagged view of every feature the product should ship over time. It is the bridge between the user's raw brain dump and what actually gets built. Every feature here is tagged with a target phase: `mvp`, `v1`, `v2`, or `v3`.

---

## Format

Features are grouped by **theme** (e.g. *Media ingest*, *Curation*, *Editing*, *Connectors*, *Profile & adaptation*). Each row:

| Feature | Phase | One-line description | Notes / open questions |
|---|---|---|---|

When a feature is broken into a concrete deliverable, it gets a corresponding Story or Epic in `project/` and a link is added to the *Notes* column.

---

## Themes (placeholders)

The likely themes coming out of the raw vision — final list locked during grooming:

1. **Media ingest** — accepting batches of photos and videos, extracting metadata (EXIF, geotags, timestamps).
2. **Curation engine** — analyzing media to identify best moments, unique poses, narrative-worthy locations, faces, scenes.
3. **Artifact generation** — producing reels, montages, journey videos, multi-photo posts, with aspect ratios and music.
4. **Preview + approval** — side-by-side preview UI before any content leaves the device.
5. **Connectors** — Instagram, Facebook, X, YouTube, etc. with explicit-consent publish flows.
6. **LLM routing** — choosing between local (≤ 32B) and remote LLMs based on hardware and quota.
7. **Inspiration learning** — ingesting links to existing posts/reels/videos to learn the user's style.
8. **Theme library** — curated and gradually-learned style themes.
9. **Auto-editing** — highlights, shadows, contrast, color grading.
10. **Agentic editing dialogue** — natural-language back-and-forth refinement of generated artifacts.

---

## Pending

- [ ] Lock the theme list during the vision-grooming session.
- [ ] Tag every feature with `mvp`/`v1`/`v2`/`v3`.
- [ ] Identify which feature is the *single critical artifact* the MVP must produce end-to-end.
- [ ] Cross-link each feature to its corresponding Initiative or Epic in `project/`.
