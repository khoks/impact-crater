# ADR-0016 — Privacy posture defaults + privacy-sensitive routing extension

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-03
**Phase:** scaffolding

## Context

A-002 surfaced privacy posture for faces and locations as MVP-required because D-016 (remote-first routing default) implies images leave the device. Concrete defaults need locking. ADR-0010 placed the EXIF-strip and face-blur paths inside the media pipeline; ADR-0014 specified that the cross-project user profile (N-010) does not flow person-library identities into LLM calls beyond the recognition collage. ADR-0016 finalizes the user-facing defaults and one significant new mechanism per Q7.

The Q7 redirect (verbatim, 2026-05-03):

> "Blur faces default OFF, can be changed by the user in which case certain features will be skipped and the user will be told so. Also, if the user turns it on, and if the user has local llm connected, then we can suggest to offload the face related functionalities to local llm and build it like that in a plug and play manner to begin with, in case user wants to 'set it on for remote but use local'."

This is **N-011** — *privacy-sensitive operation routing*. Per-data-sensitivity routing (face data goes only to local LLM when blur-faces is ON) is distinct from N-002's per-cost routing; the trigger is privacy posture, not cost optimization. The MVP architecture has the hook in place so that v1 (when local-LLM lands per ADR-0008) ships the feature plug-and-play.

The Q8 redirect (2026-05-03): strip-GPS-only as a separate toggle from full-EXIF-strip — some users want timestamps preserved for narrative ordering (ADR-0011 Stage 4 location/time clustering depends on timestamps).

## Decision

### Three project-level toggles

Stored on the project's `manifest.json` (per ADR-0006); editable in the project's Privacy panel; defaults applied on project creation:

| Toggle | Default | Effect |
|---|---|---|
| **Strip EXIF before sending to LLM** | **ON** | Removes camera/device info, software tags, lens, ISO, etc. Implies strip-GPS = ON |
| **Strip GPS only** | **ON** | Subset: removes only GPS lat/long; preserves timestamps + camera info. Mutually-not-exclusive with full-EXIF-strip; full-strip implies GPS-strip. Only takes independent effect if full-EXIF-strip is OFF |
| **Blur faces before sending to LLM** | **OFF** | When ON: face-related features are skipped on remote calls; UI surfaces the trade-off; **if local-LLM is available (v1), face ops route to local per the privacy-sensitive routing extension below (N-011)** |

### Toggle interaction matrix

| EXIF-strip | GPS-strip | Blur-faces | Behavior |
|---|---|---|---|
| ON | (n/a, implied ON) | OFF | **Default.** Camera info + GPS stripped; timestamps preserved; faces visible to LLM; person-library + recognition (N-008) work fully |
| ON | (implied) | ON | Camera info + GPS stripped; faces blurred on remote calls; person-library skipped on remote; **if local-LLM available, face ops routed to local with unblurred faces (N-011)** |
| OFF | ON | OFF | GPS-only stripped (timestamps + camera info preserved); faces visible to LLM |
| OFF | ON | ON | GPS stripped; faces blurred on remote; local-LLM routing per N-011 |
| OFF | OFF | OFF | Full passthrough — most permissive; every metadata field visible |
| OFF | OFF | ON | Full metadata passthrough except faces blurred on remote |

The **Privacy panel UI** explains each combination's trade-offs in plain English ("blurring faces means we can't recognize people from your library; if you have a local LLM connected, we can do face recognition there instead").

### EXIF / GPS strip implementation

Per ADR-0010, strip-EXIF and strip-GPS-only paths run inside the media pipeline before any in-flight image bytes are sent to an LLM client. Implementation:

- Source media is **never modified in place**.
- Stripped variants are written to `~/.impact-crater/projects/{project_id}/cache/stripped/{content_hash}.{ext}` keyed by `(content_hash, strip_mode)` where `strip_mode = "full_exif" | "gps_only" | "none"`.
- The `LLMClient` call sites (per ADR-0007) read the appropriate stripped variant based on the project's settings, not the source.
- Cache reuse: a stripped variant is computed once per `(content_hash, strip_mode)` and reused across calls + across projects (the strip is deterministic).
- Library: `pyexiv2` (per ADR-0010); strip is byte-level, not re-encode (preserves image quality).

### Face blur implementation

When blur-faces is ON, the in-flight image bytes sent to **remote** LLM clients (Anthropic, Google) get a face-blurred variant:

