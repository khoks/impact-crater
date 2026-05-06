"""Tests for the YouTubeConnector with an injected test transport."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from impact_crater import audit
from impact_crater.connectors import (
    ConnectorAuthError,
    ConnectorUploadResult,
    ConnectorValidationError,
    PublishMetadata,
)
from impact_crater.connectors.youtube import (
    YouTubeConnector,
    _read_credentials,
    store_credentials,
)
from impact_crater.storage.migrations import run_pending_migrations


class FakeTransport:
    """Drives the connector's upload + refresh paths without real HTTP."""

    def __init__(self, *, success: bool = True, fail_code: int = 200) -> None:
        self.success = success
        self.fail_code = fail_code
        self.upload_calls: list[dict] = []

    def refresh(self, creds: dict[str, Any]) -> dict[str, Any]:
        return {**creds, "access_token": "rotated-access-token", "expires_at": int(time.time()) + 3600}

    async def upload(
        self,
        *,
        render_path: Path,
        metadata: dict[str, Any],
        credentials: dict[str, Any],
        on_progress,
    ) -> ConnectorUploadResult:
        self.upload_calls.append(
            {"render_path": str(render_path), "metadata": metadata, "credentials": credentials}
        )
        if not self.success:
            from impact_crater.connectors import ConnectorError

            raise ConnectorError("upload failed", status_code=self.fail_code)
        if on_progress is not None:
            for v in (0.25, 0.5, 0.75, 1.0):
                await on_progress(v)
        privacy = metadata.get("status", {}).get("privacyStatus", "public")
        return ConnectorUploadResult(
            external_id="vid-abc123",
            external_url="https://youtube.com/watch?v=vid-abc123",
            visibility=privacy,
            response_code=200,
            response_summary="ok",
        )


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


@pytest.fixture
async def connected(db_initialized) -> None:
    """Store a fake set of credentials so `is_connected()` is True."""
    await store_credentials(
        {
            "user_handle": "test-user@example.com",
            "access_token": "fake-access",
            "refresh_token": "fake-refresh",
            "expires_at": int(time.time()) + 3600,
            "scopes_granted": ["youtube.upload"],
        }
    )


# ---- Validation -------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_validate_artifact_passes_for_good_input(tmp_path: Path) -> None:
    p = tmp_path / "render.mp4"
    p.write_bytes(b"\x00" * 1024)
    metadata = PublishMetadata(title="Hike", description="The summit", tags=["alps"])
    result = await YouTubeConnector().validate_artifact(p, metadata)
    assert result.valid is True
    assert result.issues == []


@pytest.mark.usefixtures("db_initialized")
async def test_validate_rejects_missing_render(tmp_path: Path) -> None:
    metadata = PublishMetadata(title="x")
    result = await YouTubeConnector().validate_artifact(
        tmp_path / "nope.mp4", metadata
    )
    assert result.valid is False
    assert any("not found" in i for i in result.issues)


@pytest.mark.usefixtures("db_initialized")
async def test_validate_rejects_overlong_title(tmp_path: Path) -> None:
    p = tmp_path / "render.mp4"
    p.write_bytes(b"\x00" * 1024)
    metadata = PublishMetadata(title="x" * 200)
    result = await YouTubeConnector().validate_artifact(p, metadata)
    assert result.valid is False
    assert any("100" in i for i in result.issues)


@pytest.mark.usefixtures("db_initialized")
async def test_validate_rejects_zero_byte_render(tmp_path: Path) -> None:
    p = tmp_path / "empty.mp4"
    p.write_bytes(b"")
    result = await YouTubeConnector().validate_artifact(p, PublishMetadata(title="x"))
    assert result.valid is False
    assert any("empty" in i for i in result.issues)


# ---- Connection state -------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_is_connected_false_initially() -> None:
    assert await YouTubeConnector().is_connected() is False


async def test_is_connected_true_after_storing(connected) -> None:
    assert await YouTubeConnector().is_connected() is True


async def test_disconnect_removes_credentials(connected) -> None:
    conn = YouTubeConnector()
    assert await conn.is_connected() is True
    await conn.disconnect()
    assert await conn.is_connected() is False


