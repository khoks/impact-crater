---
id: I-5
title: v3 — Hosted multi-tenant SaaS
type: initiative
status: backlog
priority: P3
phase: v3
tags: [v3]
created: 2026-06-14
updated: 2026-06-14
---

## North-star outcome

The same codebase runs as a hosted multi-tenant SaaS: object storage, Postgres, per-tenant profiles, auth, billing, and a public launch — a config flip on the self-hosted-first design, not a rewrite.

## Why now

Timing depends on go-to-market readiness, not engineering readiness (the ADR-0006 storage design already anticipates the swap).

## Scope

Hosted infra; multi-tenancy + auth + billing; public launch.

## Children

- E-5.1 — see epic (todo)
- E-5.2 — see epic (todo)
- E-5.3 — see epic (todo)

## Linked decisions and ADRs

ROADMAP.md §v3, ADR-0005, ADR-0006

## Activity log

- 2026-06-14 — created (roadmap backfill so the in-app workplan tracker shows the full plan; A-024 follow-up)
