"""The local API guard (S-3.11.3): bearer token, Host check, WebSocket auth, --host refusal."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from impact_crater import api_auth, cli, paths
from impact_crater.app import _index_html, create_app
from starlette.requests import Request
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _client(
    *, host: str = "127.0.0.1", client_ip: str = "127.0.0.1", allow_remote: bool = False
) -> httpx.AsyncClient:
    app = create_app(allow_remote=allow_remote)
    transport = httpx.ASGITransport(app=app, client=(client_ip, 5000))
    return httpx.AsyncClient(transport=transport, base_url=f"http://{host}")


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


async def test_loopback_read_needs_no_token(local: httpx.AsyncClient) -> None:
    assert (await local.get("/api/health")).status_code == 200


async def test_session_hands_the_token_to_loopback_only() -> None:
    async with _client() as ac:
        r = await ac.get("/api/session")
        assert r.status_code == 200
        assert r.json()["token"] == api_auth.get_or_create_token()
    async with _client(client_ip="192.168.1.20", allow_remote=True) as remote:
        assert (await remote.get("/api/session")).status_code == 403


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


def _request(client_ip: str) -> Request:
    return Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": (client_ip, 1)}
    )


def test_served_page_carries_the_token_for_loopback_only(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        "<html><head><title>x</title></head></html>", encoding="utf-8"
    )
    local_page = _index_html(tmp_path, "tok-123", _request("127.0.0.1")).body.decode()
    assert '<meta name="impact-crater-api-token" content="tok-123">' in local_page
    remote_page = _index_html(tmp_path, "tok-123", _request("192.168.1.20")).body.decode()
    assert "tok-123" not in remote_page