async def test_credentials_round_trip_decrypts(connected) -> None:
    creds = await _read_credentials()
    assert creds is not None
    assert creds["access_token"] == "fake-access"
    assert creds["refresh_token"] == "fake-refresh"
    assert creds["user_handle"] == "test-user@example.com"


# ---- Upload -----------------------------------------------------------


async def test_upload_happy_path(connected, tmp_path: Path) -> None:
    p = tmp_path / "render.mp4"
    p.write_bytes(b"\x00" * 2048)
    transport = FakeTransport(success=True)
    conn = YouTubeConnector(transport=transport)
    result = await conn.upload(
        p, PublishMetadata(title="Hike", visibility="unlisted")
    )
    assert isinstance(result, ConnectorUploadResult)
    assert result.external_id == "vid-abc123"
    assert result.external_url.startswith("https://youtube.com/")
    assert result.visibility == "unlisted"
    # Body conversion: visibility maps to privacyStatus.
    body = transport.upload_calls[0]["metadata"]
    assert body["status"]["privacyStatus"] == "unlisted"
    assert body["snippet"]["title"] == "Hike"


async def test_upload_progress_callback_invoked(
    connected, tmp_path: Path
) -> None:
    p = tmp_path / "render.mp4"
    p.write_bytes(b"\x00" * 2048)
    progress: list[float] = []

    async def on_progress(v: float) -> None:
        progress.append(v)

    await YouTubeConnector(transport=FakeTransport()).upload(
        p, PublishMetadata(title="x"), on_progress=on_progress
    )
    assert progress == [0.25, 0.5, 0.75, 1.0]


async def test_upload_raises_validation_error_on_bad_metadata(
    connected, tmp_path: Path
) -> None:
    p = tmp_path / "render.mp4"
    p.write_bytes(b"\x00" * 1024)
    with pytest.raises(ConnectorValidationError):
        await YouTubeConnector(transport=FakeTransport()).upload(
            p, PublishMetadata(title="")
        )


@pytest.mark.usefixtures("db_initialized")
async def test_upload_raises_auth_error_when_not_connected(tmp_path: Path) -> None:
    p = tmp_path / "render.mp4"
    p.write_bytes(b"\x00" * 1024)
    with pytest.raises(ConnectorAuthError):
        await YouTubeConnector(transport=FakeTransport()).upload(
            p, PublishMetadata(title="x")
        )


# ---- Refresh ----------------------------------------------------------


async def test_refresh_credentials_updates_access_token(connected) -> None:
    transport = FakeTransport()
    conn = YouTubeConnector(transport=transport)
    await conn.refresh_credentials()
    creds = await _read_credentials()
    assert creds is not None
    assert creds["access_token"] == "rotated-access-token"


@pytest.mark.usefixtures("db_initialized")
async def test_refresh_no_credentials_raises_auth() -> None:
    with pytest.raises(ConnectorAuthError):
        await YouTubeConnector(transport=FakeTransport()).refresh_credentials()


# ---- Audit log integration -------------------------------------------


async def test_audit_write_appends_jsonl_and_db(connected) -> None:
    # Audit FKs into projects + snapshots; insert the parents first.
    from impact_crater.storage.db import connection

    async with connection() as db:
        await db.execute(
            "INSERT INTO projects (id, name) VALUES (?, ?)", ("proj-1", "p1")
        )
        await db.execute(
            "INSERT INTO snapshots (id, project_id, plan_path, render_status) "
            "VALUES (?, ?, '/tmp/plan.json', 'success')",
            ("snap-1", "proj-1"),
        )
        await db.commit()
    entry = audit.AuditEntry(
        project_id="proj-1",
        snapshot_id="snap-1",
        platform="youtube",
        external_id="vid-xyz",
        external_url="https://youtube.com/watch?v=vid-xyz",
        user_approval_token="tok-abc",
        render_content_hash="hash-1",
    )
    await audit.write(entry)
    rows = await audit.list_for_project("proj-1")
    assert len(rows) == 1
    assert rows[0]["external_id"] == "vid-xyz"
    assert rows[0]["snapshot_id"] == "snap-1"
