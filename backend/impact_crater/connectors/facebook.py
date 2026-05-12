"""FacebookConnector — v1 multi-platform publish.

Posts a video to a Facebook **Page** via the Graph API. Personal-profile
posting was deprecated; only Pages can post via the API.

Unlike Instagram, the Page Videos endpoint accepts inline multipart
binary, so we don't need IC_PUBLIC_BASE_URL — the connector POSTs the
MP4 directly to graph.facebook.com.

Env vars
--------
  IC_FACEBOOK_PAGE_ACCESS_TOKEN   long-lived Page access token with
                                  pages_manage_posts + pages_show_list
                                  + pages_read_engagement
  IC_FACEBOOK_PAGE_ID             numeric Page ID (graph.facebook.com/me/accounts → id)

Visibility note: Facebook posts have a separate `published` field. We
map our Visibility enum:
  public   → published=true (visible on the Page wall)
  unlisted → published=false + `unpublished_content_type=DRAFT` (a draft
             only visible in the Page's drafts inbox)
  private  → not supported by the Page API. Connector raises validation
             error and suggests "unlisted" (which uses Drafts) or YouTube.
"""

from __future__ import annotations

import asyncio
import email.generator
import email.mime.application
import email.mime.multipart
import email.mime.text
import io
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from impact_crater.connectors.base import (
    ConnectorAuthError,
    ConnectorError,
    ConnectorUploadResult,
    ConnectorValidationError,
    ConnectorValidationResult,
    PublishMetadata,
    Visibility,
)

log = logging.getLogger(__name__)

ProgressCallback = Callable[[float], Awaitable[None]]

_ENV_PAGE_ACCESS_TOKEN = "IC_FACEBOOK_PAGE_ACCESS_TOKEN"
_ENV_PAGE_ID = "IC_FACEBOOK_PAGE_ID"
_GRAPH_HOST = "https://graph.facebook.com/v21.0"

# Facebook Page limits per https://developers.facebook.com/docs/graph-api/reference/page/videos
_MAX_TITLE = 255
_MAX_DESCRIPTION = 63206  # Facebook post limit


class FacebookConnector:
    """Facebook Page video connector via Meta Graph API."""

    name: str = "facebook"

    def __init__(self, *, transport: Any = None) -> None:
        self._transport = transport

    # ---- Connection state --------------------------------------------

    async def is_connected(self) -> bool:
        return _has_env_credentials()

    async def disconnect(self) -> None:  # pragma: no cover — symmetric
        log.info(
            "facebook_disconnect_noop (env-driven creds; unset env vars to disconnect)"
        )

    async def refresh_credentials(self) -> None:
        return None

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
            # Page Videos endpoint supports up to 10 GB. We're nowhere near.
            if size == 0:
                issues.append("render file is empty")
                suggestions.append("Render produced a 0-byte file; investigate Stage 7.")
            elif size > 10 * 1024 * 1024 * 1024:
                issues.append("render exceeds Facebook's 10 GB single-upload limit")
                suggestions.append("Use a smaller target duration.")

        if len(metadata.title or "") > _MAX_TITLE:
            issues.append(f"title exceeds {_MAX_TITLE} characters")
            suggestions.append(f"Shorten title to ≤ {_MAX_TITLE} chars.")
        if len(metadata.description or "") > _MAX_DESCRIPTION:
            issues.append(f"description exceeds {_MAX_DESCRIPTION} characters")
            suggestions.append("Trim the description.")

        if metadata.visibility == "private":
            issues.append("Facebook Page API has no 'private' visibility")
            suggestions.append(
                "Use 'unlisted' (saves as a Draft) or pick YouTube for true private posts."
            )

        if not _has_env_credentials():
            issues.append(
                "Facebook creds missing — set IC_FACEBOOK_PAGE_ACCESS_TOKEN + IC_FACEBOOK_PAGE_ID"
            )
            suggestions.append("See docs/connectors/facebook-setup.md.")

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

        page_id = os.environ[_ENV_PAGE_ID]
        token = os.environ[_ENV_PAGE_ACCESS_TOKEN]
        # Map our Visibility → FB's published flag.
        published = metadata.visibility == "public"

        body_fields: dict[str, str] = {
            "title": metadata.title or "",
            "description": metadata.description or "",
            "published": "true" if published else "false",
            "access_token": token,
        }
        if not published:
            # Save as Draft so it lives in the Page's drafts inbox.
            body_fields["unpublished_content_type"] = "DRAFT"

        log.info(
            "facebook_publish_start page_id=%s file_size=%d published=%s",
            page_id,
            render_path.stat().st_size,
            published,
        )

        if on_progress is not None:
            try:
                await on_progress(0.1)
            except Exception:  # pragma: no cover
                pass

        if self._transport is not None:
            response = await self._transport.upload_video(
                page_id=page_id,
                render_path=render_path,
                fields=body_fields,
            )
        else:
            response = await asyncio.to_thread(
                _upload_video_multipart,
                f"{_GRAPH_HOST}/{page_id}/videos",
                render_path,
                body_fields,
            )

        if on_progress is not None:
            try:
                await on_progress(1.0)
            except Exception:  # pragma: no cover
                pass

        # The Page Videos endpoint returns {"id": "<video_id>"}.
        video_id = str(response.get("id", ""))
        if not video_id:
            raise ConnectorError(
                f"Facebook Page Videos returned no id: {response!r}",
                status_code=502,
            )

        # FB doesn't return a permalink in the upload response. We have
        # to fetch it.
        permalink = ""
        try:
            perm = await asyncio.to_thread(
                _http_get,
                f"{_GRAPH_HOST}/{video_id}",
                {"fields": "permalink_url", "access_token": token},
            )
            # `permalink_url` is a relative path; prefix with facebook.com.
            raw = str(perm.get("permalink_url", ""))
            if raw and raw.startswith("/"):
                permalink = f"https://www.facebook.com{raw}"
            elif raw:
                permalink = raw
        except Exception as exc:  # pragma: no cover — best-effort
            log.warning(
                "facebook_permalink_fetch_failed video_id=%s error=%r", video_id, exc
            )

        log.info(
            "facebook_publish_succeeded video_id=%s permalink=%s published=%s",
            video_id,
            permalink,
            published,
        )

        return ConnectorUploadResult(
            external_id=video_id,
            external_url=permalink or f"https://www.facebook.com/{page_id}/videos/{video_id}",
            visibility=metadata.visibility,
            response_code=200,
            response_summary=json.dumps({"id": video_id}),
        )


