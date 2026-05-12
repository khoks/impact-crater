"""InstagramConnector — v1 multi-platform publish.

Posts a Reel via the Meta Graph API (Instagram Graph API). Posting requires
an **Instagram Business or Creator account** linked to a Facebook Page;
personal accounts have no posting API. Per-publish flow:

  1. POST /{ig_user_id}/media         — create a container referencing the
                                        video URL + caption
  2. (poll)  GET /{container_id}      — wait for status_code=FINISHED
  3. POST /{ig_user_id}/media_publish — publish the container

Critical wrinkle: the Graph API can't take video bytes inline. It needs a
publicly-fetchable HTTPS URL that Meta's servers can pull from. For dev
we expose the rendered MP4 via the running impact-crater server itself,
addressing it through `IC_PUBLIC_BASE_URL` (e.g. an ngrok tunnel pointing
at http://127.0.0.1:8765). If that env var is unset, real posting raises
a clear ConnectorAuthError pointing the user to set it. Dry-run mode
still validates without actually building the URL.

Env vars
--------
  IC_INSTAGRAM_ACCESS_TOKEN   long-lived user access token with
                              instagram_content_publish + pages_show_list
                              + instagram_basic + pages_read_engagement
  IC_INSTAGRAM_USER_ID        the IG Business Account ID
                              (graph.facebook.com/me/accounts → instagram_business_account)
  IC_PUBLIC_BASE_URL          public HTTPS base for /api/snapshots/{id}/render.mp4
                              (e.g. an ngrok URL for dev). Optional in
                              dry-run; required for real posting.

Visibility note: Instagram has no per-post visibility selector via the
API. Reels are always posted publicly to the account's followers. The
`visibility` arg is recorded in the audit log but does not affect what
the API does. Our connector raises `ConnectorValidationError` if a
caller asks for "private" or "unlisted" so the audit-log isn't misleading.
"""

from __future__ import annotations

import asyncio
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

_ENV_ACCESS_TOKEN = "IC_INSTAGRAM_ACCESS_TOKEN"
_ENV_USER_ID = "IC_INSTAGRAM_USER_ID"
_ENV_PUBLIC_BASE_URL = "IC_PUBLIC_BASE_URL"
_GRAPH_HOST = "https://graph.facebook.com/v21.0"

# IG Reels limits per https://developers.facebook.com/docs/instagram-api/guides/content-publishing
_MAX_CAPTION = 2200
_MAX_DURATION_S = 90


