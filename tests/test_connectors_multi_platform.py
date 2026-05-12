"""Tests for the v1 multi-platform connector framework.

Covers:
  - The factory: get_connector(platform) dispatch + unknown raises
  - DryRunConnector: validates but doesn't post; preserves wrapped name
  - is_dry_run_enabled(): env-var flag semantics
  - InstagramConnector: caption composition, env-var detection,
    visibility=public enforcement, container-poll flow with stub transport
  - FacebookConnector: env-var detection, visibility mapping,
    multipart upload with stub transport
  - YouTubeConnector env-driven path: env-var detection only (real
    google client wiring tested by existing test_publish.py via the
    transport-injection seam)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from impact_crater.connectors import (
    DryRunConnector,
    FacebookConnector,
    InstagramConnector,
    PublishMetadata,
    YouTubeConnector,
    get_connector,
    is_dry_run_enabled,
)
from impact_crater.connectors.base import (
    ConnectorAuthError,
    ConnectorUploadResult,
    ConnectorValidationError,
)


# ---- Factory ----------------------------------------------------------


def test_get_connector_returns_each_platform() -> None:
    """The factory must dispatch by platform name. Default env state
    means dry-run is on → results are wrapped by DryRunConnector but
    still expose the wrapped `name`."""
    for platform in ("youtube", "instagram", "facebook"):
        c = get_connector(platform)
        assert c.name == platform


def test_get_connector_unknown_platform_raises() -> None:
    with pytest.raises(ValueError) as excinfo:
        get_connector("tiktok")
    assert "tiktok" in str(excinfo.value)


# ---- Dry-run flag -----------------------------------------------------


def test_is_dry_run_enabled_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Safe-by-default: unset env var → dry-run on."""
    monkeypatch.delenv("IC_PUBLISH_DRY_RUN", raising=False)
    assert is_dry_run_enabled() is True


@pytest.mark.parametrize("val", ["0", "false", "False", "no", "off", ""])
def test_is_dry_run_disabled_when_explicitly_off(
    monkeypatch: pytest.MonkeyPatch, val: str
) -> None:
    monkeypatch.setenv("IC_PUBLISH_DRY_RUN", val)
    assert is_dry_run_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "anything-else"])
def test_is_dry_run_enabled_when_explicitly_on(
    monkeypatch: pytest.MonkeyPatch, val: str
) -> None:
    monkeypatch.setenv("IC_PUBLISH_DRY_RUN", val)
    assert is_dry_run_enabled() is True


# ---- DryRunConnector --------------------------------------------------


async def test_dry_run_returns_synthetic_upload_when_valid(tmp_path: Path) -> None:
    """Validates + short-circuits to a fake ConnectorUploadResult."""
    inner = AsyncMock()
    inner.name = "youtube"
    inner.validate_artifact = AsyncMock(
        return_value=type("V", (), {"valid": True, "issues": [], "suggested_actions": []})()
    )

    f = tmp_path / "render.mp4"
    f.write_bytes(b"\x00\x00\x00")
    metadata = PublishMetadata(title="Hello", description="World", visibility="public")
    dr = DryRunConnector(inner)

    result = await dr.upload(f, metadata)

    assert isinstance(result, ConnectorUploadResult)
    assert result.external_id.startswith("dry-run-")
    assert result.external_url.startswith("https://dry-run.local/youtube/")
    assert result.visibility == "public"
    assert "DRY-RUN" in result.response_summary
    # Crucially: the inner connector's upload() must NOT have been called.
    inner.upload.assert_not_called()


async def test_dry_run_propagates_validation_errors(tmp_path: Path) -> None:
    """A validation failure must still raise — dry-run isn't a free pass."""
    inner = AsyncMock()
    inner.name = "youtube"
    inner.validate_artifact = AsyncMock(
        return_value=type(
            "V",
            (),
            {
                "valid": False,
                "issues": ["title is required"],
                "suggested_actions": ["Enter a title."],
            },
        )()
    )

    metadata = PublishMetadata(title="", visibility="public")
    dr = DryRunConnector(inner)

    with pytest.raises(ConnectorValidationError) as excinfo:
        await dr.upload(tmp_path / "render.mp4", metadata)
    assert "title is required" in str(excinfo.value)


