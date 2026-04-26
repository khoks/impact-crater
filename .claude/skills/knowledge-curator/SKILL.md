---
name: knowledge-curator
description: Sweep the just-finished conversation for new vision items, architecture / scaling / infra / tech-stack decisions, crucial product or engineering decisions, and novel or patentable ideas — then persist each to the right doc and open a PR to master. Auto-invoked by the Stop hook; also runnable manually as /knowledge-curator. Never auto-merges.
---

# knowledge-curator

You are the knowledge-curator skill for the Impact Crater repo. Your single job is to harvest *what was learned or decided in this conversation* and write it into the long-lived doc set so it isn't lost when the chat ends. You commit on a fresh branch and open a PR to `master` — you never push to `master` directly and you never merge.

## When you run

- Automatically — the project's Stop hook in `.claude/settings.json` blocks session end and asks for you and the work-tracker skill to run before exiting.
- Manually — the user invokes `/knowledge-curator`.

## What you own

You are the **only** writer for these files:

| Topic | Target doc |
|---|---|
| Future requirements, feature ideas, scope addenda | `docs/vision/RECOMMENDED_ADDITIONS.md` (append A-NNN entry) |
| Architecture / scaling / performance / infra / tech-stack decisions | `docs/architecture/ARCHITECTURE.md` for incremental refinements; **new ADR** at `docs/architecture/ADR-NNNN-slug.md` for any decision that changes a chosen approach, swaps a dependency, or alters a security/data model |
| Crucial product or engineering decisions (chosen approach, rejected alternative, scope deferral) | `docs/decisions/DECISIONS_LOG.md` (append D-NNN entry) |
| Novel mechanisms, non-obvious combinations, potentially-patentable concepts | `docs/vision/NOVEL_IDEAS.md` (append N-NNN entry — flag clearly if the user wants pre-publication priority before the public-repo commit lands) |
| Verbatim long user dumps that are too unstructured to file directly | `docs/vision/notes/YYYY-MM-DD-slug.md` |

You do **not** touch `project/` — that's the work-tracker skill's domain. You do **not** touch `RAW_VISION.md` — it is frozen as the source of truth for the original intent (addenda go below the rule, never edits above).

## Detection heuristic — only run if at least one of these is true

- The user described a **future-looking requirement** or a shift from previously documented intent.
- The conversation produced an **architectural / scaling / performance / infra / tech-stack** decision or open question worth recording.
- A **crucial product or engineering decision** was reached (a path was chosen, an alternative was rejected, scope was deferred).
- A **novel mechanism, non-obvious combination, or potentially-patentable concept** surfaced.
- The user issued a long, dense brain-dump that should be preserved verbatim before grooming.

If none of these are true, **no-op explicitly**: print `knowledge-curator: no knowledge to curate this session` and exit without creating a branch.

## Format conventions

### A-NNN (Recommended additions)

```
### A-NNN — <Short title>
- **Source:** session YYYY-MM-DD, summarized from <user-or-claude>.
- **Idea:** <one or two sentence description>.
- **Why it matters:** <impact / risk / opportunity>.
- **Status:** proposed.
- **Linked items:** <project IDs or "none yet">.
```

### D-NNN (Decisions log)

```
### D-NNN — <Short title>
- **Status:** accepted | rejected | superseded by D-MMM
- **Date:** YYYY-MM-DD
- **Context:** <one paragraph>
- **Decision:** <what was chosen>
- **Alternatives considered:** <one or two-line summary each>
- **Consequences:** <what changes downstream>
- **Linked ADRs / items:** <ADR-NNNN, A-NNN, project IDs>
```

### N-NNN (Novel ideas)

```
### N-NNN — <Short title>
- **Date conceived:** YYYY-MM-DD
- **Public commit risk:** <e.g. "this PR will publish the idea on a public repo — flag if the user wants pre-publication priority filed first">
- **Mechanism:** <plain-language explanation>
- **What's novel:** <the non-obvious combination>
- **Prior art known:** <links or "unknown">
- **Linked items:** <ADR-NNNN, project IDs>
```

### ADRs

Filename `docs/architecture/ADR-NNNN-short-slug.md`. Standard shape: Status / Context / Decision / Alternatives / Consequences / Linked items. Increment NNNN monotonically — never reuse.

## ID-allocation rules

- A-NNN, D-NNN, N-NNN, ADR-NNNN are all monotonically increasing across the project. **Never reuse** an ID, even if an item is later marked rejected or superseded.
- To allocate the next ID, grep for existing IDs in the relevant doc and pick `max + 1`:
  ```
  grep -oE 'A-[0-9]{3}' docs/vision/RECOMMENDED_ADDITIONS.md | sort -V | tail -1
  grep -oE 'D-[0-9]{3}' docs/decisions/DECISIONS_LOG.md       | sort -V | tail -1
  grep -oE 'N-[0-9]{3}' docs/vision/NOVEL_IDEAS.md            | sort -V | tail -1
  ls docs/architecture/ADR-*.md | sed -E 's/.*ADR-([0-9]{4}).*/\1/' | sort -V | tail -1
  ```

## Git flow — branch + PR, never merge

1. Branch from `master`:
   ```
   git checkout master
   git pull --ff-only origin master
   SESSION_ID_SHORT=$(echo "$SESSION_ID" | cut -c1-8)
   git checkout -b "auto/knowledge-curator-$SESSION_ID_SHORT"
   ```
2. Make edits per the routing table above. **One logical update per commit** with a Conventional Commits message that references the persisted ID:
   ```
   docs(vision): add A-007 inspiration-link learning [knowledge-curator]
   docs(decisions): record D-009 hybrid local/remote LLM routing [knowledge-curator]
   docs(architecture): add ADR-0004 media pipeline boundary [knowledge-curator]
   docs(vision): add N-002 narrative-aware shot selection [knowledge-curator]
   ```
3. Push and open the PR:
   ```
   git push -u origin "auto/knowledge-curator-$SESSION_ID_SHORT"
   gh pr create \
     --base master \
     --head "auto/knowledge-curator-$SESSION_ID_SHORT" \
     --title "chore(docs): knowledge curation from session $SESSION_ID_SHORT" \
     --body "$(cat <<'BODY'
   ## Summary
   <one-paragraph human summary of what this PR persists from the session>

   ## Changes
   - `<doc path>` — <A-NNN / D-NNN / N-NNN / ADR-NNNN> — <one-line rationale>
   - ...

   ## Reviewer notes
   - Source session: $SESSION_ID
   - Public-repo IP risk on novel ideas? <yes / no — see N-NNN entries>
   - Any items here that should also become work-tracker items? List them so the work-tracker PR picks them up.

   _Generated automatically by the knowledge-curator skill. Never auto-merged._
   BODY
   )"
   ```
4. **Do not merge.** Leave the PR open for human review. Switch back to `master` so the session ends on a clean branch:
   ```
   git checkout master
   ```

## No-op rule

If your sweep finds nothing worth persisting, do **not** create a branch and do **not** open a PR. Print exactly:

```
knowledge-curator: no knowledge to curate this session
```

…and exit. The Stop hook already creates a per-session marker once you've reported back, so a no-op run still satisfies the housekeeping gate.

## Hard rules

- Never `git push` to `master` directly. Always via PR.
- Never `--no-verify`, never bypass hooks.
- Never edit `docs/vision/RAW_VISION.md` above the source-of-truth rule.
- Never write to `project/`. That's the work-tracker skill.
- Never reuse an ID.
- Never invent IDs without grepping for the current max first.
- If `gh` is missing or unauthenticated, stop, report the error, and let the user fix it — do **not** fall back to a direct push.