# ---- Helpers ----------------------------------------------------------


def _has_env_credentials() -> bool:
    return all(
        os.environ.get(name, "").strip()
        for name in (_ENV_PAGE_ACCESS_TOKEN, _ENV_PAGE_ID)
    )


def _upload_video_multipart(
    url: str,
    render_path: Path,
    fields: dict[str, str],
) -> dict[str, Any]:
    """POST a multipart/form-data request with the video file + form fields.

    Uses stdlib email + urllib to avoid adding `requests` as a dep.
    For very large files this loads everything into memory, which is
    fine for MVP video sizes (<200 MB) but should be streamed in v2.
    """
    boundary = "----ICBoundary" + os.urandom(8).hex()
    body = io.BytesIO()
    crlf = b"\r\n"
    for k, v in fields.items():
        body.write(b"--" + boundary.encode("ascii") + crlf)
        body.write(
            f'Content-Disposition: form-data; name="{k}"'.encode("ascii") + crlf
        )
        body.write(crlf)
        body.write(str(v).encode("utf-8"))
        body.write(crlf)
    # File part.
    body.write(b"--" + boundary.encode("ascii") + crlf)
    body.write(
        f'Content-Disposition: form-data; name="source"; filename="{render_path.name}"'.encode(
            "utf-8"
        )
        + crlf
    )
    body.write(b"Content-Type: video/mp4" + crlf)
    body.write(crlf)
    with render_path.open("rb") as f:
        body.write(f.read())
    body.write(crlf)
    body.write(b"--" + boundary.encode("ascii") + b"--" + crlf)

    body_bytes = body.getvalue()
    req = urllib.request.Request(
        url,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body_bytes)),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise ConnectorError(
            f"Facebook /videos {exc.code}: {body_text[:500]}",
            status_code=exc.code,
        ) from exc


def _http_get(url: str, params: dict[str, str]) -> dict[str, Any]:
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise ConnectorError(
            f"Graph API {exc.code}: {body_text[:500]}",
            status_code=exc.code,
        ) from exc


# Re-exports for ruff.
_ = (Visibility, email.generator, email.mime.application, email.mime.multipart, email.mime.text)