class InstagramConnector:
    """Instagram Reels connector via Meta Graph API."""

    name: str = "instagram"

    def __init__(self, *, transport: Any = None) -> None:
        # `transport` is an optional injection point for tests. None →
        # real urllib.request calls via _http_get / _http_post.
        self._transport = transport

    # ---- Connection state --------------------------------------------

    async def is_connected(self) -> bool:
        return _has_env_credentials()

    async def disconnect(self) -> None:  # pragma: no cover — symmetric
        log.info("instagram_disconnect_noop (env-driven creds; unset env vars to disconnect)")

    async def refresh_credentials(self) -> None:
        # Long-lived tokens last ~60 days. The user re-mints offline.
        # No-op here.
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
        # Instagram's caption is the only text. We compose it from title + description.
        composed = _compose_caption(metadata)
        if not composed.strip():
            issues.append("Instagram needs a non-empty caption (title or description)")
            suggestions.append("Enter a title — Instagram captions are required.")
        if len(composed) > _MAX_CAPTION:
            issues.append(f"caption exceeds {_MAX_CAPTION} characters ({len(composed)} given)")
            suggestions.append(f"Trim the title + description combined to ≤ {_MAX_CAPTION} chars.")

        if metadata.visibility != "public":
            issues.append(
                f"Instagram API has no '{metadata.visibility}' visibility — Reels are always public"
            )
            suggestions.append("Set visibility=public, or pick a different platform for non-public posts.")

        if not _has_env_credentials():
            issues.append("Instagram creds missing — set IC_INSTAGRAM_ACCESS_TOKEN + IC_INSTAGRAM_USER_ID")
            suggestions.append("See docs/connectors/instagram-setup.md for the credential setup.")

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

        # Real posting also needs a public URL so Meta's pulls the video.
        public_base = os.environ.get(_ENV_PUBLIC_BASE_URL, "").strip().rstrip("/")
        if not public_base:
            raise ConnectorAuthError(
                "Instagram needs IC_PUBLIC_BASE_URL set to an HTTPS host that "
                "Meta's API can fetch /api/snapshots/{id}/render.mp4 from "
                "(e.g. an ngrok tunnel for dev).",
                suggested_action=(
                    "Run `ngrok http 8765` and set IC_PUBLIC_BASE_URL=https://<tunnel>.ngrok.io"
                ),
            )

        # The connector receives render_path; the snapshot_id is embedded
        # in the path: .../snapshots/{snapshot_id}/render.mp4. Extract it
        # so we can build the public URL.
        snapshot_id = render_path.parent.name
        video_url = f"{public_base}/api/snapshots/{snapshot_id}/render.mp4"

        access_token = os.environ[_ENV_ACCESS_TOKEN]
        ig_user_id = os.environ[_ENV_USER_ID]
        caption = _compose_caption(metadata)

        log.info(
            "instagram_publish_start ig_user_id=%s video_url=%s caption_chars=%d",
            ig_user_id,
            video_url,
            len(caption),
        )

        if on_progress is not None:
            try:
                await on_progress(0.1)
            except Exception:  # pragma: no cover
                pass

        # Step 1: create container.
        container = await self._post(
            f"/{ig_user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": access_token,
            },
        )
        container_id = str(container.get("id", ""))
        if not container_id:
            raise ConnectorError(
                f"Instagram /media returned no id: {container!r}",
                status_code=502,
            )

        # Step 2: poll until status_code=FINISHED. Meta ingests the video
        # asynchronously; this can take 10-60s for short clips.
        deadline_s = 180
        sleep_s = 3.0
        elapsed = 0
        while elapsed < deadline_s:
            await asyncio.sleep(sleep_s)
            elapsed += sleep_s
            status = await self._get(
                f"/{container_id}",
                params={"fields": "status_code,status", "access_token": access_token},
            )
            sc = str(status.get("status_code", ""))
            log.debug(
                "instagram_container_status container_id=%s status_code=%s elapsed_s=%d",
                container_id,
                sc,
                elapsed,
            )
            if sc == "FINISHED":
                break
            if sc in ("ERROR", "EXPIRED"):
                raise ConnectorError(
                    f"Instagram container failed: status_code={sc}, status={status.get('status')!r}",
                    status_code=502,
                    suggested_action=(
                        "Common causes: video URL not publicly reachable, "
                        "duration > 90s, or codec rejected. Check IC_PUBLIC_BASE_URL."
                    ),
                )
            if on_progress is not None:
                try:
                    await on_progress(min(0.9, 0.1 + elapsed / deadline_s * 0.8))
                except Exception:  # pragma: no cover
                    pass
        else:
            raise ConnectorError(
                f"Instagram container did not reach FINISHED within {deadline_s}s",
                status_code=504,
                suggested_action="Try a shorter video or check IC_PUBLIC_BASE_URL reachability.",
            )

        # Step 3: publish.
        publish = await self._post(
            f"/{ig_user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": access_token,
            },
        )
        media_id = str(publish.get("id", ""))

        if on_progress is not None:
            try:
                await on_progress(1.0)
            except Exception:  # pragma: no cover
                pass

        # Build a watch URL. Instagram returns no permalink in the publish
        # response; we have to either fetch /{media_id}?fields=permalink
        # OR construct an indirect URL. Fetching the permalink is one
        # extra call but gives a real link.
        permalink = ""
        try:
            perm = await self._get(
                f"/{media_id}",
                params={"fields": "permalink", "access_token": access_token},
            )
            permalink = str(perm.get("permalink", ""))
        except Exception as exc:  # pragma: no cover — best-effort
            log.warning("instagram_permalink_fetch_failed media_id=%s error=%r", media_id, exc)

        log.info(
            "instagram_publish_succeeded media_id=%s permalink=%s",
            media_id,
            permalink,
        )

        return ConnectorUploadResult(
            external_id=media_id,
            external_url=permalink or f"https://www.instagram.com/p/{media_id}/",
            visibility="public",
            response_code=200,
            response_summary=json.dumps({"id": media_id}),
        )

    # ---- HTTP -------------------------------------------------------

    async def _post(self, path: str, *, data: dict[str, str]) -> dict[str, Any]:
        if self._transport is not None:
            return await self._transport.post(path, data)
        return await asyncio.to_thread(_http_post, _GRAPH_HOST + path, data)

    async def _get(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        if self._transport is not None:
            return await self._transport.get(path, params)
        return await asyncio.to_thread(_http_get, _GRAPH_HOST + path, params)


# ---- Helpers ----------------------------------------------------------


def _has_env_credentials() -> bool:
    return all(
        os.environ.get(name, "").strip()
        for name in (_ENV_ACCESS_TOKEN, _ENV_USER_ID)
    )


def _compose_caption(metadata: PublishMetadata) -> str:
    """Build an IG caption from title + description + tags.

    IG's only text field is `caption`; we concatenate title (line 1),
    description (paragraph), and tags (#hashtag suffix).
    """
    parts: list[str] = []
    title = (metadata.title or "").strip()
    desc = (metadata.description or "").strip()
    if title:
        parts.append(title)
    if desc:
        parts.append(desc)
    if metadata.tags:
        # IG accepts #hashtags inline. Sanitize the tag string — drop spaces.
        hashtags = " ".join(
            f"#{''.join(c for c in t if c.isalnum())}"
            for t in metadata.tags
            if t.strip()
        )
        if hashtags:
            parts.append(hashtags)
    return "\n\n".join(parts)


def _http_post(url: str, data: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise ConnectorError(
            f"Graph API {exc.code}: {body_text[:500]}",
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


# Re-exports for ruff F401 quietness.
_ = (Visibility,)
