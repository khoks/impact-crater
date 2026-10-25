# ADR-0018 — Local image embedder (CLIP/SigLIP) replaces caption-then-embed

Status: **accepted — staged** (proposed 2026-06-29; interface + stub shipped 2026-07-01 in PR #72; accepted 2026-10-25 under S-2.13.5; the weights backend lands in restart Phase 3 as S-2.10.8 — see the amendment below). Cascades from [ADR-0008](./ADR-0008-local-llm-runtime-slot.md) (local runtime slot) and [ADR-0009](./ADR-0009-cost-tiered-model-lineup.md) (routing).

## Context

Gemini has no native image-embedding endpoint, so Stage 2's `embed_image` captions the image, then embeds the **caption text** (`google_client.py`). The vector therefore lives in caption-text space, not visual space, with two consequences seen in the SW-US-trip job (snapshot `b4b73c7b1fe044b7`):

- Two genuinely different moments with similar captions collide → semantic dedup (cosine ≥ 0.93 within 120s) and the diversity term ride a weak signal.
- Six near-identical Grand Canyon golden-hour shots survived dedup because their captions differed just enough, while a human reads them as one repeated shot.

This is the root cause of the F2/F3 variety/dedup weakness that the Stage 5 prompt caps (S-2.10.3) only treat as a symptom. Anthropic also has no native image-embedding endpoint, so this cannot be fixed by a routing swap — the embedder must be local or third-party.

## Decision (proposed)

Replace caption-then-embed in Stage 2 with a **local image embedder** — `open_clip` (ViT-L/14 or ViT-H/14) or SigLIP — running in the ADR-0008 runtime slot, producing true visual vectors. Keep the Gemini caption-embed as a low-resource / cloud fallback (hardware-tier routing per D-044's philosophy). Re-tune the semantic-dedup and diversity thresholds for the new embedding space (the 0.93 cosine is calibrated for caption-text vectors and will change). Video scene middle-frames embed visually for free.

## Consequences

- New dependency tree + model weights (one-time pull) + a runtime slot — the largest single change in E-2.10; v1, not bundled with the MVP prompt/scoring fixes.
- Removes one Tier-S Flash call per asset (caption-for-embedding) — partial cost offset.
- Similarity thresholds across Stage 4 must be re-validated; near-identical bursts that currently survive should collapse.
- Also unblocks higher-quality cast clustering (a real face/identity signal) if extended there later.

Linked: S-2.10.8, E-2.10, ADR-0008, ADR-0009.

## Amendment 2026-10-25 — accepted, staged (S-2.13.5)

What exists, verified against master `d9bb392`: `media/image_embed.py` holds the `ImageEmbedder` protocol, the `RouterImageEmbedder` default (delegates to the router's caption-then-embed `embed_image`) and `LocalClipImageEmbedder`, a **stub** that returns `None` so callers fall back to the routed op; `build_image_embedder` has zero callers. Stage 2 therefore still embeds caption text through `gemini-embedding-001`. The decision stands as written. It is *accepted* because the restart plan schedules it (`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md` Phase 3 item 2; S-2.10.8 under E-3.1) and *staged* because nothing in it runs yet — the status is not "proposed" any more because the alternative (fixing dedup through prompt caps alone) was tried in S-2.10.3 and treated the symptom.

Conditions S-2.10.8 inherits from this amendment: (1) the hardware probe (S-3.1.5) lands first and picks the device; (2) local vectors are written under a **distinct cache namespace** — the router cache key does not include the media-layer backend, so caption-space and CLIP-space vectors would otherwise collide in the 0.93 dedup cosine; (3) the checkpoint is pinned and its licence recorded in `NOTICE.md` before the flag flips (D-059: open_clip code MIT, LAION checkpoints MIT, SigLIP WebLI checkpoints Apache-2.0 per their model cards, DataComp / DFN checkpoints under their own terms); (4) the 0.93 threshold is re-tuned on the E-3.10 fixtures, with before / after evidence, before the default changes; (5) weights are downloaded to the user's cache at first use, never into the repo or the wheel.

## Amendment 2026-10-25 — remote image embeddings first (D-061)

`gemini-embedding-2` (GA 2026-04-22) embeds image bytes natively into the same space as text at $0.00012 per image, which delivers this ADR's goal — true visual vectors instead of caption-then-embed — without a local runtime. D-061 therefore stages the work: S-2.10.9 switches `embed_image` to gemini-embedding-2 and S-3.10.1 re-tunes the semantic-dedup cosine threshold on the Zion fixture (the 001 and 2 spaces are incompatible); the local open_clip / SigLIP backend described above remains the on-device path for restart Phases 3 / 5 (S-2.10.8), chosen for privacy routing and offline use rather than as the only way to get image vectors.
