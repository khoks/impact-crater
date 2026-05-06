"""Tests for the reference-collage builder per ADR-0010 § N-008."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from impact_crater import paths
from impact_crater.media.collage import build_reference_collage
from impact_crater.storage import persons as persons_repo
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


def _photo_at(tmp_path: Path, name: str, color: tuple[int, int, int]) -> Path:
    p = tmp_path / name
    Image.new("RGB", (640, 480), color).save(p, format="JPEG", quality=85)
    return p


@pytest.mark.usefixtures("db_initialized")
async def test_build_collage_returns_none_when_library_empty() -> None:
    out = await build_reference_collage(media_resolver=lambda h: Path("nope"))
    assert out is None


@pytest.mark.usefixtures("db_initialized")
async def test_build_collage_two_persons_three_faces_each(tmp_path: Path) -> None:
    # 2 persons × 3 face photos.
    photos: dict[str, Path] = {}
    p1 = await persons_repo.create_person(display_name="Alice")
    p2 = await persons_repo.create_person(display_name="Bob")
    for i, person in enumerate([p1, p2]):
        for j in range(3):
            ph = _photo_at(tmp_path, f"{person.id}-{j}.jpg", (50 + i * 100, 50 + j * 50, 100))
            content_hash = f"hash-{person.id}-{j}"
            photos[content_hash] = ph
            await persons_repo.add_face_photo(
                person_id=person.id,
                content_hash=content_hash,
                face_crop_bbox=(0.25, 0.25, 0.5, 0.5),
            )

    def resolver(h: str) -> Path:
        return photos[h]

    out = await build_reference_collage(media_resolver=resolver)
    assert out is not None
    assert out.path.is_file()
    assert out.person_count == 2
    assert out.face_count == 6
    # Library version hash is deterministic — should be 32 hex chars per impl.
    assert len(out.library_version_hash) == 32

    img = Image.open(out.path)
    # 5 cells per row × 256 = 1280 wide; 2 rows × (256 + 32) = 576 tall.
    assert img.size == (1280, 576)


@pytest.mark.usefixtures("db_initialized")
async def test_collage_caches_by_library_version_hash(tmp_path: Path) -> None:
    p = await persons_repo.create_person(display_name="Alice")
    ph = _photo_at(tmp_path, "alice.jpg", (200, 80, 30))
    await persons_repo.add_face_photo(
        person_id=p.id,
        content_hash="hash-1",
        face_crop_bbox=(0, 0, 1, 1),
    )

    def resolver(h: str) -> Path:
        return ph

    out1 = await build_reference_collage(media_resolver=resolver)
    out2 = await build_reference_collage(media_resolver=resolver)
    assert out1 is not None and out2 is not None
    assert out1.library_version_hash == out2.library_version_hash
    assert out1.path == out2.path

    # Add a second face → hash changes → new collage path.
    await persons_repo.add_face_photo(
        person_id=p.id,
        content_hash="hash-2",
        face_crop_bbox=(0, 0, 1, 1),
    )
    out3 = await build_reference_collage(media_resolver=resolver)
    assert out3 is not None
    assert out3.library_version_hash != out1.library_version_hash
    assert out3.path != out1.path


@pytest.mark.usefixtures("db_initialized")
async def test_collage_files_land_in_expected_cache_dir(tmp_path: Path) -> None:
    p = await persons_repo.create_person(display_name="Z")
    ph = _photo_at(tmp_path, "z.jpg", (0, 0, 0))
    await persons_repo.add_face_photo(
        person_id=p.id,
        content_hash="hz",
        face_crop_bbox=(0, 0, 1, 1),
    )
    out = await build_reference_collage(media_resolver=lambda h: ph)
    assert out is not None
    expected_dir = paths.cache_dir() / "face-library"
    assert out.path.parent == expected_dir
