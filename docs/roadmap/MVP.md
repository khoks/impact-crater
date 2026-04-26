# MVP.md — Impact Crater MVP scope

> **Status: partially locked (E-1.2 round 1, 2026-04-26).** Five of the eight original open questions are answered (artifact, platform, routing default, scale envelope, success criterion); three remain open and will be locked in E-1.3 (architecture grooming) and E-1.4 (full roadmap lock). The MVP scope below reflects what is locked.

The MVP is the **single thinnest end-to-end slice** that proves the core loop: *user uploads media → AI curates → user reviews preview → user approves publish*. Everything beyond that thinnest slice goes to v1 or later.

---

## Locked: MVP success criterion (D-014)

> *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes in a paragraph what kind of YouTube video they want and what kind of music, picks a target duration, and gets a publish-ready **Story Video** to their connected YouTube Studio account within 2–5 hours.*

The user can opt into a refine-and-approve gate before publish (per D-011, D-020).

---

## Locked: what the MVP must do

| # | Constraint | Locked by |
|---|---|---|
| 1 | **One artifact type, end-to-end:** Story Video — a single themed video with background music | [D-006](../decisions/DECISIONS_LOG.md), [D-015](../decisions/DECISIONS_LOG.md) |
| 2 | **One platform connector, end-to-end:** YouTube via the user's connected YouTube Studio account | [D-007](../decisions/DECISIONS_LOG.md) |
| 3 | **One LLM routing default, end-to-end:** remote-first; routing abstraction in place from day one so local-first is a v1 config flip, not a rewrite | [D-016](../decisions/DECISIONS_LOG.md) |
| 4 | **Project / job model:** persistent, async, resumable. Closing the laptop and re-opening must restore state | [D-011](../decisions/DECISIONS_LOG.md), [A-001](../vision/RECOMMENDED_ADDITIONS.md), [A-005](../vision/RECOMMENDED_ADDITIONS.md) |
| 5 | **Preview → approve → publish:** approval gate always on, no opt-out | [D-020](../decisions/DECISIONS_LOG.md) |
| 6 | **Scale envelope:** up to 1000 photos + 50 videos per job, 2–5 hour wall-clock ceiling | [D-012](../decisions/DECISIONS_LOG.md), [D-014](../decisions/DECISIONS_LOG.md) |
| 7 | **Curation pipeline:** hybrid (deterministic pre-filter → multimodal-LLM judgment) with rich per-photo / per-scene metadata; scene segmentation for video | [D-009](../decisions/DECISIONS_LOG.md) |
| 8 | **Music modes:** standard mode (background music) + music-video sub-mode (basic beat alignment); user-supplied music only at MVP | [D-010](../decisions/DECISIONS_LOG.md), [D-018](../decisions/DECISIONS_LOG.md), [A-013](../vision/RECOMMENDED_ADDITIONS.md) |
| 9 | **Effort-level UX:** L1–L3 + agentic max-permissible recommendation | [D-013](../decisions/DECISIONS_LOG.md), [A-015](../vision/RECOMMENDED_ADDITIONS.md) |
| 10 | **Agent harness:** single orchestrator with structured tool calls | [D-017](../decisions/DECISIONS_LOG.md) |
| 11 | **Mobile posture:** desktop-only at MVP. Mobile is its own v2 epic. (Optional desktop-side cloud-folder watcher is a stretch.) | [D-019](../decisions/DECISIONS_LOG.md) |
| 12 | **Refine loop:** opt-in at job creation, default OFF | [D-011](../decisions/DECISIONS_LOG.md), [D-020](../decisions/DECISIONS_LOG.md) |
| 13 | **Privacy posture:** explicit consent / strip-EXIF / blur-faces controls — load-bearing because remote-first sends images off-device | [A-002](../vision/RECOMMENDED_ADDITIONS.md), [D-016](../decisions/DECISIONS_LOG.md) |
| 14 | **Publishing audit log:** append-only record per project | [A-003](../vision/RECOMMENDED_ADDITIONS.md) |
| 15 | **Cross-job analysis cache (MVP-lite):** universal + model-versioned reuse classes; partial-result reuse → v1 | [A-011](../vision/RECOMMENDED_ADDITIONS.md), [N-007](../vision/NOVEL_IDEAS.md) |
| 16 | **Auto-captions (MVP-lite):** generated at curation; user reviews pre-publish | [A-009](../vision/RECOMMENDED_ADDITIONS.md) |
| 17 | **Per-day spend cap:** hard stop against runaway jobs | [A-004](../vision/RECOMMENDED_ADDITIONS.md) |

The full feature catalog with phase tags lives in [`GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md).

---

## Locked: what the MVP must explicitly NOT do

- Multiple artifact types in one project (only Story Video — D-006).
- Multiple platforms in one publish (only YouTube — D-007).
- Local-first LLM routing default (v1 — D-016).
- Live-job pattern (v1 — A-012, N-005).
- Reference-media style learning (v1 — A-014, N-004).
- Operation-aware LLM router (v1 — N-002, gates the local-first v1 commitment).
- Section-to-media natural-language mapping inside music-video mode (v1 — A-013).
- L4 / L5 effort levels, full cost-transparency UI, upgrade-path agent (v1 — A-015).
- Auto photo / video editing (v1 — per RAW_VISION).
- Multi-version artifact comparison (v1 — A-006).
- Theme library (v1 — A-014 substrate).
- Royalty-free music starter pack and licensed library integration (v1 — D-018).
- Mobile UI (v2 — D-019).
- Multi-agent harness (v2 — D-017).
- Conversational refinement at scale (v2 — D-011, D-017).
- Generated music (v2 — D-018).
- Hosted-service mode (v3 — CLAUDE.md mission).

---

## Open questions remaining (move to E-1.3 / E-1.4)

These are the original eight MVP open questions, with status:

| # | Question | Status | Goes to |
|---|---|---|---|
| 1 | Which single artifact type is the MVP critical path? | **Locked** — Story Video (D-006, D-015) | — |
| 2 | Which single platform is the first connector? | **Locked** — YouTube (D-007) | — |
| 3 | Local-first or remote-first routing default? | **Locked** — remote-first (D-016) | — |
| 4 | Which vision-LLM(s) at the MVP capability tier? | **Open** | E-1.3 (architecture grooming, ADR) |
| 5 | Which video / photo processing engine does rendering use? | **Open** | E-1.3 (architecture grooming, ADR) |
| 6 | Storage layout — directories on disk, rows in a DB, or both? | **Open** | E-1.3 (architecture grooming, ADR) |
| 7 | How many photos / how long a video must the MVP handle? | **Locked** — 1000 photos + 50 videos / 2–5 hr (D-012) | — |
| 8 | MVP success criterion (concrete, testable)? | **Locked** — D-014 verbatim above | — |

E-1.3 will produce the ADRs that close Q4, Q5, Q6. E-1.4 will turn the locked + closed answers into a sequenced milestone plan with effort estimates per Story.

---

## Until the remaining questions close

Anything that depends on Q4, Q5, or Q6 (e.g., specific provider integration code, render-engine bindings, persistence schema) **does not start** until the relevant ADR lands. Work-tracker filings for such Stories should set `phase: scaffolding` or be blocked by E-1.3.

Anything that is in the locked MVP scope above and *doesn't* depend on Q4/Q5/Q6 (e.g., the four-level work hierarchy itself, governance ADRs, this document) can proceed.
