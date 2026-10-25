<div align="center">
  <a href="https://khoks.github.io/impact-crater/">
    <img src="docs/logo.png" alt="Impact Crater" width="110" />
  </a>
</div>

# Impact Crater

> A dead-simple 1-click media-to-video creator. Dump a pile of photos and videos, describe in your own words what you want and where to post it, click **Submit** — and you're **done**. Behind that one click the AI does everything: analysis, selection, sequencing, music matching, and rendering into ready-to-publish artifacts — reels, albums, journey videos, montages. The one intentional pause is yours: nothing is pushed to your connected platforms until you preview it and approve.

<p align="center">
  <a href="https://notebooklm.google.com/notebook/d7db525d-d686-47d9-995b-211092185d03/artifact/39a9e5a9-eccb-4cd2-a52a-9d07423c4eb0?utm_source=nlm_web_share&utm_medium=google_oo&utm_campaign=art_share_1&utm_content=&utm_smc=nlm_web_share_google_oo_art_share_1_">
    <img src="docs/banner.png" alt="Impact Crater — video masterpieces from your media; you describe, the AI does it" width="100%" />
  </a>
  <br/>
  <a href="https://notebooklm.google.com/notebook/d7db525d-d686-47d9-995b-211092185d03/artifact/39a9e5a9-eccb-4cd2-a52a-9d07423c4eb0?utm_source=nlm_web_share&utm_medium=google_oo&utm_campaign=art_share_1&utm_content=&utm_smc=nlm_web_share_google_oo_art_share_1_"><b>▶ Watch the video overview</b></a> <sub>(preview produced in June 2026)</sub>
</p>

![Impact Crater — from raw media to masterpiece: drop media and describe your vision, the AI analyzes and curates, hardware-adaptive cost balancing, a human-in-the-loop approval gate, and plain-language refinement](docs/From_Raw_Media_to_Masterpiece.png)
<sub>Banner, infographic and video overview: preview produced in June 2026.</sub>

You give Impact Crater a folder of photos and videos and a sentence about what you want ("a per-location Instagram reel and one full-journey video with a music score from my Grand Canyon trip"), click Submit, and you're done — behind that one click it does the analysis, selection, sequencing, music matching, and rendering. The architecture reserves a slot for on-device models; today every AI call goes to the cloud providers you configure (Anthropic and Google), within the daily spend cap you set. Everything previews in a side-by-side viewer before any social post is made.

**What else it does for you** — all in service of making that one click faster, cheaper, and more personal: it stores your feedback on its decisions for the maintainer to act on, builds a cast of the people who recur across a trip's media, caches its analysis so re-runs are fast and cheap, and is building toward the Ultimate Trip Package.

Self-hosted-first. Open-source under [BSL 1.1](./LICENSE) (auto-converts to Apache 2.0 in 2030).

## Status

**MVP: curate→preview proven, publish not yet exercised** (as of 2026-10-25). The curate→preview half of the MVP gate passed on 2026-06-18 on a real 1,663-asset trip (1,481 photos + 182 videos → 2,067 shots → a publish-ready 108-second Story Video). Hardening continued through 2026-07-01. Publishing has never been exercised: the connectors default to dry-run and read their credentials from environment variables, and no real post of any kind has been made. The project resumed on 2026-10-24 with an audited restart plan — [`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md`](./docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md) — whose Phase 0 (truth-and-hygiene) is in progress; Phase 1 is the first real private YouTube publish, which closes the MVP. Under the hood: 21 ADRs, 58 recorded decisions, 15 novel mechanisms, and 29 recommended additions; the locked scope is in [`docs/roadmap/MVP.md`](./docs/roadmap/MVP.md) and the phase-tagged feature catalog in [`docs/vision/GROOMED_FEATURES.md`](./docs/vision/GROOMED_FEATURES.md).

## Quick start

Prerequisites:

- **Python 3.12** (3.11 is the declared floor in `pyproject.toml`; the dev venv and lock file are 3.12)
- **Node 20+** (24 is what development runs on)
- **ffmpeg + ffprobe** — on `PATH`, or pointed to with `IMPACT_CRATER_FFMPEG` / `IMPACT_CRATER_FFPROBE`; the probe and render stages shell out to them. On Windows `winget install Gyan.FFmpeg` is found automatically; on macOS/Linux use your package manager.
- **API keys** for Anthropic and Google — every AI call today goes to those two providers.

