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
    ConnectorAuthError,
    ConnectorError,
    ConnectorValidationError,
    PublishMetadata,
    Visibility,
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


class PublishResponse(BaseModel):
    external_id: str
    external_url: str
    visibility: str
    audit_token: str


_connector_factory: "callable[[], YouTubeConnector]" = lambda: YouTubeConnector()


def set_connector_factory(factory: "callable[[], YouTubeConnector]") -> None:
    """Tests + the OAuth wiring use this to inject a transport-equipped connector."""
    global _connector_factory
    _connector_factory = factory


def _get_connector() -> YouTubeConnector:
    """Return a YouTubeConnector instance.

    M7 baseline returns a connector without a transport — production
    callers won't reach the upload path until the user has wired OAuth
    and a real google-api-python-client transport is bound. The Settings
    UI's "Connect YouTube" button is what triggers that wiring.
    """
    return _connector_factory()


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

    log.info(
        "publish_attempt platform=youtube snapshot_id=%s project_id=%s "
        "render_path=%s title=%r visibility=%s",
        snapshot_id,
        row["project_id"],
        str(render_path),
        req.title[:120],
        req.visibility,
    )

    connector = _get_connector()
    try:
        result = await connector.upload(render_path, metadata)
    except ConnectorAuthError as exc:
        log.warning(
            "publish_auth_failed snapshot_id=%s project_id=%s error=%s",
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
            "publish_validation_failed snapshot_id=%s project_id=%s error=%s",
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
            "publish_connector_failed snapshot_id=%s project_id=%s "
            "status_code=%s error=%s",
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
    entry = audit.AuditEntry(
        project_id=row["project_id"],
        snapshot_id=snapshot_id,
        platform="youtube",
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
        "publish_succeeded platform=youtube snapshot_id=%s project_id=%s "
        "external_id=%s external_url=%s visibility=%s audit_token=%s",
        snapshot_id,
        row["project_id"],
        result.external_id,
        result.external_url,
        result.visibility,
        audit_token,
    )

    return PublishResponse(
        external_id=result.external_id,
        external_url=result.external_url,
        visibility=result.visibility,
        audit_token=audit_token,
    )


# ---- Connector status -------------------------------------------------


@router.get("/connectors/youtube/status")
async def youtube_status() -> dict[str, Any]:
    connector = _get_connector()
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
    await _get_connector().disconnect()
    return {"disconnected": True}


# ---- Audit log --------------------------------------------------------


@router.get("/projects/{project_id}/audit")
async def project_audit(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return await audit.list_for_project(project_id, limit=limit)
