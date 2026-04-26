# ROADMAP.md — Impact Crater phased roadmap

> **Status: stub.** Phase boundaries and contents are filled in during roadmap-grooming (Epic `E-1.4`). The five-phase shape itself is locked.

The project moves through five named phases. A phase is a *capability bundle*, not a date — phases ship when they ship. The `phase` frontmatter field on every Initiative / Epic / Story / Task ties the work item to its target phase.

---

## Phases

| Phase | Name | Capability bundle (provisional) |
|---|---|---|
| `scaffolding` | **Project foundation** | Repo, vision, architecture, tracking system, skills. *Code begins after this phase closes.* |
| `mvp` | **Single thin slice** | One artifact type, one platform, one LLM-routing path, end-to-end. See [`MVP.md`](./MVP.md). |
| `v1` | **Multi-artifact, multi-platform, basic editing** | Multiple artifact types per project, multiple platform connectors, basic auto-photo / auto-video editing, inspiration-link ingestion, beginnings of theme library. |
| `v2` | **Adaptive style + mobile** | Theme library that learns the user's style. Mobile UI (thin client; heavy compute remains on the workstation or the cloud). Voice or agentic-conversation editing. |
| `v3` | **Hosted-service mode + advanced agentic editing** | Optional hosted mode behind the same codebase, gated by license terms. Multi-user / household / family workspace concepts. Sophisticated multi-agent harness for complex edits. |

---

## What's locked vs. open

**Locked at scaffolding:**
- Five-phase shape, with the `scaffolding`/`mvp`/`v1`/`v2`/`v3` names.
- The `phase` frontmatter field is the authoritative tag for any work item.

**Open until grooming:**
- The MVP feature set ([`MVP.md`](./MVP.md) — currently a stub).
- Per-phase milestone lists (none of v1 / v2 / v3 are itemized yet).
- Calendar dates (intentionally omitted; phases ship when they ship).

---

## Where work lives

- **Active and upcoming work** lives in `project/` as Initiatives → Epics → Stories → Tasks, each tagged with the right `phase`. See [`project/BOARD.md`](../../project/BOARD.md).
- **Future-looking ideas** that don't yet have a `project/` item live in [`docs/vision/RECOMMENDED_ADDITIONS.md`](../vision/RECOMMENDED_ADDITIONS.md) and [`docs/vision/GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md). The next grooming session converts them into `project/` items.
