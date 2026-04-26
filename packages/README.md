# packages/

Shared libraries consumed by `apps/` (LLM provider adapters, media pipeline primitives, curation engine, connector clients, schemas). Empty until the MVP build begins.

A package boundary lands here only when a piece of logic is genuinely shared across two or more apps — premature extraction is explicitly discouraged (see [CLAUDE.md](../CLAUDE.md)).
