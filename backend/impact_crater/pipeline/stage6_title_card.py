"""Stage 6.x — opt-in AI title/splash card (S-2.11.5).

Generates an AI background image (remote image-gen, per D-054), composites the
trip's main people (from the A-018 cast) + a title + the year onto it, and
returns a `title_card` RenderClip to prepend to the timeline.

Fully fail-soft: if image-gen fails it falls back to a typographic title over a
representative photo; if even that is unavailable it returns None and the render
proceeds with no card. Faces are composited LOCALLY — only the text spirit
prompt is ever sent to the image API, never the photos.
"""

from __future__ import annotations

import collections
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from impact_crater.media import cast as cast_mod
from impact_crater.pipeline.stage6_plan import RenderClip, TitleCardSpec

log = logging.getLogger(__name__)

_W, _H = 1920, 1080


_TITLE_MS = 3000
_MAX_FACES = 4
_FACE_PX = 200
_SAFE_W = int(_W * 0.88)  # keep title inside ~12% side margins

_FILLER = {"a", "an", "the", "our", "my", "of", "video", "highlight", "reel", "trip", "this"}


async def build_title_clip(
    *,
    router: Any,
    plan: Any,
    media: list[Any],
    cast: Any,
    brief: str,
    spec: TitleCardSpec,
    snapshot_dir: Path,
    background_path: str | None = None,
) -> RenderClip | None:
    """Build a `title_card` RenderClip from a `TitleCardSpec`, or None.

    `background_path` (S-2.12.4): when given, reuse that raw AI background instead
    of generating a new one — so a refinement that only changes the text or
    placement doesn't pay for a fresh image. The raw background is always
    persisted to `title_card_bg.png` so the next refine can reuse it.
    """
    try:
        media_by_hash = {m.content_hash: m for m in media}
        year = _derive_year(media)
        title = (spec.title_text or "").strip() or await _title_from_brief(router, brief, year) or "Our Trip"

        bg = _open_path(background_path) if background_path else None
        if bg is None:
            spirit = spec.spirit_prompt or _spirit_prompt(brief, year, style=spec.style)
            try:
                raw = await router.generate_title_background(spirit_prompt=spirit)
                bg = Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception as exc:
                log.warning("title_card_image_gen_failed (fallback to photo): %r", str(exc)[:200])
        if bg is None:
            bg = _fallback_background(plan, media_by_hash)
        if bg is None:
            log.warning("title_card_no_background; skipping card")
            return None

        out_dir = Path(snapshot_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Persist the raw background so a later text/placement refine can reuse it.
        _cover(bg, _W, _H).save(out_dir / "title_card_bg.png", format="PNG")

        canvas = _cover(bg, _W, _H)
        _add_scrim(canvas)
        if spec.show_faces:
            _paste_faces(canvas, _collect_faces(cast, media_by_hash))
        _draw_title(canvas, title, year if spec.show_year else "", spec)

        out = out_dir / "title_card.png"
        canvas.save(out, format="PNG")
        return RenderClip(
            candidate_ref="__title__",
            kind="title_card",
            source_path=str(out),
            intended_duration_ms=_TITLE_MS,
            aspect_ratio_action="as_is",
            role="title",
            notes="auto title card",
        )
    except Exception as exc:  # never block the render
        log.warning("title_card_failed (proceeding without): %r", str(exc)[:200])
        return None


# ---- Derivations -------------------------------------------------------


def _derive_year(media: list[Any]) -> str:
    years: list[int] = []
    for m in media:
        ts = getattr(m, "capture_timestamp", None)
        if ts:
            try:
                years.append(datetime.fromisoformat(ts).year)
            except (TypeError, ValueError):
                pass
    if not years:
        return ""
    return str(collections.Counter(years).most_common(1)[0][0])


async def _title_from_brief(router: Any, brief: str, year: str) -> str | None:
    """Prefer a clean, LLM-written 2-5 word title; fall back to the heuristic.

    Fail-soft: any router error (missing op, quota-denied, non-JSON) drops to
    the deterministic heuristic so the card is never blocked."""
    llm_title: str | None = None
    try:
        llm_title = await router.generate_title_text(brief=brief, year=year)
    except Exception as exc:
        log.warning("title_text_gen_failed (fallback to heuristic): %r", str(exc)[:200])
    return _clean_title(llm_title) or _derive_title(brief)


def _clean_title(title: str | None) -> str | None:
    """Sanitize an LLM title: strip wrapping quotes + edge punctuation. None if empty."""
    if not title:
        return None
    cleaned = " ".join(title.split()).strip().strip("\"'").strip(" .,;:—-")
    return cleaned or None


def _derive_title(brief: str) -> str | None:
    """A short title from the brief's first clause, minus filler words."""
    if not brief:
        return None
    clause = brief.strip().split(".")[0]
    words = [w for w in clause.replace(",", " ").split() if w.strip(".,").lower() not in _FILLER]
    if not words:
        return None
    return " ".join(words[:5]).strip(" .,").title() or None


def _spirit_prompt(brief: str, year: str, *, style: str | None = None) -> str:
    base = (brief or "a travel highlight video").strip()[:240]
    parts = [base]
    if style:
        parts.append(f"visual style: {style.strip()[:120]}")
    body = "; ".join(parts)
    return f"{body}{(' (' + year + ')') if year else ''}"


# ---- Background --------------------------------------------------------


def _fallback_background(plan: Any, media_by_hash: dict[str, Any]) -> Image.Image | None:
    """A representative photo for the typographic fallback card."""
    for c in getattr(plan, "clips", []) or []:
        if getattr(c, "kind", None) in ("photo", "burst_montage"):
            img = _open_path(getattr(c, "source_path", None))
            if img is not None:
                return img
    for m in media_by_hash.values():
        img = _open_path(getattr(m, "thumb_1024_path", None) or getattr(m, "source_path", None))
        if img is not None:
            return img
    return None


def _open_path(path: str | None) -> Image.Image | None:
    if not path:
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+center-crop so img fills w×h."""
    scale = max(w / img.width, h / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))))
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _add_scrim(canvas: Image.Image) -> None:
    """Darken the whole image a touch + a stronger bottom gradient for text."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, 0, _W, _H], fill=(0, 0, 0, 70))
    for i in range(_H // 2, _H):
        a = int(160 * (i - _H / 2) / (_H / 2))
        d.line([(0, i), (_W, i)], fill=(0, 0, 0, a))
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), (0, 0))


