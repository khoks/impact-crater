"""YouTubeConnector per ADR-0013.

Two credential paths, in order of precedence:

  1. **Env-var path** (v1 — multi-platform, env-driven). Reads
     `IC_YOUTUBE_CLIENT_ID`, `IC_YOUTUBE_CLIENT_SECRET`,
     `IC_YOUTUBE_REFRESH_TOKEN` from the process env. Builds a Google
     `Credentials` object and uses google-api-python-client to upload
     via resumable `videos.insert`. No DB writes, no OAuth dance — the
     user obtained the refresh token once via a separate one-time
     consent flow (see docs/connectors/youtube-setup.md).

  2. **DB-backed path** (M7 — original ADR-0013 design). Reads creds
     from the `connector_credentials` table (Fernet-encrypted). The
     OAuth init/callback that writes those rows was never finished;
     this path stays for the eventual Connect-in-Settings UI.

Tests use the `transport` injection point: callers can pass a stub
that fakes the YouTube API surface without real HTTP. Production
callers don't pass anything and the real google-api-python-client is
used.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from impact_crater import crypto
from impact_crater.connectors.base import (
    ConnectorAuthError,
    ConnectorError,
    ConnectorUploadResult,
    ConnectorValidationError,
    ConnectorValidationResult,
    PublishMetadata,
    Visibility,
)
from impact_crater.storage.db import connection

# Env vars for the env-driven credential path (v1).
_ENV_CLIENT_ID = "IC_YOUTUBE_CLIENT_ID"
_ENV_CLIENT_SECRET = "IC_YOUTUBE_CLIENT_SECRET"
_ENV_REFRESH_TOKEN = "IC_YOUTUBE_REFRESH_TOKEN"
_TOKEN_URI = "https://oauth2.googleapis.com/token"

log = logging.getLogger(__name__)

# YouTube limits per https://developers.google.com/youtube/v3/docs/videos
_MAX_TITLE = 100
_MAX_DESCRIPTION = 5000
_MAX_TAGS_TOTAL_CHARS = 500


ProgressCallback = Callable[[float], Awaitable[None]]


class YouTubeConnector:
    """YouTube Data API v3 connector. MVP per ADR-0013."""

    name: str = "youtube"

    def __init__(
        self,
        *,
        oauth_client_config: dict[str, Any] | None = None,
        transport: Any = None,
    ) -> None:
        """
        Args:
            oauth_client_config: dict with `client_id` + `client_secret` + scopes.
                                  Production reads this from settings; tests
                                  inject a stub.
            transport: optional injected `_YouTubeTransport`-like object that
                       handles the actual HTTP. None → real google-api-python-client.
        """
        self._oauth_client_config = oauth_client_config
        self._transport = transport

    # ---- Connection state --------------------------------------------

    async def is_connected(self) -> bool:
        # Env-var path takes precedence — if all three are set, we're
        # connected regardless of what's in the DB.
        if _has_env_credentials():
            return True
        creds = await _read_credentials()
        return creds is not None

    async def disconnect(self) -> None:
        await _delete_credentials()

    async def refresh_credentials(self) -> None:
        creds = await _read_credentials()
        if creds is None:
            raise ConnectorAuthError(
                "no YouTube credentials stored",
                suggested_action="Reconnect YouTube in Settings.",
            )
        # Real impl: google.auth.transport.requests.Request().refresh(creds).
        # Tests inject a transport that handles refresh.
        if self._transport is not None and hasattr(self._transport, "refresh"):
            new_token = self._transport.refresh(creds)
            await _write_credentials(new_token)

    # ---- Validation --------------------------------------------------

    async def validate_artifact(
        self, render_path: Path, metadata: PublishMetadata
    ) -> ConnectorValidationResult:
        issues: list[str] = []
        suggestions: list[str] = []

        if not render_path.is_file():
            issues.append(f"render file not found: {render_path}")
            suggestions.append("Re-run the render step before publishing.")
        else:
            size = render_path.stat().st_size
            if size == 0:
                issues.append("render file is empty")
                suggestions.append("Render produced a 0-byte file; investigate Stage 7.")
            elif size > 256 * 1024 * 1024 * 1024:  # YouTube limit ~ 256 GB
                issues.append("render file exceeds YouTube's 256 GB limit")
                suggestions.append("Use a smaller target duration or lower bitrate.")

        if not metadata.title or not metadata.title.strip():
            issues.append("title is required")
            suggestions.append("Enter a non-empty title.")
        if len(metadata.title) > _MAX_TITLE:
            issues.append(f"title exceeds {_MAX_TITLE} characters")
            suggestions.append(f"Shorten the title to ≤ {_MAX_TITLE} chars.")
        if len(metadata.description) > _MAX_DESCRIPTION:
            issues.append(f"description exceeds {_MAX_DESCRIPTION} characters")
            suggestions.append("Trim the description.")
        tag_chars = sum(len(t) for t in metadata.tags)
        if tag_chars > _MAX_TAGS_TOTAL_CHARS:
            issues.append(f"tags total {tag_chars} chars exceeds {_MAX_TAGS_TOTAL_CHARS}")
            suggestions.append("Drop some tags.")

        return ConnectorValidationResult(
            valid=not issues,
            issues=issues,
            suggested_actions=suggestions,
        )

    # ---- Upload ------------------------------------------------------

    async def upload(
        self,
        render_path: Path,
        metadata: PublishMetadata,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> ConnectorUploadResult:
        validation = await self.validate_artifact(render_path, metadata)
        if not validation.valid:
            raise ConnectorValidationError(
                "; ".join(validation.issues),
                status_code=400,
                suggested_action="; ".join(validation.suggested_actions),
            )

        # Path 1: env-driven creds (v1). Real google-api-python-client.
        # Tests inject a transport to bypass the real HTTP.
        if _has_env_credentials():
            body = _metadata_to_youtube_body(metadata)
            if self._transport is not None:
                return await self._transport.upload(
                    render_path=render_path,
                    metadata=body,
                    credentials={
                        "client_id": os.environ[_ENV_CLIENT_ID],
                        "client_secret": os.environ[_ENV_CLIENT_SECRET],
                        "refresh_token": os.environ[_ENV_REFRESH_TOKEN],
                    },
                    on_progress=on_progress,
                )
            return await _real_youtube_upload(
                render_path=render_path,
                body=body,
                on_progress=on_progress,
            )

        # Path 2: DB-backed creds (M7 original design). Kept for the
        # eventual Connect-in-Settings UI; not exercised today.
        creds = await _read_credentials()
        if creds is None:
            raise ConnectorAuthError(
                "YouTube not connected. Set IC_YOUTUBE_CLIENT_ID, "
                "IC_YOUTUBE_CLIENT_SECRET, IC_YOUTUBE_REFRESH_TOKEN in the "
                "process env (see docs/connectors/youtube-setup.md).",
                suggested_action="Add env vars and restart the server.",
            )

        if self._transport is None:
            raise ConnectorError(
                "DB-backed creds present but no transport injected — the "
                "in-app OAuth UI is not wired yet. Prefer the env-driven path "
                "for v1.",
                status_code=500,
                suggested_action="Use IC_YOUTUBE_* env vars instead.",
            )

        return await self._transport.upload(
            render_path=render_path,
            metadata=_metadata_to_youtube_body(metadata),
            credentials=creds,
            on_progress=on_progress,
        )


# ---- Helpers -----------------------------------------------------------


def _metadata_to_youtube_body(m: PublishMetadata) -> dict[str, Any]:
    return {
        "snippet": {
            "title": m.title,
            "description": m.description,
            "tags": m.tags,
            "categoryId": m.category or "22",  # 22 = "People & Blogs"
        },
        "status": {
            "privacyStatus": m.visibility,
            "selfDeclaredMadeForKids": False,
        },
    }


async def _read_credentials() -> dict[str, Any] | None:
    """Decrypted credentials dict from the connector_credentials table."""
    async with connection() as db:
        cur = await db.execute(
            """
            SELECT user_handle, access_token, refresh_token, expires_at, scopes_granted
            FROM connector_credentials
            WHERE connector_name = ?
            """,
            ("youtube",),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {
        "user_handle": row["user_handle"],
        "access_token": crypto.decrypt(row["access_token"]),
        "refresh_token": (
            crypto.decrypt(row["refresh_token"]) if row["refresh_token"] else None
        ),
        "expires_at": int(row["expires_at"]),
        "scopes_granted": (row["scopes_granted"] or "").split(","),
    }


async def _write_credentials(creds: dict[str, Any]) -> None:
    """Upsert credentials with Fernet-encrypted tokens."""
    enc_access = crypto.encrypt(creds["access_token"])
    enc_refresh = (
        crypto.encrypt(creds["refresh_token"]) if creds.get("refresh_token") else None
    )
    async with connection() as db:
        await db.execute(
            """
            INSERT INTO connector_credentials
                (connector_name, user_handle, access_token, refresh_token,
                 expires_at, scopes_granted)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(connector_name, user_handle) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                scopes_granted = excluded.scopes_granted,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                "youtube",
                creds["user_handle"],
                enc_access,
                enc_refresh,
                int(creds.get("expires_at", time.time() + 3600)),
                ",".join(creds.get("scopes_granted", [])),
            ),
        )
        await db.commit()