- Face detection is done by **the vision LLM itself** (per ADR-0010's vision-LLM-only face-detection decision); since blur happens before sending, the *blur-time* face detection has to be deterministic. **MVP uses a lightweight local face-detection model** for this single purpose: a CPU-friendly detector like `face-recognition` (dlib) or `mediapipe` face detection. This is the **one** place a face-detection-only model enters the dependency graph; it never does identity, just bbox detection for blur masking.
- The detected face boxes are Gaussian-blurred (radius proportional to box width).
- Output cached at `~/.impact-crater/projects/{project_id}/cache/face_blurred/{content_hash}.{ext}`.

**Open exception:** when blur-faces is ON AND local-LLM is connected (v1), the local-LLM call site receives the **unblurred** image (the face data never leaves the device). This is the **N-011 mechanism** below.

### Privacy-sensitive operation routing (N-011)

When blur-faces is ON AND a `LocalLLMClient` is registered (per ADR-0008), the `LLMRouter` (per ADR-0007) consults a per-operation `privacy_class` and a per-provider `eligibility_for_class` map. If a privacy-sensitive operation has a local-eligible provider available, route there.

#### Per-operation `privacy_class`

Extension to ADR-0007's routing config schema:

```yaml
# config/llm-routing.yaml — extended schema
extract_metadata_image:
  provider: anthropic
  model: claude-sonnet-4-7
  privacy_class: face_data       # face information may be in the image
caption_image:
  provider: google
  model: gemini-2.5-flash
  privacy_class: face_data       # caption may describe people
score_image:
  provider: google
  model: gemini-2.5-flash
  privacy_class: visual_only     # quality scoring doesn't extract face identity
embed_image:
  provider: google
  model: text-embedding-004
  privacy_class: visual_only     # embeddings are dense; not face-identity
judge_narrative_arc:
  provider: anthropic
  model: claude-opus-4-7
  privacy_class: derived_metadata  # works on already-extracted metadata, no raw faces
parse_user_brief:
  provider: anthropic
  model: claude-sonnet-4-7
  privacy_class: text_only
# ... etc per operation
```

Privacy classes (MVP): `face_data` (image input may contain identifiable faces), `visual_only` (image input but no face-identity required), `derived_metadata` (text input only — already-extracted features), `text_only` (no media at all).

#### Per-provider `eligibility_for_class`

Each provider declares which privacy classes it's eligible to handle:

```yaml
# config/providers.yaml — extension
anthropic:
  eligibility_for_class: [text_only, derived_metadata, visual_only, face_data]
google:
  eligibility_for_class: [text_only, derived_metadata, visual_only, face_data]
local:
  eligibility_for_class: [text_only, derived_metadata, visual_only, face_data]
```

By default, all providers handle all classes. The user's privacy posture filters this:

- When **blur-faces = OFF**: no filtering. All providers handle all classes.
- When **blur-faces = ON**: remote providers' eligibility for `face_data` is **dynamically removed**. The router checks: "operation has `privacy_class: face_data`; remote providers are not eligible. Is local eligible? If yes, route there. If no (no local LLM connected), **skip the operation** and surface the consequence to the user."

#### Skipped-operation behavior

When `face_data` operations are skipped:

- The `extract_metadata_image` call returns a **degraded metadata object** with `recognized_persons = []`, `people = {count: <best-effort from face-blur detector>, demographics: null}`.
- The `caption_image` call returns a generic caption that doesn't describe people specifically (the prompt template has a `redact_people=true` mode that instructs the LLM to caption without person-specific descriptors).
- The N-001 narrative-arc judgment proceeds with the degraded metadata. Per-person motifs in the narrative are unavailable; the judge falls back to scene/location/object motifs.
- The UI surface displays a Privacy Banner: **"Blur-faces is ON. Person identification, age/gender extraction, and person-specific captions are skipped. Connect a local LLM to enable these on-device."**

#### Plug-and-play hook (MVP)

The MVP architecture has all the hooks in place:

- ADR-0007 `LLMRouter` consults the `privacy_class` + `eligibility_for_class` matrix.
- ADR-0008 `LocalLLMClient` slot exists; when v1 lands, the local provider's `eligibility_for_class` includes `face_data` and the routing kicks in.
- The routing config can be edited to swap providers per privacy class even at MVP, just without an actual local destination.
- The "skipped operation" path is implemented so MVP behavior with blur-faces ON is correct (degraded but not crashing).

When v1 ships ADR-0008's local-LLM runtime, **no code changes are needed** for the privacy-routing feature — the local provider just becomes the destination for `face_data` operations under blur-faces ON.

### Person-library + face-blur interaction

- Person library (per ADR-0010 / N-008) lives entirely in SQLite tables locally; **never sent to the LLM** beyond the labeled reference collage during a recognition call.
- When blur-faces is ON and remote-only routing is in effect: the reference collage is **not built or sent** (since `extract_metadata_image` is skipped or routed to local).
- When blur-faces is ON and local routing is available: the reference collage is built and sent to the local LLM only.
- Removing a person from the library always invalidates relevant cached extractions per ADR-0010 `library_version_hash` cache-key component.

### Audit-log privacy

Per ADR-0013, the audit log includes `external_url` + minimal metadata. No raw image data. No PII beyond the OAuth-tied user handle. Privacy posture toggles do not affect audit-log content (it's about publish events, not analysis).

### Profile + feedback log privacy

Per ADR-0014, the cross-project user profile sees abstracted patterns (e.g., `bias_toward_landscape_vs_people`) derived from candidate-set composition, not identities. Feedback events reference content hashes for traceability but never embed image data. The profile is read into Tier-M LLM calls (Anthropic / Google at MVP per ADR-0009 `orchestrator_reasoning`); this is acceptable because:

- The profile contains aggregated patterns, not personally-identifiable information beyond what a curation user implicitly shares.
- Anthropic and Google have "API data not used for training" guarantees for paid API usage.
- User can reset the profile at any time per ADR-0014.

### Provider data-handling policies (informational)

ADR-0016 documents the operating assumption that paid API usage of Anthropic and Google does not feed model training. This is current policy as of 2026-05-03; should change, the user is responsible for re-checking.

### Settings UI

Privacy panel lives at Settings → Privacy. Sections:

- **Per-project defaults** (the three toggles + their interaction explainer).
- **What we send to LLM providers** (plain-English list of what each privacy class includes).
- **Person library management** (link to the person-library UI; show count of stored persons + face photos).
- **Reset profile** (one-click; per ADR-0014).
- **Project export options** (deferred to v1; would include "exclude face library" by default).

A "high-privacy mode" that prompts on first-send-per-project is **deferred to v1**; per Q12 of round-3 questions (implicit during proposal), MVP doesn't include it.

## Alternatives considered

- **Blur-faces default = ON.** More privacy-conservative. Rejected per Q7 — defaulting to ON would silently disable person-library + recognition for users who don't change it; UI complexity to explain why features are missing. The OFF default with clear toggle-explainer matches user intent.
- **Single EXIF-strip toggle (no separate GPS-strip).** Originally proposed at the top of round 3. Rejected per Q8 — some users want timestamps for narrative ordering (Stage 4 clustering uses timestamps).
- **No privacy-sensitive routing (N-011).** The simpler version. Rejected per Q7 — the user wants the local-LLM routing path baked in even at MVP (architectural hook), so v1 can ship it plug-and-play.
- **Pre-emptive face-blur ON for any LLM call (regardless of provider).** Rejected — defeats the point of N-011's local-route. The routing decision per provider is the right grain.
- **Separate face-detection-only library at MVP (e.g., dlib for blur masking).** Accepted — necessary for the blur path because the LLM-only-face-detection (per ADR-0010) doesn't help when we need a face mask *before* sending to the LLM. dlib (`face-recognition`) or mediapipe is the candidate; v1 confirms which.
- **Privacy class taxonomy with more granularity** (e.g., separate `person_metadata` vs `face_pixels`). Considered. Rejected at MVP — four classes (face_data / visual_only / derived_metadata / text_only) is enough granularity. v1 can add more if needed.
- **Per-image privacy review mode** ("ask before sending each image to LLM"). Friction-heavy; deferred to v1 as a "high-privacy" mode.

## Consequences

- **The privacy panel is a real UI surface that needs design.** Three toggles + explainer + interaction matrix + person-library link + reset-profile button. Lands in MVP.
- **One new dependency** (face-detection-only library for blur masking) enters the dependency graph. ADR-0010 didn't include it because face-detection was vision-LLM-only there; ADR-0016's blur path needs deterministic face detection BEFORE sending to LLM.
- **The privacy-sensitive routing extension to ADR-0007** is a small but non-trivial change to the routing config schema (`privacy_class` + `eligibility_for_class`). The MVP routing config + router code includes the hooks.
- **Skipped-operation degradation matters.** A user with blur-faces ON and no local LLM should still get a usable Story Video; just one without person-specific motifs. The degraded path needs Stage-5 prompt variants that handle missing-person-data gracefully.
- **The plug-and-play hook means v1 local-LLM work is "drop the runtime in"** — no architectural changes for the privacy-routing feature.
- **The "API data not used for training" assumption is a third-party promise** that the project documents but doesn't control. Should change, the project's privacy story changes too. Documentation in this ADR makes the assumption explicit so it can be re-evaluated.
- **Cache invalidation on privacy-toggle change:** flipping blur-faces ON invalidates cached `face_data`-class operations (they need re-run with the new privacy posture). The `cache_index` table per ADR-0006 grows a `privacy_class` column; cache key includes the resolved provider after privacy-routing.

## Linked items

- A-002 (privacy posture for faces and locations — finalized here), D-016 (remote-first routing default — the reason privacy posture matters), N-002 (operation-aware router future — N-011's privacy-sensitive routing is a sibling concept; both will share the same router infra in v1), N-008 (person library — interaction matrix here), N-010 (cross-project profile — privacy posture for what flows in).
- ADR-0007 (routing dispatch — extended here with `privacy_class` + `eligibility_for_class`), ADR-0008 (local-LLM slot — the v1 destination for `face_data` operations under blur-faces ON), ADR-0009 (per-operation routing config — extended with privacy_class), ADR-0010 (EXIF-strip + face-blur paths in media pipeline; person library), ADR-0011 (Stage 5 prompt variants for degraded face-data), ADR-0013 (audit log privacy posture — unaffected here), ADR-0014 (profile data flowing into Tier-M calls).
- Cascades to: future v1 ADR for the local-LLM runtime (when it lands, privacy-routing becomes functional).
- Novel mechanism: **N-011** (privacy-sensitive operation routing) — see [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md).
- Decision-log entry: D-035 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.3.4 in [`project/tasks/`](../../project/tasks/T-1.3.3.4-adr-0016-privacy-posture.md).
