"""Reference-collage builder per ADR-0010 § N-008.

Tiles labeled face crops into a single PNG. The collage is the input
the vision LLM consults at Stage 3 to identify which library people
appear in the analyzed photo.

Layout: one row per person, up to 5 face crops per row, person name
overlaid above. Crops are rendered at 256×256.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from impact_crater import paths
from impact_crater.storage.persons import FacePhoto, Person, list_face_photos, list_persons

CELL_PX = 256
LABEL_HEIGHT_PX = 32
ROW_HEIGHT_PX = CELL_PX + LABEL_HEIGHT_PX
MAX_CELLS_PER_ROW = 5


@dataclass(frozen=True)
class CollageResult:
    path: Path
    library_version_hash: str
    person_count: int
    face_count: int


async def build_reference_collage(
    *,
    media_resolver: "callable[[str], Path] | None" = None,
) -> CollageResult | None:
    """Build (or load cached) reference collage for the current library.

    Returns None when the library is empty.

    `media_resolver` maps a content_hash → Path to the source media on
    disk. The runner provides this; tests pass a stub.
    """
    persons = await list_persons()
    if not persons:
        return None

    # Group: one (person, face_photos) per person.
    pairs: list[tuple[Person, list[FacePhoto]]] = []
    for p in persons:
        photos = await list_face_photos(p.id)
        if photos:
            pairs.append((p, photos[:MAX_CELLS_PER_ROW]))
    if not pairs:
        return None

    library_hash = _library_version_hash(pairs)
    cache_dir = paths.cache_dir() / "face-library"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{library_hash}.png"
    if out_path.is_file():
        return CollageResult(
            path=out_path,
            library_version_hash=library_hash,
            person_count=len(pairs),
            face_count=sum(len(faces) for _, faces in pairs),
        )

    if media_resolver is None:
        raise ValueError(
            "build_reference_collage needs a media_resolver callable to "
            "translate content_hash → on-disk path"
        )

    canvas_w = CELL_PX * MAX_CELLS_PER_ROW
    canvas_h = ROW_HEIGHT_PX * len(pairs)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("arial.ttf", size=20)
    except OSError:
        font = ImageFont.load_default()

    for row_idx, (person, faces) in enumerate(pairs):
        # Label band.
        y_label = row_idx * ROW_HEIGHT_PX
        draw.rectangle(
            (0, y_label, canvas_w, y_label + LABEL_HEIGHT_PX),
            fill=(20, 24, 32),
        )
        draw.text(
            (8, y_label + 6),
            person.display_name,
            fill=(255, 255, 255),
            font=font,
        )
        # Face cells.
        y_face = y_label + LABEL_HEIGHT_PX
        for col_idx, face in enumerate(faces[:MAX_CELLS_PER_ROW]):
            x = col_idx * CELL_PX
            face_img = _crop_face(face, media_resolver)
            face_img = face_img.resize((CELL_PX, CELL_PX), Image.Resampling.LANCZOS)
            canvas.paste(face_img, (x, y_face))

    canvas.save(out_path, format="PNG")
    return CollageResult(
        path=out_path,
        library_version_hash=library_hash,
        person_count=len(pairs),
        face_count=sum(len(faces) for _, faces in pairs),
    )


# ---- Helpers ----


def _library_version_hash(pairs: list[tuple[Person, list[FacePhoto]]]) -> str:
    """sha256(sorted person_ids + photo_hashes) per ADR-0010 § N-008."""
    items = []
    for person, faces in sorted(pairs, key=lambda p: p[0].id):
        items.append(person.id)
        items.extend(sorted(f.id for f in faces))
    return hashlib.sha256("|".join(items).encode("utf-8")).hexdigest()[:32]


def _crop_face(face: FacePhoto, media_resolver: "callable[[str], Path]") -> Image.Image:
    src_path = media_resolver(face.content_hash)
    img = Image.open(src_path).convert("RGB")
    w, h = img.size
    # bbox is normalized 0..1
    x, y, bw, bh = face.face_crop_bbox
    px, py = int(x * w), int(y * h)
    pw, ph = int(bw * w), int(bh * h)
    # Clamp + ensure positive area.
    px = max(0, min(px, w - 1))
    py = max(0, min(py, h - 1))
    pw = max(1, min(pw, w - px))
    ph = max(1, min(ph, h - py))
    return img.crop((px, py, px + pw, py + ph))
