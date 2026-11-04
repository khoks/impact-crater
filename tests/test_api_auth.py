"""The local API guard (S-3.11.3): bearer token, Host check, WebSocket auth, --host refusal."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from impact_crater import api_auth, cli, paths
from impact_crater.app import _dist_file, _index_html, create_app
from impact_crater.storage.migrations import run_pending_migrations
from starlette.requests import Request
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _client(
    *,
    host: str = "127.0.0.1",
    client_ip: str = "127.0.0.1",
    allow_remote: bool = False,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    app = create_app(allow_remote=allow_remote)
    transport = httpx.ASGITransport(app=app, client=(client_ip, 5000))
    return httpx.AsyncClient(transport=transport, base_url=f"http://{host}", headers=headers)


@pytest.fixture
async def local() -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as ac:
        yield ac


def test_token_is_created_once_and_kept() -> None:
    first = api_auth.get_or_create_token()
    assert len(first) >= 32
    assert paths.api_token_path().read_text(encoding="utf-8").strip() == first
    assert api_auth.get_or_create_token() == first


async def test_mutating_request_without_token_is_401(local: httpx.AsyncClient) -> None:
    r = await local.post("/api/settings/update", json={"spend_cap_total_usd": 5})
    assert r.status_code == 401
    assert ".api-token" in r.json()["detail"]


async def test_mutating_request_with_wrong_token_is_401(local: httpx.AsyncClient) -> None:
    r = await local.post(
        "/api/settings/update",
        json={"spend_cap_total_usd": 5},
        headers={"Authorization": "Bearer not-the-token"},
    )
    assert r.status_code == 401


async def test_local_reads_need_the_token_except_tag_loaded_media(
    local: httpx.AsyncClient,
) -> None:
    await run_pending_migrations()
    assert (await local.get("/api/health")).status_code == 200
    # <video> / <img> cannot send the header: these reach their handler (404 / 400 for a
    # made-up id) without it.
    assert (await local.get("/api/snapshots/nope/render.mp4")).status_code == 404
    assert (await local.get("/api/media/nope/thumb.jpg")).status_code != 401
    # Everything else needs it, reads included (folder listings, projects, briefs).
    assert (await local.get("/api/projects")).status_code == 401
    assert (await local.get("/api/folder/scan", params={"path": "C:/"})).status_code == 401


async def test_session_hands_the_token_to_loopback_only() -> None:
    async with _client() as ac:
        r = await ac.get("/api/session")
        assert r.status_code == 200
        assert r.json()["token"] == api_auth.get_or_create_token()
    async with _client(client_ip="192.168.1.20", allow_remote=True) as remote:
        assert (await remote.get("/api/session")).status_code == 403


async def test_rebinding_page_gets_no_token_even_with_allow_remote() -> None:
    # The page's own name rebinds to 127.0.0.1; with --allow-remote the Host check is off.
    async with _client(host="evil.example:8765", allow_remote=True) as ac:
        assert (await ac.get("/api/session")).status_code == 403
        assert (await ac.get("/api/snapshots/nope/render.mp4")).status_code == 401


async def test_forwarded_requests_are_not_local() -> None:
    # A tunnel or `vite --host` forwards a remote caller from 127.0.0.1.
    forwarded = {"X-Forwarded-For": "203.0.113.9"}
    async with _client(headers=forwarded) as ac:
        assert (await ac.get("/api/session")).status_code == 403
    async with _client(headers={"X-Forwarded-For": "127.0.0.1"}) as ac:
        assert (await ac.get("/api/session")).status_code == 200
    async with _client(headers={"Forwarded": "for=203.0.113.9"}) as ac:
        assert (await ac.get("/api/session")).status_code == 403


async def test_ipv6_loopback_host_is_accepted() -> None:
    async with _client(host="[::1]:8765", client_ip="::1") as ac:
        assert (await ac.get("/api/session")).status_code == 200


async def test_folder_scan_refuses_network_paths() -> None:
    async with _client(headers=api_auth.auth_header()) as ac:
        for unc in (r"\\attacker\share", "//attacker/share"):
            r = await ac.get("/api/folder/scan", params={"path": unc})
            assert r.status_code == 400
            assert "network paths" in r.json()["detail"]


async def test_openapi_declares_the_bearer_scheme(local: httpx.AsyncClient) -> None:
    schema = (await local.get("/api/openapi.json")).json()
    assert schema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"


def test_static_files_never_escape_the_dist_folder(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "favicon.png").write_bytes(b"png")
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / ".api-token").write_text("secret", encoding="utf-8")
    assert _dist_file(dist, "favicon.png") == (dist / "favicon.png").resolve()
    assert _dist_file(dist, "../.api-token") is None
    assert _dist_file(dist, str(tmp_path / ".api-token")) is None
    assert _dist_file(dist, "index.html") is None


async def test_foreign_host_header_is_refused() -> None:
    # A DNS-rebinding page reaches 127.0.0.1 with its own name in the Host header.
    async with _client(host="evil.example") as ac:
        assert (await ac.get("/api/health")).status_code == 400


async def test_remote_client_needs_the_token_even_to_read() -> None:
    async with _client(host="192.168.1.5", client_ip="192.168.1.20", allow_remote=True) as ac:
        assert (await ac.get("/api/health")).status_code == 401
        r = await ac.get("/api/health", headers=api_auth.auth_header())
        assert r.status_code == 200


# TestClient sends Host: testserver for a relative WebSocket path.
_WS_URL = "ws://127.0.0.1/api/jobs/ws/no-such-job"


def _ws_client() -> TestClient:
    return TestClient(create_app(), base_url="http://127.0.0.1")


def test_websocket_with_token_reaches_the_endpoint() -> None:
    with _ws_client().websocket_connect(_WS_URL) as ws:
        ws.send_json({"type": "auth", "token": api_auth.get_or_create_token()})
        assert ws.receive_json() == {"type": "error", "detail": "unknown job"}


def test_websocket_with_wrong_token_is_closed() -> None:
    with _ws_client().websocket_connect(_WS_URL) as ws:
        ws.send_json({"type": "auth", "token": "wrong"})
        with pytest.raises(WebSocketDisconnect) as excinfo:
            ws.receive_json()
    assert excinfo.value.code == 1008


def test_websocket_from_a_foreign_origin_is_refused() -> None:
    client = _ws_client()
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect(_WS_URL, headers={"origin": "https://evil.example"}),
    ):
        pass
    assert excinfo.value.code == 1008


def test_websocket_from_the_vite_dev_origin_is_allowed() -> None:
    with _ws_client().websocket_connect(_WS_URL, headers={"origin": "http://localhost:5173"}) as ws:
        ws.send_json({"type": "auth", "token": api_auth.get_or_create_token()})
        assert ws.receive_json()["detail"] == "unknown job"


def test_non_loopback_host_without_allow_remote_refuses_to_start(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["--host", "0.0.0.0", "--no-browser"]) == 2
    assert "--allow-remote" in capsys.readouterr().err


def _request(client_ip: str, host: str = "127.0.0.1:8765") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"host", host.encode())],
            "client": (client_ip, 1),
        }
    )


def test_served_page_carries_the_token_for_loopback_only(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        "<html><head><title>x</title></head></html>", encoding="utf-8"
    )
    local_page = _index_html(tmp_path, "tok-123", _request("127.0.0.1")).body.decode()
    assert '<meta name="impact-crater-api-token" content="tok-123">' in local_page
    remote_page = _index_html(tmp_path, "tok-123", _request("192.168.1.20")).body.decode()
    assert "tok-123" not in remote_page