async def _delete_credentials() -> None:
    async with connection() as db:
        await db.execute(
            "DELETE FROM connector_credentials WHERE connector_name = ?",
            ("youtube",),
        )
        await db.commit()


# Public for the OAuth-callback handler that writes after a successful auth.
async def store_credentials(creds: dict[str, Any]) -> None:
    await _write_credentials(creds)


# ---- Env-driven credential helpers (v1 path) ---------------------------


def _has_env_credentials() -> bool:
    """True when all three env vars are non-empty."""
    return all(
        os.environ.get(name, "").strip()
        for name in (_ENV_CLIENT_ID, _ENV_CLIENT_SECRET, _ENV_REFRESH_TOKEN)
    )


async def _real_youtube_upload(
    *,
    render_path: Path,
    body: dict[str, Any],
    on_progress: ProgressCallback | None,
) -> ConnectorUploadResult:
    """Real upload via google-api-python-client. Runs the synchronous
    google client in a worker thread so the asyncio event loop stays
    free during the resumable upload."""
    import asyncio

    def _sync_upload() -> dict[str, Any]:
        # Import here so test environments without google-api-python-client
        # available can still import this module (real wiring only needed
        # when the env path is exercised).
        from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
        from googleapiclient.discovery import build  # type: ignore[import-not-found]
        from googleapiclient.http import MediaFileUpload  # type: ignore[import-not-found]

        creds = Credentials(
            token=None,
            refresh_token=os.environ[_ENV_REFRESH_TOKEN],
            client_id=os.environ[_ENV_CLIENT_ID],
            client_secret=os.environ[_ENV_CLIENT_SECRET],
            token_uri=_TOKEN_URI,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

        media = MediaFileUpload(
            str(render_path),
            mimetype="video/mp4",
            chunksize=8 * 1024 * 1024,  # 8 MB chunks for resumable upload
            resumable=True,
        )
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response: dict[str, Any] | None = None
        while response is None:
            status, response = request.next_chunk()
            # status carries progress 0..1 — ignored here because callback
            # is async and we're in a thread; the on_progress hook fires
            # below at completion. Live progress would need a thread→loop
            # bridge, deferred to v1+.
            if status is not None:
                log.debug(
                    "youtube_upload_chunk progress=%.2f", status.progress()
                )
        return response

    try:
        response = await asyncio.to_thread(_sync_upload)
    except Exception as exc:
        msg = str(exc)
        # Surface auth failures (refresh-token revoked, etc.) as
        # ConnectorAuthError so the publish API returns 401 not 502.
        if "invalid_grant" in msg.lower() or "unauthorized" in msg.lower():
            raise ConnectorAuthError(
                f"YouTube auth rejected: {msg}",
                suggested_action="Refresh token is invalid or revoked. "
                "Regenerate it per docs/connectors/youtube-setup.md.",
            ) from exc
        raise ConnectorError(
            f"YouTube upload failed: {msg}",
            status_code=502,
            suggested_action="See server logs for the underlying Google API error.",
        ) from exc

    if on_progress is not None:
        try:
            await on_progress(1.0)
        except Exception:  # pragma: no cover
            pass

    video_id = str(response.get("id", ""))
    visibility = str(
        response.get("status", {}).get("privacyStatus", body["status"]["privacyStatus"])
    )
    return ConnectorUploadResult(
        external_id=video_id,
        external_url=f"https://www.youtube.com/watch?v={video_id}",
        visibility=visibility,  # type: ignore[arg-type]
        response_code=200,
        response_summary=json.dumps({"kind": response.get("kind"), "id": video_id}),
    )


# Re-export for ruff
_ = json
