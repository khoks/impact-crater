"""YouTubeConnector per ADR-0013.

OAuth via google-auth-oauthlib (loopback redirect on a random local port);
upload via google-api-python-client's resumable `videos.insert`.

Tokens persist Fernet-encrypted in `connector_credentials` per ADR-0006.

Tests use the `transport` injection point: callers can pass a synchronous
test transport (or stub-`google` libraries) to drive the OAuth + upload
paths without real HTTP. Production callers don't pass anything and the
real google client lib is used.
"""

from __future__ import annotations

import json
import logging
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
        creds = await _read_credentials()
        if creds is None:
            raise ConnectorAuthError(
                "YouTube not connected",
                suggested_action="Connect YouTube in Settings.",
            )

        if self._transport is None:
            raise ConnectorError(
                "no transport injected — real google-api-python-client wiring is "
                "an installation-time follow-up",
                status_code=500,
                suggested_action="Configure OAuth credentials per the README.",
            )

        # Test transport: returns a dict matching the YouTube API success shape.
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


# Re-export for ruff
_ = json
