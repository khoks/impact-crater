# ADR-0005 — Process topology + language stack

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-28
**Phase:** scaffolding

## Context

The MVP critical path (D-014) requires processing up to 1000 photos and 50 videos in 2–5 hours, on a desktop-only target (D-019), self-hosted-first per the project mission. The work mixes:

- Deterministic media operations: perceptual hashing, scene segmentation, smart-crop, ffmpeg-driven render — all bound by the CV/ML ecosystem (OpenCV, ffmpeg, PIL, perceptual-hash libraries).
- LLM-driven curation: rich per-photo and per-scene metadata (D-009), LLM-as-narrative-judge (N-001), the agentic UX surface (D-013, D-017), and the orchestrator's tool-call loop.
- Long-running async work behind a preview-and-approve UI (D-020, D-022) where the user must see live job progress, then a primary "Approve" + secondary "Refine" twin-action UX after render.

The codebase has to be approachable for a single-engineer team, integrate well with the dominant CV/ML ecosystem, support async I/O for long-running LLM calls, and ship as a self-hosted-first single-binary-feeling install (no docker required for end users — that comes only in v3 hosted-service mode).

The user's E-1.2 redirects ruled out a multi-agent harness for MVP (D-017 — single orchestrator with structured tool calls), kept mobile out of MVP (D-019), and pinned remote-first routing as the MVP default (D-016).

## Decision

**Backend = Python 3.11+ with FastAPI.** Frontend = TypeScript + React. Heavy lifting = Python subprocess workers. Packaging = `pip install impact-crater` plus an `impact-crater` CLI command that starts the local server and opens the browser.

Concretely:

- **Single primary process: a FastAPI app** running on `localhost`. Hosts:
  - HTTP + WebSocket API at `/api/...` (for the React frontend and any future native frontend).
  - The agent orchestrator (D-017) as an in-process async subsystem.
  - The LLM client abstraction (ADR-0007) and routing dispatch.
  - Project / job state management against the SQLite database (ADR-0006).
  - Static-file serving at `/` for the built React frontend.
- **Frontend: TypeScript + React**, built to a `dist/` directory at install time, served as static assets from the FastAPI process. WebSocket connection to `/api/jobs/{id}/stream` for live job progress. No separate frontend server in production.
- **Heavy lifting: Python subprocess workers** spawned by the orchestrator for ffmpeg-driven decoding/encoding, OpenCV pipelines, perceptual-hash batch jobs, and other CPU-bound or memory-heavy operations. At MVP the queue is in-process (asyncio + a worker-pool pattern); graduate to a real queue (Redis/RQ-class) only if scale issues actually appear.
- **Packaging: `pip install impact-crater`** (likely from PyPI eventually; from a wheel locally during development) plus an `impact-crater` console-script entry point. Running `impact-crater` starts the FastAPI server and opens the user's default browser to the local UI. The whole thing feels like a single-binary install to the end user; under the hood it's a Python virtualenv with the React `dist/` checked into the wheel.

The LLM client abstraction (ADR-0007) sits inside this process; both the remote providers (Anthropic, Google at MVP) and the v1 local-LLM runtime (ADR-0008) plug in via the same `LLMClient` Python protocol. No process boundary between the orchestrator and the LLM clients at MVP.

## Alternatives considered

- **Node-everything (TypeScript backend).** The CV/ML ecosystem in Node is materially weaker than Python's: most useful libraries (transformers, OpenCV, ffmpeg-python, perceptual-hash, scenedetect) are first-class in Python and either missing or wrapper-only in Node. A Node backend would end up subprocessing Python for the heavy lifting anyway — net more complexity, worse cohesion. Rejected.
- **Tauri or Electron with a native frontend.** Browser-based UI is sufficient for MVP and avoids native packaging complexity (signing, auto-updaters, per-platform builds). The FastAPI process can later become the "backend" a native chrome talks to without rework. Deferred — revisit if user research shows the browser UX is friction.
- **Rust + Python (Rust hot path).** Rust on the perceptual-hash hot path would be marginally faster than the Python equivalents (`imagehash`, `pdqhash` bindings), but the actual MVP bottleneck is LLM call latency and ffmpeg, both of which are Python-friendly already. Premature optimization — adds a polyglot build chain for a non-bottleneck. Rejected for MVP; revisit if profiling shows Python perceptual hashing is actually a critical-path bottleneck.
- **Go backend.** Same CV/ML ecosystem disadvantage as Node, plus less mature LLM SDKs from the major providers. Rejected.
- **CLI-only (no UI server).** Doesn't fit D-020/D-022 — the preview-and-approve gate with twin Approve/Refine actions is fundamentally a UI surface. CLI + browser-rendered preview adds two processes for what one process handles cleanly. Rejected.
- **Pure backend service + standalone frontend dev server (Vite).** Fine for development; production wants the frontend served from the same process so end users don't need to run two commands. The build-time `dist/` static-asset pattern serves both: dev runs Vite proxying to FastAPI; production serves built assets directly.

