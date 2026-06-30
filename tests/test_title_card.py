"""Tests for the opt-in AI title/splash card (S-2.11.5) — fail-soft compositing."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from impact_crater.pipeline import stage6_title_card as tc
from impact_crater.pipeline.stage1_ingest import MediaRecord


class _OkRouter:
    async def generate_title_background(self, *, spirit_prompt: str, aspect: str = "16:9") -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (1280, 720), (40, 80, 120)).save(buf, format="PNG")
        return buf.getvalue()


class _FailRouter:
    async def generate_title_background(self, *, spirit_prompt: str, aspect: str = "16:9") -> bytes:
        raise RuntimeError("image-gen unavailable")


class _Plan:
    clips: list = []


def _photo(tmp: Path, ch: str = "p0") -> MediaRecord:
    p = tmp / f"{ch}.jpg"
    Image.new("RGB", (1920, 1080), (200, 150, 100)).save(p, quality=90)
    return MediaRecord(
        content_hash=ch, source_path=str(p), media_type="photo", file_size=1,
        quick_stats={"width": 1920, "height": 1080}, capture_timestamp="2026-04-05T10:00:00",
    )


async def test_title_card_with_ai_background(tmp_path: Path) -> None:
    clip = await tc.build_title_clip(
        router=_OkRouter(), plan=_Plan(), media=[_photo(tmp_path)], cast=None,
        brief="A highlight video of our Zion trip", title_text=None, snapshot_dir=tmp_path,
    )
    assert clip is not None
    assert clip.kind == "title_card" and clip.candidate_ref == "__title__"
    assert Image.open(clip.source_path).size == (1920, 1080)
    assert 2500 <= clip.intended_duration_ms <= 3500


async def test_title_card_falls_back_to_photo_when_image_gen_fails(tmp_path: Path) -> None:
    clip = await tc.build_title_clip(
        router=_FailRouter(), plan=_Plan(), media=[_photo(tmp_path)], cast=None,
        brief="Zion trip", title_text="My Trip", snapshot_dir=tmp_path,
    )
    assert clip is not None and clip.kind == "title_card"  # typographic fallback over a photo
    assert Path(clip.source_path).is_file()


async def test_title_card_none_when_no_background_available(tmp_path: Path) -> None:
    clip = await tc.build_title_clip(
        router=_FailRouter(), plan=_Plan(), media=[], cast=None,
        brief="x", title_text=None, snapshot_dir=tmp_path,
    )
    assert clip is None


class _Person:
    def __init__(self, content_hashes: list[str]) -> None:
        self.content_hashes = content_hashes
        self.is_group = True


class _Cast:
    def __init__(self, group: list) -> None:
        self.group = group


async def test_title_card_composites_group_faces(tmp_path: Path, monkeypatch) -> None:
    # A populated cast whose group member appears in one photo; face detection
    # is monkeypatched so we exercise the composite path without a real face.
    photo = _photo(tmp_path, "g0")
    face_buf = io.BytesIO()
    Image.new("RGB", (120, 120), (10, 220, 10)).save(face_buf, format="JPEG")
    monkeypatch.setattr(
        tc.cast_mod, "detect_and_crop_faces",
        lambda data: [(face_buf.getvalue(), (0.4, 0.4, 0.2, 0.2))],
    )
    cast = _Cast(group=[_Person([photo.content_hash])])

    faces = tc._collect_faces(cast, {photo.content_hash: photo})
    assert len(faces) == 1  # the group member's face was collected

    # _paste_faces must actually alter the canvas in the face row region.
    canvas = Image.new("RGB", (tc._W, tc._H), (0, 0, 0))
    before = canvas.getpixel((tc._W // 2, tc._H - tc._FACE_PX - 150 + tc._FACE_PX // 2))
    tc._paste_faces(canvas, faces)
    after = canvas.getpixel((tc._W // 2, tc._H - tc._FACE_PX - 150 + tc._FACE_PX // 2))
    assert before != after  # a face ring was composited onto the canvas


def test_long_title_is_shrunk_to_fit_frame() -> None:
    from PIL import ImageDraw

    canvas = Image.new("RGB", (tc._W, tc._H), (0, 0, 0))
    d = ImageDraw.Draw(canvas)
    long_title = "Early-April Through Zion Bryce Horseshow Grand Canyon Las Vegas"
    font = tc._fit_font(d, long_title, 96, tc._SAFE_W)
    width = d.textbbox((0, 0), long_title, font=font)[2]
    assert width <= tc._SAFE_W  # never runs past the safe margin


def test_derive_year_modal() -> None:
    media = [
        MediaRecord(content_hash="a", source_path="a", media_type="photo", file_size=1,
                    quick_stats={}, capture_timestamp="2026-04-05T10:00:00"),
        MediaRecord(content_hash="b", source_path="b", media_type="photo", file_size=1,
                    quick_stats={}, capture_timestamp="2026-04-06T10:00:00"),
        MediaRecord(content_hash="c", source_path="c", media_type="photo", file_size=1,
                    quick_stats={}, capture_timestamp=None),
    ]
    assert tc._derive_year(media) == "2026"
    assert tc._derive_year([]) == ""
