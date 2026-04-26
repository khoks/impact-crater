# Impact Crater

> An AI-driven photo and video curator that turns a pile of raw media plus a natural-language brief into ready-to-publish social-media artifacts — reels, albums, journey videos, montages — previewed in-app and pushed to connected platforms only after you approve.

You give Impact Crater a folder of photos and videos and a sentence about what you want ("a per-location Instagram reel and one full-journey video with a music score from my Grand Canyon trip"), and it does the analysis, selection, sequencing, music matching, and rendering. It chooses between locally hosted vision LLMs and remote API LLMs at runtime based on your hardware (GPU class, VRAM) and any API quotas you've configured, so a workstation with a 4090 leans local and a thin-client laptop leans cloud. Everything previews in a side-by-side viewer before any social post is made.

Self-hosted-first. Open-source under [BSL 1.1](./LICENSE) (auto-converts to Apache 2.0 in 2030).

## Status

**Pre-MVP — scaffolding only.** No application code yet. The repo currently contains the raw vision, the four-level work-tracking system, two auto-running Claude Code skills (knowledge-curator + work-tracker), and the foundation for grooming sessions to come. MVP scope, tech stack, and algorithms will be locked in upcoming grooming sessions and recorded as ADRs.

## Where to look

- **Vision (verbatim user input):** [`docs/vision/RAW_VISION.md`](./docs/vision/RAW_VISION.md)
- **Groomed feature catalog:** [`docs/vision/GROOMED_FEATURES.md`](./docs/vision/GROOMED_FEATURES.md) (stub — populated in next grooming session)
- **Architecture & ADRs:** [`docs/architecture/`](./docs/architecture/)
- **Decision log:** [`docs/decisions/DECISIONS_LOG.md`](./docs/decisions/DECISIONS_LOG.md)
- **MVP scope:** [`docs/roadmap/MVP.md`](./docs/roadmap/MVP.md) (stub)
- **Roadmap (scaffolding → MVP → v1 → v2 → v3):** [`docs/roadmap/ROADMAP.md`](./docs/roadmap/ROADMAP.md)
- **Live status board (Initiatives / Epics / Stories / Tasks):** [`project/BOARD.md`](./project/BOARD.md)
- **For Claude Code sessions:** [`CLAUDE.md`](./CLAUDE.md)

## Platforms

Windows-first development. Target deployment is desktop-class (high-VRAM GPUs help a lot) with optional remote-LLM fallback for thin clients. Mobile remains a v2+ consideration.

## License

[Business Source License 1.1](./LICENSE). Free to self-host for personal, family, or internal team use. Hosting Impact Crater as a paid service to third parties is not permitted until the Change Date (2030-04-25), at which point the code converts to Apache License 2.0.
