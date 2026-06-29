# ADR-0018 — Local image embedder (CLIP/SigLIP) replaces caption-then-embed

Status: **proposed** (2026-06-29). Cascades from [ADR-0008](./ADR-0008-local-llm-runtime-slot.md) (local runtime slot) and [ADR-0009](./ADR-0009-cost-tiered-model-lineup.md) (routing).

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
