"""Persons + person_face_photos repo per ADR-0010 § N-008.

Tables already exist in `001_init.sql`. This module wraps the CRUD.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from impact_crater.storage.db import connection


@dataclass
class Person:
    id: str
    display_name: str
    notes: str | None = None


@dataclass
class FacePhoto:
    id: str
    person_id: str
    content_hash: str  # of the source photo
    face_crop_bbox: tuple[float, float, float, float]  # (x, y, w, h) normalized 0..1
    is_primary: bool = False


# Per ADR-0010: default 5, range 3-10.
MAX_FACE_PHOTOS_PER_PERSON = 10


# ---- Persons ----


async def create_person(*, display_name: str, notes: str | None = None) -> Person:
    person = Person(id=uuid.uuid4().hex, display_name=display_name, notes=notes)
    async with connection() as db:
        await db.execute(
            "INSERT INTO persons (id, display_name, notes) VALUES (?, ?, ?)",
            (person.id, person.display_name, person.notes),
        )
        await db.commit()
    return person


async def list_persons() -> list[Person]:
    async with connection() as db:
        cur = await db.execute(
            "SELECT id, display_name, notes FROM persons ORDER BY display_name"
        )
        rows = await cur.fetchall()
    return [Person(id=r["id"], display_name=r["display_name"], notes=r["notes"]) for r in rows]


async def get_person(person_id: str) -> Person | None:
    async with connection() as db:
        cur = await db.execute(
            "SELECT id, display_name, notes FROM persons WHERE id = ?", (person_id,)
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return Person(id=row["id"], display_name=row["display_name"], notes=row["notes"])


async def delete_person(person_id: str) -> bool:
    async with connection() as db:
        cur = await db.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        await db.commit()
    return (cur.rowcount or 0) > 0


# ---- Face photos ----


async def add_face_photo(
    *,
    person_id: str,
    content_hash: str,
    face_crop_bbox: tuple[float, float, float, float],
    is_primary: bool = False,
) -> FacePhoto:
    existing = await list_face_photos(person_id)
    if len(existing) >= MAX_FACE_PHOTOS_PER_PERSON:
        raise ValueError(
            f"person {person_id} already has {len(existing)} face photos "
            f"(max {MAX_FACE_PHOTOS_PER_PERSON})"
        )
    fp = FacePhoto(
        id=uuid.uuid4().hex,
        person_id=person_id,
        content_hash=content_hash,
        face_crop_bbox=face_crop_bbox,
        is_primary=is_primary,
    )
    async with connection() as db:
        if is_primary:
            # Demote any existing primary.
            await db.execute(
                "UPDATE person_face_photos SET is_primary = 0 WHERE person_id = ?",
                (person_id,),
            )
        await db.execute(
            """
            INSERT INTO person_face_photos
                (id, person_id, content_hash, face_crop_bbox, is_primary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                fp.id,
                fp.person_id,
                fp.content_hash,
                json.dumps(list(face_crop_bbox)),
                1 if is_primary else 0,
            ),
        )
        await db.commit()
    return fp


async def list_face_photos(person_id: str) -> list[FacePhoto]:
    async with connection() as db:
        cur = await db.execute(
            """
            SELECT id, person_id, content_hash, face_crop_bbox, is_primary
            FROM person_face_photos
            WHERE person_id = ?
            ORDER BY is_primary DESC, added_at ASC
            """,
            (person_id,),
        )
        rows = await cur.fetchall()
    out: list[FacePhoto] = []
    for row in rows:
        bbox = json.loads(row["face_crop_bbox"])
        out.append(
            FacePhoto(
                id=row["id"],
                person_id=row["person_id"],
                content_hash=row["content_hash"],
                face_crop_bbox=tuple(bbox),  # type: ignore[arg-type]
                is_primary=bool(row["is_primary"]),
            )
        )
    return out


async def delete_face_photo(face_photo_id: str) -> bool:
    async with connection() as db:
        cur = await db.execute(
            "DELETE FROM person_face_photos WHERE id = ?", (face_photo_id,)
        )
        await db.commit()
    return (cur.rowcount or 0) > 0