# ---- Faces -------------------------------------------------------------


def _collect_faces(cast: Any, media_by_hash: dict[str, Any]) -> list[Image.Image]:
    out: list[Image.Image] = []
    group = getattr(cast, "group", None) if cast is not None else None
    if not group:
        return out
    for person in group[:_MAX_FACES]:
        for ch in getattr(person, "content_hashes", []) or []:
            rec = media_by_hash.get(ch)
            if rec is None:
                continue
            data = _read_bytes(getattr(rec, "thumb_1024_path", None) or getattr(rec, "source_path", None))
            if data is None:
                continue
            try:
                crops = cast_mod.detect_and_crop_faces(data)
            except Exception:
                crops = []
            if crops:
                crop_bytes = max(crops, key=lambda cb: cb[1][2] * cb[1][3])[0]  # largest bbox
                face = _open_bytes(crop_bytes)
                if face is not None:
                    out.append(face)
                    break  # one face per person
    return out


def _paste_faces(canvas: Image.Image, faces: list[Image.Image]) -> None:
    if not faces:
        return
    n = len(faces)
    gap = 28
    total_w = n * _FACE_PX + (n - 1) * gap
    x = (_W - total_w) // 2
    y = _H - _FACE_PX - 150
    mask = Image.new("L", (_FACE_PX, _FACE_PX), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, _FACE_PX, _FACE_PX], fill=255)
    for face in faces:
        thumb = _cover(face, _FACE_PX, _FACE_PX)
        ring = Image.new("RGBA", (_FACE_PX, _FACE_PX), (0, 0, 0, 0))
        ring.paste(thumb, (0, 0), mask)
        ImageDraw.Draw(ring).ellipse([2, 2, _FACE_PX - 2, _FACE_PX - 2], outline=(255, 255, 255, 230), width=5)
        canvas.paste(ring.convert("RGB"), (x, y), ring)
        x += _FACE_PX + gap


# ---- Text --------------------------------------------------------------


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


_NAMED_COLORS = {
    "white": (255, 255, 255), "black": (0, 0, 0), "gold": (255, 215, 0),
    "cream": (250, 240, 220), "red": (220, 60, 60), "blue": (70, 130, 220),
    "green": (70, 190, 120), "amber": (255, 190, 90),
}


def _parse_color(name: str) -> tuple[int, int, int]:
    c = (name or "white").strip().lower()
    if c.startswith("#") and len(c) == 7:
        try:
            return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        except ValueError:
            pass
    return _NAMED_COLORS.get(c, (255, 255, 255))


def _placement_cy(position: str) -> int:
    return {
        "top": int(_H * 0.08),
        "upper-third": int(_H * 0.22),
        "center": _H // 2 - 60,
        "lower-third": _H - _FACE_PX - 150 - 120,  # default: above the face row
        "bottom": int(_H * 0.80),
    }.get(position, _H - _FACE_PX - 150 - 120)


def _draw_title(canvas: Image.Image, title: str, year: str, spec: TitleCardSpec) -> None:
    d = ImageDraw.Draw(canvas)
    scale = max(0.5, min(2.0, spec.text_size_scale))
    title_font = _fit_font(d, title, int(96 * scale), _SAFE_W)
    year_font = _font(int(44 * scale))
    color = _parse_color(spec.text_color)
    cy = _placement_cy(spec.title_position)
    _centered(d, title, title_font, cy, fill=color)
    if year:
        _centered(d, year, year_font, cy + int(110 * scale), fill=color)


def _fit_font(
    d: ImageDraw.ImageDraw, text: str, start_size: int, max_width: int, min_size: int = 40
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Largest font (≤ start_size) whose rendered text fits within max_width."""
    size = start_size
    while size > min_size:
        font = _font(size)
        try:
            bbox = d.textbbox((0, 0), text, font=font)
        except Exception:
            return font
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size -= 4
    return _font(min_size)


def _centered(d: ImageDraw.ImageDraw, text: str, font: Any, y: int, *, fill: tuple) -> None:
    try:
        bbox = d.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
    except Exception:
        w = len(text) * 20
    d.text(((_W - w) // 2, y), text, font=font, fill=fill,
           stroke_width=3, stroke_fill=(0, 0, 0))


# ---- IO helpers --------------------------------------------------------


def _read_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    try:
        return Path(path).read_bytes()
    except Exception:
        return None


def _open_bytes(data: bytes) -> Image.Image | None:
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
