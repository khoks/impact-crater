"""Publish API per S-2.8 / ADR-0013.

  POST /api/snapshots/{id}/publish        — kick off the publish flow
  POST /api/connectors/youtube/disconnect — revoke + clear creds
  GET  /api/connectors/youtube/status     — connected state + handle
  GET  /api/projects/{id}/audit           — last N publishes for a project

OAuth init/callback intentionally NOT here — they need a real OAuth
client config the user provides. The callback handler will land alongside
the Connect button when the user wires up their Google Cloud project.
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from impact_crater import audit
from impact_crater.connectors import (
    LIVE_PUBLISH_PLATFORMS,
    Connector,
    ConnectorAuthError,
    ConnectorError,
    ConnectorValidationError,
    Platform,
    PublishMetadata,
    Visibility,
    get_connector,
    is_dry_run_enabled,
)
from impact_crater.connectors.youtube import YouTubeConnector
from impact_crater.storage.db import connection

log = logging.getLogger(__name__)
router = APIRouter()


class PublishRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = []
    visibility: Visibility = "public"
    # v1 multi-platform: optional, defaults to "youtube" so M7 callers still work.
    platform: Platform = "youtube"


class PublishResponse(BaseModel):
    external_id: str
    external_url: str
    visibility: str
    audit_token: str
    platform: str
    dry_run: bool


# Test-only injection point — see `set_connector_factory` below.
_connector_factory_override: "callable[[str], Connector] | None" = None


def set_connector_factory(factory: "callable[[], YouTubeConnector] | callable[[str], Connector]") -> None:
    """Tests inject a connector factory. Two signatures supported for
    backward compatibility:

      - 0-arg `() -> YouTubeConnector`  — legacy M7 tests, treated as YouTube.
      - 1-arg `(platform) -> Connector` — v1 multi-platform tests.
    """
    import inspect
    global _connector_factory_override
    try:
        n_params = len(inspect.signature(factory).parameters)
    except (TypeError, ValueError):
        n_params = 0
    if n_params == 0:
        _connector_factory_override = lambda _platform: factory()  # type: ignore[misc]
    else:
        _connector_factory_override = factory  # type: ignore[assignment]


def _get_connector(platform: str = "youtube") -> Connector:
    """Resolve a connector for `platform`. Returns dry-run-wrapped per
    the factory in `connectors.__init__`."""
    if _connector_factory_override is not None:
        return _connector_factory_override(platform)
    return get_connector(platform)


# ---- Snapshot publish -------------------------------------------------


@router.post("/snapshots/{snapshot_id}/publish", response_model=PublishResponse)
async def publish_snapshot(
    snapshot_id: str, req: PublishRequest
) -> PublishResponse:
    async with connection() as db:
        cur = await db.execute(
            "SELECT project_id, render_path FROM snapshots WHERE id = ?",
            (snapshot_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"snapshot {snapshot_id!r} not found",
        )
    if not row["render_path"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="snapshot has no rendered MP4 yet",
        )
    render_path = Path(row["render_path"])
    if not render_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"render file missing on disk: {render_path}",
        )

    metadata = PublishMetadata(
        title=req.title,
        description=req.description,
        tags=req.tags,
        visibility=req.visibility,
    )

    try:
        connector = _get_connector(req.platform)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "validation", "message": str(exc)},
        ) from exc

    dry_run = is_dry_run_enabled()
    log.info(
        "publish_attempt platform=%s snapshot_id=%s project_id=%s "
        "render_path=%s title=%r visibility=%s dry_run=%s",
        req.platform,
        snapshot_id,
        row["project_id"],
        str(render_path),
        req.title[:120],
        req.visibility,
        dry_run,
    )

    try:
        result = await connector.upload(render_path, metadata)
    except ConnectorAuthError as exc:
        log.warning(
            "publish_auth_failed platform=%s snapshot_id=%s project_id=%s error=%s",
            req.platform,
            snapshot_id,
            row["project_id"],
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"reason": "auth", "message": str(exc), "suggested_action": exc.suggested_action},
        ) from exc
    except ConnectorValidationError as exc:
        log.warning(
            "publish_validation_failed platform=%s snapshot_id=%s project_id=%s error=%s",
            req.platform,
            snapshot_id,
            row["project_id"],
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "validation", "message": str(exc), "suggested_action": exc.suggested_action},
        ) from exc
    except ConnectorError as exc:
        log.error(
            "publish_connector_failed platform=%s snapshot_id=%s project_id=%s "
            "status_code=%s error=%s",
            req.platform,
            snapshot_id,
            row["project_id"],
            exc.status_code,
            str(exc)[:300],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"reason": "connector", "message": str(exc), "status_code": exc.status_code},
        ) from exc

    audit_token = secrets.token_urlsafe(16)
    # Audit row records dry-run vs live so post-hoc you can tell which
    # external_ids are real.
    audit_platform = f"{req.platform} (dry-run)" if dry_run else req.platform
    entry = audit.AuditEntry(
        project_id=row["project_id"],
        snapshot_id=snapshot_id,
        platform=audit_platform,
        external_id=result.external_id,
        external_url=result.external_url,
        user_approval_token=audit_token,
        response_code=result.response_code,
        response_summary=result.response_summary,
        description_full=req.description,
        visibility=result.visibility,
    )
    await audit.write(entry)

    log.info(
        "publish_succeeded platform=%s snapshot_id=%s project_id=%s "
        "external_id=%s external_url=%s visibility=%s audit_token=%s dry_run=%s",
        req.platform,
        snapshot_id,
        row["project_id"],
        result.external_id,
        result.external_url,
        result.visibility,
        audit_token,
        dry_run,
    )

    return PublishResponse(
        external_id=result.external_id,
        external_url=result.external_url,
        visibility=result.visibility,
        audit_token=audit_token,
        platform=req.platform,
        dry_run=dry_run,
    )


# ---- Connector status -------------------------------------------------


@router.get("/connectors/youtube/status")
async def youtube_status() -> dict[str, Any]:
    connector = _get_connector("youtube")
    connected = await connector.is_connected()
    handle = None
    if connected:
        async with connection() as db:
            cur = await db.execute(
                "SELECT user_handle FROM connector_credentials WHERE connector_name = ?",
                ("youtube",),
            )
            row = await cur.fetchone()
        handle = row["user_handle"] if row else None
    return {"connected": connected, "user_handle": handle}


@router.post("/connectors/youtube/disconnect")
async def youtube_disconnect() -> dict[str, bool]:
    await _get_connector("youtube").disconnect()
    return {"disconnected": True}


@router.get("/connectors/{platform}/status")
async def connector_status(platform: str) -> dict[str, Any]:
    """Generic per-platform connection status (v1 multi-platform).

    Returns {connected, dry_run, env_vars_missing}. For YouTube we also
    include the user_handle from the DB if present (M7 OAuth path)."""
    if platform not in LIVE_PUBLISH_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown platform {platform!r}",
        )
    try:
        connector = _get_connector(platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connected = await connector.is_connected()
    return {
        "platform": platform,
        "connected": connected,
        "dry_run": is_dry_run_enabled(),
    }


@router.get("/connectors/status")
async def all_connectors_status() -> dict[str, Any]:
    """Snapshot of every supported platform's connection state, plus the
    dry-run flag. Used by the publish modal to populate the platform
    picker with per-platform `connected` badges in one round trip."""
    results: list[dict[str, Any]] = []
    for platform in LIVE_PUBLISH_PLATFORMS:
        try:
            connector = _get_connector(platform)
            connected = await connector.is_connected()
        except Exception:  # pragma: no cover
            connected = False
        results.append({"platform": platform, "connected": connected})
    return {
        "platforms": results,
        "dry_run": is_dry_run_enabled(),
    }


# ---- Audit log --------------------------------------------------------


@router.get("/projects/{project_id}/audit")
async def project_audit(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return await audit.list_for_project(project_id, limit=limit)
