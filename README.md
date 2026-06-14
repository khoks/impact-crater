# Impact Crater

> An AI-driven photo and video curator that turns a pile of raw media plus a natural-language brief into ready-to-publish social-media artifacts — reels, albums, journey videos, montages — previewed in-app and pushed to connected platforms only after you approve.

You give Impact Crater a folder of photos and videos and a sentence about what you want ("a per-location Instagram reel and one full-journey video with a music score from my Grand Canyon trip"), and it does the analysis, selection, sequencing, music matching, and rendering. It chooses between locally hosted vision LLMs and remote API LLMs at runtime based on your hardware (GPU class, VRAM) and any API quotas you've configured, so a workstation with a 4090 leans local and a thin-client laptop leans cloud. Everything previews in a side-by-side viewer before any social post is made.

Self-hosted-first. Open-source under [BSL 1.1](./LICENSE) (auto-converts to Apache 2.0 in 2030).

## Status

**MVP build in progress** as of 2026-05-03. Scaffolding phase is done (16 ADRs, 39 D-NNN decisions, 11 novel mechanisms, placeholder-free `MVP.md` / `ROADMAP.md` / `ARCHITECTURE.md`). The MVP is partitioned into 9 milestones (M0..M9 — see [`docs/roadmap/MVP.md`](./docs/roadmap/MVP.md)); the first one (M0 Scaffolding) lives under [`E-2.1`](./project/epics/E-2.1-scaffolding.md).

## Quick start (developers, M0)

> M0 ships the empty bootable shell. The pipeline lands incrementally over M1..M9.

Prerequisites: Python 3.11+ and Node 20+.

```bash
# 1. Install the Python package (editable install for dev)
pip install -e ".[dev]"

# 2. Build the React frontend (one-time + after frontend changes)
cd frontend
npm install
npm run build
cd ..

# 3. Start the app (opens your default browser)
impact-crater
```

First run shows the first-time-setup wizard: API keys (Anthropic + Google) + daily spend caps. Subsequent runs land on the empty project dashboard.

For dev-mode with hot-reload (Vite + uvicorn together), see [`docs/dev/M0-SMOKE-TEST.md`](./docs/dev/M0-SMOKE-TEST.md).

## Where to look

- **Full product & architecture overview (start here):** [`docs/OVERVIEW.md`](./docs/OVERVIEW.md) — a single, plain-language explanation of the whole application: what it does, what it produces, how the pipeline works end to end, the techniques behind it, the architecture with diagrams, the key flows, and the roadmap. Written for a general audience (no internal jargon).
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