# ---- InstagramConnector -----------------------------------------------


def test_instagram_is_connected_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IC_INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("IC_INSTAGRAM_USER_ID", raising=False)
    ig = InstagramConnector()
    import asyncio
    assert asyncio.run(ig.is_connected()) is False

    monkeypatch.setenv("IC_INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_INSTAGRAM_USER_ID", "12345")
    assert asyncio.run(ig.is_connected()) is True


async def test_instagram_validation_rejects_non_public_visibility(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Instagram Reels are always public — connector must reject
    private/unlisted up front rather than silently changing it."""
    monkeypatch.setenv("IC_INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_INSTAGRAM_USER_ID", "12345")
    f = tmp_path / "render.mp4"
    f.write_bytes(b"\x00" * 100)

    ig = InstagramConnector()
    result = await ig.validate_artifact(
        f, PublishMetadata(title="X", visibility="private")
    )
    assert result.valid is False
    assert any("private" in issue for issue in result.issues)


async def test_instagram_upload_requires_public_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without IC_PUBLIC_BASE_URL set, real posting must refuse cleanly
    with an auth-shaped error (so the publish API returns 401)."""
    monkeypatch.setenv("IC_INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_INSTAGRAM_USER_ID", "12345")
    monkeypatch.delenv("IC_PUBLIC_BASE_URL", raising=False)
    snap_dir = tmp_path / "snapshots" / "snapXYZ"
    snap_dir.mkdir(parents=True)
    f = snap_dir / "render.mp4"
    f.write_bytes(b"\x00" * 100)

    ig = InstagramConnector()
    with pytest.raises(ConnectorAuthError) as excinfo:
        await ig.upload(f, PublishMetadata(title="X", visibility="public"))
    assert "IC_PUBLIC_BASE_URL" in str(excinfo.value)


async def test_instagram_full_flow_with_stub_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end posting flow with the transport seam: create
    container → poll status → publish → fetch permalink."""
    monkeypatch.setenv("IC_INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_INSTAGRAM_USER_ID", "12345")
    monkeypatch.setenv("IC_PUBLIC_BASE_URL", "https://example.test")

    snap_dir = tmp_path / "snapshots" / "snapABC"
    snap_dir.mkdir(parents=True)
    f = snap_dir / "render.mp4"
    f.write_bytes(b"\x00" * 100)

    class _StubTransport:
        def __init__(self) -> None:
            self.posts: list[tuple[str, dict]] = []
            self.gets: list[tuple[str, dict]] = []

        async def post(self, path: str, data: dict) -> dict:
            self.posts.append((path, data))
            if path.endswith("/media"):
                return {"id": "container-1"}
            if path.endswith("/media_publish"):
                return {"id": "media-99"}
            raise AssertionError(f"unexpected POST {path}")

        async def get(self, path: str, params: dict) -> dict:
            self.gets.append((path, params))
            if path == "/container-1":
                return {"status_code": "FINISHED"}
            if path == "/media-99":
                return {"permalink": "https://instagram.com/p/abc/"}
            raise AssertionError(f"unexpected GET {path}")

    # Make polling instant by patching the asyncio.sleep inside the connector.
    monkeypatch.setattr("impact_crater.connectors.instagram.asyncio.sleep", AsyncMock())

    transport = _StubTransport()
    ig = InstagramConnector(transport=transport)
    result = await ig.upload(
        f, PublishMetadata(title="Hello IG", description="World", visibility="public")
    )

    assert result.external_id == "media-99"
    assert result.external_url == "https://instagram.com/p/abc/"
    # Container creation must have included the constructed video URL.
    create_call = transport.posts[0]
    assert create_call[0].endswith("/media")
    assert (
        create_call[1]["video_url"]
        == "https://example.test/api/snapshots/snapABC/render.mp4"
    )


# ---- FacebookConnector ------------------------------------------------


def test_facebook_is_connected_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IC_FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("IC_FACEBOOK_PAGE_ID", raising=False)
    fb = FacebookConnector()
    import asyncio
    assert asyncio.run(fb.is_connected()) is False

    monkeypatch.setenv("IC_FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_FACEBOOK_PAGE_ID", "98765")
    assert asyncio.run(fb.is_connected()) is True


async def test_facebook_rejects_private_visibility(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Facebook Page API has no private — connector must say so up front."""
    monkeypatch.setenv("IC_FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_FACEBOOK_PAGE_ID", "98765")
    f = tmp_path / "render.mp4"
    f.write_bytes(b"\x00" * 100)

    fb = FacebookConnector()
    result = await fb.validate_artifact(
        f, PublishMetadata(title="X", visibility="private")
    )
    assert result.valid is False
    assert any("private" in issue for issue in result.issues)


async def test_facebook_publish_with_stub_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end: upload binary via transport stub; verify published
    flag mapping + audit metadata fields."""
    monkeypatch.setenv("IC_FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IC_FACEBOOK_PAGE_ID", "98765")
    f = tmp_path / "render.mp4"
    f.write_bytes(b"\x00" * 200)

    class _StubTransport:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def upload_video(self, *, page_id: str, render_path: Path, fields: dict) -> dict:
            self.calls.append(
                {"page_id": page_id, "render_path": render_path, "fields": fields}
            )
            return {"id": "fbvid-42"}

    # The connector also fetches permalink_url after upload via _http_get
    # (no transport seam there because it's a thread-blocking urllib call).
    # Patch it to a no-op so the test doesn't hit the network.
    monkeypatch.setattr(
        "impact_crater.connectors.facebook._http_get",
        lambda url, params: {"permalink_url": "/page/posts/123"},
    )

    transport = _StubTransport()
    fb = FacebookConnector(transport=transport)
    result = await fb.upload(
        f,
        PublishMetadata(
            title="Hello FB", description="World", visibility="unlisted"
        ),
    )

    assert result.external_id == "fbvid-42"
    assert result.external_url == "https://www.facebook.com/page/posts/123"
    # visibility=unlisted → published=false + DRAFT
    assert transport.calls[0]["fields"]["published"] == "false"
    assert transport.calls[0]["fields"]["unpublished_content_type"] == "DRAFT"


# ---- YouTubeConnector (env path detection) ----------------------------


def test_youtube_env_path_detected_when_all_three_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting all three IC_YOUTUBE_* env vars must make is_connected
    return True without touching the DB."""
    monkeypatch.setenv("IC_YOUTUBE_CLIENT_ID", "abc.apps.googleusercontent.com")
    monkeypatch.setenv("IC_YOUTUBE_CLIENT_SECRET", "GOCSPX-xxx")
    monkeypatch.setenv("IC_YOUTUBE_REFRESH_TOKEN", "1//refresh-tok")

    yt = YouTubeConnector()
    import asyncio
    assert asyncio.run(yt.is_connected()) is True


def test_youtube_env_path_requires_all_three(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing any one of the three should fall back to the DB path
    (which returns False in tests since no creds are stored)."""
    monkeypatch.setenv("IC_YOUTUBE_CLIENT_ID", "abc")
    monkeypatch.setenv("IC_YOUTUBE_CLIENT_SECRET", "shh")
    monkeypatch.delenv("IC_YOUTUBE_REFRESH_TOKEN", raising=False)

    # is_connected() drops to the DB path which queries connector_credentials.
    # In an in-test DB with no migrations applied yet, that would error;
    # but our test_quota.py + others run migrations as a fixture. We
    # don't depend on that here — just verify the env-path doesn't fire.
    from impact_crater.connectors.youtube import _has_env_credentials
    assert _has_env_credentials() is False


# Ensure tests don't leave env vars set for other tests.
@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "IC_YOUTUBE_CLIENT_ID",
        "IC_YOUTUBE_CLIENT_SECRET",
        "IC_YOUTUBE_REFRESH_TOKEN",
        "IC_INSTAGRAM_ACCESS_TOKEN",
        "IC_INSTAGRAM_USER_ID",
        "IC_FACEBOOK_PAGE_ACCESS_TOKEN",
        "IC_FACEBOOK_PAGE_ID",
        "IC_PUBLIC_BASE_URL",
        "IC_PUBLISH_DRY_RUN",
    ):
        monkeypatch.delenv(name, raising=False)


# `os.environ` import kept for symmetry with the connectors under test.
_ = os
