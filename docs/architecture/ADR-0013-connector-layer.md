# ADR-0013 — Connector layer credential model + audit-log shape

**Status:** Accepted — amended 2026-10-25 (see [Amendments](#amendments): the env-var credential layer and dry-run default that shipped are layered beside the OAuth / Fernet design below, which is dormant, not superseded; key management added)
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-03
**Phase:** scaffolding

## Context

D-007 fixes MVP platform = YouTube only. v1 adds Instagram, Facebook, X (one connector at a time per the v1 plan in GROOMED_FEATURES.md). A-003 fixes the publishing audit log as MVP scope. ADR-0006 partially pinned the audit-log shape (append-only JSONL at `~/.impact-crater/audit.jsonl` mirrored in the SQLite `audit` table). ADR-0013 finalizes:

1. The `Connector` abstraction (so v1 platforms plug in without rework).
2. The YouTube auth + resumable-upload flow at MVP.
3. Token storage.
4. The publish flow (preview → explicit user approval → upload → audit).
5. Behavior on API rejections (size, format, content policy).
6. The finalized audit-entry schema.

Two user redirects (2026-05-03):

- **Q1: default video privacy on upload = `public`**, with the user explicitly choosing visibility per upload (private / unlisted / public). The user chose to lean on the explicit Approve gate (D-020) as the safety net rather than defaulting to private.
- **Q2: token storage = all in SQLite** (rejected the OS-keyring proposal). Single-store simplicity preferred over keyring-per-OS portability.

## Decision

### `Connector` Python protocol

```python
class Connector(Protocol):
    name: str                                    # "youtube", "instagram", ...

    async def authenticate(self) -> AuthResult: ...
    async def is_authenticated(self) -> bool: ...
    async def revoke_credentials(self) -> None: ...

    async def validate_artifact(self, artifact: Artifact) -> ValidationResult:
        """Pre-flight check: size, format, duration, content-policy hints."""
        ...

    async def upload(
        self, artifact: Artifact, metadata: PublishMetadata, *,
        progress_callback: Callable[[UploadProgress], None] | None = None,
    ) -> UploadResult: ...
```

`Artifact` = the rendered media file + its provenance (project_id, snapshot_id, render_content_hash). `PublishMetadata` = title, description, tags, visibility, language, custom thumbnail, schedule. `UploadResult` = external_id (YouTube video ID), external_url, response_code, response_summary.

The protocol is the only contract every connector implements. Adding a new platform = one new file (`backend/impact_crater/connectors/{platform}.py`), no call-site changes.

### `YouTubeConnector` (MVP)

- **Auth:** OAuth 2.0 with `https://www.googleapis.com/auth/youtube.upload` scope + offline access for refresh tokens.
- **SDK:** `google-auth-oauthlib` for the OAuth dance + `google-api-python-client` for the YouTube Data API v3 calls.
- **OAuth flow:** local-loopback redirect (`http://localhost:<random_port>/oauth-callback`) — no need for a hosted callback URL. Standard pattern for desktop OAuth apps. The orchestrator opens the user's browser; the callback hits the FastAPI process; FastAPI completes the token exchange.
- **Upload protocol:** YouTube Data API v3 `videos.insert` resumable upload. 256 MB chunks. Resume on network blip. Progress streamed to the FastAPI websocket (per ADR-0005) so the UI shows "uploading 47% — 230 MB of 489 MB."
- **Default video privacy on upload (per Q1) = `public`.** The user picks visibility (private / unlisted / public) explicitly per upload via the publish UI; the form pre-selects `public` but the user can change before clicking Approve. The explicit Approve gate (D-020) is the safety net.
- **Custom thumbnail:** the connector accepts an optional thumbnail PNG/JPG; if absent, YouTube auto-picks.
- **Quota awareness:** YouTube Data API daily quota is 10,000 units by default. `videos.insert` costs 1,600 units per upload, so 6 uploads/day is the practical ceiling (at the default quota). The connector reports remaining quota after each call (response headers); ADR-0015 surfaces it via the cost-transparency UI.
- **Schedule (publish-at-future-time):** YouTube supports `publishAt` for unlisted/private videos. MVP exposes this through `PublishMetadata.publish_at`; the connector translates.

### Token storage (per Q2)

**All in SQLite** at `~/.impact-crater/db/impact-crater.sqlite`. No OS keyring at MVP.

Schema extension to ADR-0006:

```sql
CREATE TABLE connector_credentials (
    connector_name TEXT NOT NULL,           -- "youtube"
    user_handle    TEXT NOT NULL,           -- canonical user identifier from the platform
    access_token   TEXT NOT NULL,           -- encrypted at rest (Fernet, key derived from setup-time passphrase or OS-managed key)
    refresh_token  TEXT,                    -- encrypted; NULL if not applicable
    expires_at     INTEGER NOT NULL,        -- UNIX timestamp; orchestrator refreshes proactively at expires_at - 300
    scopes_granted TEXT NOT NULL,           -- comma-separated OAuth scopes
    created        INTEGER NOT NULL,
    updated        INTEGER NOT NULL,
    PRIMARY KEY (connector_name, user_handle)
);
```

**At-rest encryption:** access_token + refresh_token are encrypted with `cryptography.fernet` using a key stored in `~/.impact-crater/db/.fernet-key` (file-permissions 0600 on Unix; equivalent ACL on Windows). The Fernet key itself is generated at first-time setup and never leaves the machine. This matches the user's "all in SQLite" choice while still keeping tokens not-plaintext-on-disk.

**Trade-off vs OS keyring (rejected per Q2):** keyring would have meant per-OS adapters (Credential Manager / Keychain / Secret Service) and an extra Python dependency (`keyring`). SQLite-with-Fernet keeps the storage layer single and matches the rest of the storage architecture (per ADR-0006). The on-disk file is still readable by any process running as the user — the same exposure model as keyring on a single-user machine — but without the cross-OS surface area.

### Publish flow

```
[user clicks Approve in preview UI]
        ↓
orchestrator.publish(snapshot_id, platform="youtube", metadata)
        ↓
connector = registry["youtube"]
        ↓
result = connector.validate_artifact(artifact)
  • file size ≤ YouTube limit (256 GB; not an MVP concern)
  • format = MP4/H.264/AAC (ADR-0010 already produces this)
  • duration ≤ YouTube limit (12 hours by default; not an MVP concern)
  • metadata length checks (title ≤ 100 chars, description ≤ 5000 chars)
  → on failure: raise ConnectorValidationError, surface via cost-transparency UI
        ↓
upload_result = connector.upload(artifact, metadata, progress_callback=ws_progress)
  • progress streamed to FastAPI websocket → UI shows live %
  • resumable upload retries on network blip
  → on permanent failure: raise ConnectorUploadError with response_code + response_summary
        ↓
audit_event = AuditEntry(
    timestamp=now(),
    project_id=...,
    snapshot_id=...,
    platform="youtube",
    external_id=upload_result.external_id,
    external_url=upload_result.external_url,
    response_code=upload_result.response_code,
    response_summary=upload_result.response_summary,
    render_content_hash=artifact.render_content_hash,
    user_approval_token=...,                # opaque, in-session-bound; see below
)
audit_log.append(audit_event)               # JSONL append + SQLite mirror
```

### Audit-entry shape (finalized)

JSONL line shape (mirrored as a row in the `audit` SQLite table per ADR-0006):

```json
{
  "schema_version": 1,
  "timestamp": "2026-05-03T14:23:01Z",
  "project_id": "proj_a1b2c3",
  "snapshot_id": "snap_x9y8z7",
  "platform": "youtube",
  "external_id": "dQw4w9WgXcQ",
  "external_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "response_code": 200,
  "response_summary": "OK; uploadStatus=uploaded; processingStatus=processing",
  "render_content_hash": "sha256:e4d909c290d0fb1ca068ffaddf22cbd0",
  "user_approval_token": "uat_8d4f1e9a0c",
  "publish_metadata": {
    "title": "...",
    "description_truncated_200": "...",       /* full description in publish_metadata.description below */
    "visibility": "public",
    "tags_count": 12,
    "scheduled_publish_at": null
  }
}
```

**`user_approval_token`** = an opaque, in-session-bound token issued by the FastAPI process when the user clicks Approve. It binds the audit entry to a specific user click, distinguishable from system-initiated retries. No PII; no OAuth identifier; the per-platform user identity lives in `connector_credentials.user_handle`.

The `publish_metadata.description_truncated_200` keeps the audit log compact while preserving the gist; the full description is mirrored on the `audit` SQLite row in a separate `description_full` TEXT column for users who want to grep their publish history.

### API rejection handling

When a connector returns a permanent error, raise a structured exception:

```python
class ConnectorError(Exception):
    connector_name: str
    response_code: int
    response_summary: str
    user_actionable: bool                      # True if user can retry after fixing something
    suggested_action: str | None               # "Title is too long; trim to 100 chars" etc.

class ConnectorValidationError(ConnectorError):    # pre-flight failures
class ConnectorUploadError(ConnectorError):        # mid-upload failures
class ConnectorAuthError(ConnectorError):          # token-revoked, scope-changed, etc.
```

The orchestrator surfaces these via the cost-transparency UI (per ADR-0015) with the `suggested_action` text. Auth errors trigger the re-auth flow.

YouTube-specific rejection mapping at MVP:

| HTTP code | YouTube error | Mapped to | User-actionable? | Suggested action |
|---|---|---|---|---|
| 400 | `videoTitleEmpty` / similar | `ConnectorValidationError` | Yes | "Add a title" |
| 401 | Token expired and refresh failed | `ConnectorAuthError` | Yes | "Re-authenticate with YouTube" |
| 403 | `quotaExceeded` | `ConnectorUploadError` | Yes | "Daily YouTube quota exhausted; try again tomorrow" |
| 403 | `insufficientPermissions` | `ConnectorAuthError` | Yes | "Re-authenticate and grant upload permission" |
| 403 | `youtubeSignupRequired` / `accountClosed` | `ConnectorAuthError` | Yes | Surface platform's own message |
| 403 | `videoBlockedDueToContent` | `ConnectorUploadError` | Maybe | Surface platform's own message verbatim |
| 5xx | Transient | Retry with backoff inside the connector; raise after 3 attempts | n/a | n/a |

### Token refresh

The orchestrator runs a background task that, before any connector call, checks if `expires_at` is within 5 minutes; if so, attempts a refresh using `refresh_token`. If refresh succeeds, the new `(access_token, refresh_token, expires_at)` tuple replaces the stored row. If refresh fails (refresh_token revoked, etc.), raise `ConnectorAuthError`; the user re-authenticates.

### v1 connector additions

Each new platform is a new `Connector` implementation. The protocol stays. Per-platform specifics (Instagram = Graph API + Facebook Login; X = OAuth 1.0a + media upload + tweet; Facebook = Graph API) live inside the implementation. The audit-log entry is the same shape (`platform` discriminator).

Cross-platform formatting (aspect ratio, duration per platform per A-008 / A-009) is handled in ADR-0010 / ADR-0011 — the orchestrator picks the right render-plan variant per target platform; the connector just uploads.

## Alternatives considered

- **Default video privacy = `private`** (originally proposed). Safer-by-default for accidental publishes. Rejected per Q1 — the user chose to lean on the Approve gate (D-020) as the safety net; defaulting to public matches the most common intent (the user is publishing because they want to publish). The per-upload visibility selector is in the publish UI; users can change before clicking Approve.
- **OS keyring for token storage** (originally proposed). Cross-OS abstractions add a dependency (`keyring`); per-OS keyring backends each have edge cases (Linux Secret Service availability varies). Rejected per Q2 — SQLite with Fernet encryption is a single store, simpler dependency surface, comparable security model on a single-user machine.
- **Plaintext token storage in SQLite.** Considered. Rejected — Fernet adds ~50 lines and meaningful protection against casual filesystem inspection.
- **Hosted OAuth callback URL (instead of local loopback).** Would require running a public HTTP endpoint just for the callback; conflicts with self-hosted-first ethos. Rejected — local loopback works for desktop OAuth apps and is widely supported.
- **Lazy auth (auth on first publish, not on-setup).** Considered. Compatible with the `connector.authenticate()` design but worse UX — the user gets the OAuth dance interrupting a publish flow. Setup-time auth (during first-time setup wizard) is the documented pattern; lazy auth is a fallback when the user adds a new connector mid-session.
- **Skip the audit log at MVP.** Rejected — A-003 explicitly puts it in MVP scope. Append-only JSONL + SQLite mirror is cheap.

## Consequences

- **Public-default video privacy means the Approve gate is doing real work.** UI design must make the visibility selector unmissable in the publish form; the Approve button text reads "Publish as `public`" (or whatever visibility is selected) so the user sees the consequence one more time before clicking.
- **Token refresh is a background task running before every connector call.** Adds one SQLite read per call; negligible.
- **Fernet key file at `~/.impact-crater/db/.fernet-key`** must be backed up if the user wants to recover their stored credentials on a new machine. Loss of the key invalidates all stored tokens; the user re-authenticates per connector. Acceptable trade-off.
- **YouTube Data API daily quota (10k units default; 1600/upload) caps practical MVP usage at ~6 publishes/day per Google account.** Surfaced via ADR-0015 cost-transparency UI. Users with serious volume can request quota increases from Google.
- **The `Connector` protocol is the v1 contract.** Adding Instagram / Facebook / X = 3 new files, each implementing the protocol. No orchestrator-level changes.
- **`user_approval_token` is in-session-bound and opaque.** It distinguishes user-initiated publishes from any system-initiated retries (e.g., resumed-after-crash uploads). The token lives only in the audit log; not exposed to LLM or to platform.
- **Per-platform formatting (aspect ratio, duration limits) lives in ADR-0010 / ADR-0011**, not here. The connector just receives a finalized artifact and uploads it; if the artifact doesn't meet platform requirements, `validate_artifact` rejects it before the upload attempt.

## Linked items

- D-007 (MVP platform = YouTube), D-020 (publish-approval-always-on — the Approve gate is the safety net for the public-default visibility), A-003 (publishing audit log — finalized here), A-008 (per-platform formatting in v1 — connector accepts artifact, doesn't reformat), A-009 (auto-captions — in MVP per A-009; the connector passes captions in `PublishMetadata`).
- ADR-0005 (FastAPI + websocket — local OAuth callback, upload-progress stream), ADR-0006 (SQLite + audit-log path; `connector_credentials` table extension), ADR-0007 (orchestrator harness uses connector tools), ADR-0010 (artifact format produced by render), ADR-0011 (orchestrator's publish step), ADR-0014 (orchestrator's tool surface includes `validate_publish_artifact`, `upload_to_youtube`, `record_audit_event`), ADR-0015 (cost-transparency UI surfaces quota status + connector errors).
- Decision-log entry: D-032 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.3.1 in [`project/tasks/`](../../project/tasks/T-1.3.3.1-adr-0013-connector-layer.md).

## Amendments

### 2026-10-25 — what shipped: env-var credentials and a dry-run default, layered beside the dormant OAuth / Fernet path (S-2.13.5)

Verified against master `d9bb392`. PR #19 (2026-05-05) added `connectors/{base,youtube}.py` behind the `Connector` protocol; PR #34 (2026-05-11) added `instagram.py`, `facebook.py`, `dry_run.py` and the env-var credential path. **Zero publishes of any kind have executed**: the audit table was empty at the 2026-10-24 restart audit and none of the three connectors has been live-tested. The first real (private) YouTube publish is restart Phase 1 and closes the MVP (D-057).

**Protocol as built.** `Connector` exposes `validate_artifact / upload / refresh_credentials / is_connected / disconnect` — no `authenticate`, and `revoke_credentials` became `disconnect`. `PublishMetadata` is `title / description / tags / visibility / category`; no language, thumbnail or `publish_at`. Errors are `ConnectorError` → `ConnectorAuthError / ConnectorValidationError / ConnectorRateLimitError`, each carrying `status_code` and `suggested_action` (no `ConnectorUploadError`, no `user_actionable` flag). `connectors.get_connector(platform)` is the registry; `Platform` is `youtube | instagram | facebook`.

**Credential model as built — two layers, both present.**

1. *Env-var layer — what runs.* Each connector reads credentials from the process environment: YouTube `IC_YOUTUBE_CLIENT_ID` / `IC_YOUTUBE_CLIENT_SECRET` / `IC_YOUTUBE_REFRESH_TOKEN` (a `google.oauth2.credentials.Credentials` is built from them and `videos.insert` runs as a resumable upload in a worker thread — 8 MB chunks, not 256 MB, and progress is reported only at completion); Instagram `IC_INSTAGRAM_ACCESS_TOKEN` / `IC_INSTAGRAM_USER_ID`; Facebook `IC_FACEBOOK_PAGE_ACCESS_TOKEN` / `IC_FACEBOOK_PAGE_ID`. The one-time consent flow that mints the YouTube refresh token is a manual procedure in `docs/connectors/youtube-setup.md`, not app code. Env vars take precedence over the database.
2. *OAuth / Fernet layer — dormant, not superseded.* The `connector_credentials` table, the Fernet key at `~/.impact-crater/db/.fernet-key` and the `youtube.py` read / upsert / delete helpers exist, and `api/publish.py` still reads `user_handle` from the table for `GET /api/connectors/youtube/status`. Nothing writes the table because the loopback OAuth init / callback was never built. This layer is the base **S-3.3.5** (Connect YouTube in Settings, restart Phase 1) builds on: the design above becomes real there, with env vars demoted to a documented fallback.

**Dry-run default.** `IC_PUBLISH_DRY_RUN` is read by `connectors/dry_run.py::is_dry_run_enabled`; unset, empty, or any value other than `0 / false / no / off`, means **on** (until 2026-10-25 an *empty* value switched live posting on — fixed with a test, D-060). `get_connector` then wraps the connector in `DryRunConnector`, which runs the full `validate_artifact` preflight and returns a synthetic `dry-run-…` id with a `https://dry-run.local/…` URL; the audit row's `platform` reads `<platform> (dry-run)` and the publish modal shows a DRY-RUN badge. The first real publish sets `IC_PUBLISH_DRY_RUN=0` for one session and flips it back.

**Instagram needs a public HTTPS media URL.** The Graph API pulls the video from a URL Meta's servers can reach, so a real Instagram post requires `IC_PUBLIC_BASE_URL` pointing at an HTTPS host serving `/api/snapshots/{id}/render.mp4`. Today that means exposing the running server (the setup doc suggests an ngrok tunnel), which exposes the whole unauthenticated API — so **no tunnel until S-3.11.3** (loopback-only default, `--allow-remote`, per-install bearer token) has landed; the long-term shape is a signed media URL only. Instagram has no per-post visibility: the connector rejects anything but `public`.

**Visibility defaults.** The API keeps `public` as its default (`PublishRequest.visibility`, `PublishMetadata.visibility`) — Q1 stands for the API contract. The **UI default becomes private-first**: the publish form pre-selects `private` on first use (today `frontend/src/routes/JobPreview.tsx` pre-selects `public`) and remembers the last-used visibility per platform afterwards; `docs/connectors/youtube-setup.md` already tells the user to start with a private test post. Implemented with S-3.3.5, whose connector-status work derives the default visibility; the Approve button keeps showing the selected visibility.

**Audit as built.** `audit.AuditEntry` appends to `audit.jsonl` and the `audit` table: `platform`, `external_id / external_url`, `response_code / response_summary`, `description_full`, `visibility`, and a `user_approval_token` minted per publish (`secrets.token_urlsafe(16)`). The table keeps this ADR's `render_content_hash` and `publish_metadata` columns: `render_content_hash` is never populated (always `""`, `api/publish.py` does not set it) and `publish_metadata` holds only `{"visibility": …}` — visibility has no column of its own; the JSONL line carries the full dataclass including `visibility`.

**Not built:** `publishAt` scheduling, custom thumbnails, the YouTube quota readout, upload-progress streaming, the token-refresh background task, X / LinkedIn / TikTok (X is S-3.3.4).

### 2026-10-25 — Key management (S-2.13.5)

This section is the single home for the Fernet key; `SECURITY.md` and ADR-0006 point here.

- **What the key protects.** The Anthropic and Google API keys in the `settings` table (`storage/settings.py`, rows flagged `encrypted`) and — once S-3.3.5 writes them — the OAuth tokens in `connector_credentials`. Everything else under `~/.impact-crater` (SQLite metadata, cache payloads, renders, telemetry, audit log, feedback screenshots) is plaintext.
- **Where it lives.** `~/.impact-crater/db/.fernet-key` (`paths.fernet_key_path`), one line of URL-safe base64, generated on first use by `crypto.get_or_create_key`, beside the SQLite file. `IMPACT_CRATER_HOME` moves the whole tree, key included.
- **Permissions, honestly.** `paths.harden_secret_file` runs `chmod 0600` on POSIX and is a **no-op on Windows**: the "restrictive file permissions" claim in `crypto.py`'s docstring does not hold on NTFS, where the file inherits the user-profile ACL — readable by every process running as the user and by local administrators. That is the same exposure as the SQLite file beside it and as an OS-keyring entry on a single-user machine, so it is **accepted**; a `win32security` / `icacls` tightening is not scheduled. The key defends against casual inspection and against a backup of the database alone, not against code already running as the user.
- **Backup / restore.** Back up `~/.impact-crater` as one unit — `db/` (SQLite + `.fernet-key`), `projects/`, `cache/`, `audit.jsonl`, `telemetry.jsonl`, `feedback.jsonl`, `feedback_screenshots/`, `profile/`. Restoring the database without the key leaves every encrypted setting unreadable; restoring the key without the database is harmless. On a new machine, restore the tree (or point `IMPACT_CRATER_HOME` at the restored copy) **before** the first start, otherwise the first start mints a fresh key and the restored ciphertexts never decrypt.
- **Key loss or corruption.** `crypto.get_or_create_key` raises `FernetUnavailableError` when the file exists but is not a valid key; `decrypt` raises it when a ciphertext does not validate against the current key. Recovery: delete `.fernet-key`, restart (a new key is generated), re-enter the Anthropic / Google API keys in the setup wizard or Settings, and reconnect each connector (or re-export its env vars). No other data is affected. The error surface is still raw — the UI does not yet say "key changed, re-enter your keys"; that copy belongs to S-3.11.3's `SECURITY.md` work.
- **Rotation.** Not supported; there is no re-encrypt path. Rotating means the recovery procedure above.
- **Env-var credentials sit outside this model.** `IC_*` values live in the user's shell or launcher script; `.gitignore` excludes `.env*`, `*.key`, `.fernet-key` and the personal `start-impact-crater.*` launchers.