```bash
# 1. Install the Python package (editable install for dev)
pip install -e ".[dev]"
#    For a reproducible install matching the maintainer's venv instead:
#    pip install -r requirements-lock.txt && pip install -e ".[dev]" --no-deps

# 2. Build the React frontend (one-time + after frontend changes)
cd frontend
npm install
npm run build
cd ..

# 3. Start the app (opens your default browser)
impact-crater
```

First run shows the first-time-setup wizard: API keys (Anthropic + Google) + daily spend caps. Subsequent runs land on the project dashboard.

For dev mode with hot reload (uvicorn `--reload` + the Vite dev server together) use [`scripts/windows/start.ps1`](./scripts/windows/start.ps1) (one-shot launcher with prerequisite checks) or [`scripts/windows/dev.ps1`](./scripts/windows/dev.ps1). The older [`docs/dev/M0-SMOKE-TEST.md`](./docs/dev/M0-SMOKE-TEST.md) is kept as a historical checklist only.

## Publishing

Connectors for **YouTube**, **Instagram** (container → poll → publish; needs a public HTTPS media URL) and **Facebook** (Page video) exist in the codebase. They read credentials from environment variables, default to **dry-run** (`IC_PUBLISH_DRY_RUN=1` — the request is validated and audited, nothing is sent), and have **never been live-tested**: no real publish has happened yet. In-app OAuth ("Connect in Settings") is not built. Output is 16:9 1080p only. Setup: [`docs/connectors/README.md`](./docs/connectors/README.md), then the per-platform guides for [YouTube](./docs/connectors/youtube-setup.md), [Instagram](./docs/connectors/instagram-setup.md) and [Facebook](./docs/connectors/facebook-setup.md). The preview-then-approve gate stays on regardless of mode.

## Where to look

- **Full product & architecture overview (start here):** [`docs/OVERVIEW.md`](./docs/OVERVIEW.md) — a single, plain-language explanation of the whole application: what it does, what it produces, how the pipeline works end to end, the techniques behind it, the architecture with diagrams, the key flows, and the roadmap. Written for a general audience (no internal jargon).
- **Restart landscape + phase-wise plan (2026-10-24):** [`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md`](./docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md) — the audited state of the project after the mid-2026 pause and the plan from here.
- **Vision (verbatim user input):** [`docs/vision/RAW_VISION.md`](./docs/vision/RAW_VISION.md)
- **Groomed feature catalog:** [`docs/vision/GROOMED_FEATURES.md`](./docs/vision/GROOMED_FEATURES.md)
- **Architecture & ADRs:** [`docs/architecture/`](./docs/architecture/)
- **Decision log:** [`docs/decisions/DECISIONS_LOG.md`](./docs/decisions/DECISIONS_LOG.md)
- **MVP scope:** [`docs/roadmap/MVP.md`](./docs/roadmap/MVP.md)
- **Roadmap (scaffolding → MVP → v1 → v2 → v3):** [`docs/roadmap/ROADMAP.md`](./docs/roadmap/ROADMAP.md)
- **Publishing connectors (setup guides):** [`docs/connectors/`](./docs/connectors/)
- **Live status board (Initiatives / Epics / Stories / Tasks):** [`project/BOARD.md`](./project/BOARD.md)
- **Contributing, security policy, conduct, third-party notices:** [`CONTRIBUTING.md`](./CONTRIBUTING.md) (DCO sign-off, branch → PR → squash, the checks to run), [`SECURITY.md`](./SECURITY.md) (loopback-only today, no API auth yet, how to report), [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md), [`NOTICE.md`](./NOTICE.md) (dependency and ML-model licences)
- **For Claude Code sessions:** [`CLAUDE.md`](./CLAUDE.md)

## Platforms

Windows 11 is the platform the project is developed and tested on; macOS and Linux are untested (their bootstrap scripts under `scripts/mac` and `scripts/linux` are stubs). It runs as a local web app on desktop-class machines; because today's AI work runs on cloud providers, no GPU is required — the reserved on-device model slot is where a high-VRAM GPU will matter later. Mobile remains a v2+ consideration.

## License

[Business Source License 1.1](./LICENSE). Free to self-host for personal, family, or internal team use. Hosting Impact Crater as a paid service to third parties is not permitted until the Change Date (2030-04-25), at which point the code converts to Apache License 2.0. Third-party components and ML model assets — including the opt-in insightface model pack, which is non-commercial-research-only — are listed with their licences in [`NOTICE.md`](./NOTICE.md).
