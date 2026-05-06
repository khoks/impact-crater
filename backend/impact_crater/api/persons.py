"""Person library REST API per ADR-0010 § N-008."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from impact_crater.storage import persons as persons_repo

router = APIRouter()


class PersonOut(BaseModel):
    id: str
    display_name: str
    notes: str | None


class FacePhotoOut(BaseModel):
    id: str
    person_id: str
    content_hash: str
    face_crop_bbox: tuple[float, float, float, float]
    is_primary: bool


class CreatePersonRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    notes: str | None = None


class AddFacePhotoRequest(BaseModel):
    content_hash: str = Field(min_length=8)
    face_crop_bbox: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    is_primary: bool = False


@router.get("", response_model=list[PersonOut])
async def list_persons() -> list[PersonOut]:
    rows = await persons_repo.list_persons()
    return [PersonOut(id=r.id, display_name=r.display_name, notes=r.notes) for r in rows]


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(req: CreatePersonRequest) -> PersonOut:
    p = await persons_repo.create_person(display_name=req.display_name, notes=req.notes)
    return PersonOut(id=p.id, display_name=p.display_name, notes=p.notes)


@router.delete("/{person_id}")
async def delete_person(person_id: str) -> dict[str, bool]:
    ok = await persons_repo.delete_person(person_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"person {person_id!r} not found")
    return {"deleted": True}


@router.get("/{person_id}/face-photos", response_model=list[FacePhotoOut])
async def list_face_photos(person_id: str) -> list[FacePhotoOut]:
    if (await persons_repo.get_person(person_id)) is None:
        raise HTTPException(status_code=404, detail=f"person {person_id!r} not found")
    rows = await persons_repo.list_face_photos(person_id)
    return [
        FacePhotoOut(
            id=r.id,
            person_id=r.person_id,
            content_hash=r.content_hash,
            face_crop_bbox=r.face_crop_bbox,
            is_primary=r.is_primary,
        )
        for r in rows
    ]


@router.post(
    "/{person_id}/face-photos",
    response_model=FacePhotoOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_face_photo(person_id: str, req: AddFacePhotoRequest) -> FacePhotoOut:
    if (await persons_repo.get_person(person_id)) is None:
        raise HTTPException(status_code=404, detail=f"person {person_id!r} not found")
    try:
        fp = await persons_repo.add_face_photo(
            person_id=person_id,
            content_hash=req.content_hash,
            face_crop_bbox=req.face_crop_bbox,
            is_primary=req.is_primary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FacePhotoOut(
        id=fp.id,
        person_id=fp.person_id,
        content_hash=fp.content_hash,
        face_crop_bbox=fp.face_crop_bbox,
        is_primary=fp.is_primary,
    )


@router.delete("/face-photos/{face_photo_id}")
async def delete_face_photo(face_photo_id: str) -> dict[str, bool]:
    ok = await persons_repo.delete_face_photo(face_photo_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"face photo {face_photo_id!r} not found")
    return {"deleted": True}
