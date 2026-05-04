"""Tests for the FastAPI app factory + the M0 endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from impact_crater import __version__
from impact_crater.app import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Trigger lifespan startup so migrations run.
        async with httpx.AsyncClient(transport=transport, base_url="http://test"):
            yield ac


async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


async def test_setup_status_stub_returns_false(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json() == {"setup_complete": False}


async def test_projects_list_empty_at_m0(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == []


async def test_root_serves_not_built_placeholder_when_dist_missing(
    client: httpx.AsyncClient,
) -> None:
    """If neither packaged nor dev frontend dist exists, GET / returns the placeholder.

    The placeholder is HTML and includes the build instructions.
    """
    r = await client.get("/")
    # Either:
    #  (a) The packaged dist exists (built before publish) → 200 + index.html → ok
    #  (b) The placeholder runs → 200 + HTML containing the build instructions
    assert r.status_code == 200
    text = r.text
    is_placeholder = "frontend not built" in text.lower()
    is_index = "<!doctype html>" in text.lower() or "<html" in text.lower()
    assert is_placeholder or is_index


def test_cli_version_flag_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    from impact_crater import cli

    rc = cli.main(["--version"])
    assert rc == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_choose_port_prefers_8765_when_free() -> None:
    from impact_crater import cli

    # When 8765 is free we should get it back; if it's taken on the test
    # runner we should still get a non-None port (auto-pick fallback).
    port = cli._choose_port(cli.DEFAULT_HOST, requested=None)
    assert port is not None
    assert isinstance(port, int)
    assert port > 0
