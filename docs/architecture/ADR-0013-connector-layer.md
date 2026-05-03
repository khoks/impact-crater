# ADR-0013 — Connector layer credential model + audit-log shape

**Status:** Accepted
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