## Consequences

- **Single-language backend.** Cognitive load is one language, one ecosystem. Type-checked with `mypy` (strict mode). Linted with `ruff`.
- **One pip install, one command.** End users run `pip install impact-crater` then `impact-crater`. The browser opens to the local UI; everything else is invisible.
- **Frontend as static assets.** The React `dist/` lives inside the published wheel. CI builds the frontend before packaging.
- **Async-first.** All LLM client methods are `async`; the orchestrator is async; FastAPI handlers are async. Sync wrappers only at boundaries where the caller is synchronous (e.g., a CLI subcommand that doesn't need the async context).
- **Subprocess workers managed by the orchestrator.** Workers run ffmpeg / OpenCV / perceptual-hash batches. Failures bubble through structured exceptions; resume logic (A-005) is the orchestrator's responsibility against the persisted snapshot graph (N-003).
- **Adding a native frontend later (Tauri/Electron) is a packaging-only change.** The FastAPI process becomes the "backend" the native frontend talks to over `localhost`. The browser UX stays available.
- **Local LLMs (v1) plug in trivially.** ADR-0008's `LocalLLMClient` slot lives in the same Python process; v1 work imports `vllm` / `llama_cpp` / `ollama` and registers a new provider in the routing config. No architectural rework.
- **Adding CI + auto-update later.** Out of scope at MVP. The pip install path supports `pip install --upgrade` for now; auto-update inside the running app comes when it matters.
- **Hosted-service mode (v3) is a config flip.** The FastAPI + Python + SQLite stack runs equally well as a multi-tenant deployment behind a load balancer with Postgres swapped in for SQLite (ADR-0006 anticipates this).

## Implementation hints (informational, not load-bearing on the ADR)

- Suggested directory layout (when code lands; locked at first feature work, not now):
  - `backend/` — Python package `impact_crater` with `app.py` (FastAPI), `orchestrator/`, `llm_clients/`, `pipeline/`, `storage/`, `connectors/`.
  - `frontend/` — TypeScript + React app; build output in `frontend/dist/`.
  - `prompts/` — versioned prompt templates per operation (referenced by ADR-0007).
  - `config/` — yaml config files (LLM routing per ADR-0009, etc.).
  - `scripts/` — packaging, dev-mode launchers, OS-adapter scripts (`scripts/{windows,mac,linux}/`).
- Suggested test stack: `pytest` + `pytest-asyncio` + `pytest-mock`; `vitest` + `@testing-library/react` for the frontend.
- Suggested Python deps (locked at first feature work, not here): `fastapi`, `uvicorn`, `pydantic`, `anthropic`, `google-generativeai`, `numpy`, `Pillow`, `opencv-python-headless`, `ffmpeg-python`, `imagehash`, `scenedetect`, `httpx`, `aiofiles`, `aiosqlite`.

## Linked items

- D-014 (MVP success criterion — the wall-clock and scale this stack must hit), D-016 (routing default — remote-first MVP, abstraction must exist), D-017 (single-orchestrator harness — lives in this process), D-019 (desktop-only MVP — packaging implication), D-020 + D-022 (publish-approval + refine-loop UX — frontend implication), N-003 (project as versioned artifact — storage implication for ADR-0006), A-005 (failure recovery — orchestrator responsibility).
- Decision-log entry: D-023 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.1.1 in [`project/tasks/`](../../project/tasks/T-1.3.1.1-adr-0005-process-topology-language-stack.md).
- Cascades to: ADR-0006 (storage paths must be Python-writable), ADR-0007 (LLM client protocol is Python), ADR-0008 (local-LLM slot is Python), ADR-0009 (model lineup config is YAML loaded by Python).
