"""Tests for the person library REST API + repo per ADR-0010 § N-008."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from impact_crater.app import create_app
from impact_crater.storage import persons as persons_repo
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---- Repo-direct tests ------------------------------------------------


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


@pytest.mark.usefixtures("db_initialized")
async def test_create_and_list_persons() -> None:
    p = await persons_repo.create_person(display_name="Alice")
    rows = await persons_repo.list_persons()
    assert len(rows) == 1
    assert rows[0].id == p.id
    assert rows[0].display_name == "Alice"


@pytest.mark.usefixtures("db_initialized")
async def test_add_face_photo_caps_at_max() -> None:
    p = await persons_repo.create_person(display_name="Bob")
    for i in range(persons_repo.MAX_FACE_PHOTOS_PER_PERSON):
        await persons_repo.add_face_photo(
            person_id=p.id,
            content_hash=f"h-{i}",
            face_crop_bbox=(0.0, 0.0, 1.0, 1.0),
        )
    with pytest.raises(ValueError, match="max"):
        await persons_repo.add_face_photo(
            person_id=p.id,
            content_hash="h-overflow",
            face_crop_bbox=(0.0, 0.0, 1.0, 1.0),
        )


@pytest.mark.usefixtures("db_initialized")
async def test_setting_primary_demotes_existing_primary() -> None:
    p = await persons_repo.create_person(display_name="Cora")
    f1 = await persons_repo.add_face_photo(
        person_id=p.id, content_hash="h1", face_crop_bbox=(0, 0, 1, 1), is_primary=True
    )
    f2 = await persons_repo.add_face_photo(
        person_id=p.id, content_hash="h2", face_crop_bbox=(0, 0, 1, 1), is_primary=True
    )
    rows = await persons_repo.list_face_photos(p.id)
    primaries = [r for r in rows if r.is_primary]
    assert len(primaries) == 1
    assert primaries[0].id == f2.id
    # f1 still in list, just not primary.
    assert any(r.id == f1.id and not r.is_primary for r in rows)


# ---- HTTP tests -------------------------------------------------------


async def test_post_persons_creates_and_get_returns(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/persons", json={"display_name": "Dora"})
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await client.get("/api/persons")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())


async def test_delete_persons_404_for_unknown(client: httpx.AsyncClient) -> None:
    r = await client.delete("/api/persons/nonexistent")
    assert r.status_code == 404


async def test_face_photo_round_trip(client: httpx.AsyncClient) -> None:
    p = await client.post("/api/persons", json={"display_name": "Eli"})
    pid = p.json()["id"]
    fp = await client.post(
        f"/api/persons/{pid}/face-photos",
        json={"content_hash": "abc123def456", "face_crop_bbox": [0.1, 0.2, 0.3, 0.4]},
    )
    assert fp.status_code == 201
    body = fp.json()
    assert body["face_crop_bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert body["is_primary"] is False

    listed = await client.get(f"/api/persons/{pid}/face-photos")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_add_face_photo_404_when_person_missing(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/persons/nope/face-photos",
        json={"content_hash": "abcdef0123"},
    )
    assert r.status_code == 404
