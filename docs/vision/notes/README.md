# `docs/vision/notes/` — long user dumps and reconstructions

This folder holds vision material that is too long or too unstructured to file directly as an addendum in [`../RAW_VISION.md`](../RAW_VISION.md), a groomed entry in [`../RECOMMENDED_ADDITIONS.md`](../RECOMMENDED_ADDITIONS.md) or an idea in [`../NOVEL_IDEAS.md`](../NOVEL_IDEAS.md). It is the home the `knowledge-curator` skill's routing table names for "Verbatim long user dumps that are too unstructured to file directly" (`.claude/skills/knowledge-curator/SKILL.md`) and that `CLAUDE.md` lists as "Long verbatim user dumps → `docs/vision/notes/YYYY-MM-DD-slug.md`". The rule predates the folder — it has been in the skill since the project's initial scaffolding (2026-04-26) — but nothing had ever been written here until the restart audit noticed (`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md`, "`docs/vision/notes/` was never created"), and the folder was created on 2026-10-25 under the public-trust docs pass (S-2.13.4).

Two kinds of file live here:

1. **Verbatim dumps** — a long user brain-dump captured as said (typos preserved), before grooming. The groomed outcome (A-/N-/D- entries, tracker items) is filed in the usual docs and links back here.
2. **Reconstructions** — when a session's transcript was not retained, the closest surviving account of what the user said, rebuilt from the records written that day (tracker activity logs, decision-log entries, PR titles, board notes). A reconstruction is never presented as verbatim.

## Naming

`YYYY-MM-DD-slug.md` — the date the user said it (not the date the file was written), then a short kebab-case slug. One file per session or per dump; a session with two distinct dumps may use two files.

## Rules

- **Label reconstructions as such.** A reconstruction opens with the sentence *"reconstructed from the tracker and decision records — only the phrases in quotation marks are the user's recorded words"*, states that the transcript is lost, and carries a **Sources** section citing every file (and line, where it is stable) the text was drawn from. Quoted fragments are copied exactly as the cited record wrote them down; if the record is itself a same-day summary rather than a transcript, say so.
- **Never invent words.** Anything not found in a record is written as paraphrase, outside quotation marks, and marked as the author's reading.
- **Verbatim stays verbatim.** A verbatim dump is not edited for grammar or spelling; clarifications go in a separate, dated section below it.
- **Amend, never rewrite.** Files gain dated sections; nothing is deleted. If a lost transcript later surfaces, add the verbatim text in a dated section and leave the reconstruction in place with a pointer to it.
- **Internal IDs are fine here.** These are internal working notes. The external mirror, `docs/OVERVIEW.md`, must not cite them or carry their IDs.
- **`RAW_VISION.md` addenda link here** whenever an addendum is a summary or a reconstruction of a longer account kept in this folder.

## Index

| File | Date said | Kind | What it holds |
|---|---|---|---|
| [`2026-06-30-round-2-feedback-and-arbitrary-nl-refinement.md`](./2026-06-30-round-2-feedback-and-arbitrary-nl-refinement.md) | 2026-06-30 | reconstruction | The round-2 output feedback on the SW-US trip re-renders (ten points; the "do all" instruction) and the "make refinement handle arbitrary NL requests" instruction; what was built from them and what was not. |
