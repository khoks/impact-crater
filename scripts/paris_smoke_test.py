"""Real-world Paris smoke test — downloads ~10 CC-licensed Wikimedia
Commons photos of Paris, generates a short audio clip, runs the full
M1+M2 pipeline against real Anthropic + Google APIs and real ffmpeg.

Uses a fresh temp IMPACT_CRATER_HOME so it doesn't touch the user's
real install. API keys come from system env vars.
"""

from __future__ import annotations

import asyncio
import math
import os
import struct
import sys
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

# Set up isolated home BEFORE any impact_crater import.
TEMP_ROOT = Path(tempfile.mkdtemp(prefix="ic-paris-"))
os.environ["IMPACT_CRATER_HOME"] = str(TEMP_ROOT)

# Paris photos from Wikimedia Commons. Using `Special:FilePath`, which
# 302-redirects to the current canonical thumb URL and is robust to file
# renames. All sourced files are public-domain or Creative Commons.
def fetch_paris_image_urls(max_count: int = 12, width: int = 800) -> list[str]:
    """Pull the Paris article's media-list from Wikipedia REST API and
    return current thumb URLs. Robust to file renames because we ask
    Wikipedia for the live list every run.
    """
    import json as _json

    api = "https://en.wikipedia.org/api/rest_v1/page/media-list/Paris"
    headers = {"User-Agent": "ImpactCraterSmokeTest/0.1"}
    req = urllib.request.Request(api, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = _json.loads(resp.read().decode("utf-8"))

    out: list[str] = []
    for item in data.get("items", []):
        if item.get("type") != "image":
            continue
        srcset = item.get("srcset") or []
        # Pick the largest src that's still ≤ requested width × 2.
        chosen: str | None = None
        for entry in srcset:
            src = entry.get("src", "")
            if src.startswith("//"):
                src = "https:" + src
            if src:
                chosen = src
                # Prefer a larger thumb if available.
                if f"/{width}px-" in src or f"/{width * 2}px-" in src:
                    break
        if chosen:
            out.append(chosen)
        if len(out) >= max_count:
            break
    return out


PHOTO_URLS: list[str] = []  # populated at run time


def download_photos(dest: Path, urls: list[str]) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    headers = {
        "User-Agent": "ImpactCraterSmokeTest/0.1 (https://github.com/khoks/impact-crater)"
    }
    for i, url in enumerate(urls):
        name = f"paris-{i:02d}.jpg"
        path = dest / name
        if path.is_file():
            out.append(path)
            continue
        try:
            print(f"  fetching {url[:90]}...")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                blob = resp.read()
            # Skip non-JPEGs (the Paris media-list includes SVGs etc).
            if not blob.startswith(b"\xff\xd8"):
                print(f"    skipped (not JPEG)")
                continue
            path.write_bytes(blob)
            out.append(path)
        except Exception as exc:
            print(f"    skipped ({exc})")
    return out


def write_audio(path: Path, *, duration_ms: int = 14_000, bpm: float = 96.0) -> None:
    """Simple click track at `bpm` so the music_video path has real beats."""
    sr = 22050
    n = int(sr * duration_ms / 1000)
    y = bytearray()
    beat_period = 60.0 / bpm
    next_beat = 0.0
    click_len = int(sr * 0.04)
    for i in range(n):
        t = i / sr
        sample = 0
        if t >= next_beat and i + click_len < n:
            # Decaying sine click on the beat.
            tt = (i - int(next_beat * sr)) / sr
            sample = int(0.4 * 32767 * math.sin(2 * math.pi * 880 * tt) * math.exp(-tt * 60))
            if i - int(next_beat * sr) >= click_len:
                next_beat += beat_period
        y.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(y))


async def main() -> int:
    print(f"Temp home: {TEMP_ROOT}")
    print(f"Anthropic key: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'MISSING'}")
    print(f"Google key:    {'set' if os.environ.get('GOOGLE_API_KEY') else 'MISSING'}")

    print("\n[1/4] Querying Wikipedia for Paris article media list...")
    urls = fetch_paris_image_urls(max_count=14, width=800)
    print(f"  -> {len(urls)} candidate image URLs")

    print("\n[1.5/4] Downloading photos...")
    photo_dir = TEMP_ROOT / "photos"
    photos = download_photos(photo_dir, urls)
    if len(photos) < 4:
        print(f"  ERROR: only got {len(photos)} photos; need at least 4")
        return 1
    total_size = sum(p.stat().st_size for p in photos)
    print(f"  downloaded {len(photos)} photos, total {total_size/1024:.0f} KB")

    print("\n[2/4] Generating click-track audio (96 BPM, 14s)...")
    audio_path = TEMP_ROOT / "song.wav"
    write_audio(audio_path, duration_ms=14_000, bpm=96)
    print(f"  wrote {audio_path.stat().st_size/1024:.0f} KB")

    print("\n[3/4] Setting spend cap + running pipeline...")
    from impact_crater.pipeline.runner import (
        FullJobConfig,
        build_router_from_settings,
        run_full_pipeline,
    )
    from impact_crater.storage import settings as ss
    from impact_crater.storage.migrations import run_pending_migrations

    await run_pending_migrations()
    await ss.set_value(ss.KEY_TOTAL_CAP_USD, "20.00")

    router = await build_router_from_settings()
    config = FullJobConfig(
        media_paths=photos,
        brief=(
            "A short cinematic walking tour of Paris highlights. Open with a "
            "wide iconic landmark to set the scene; build through bridge, "
            "garden, and street-level shots; close with a quiet evening view "
            "of the Eiffel Tower over the Seine."
        ),
        target_duration_seconds=12,
        audio_path=audio_path,
        mode="standard",
    )

    print("  -> kicking off run_full_pipeline (Stages 1-7)")
    started = time.time()
    result = await run_full_pipeline(config, router=router)
    elapsed = time.time() - started

    print(f"\n[4/4] DONE in {elapsed:.1f}s")
    print(f"  project_id      : {result.project_id}")
    print(f"  snapshot_id     : {result.snapshot_id}")
    print(f"  render_path     : {result.render_path}")
    print(f"  output_bytes    : {result.output_bytes:,}")
    print(f"  media_count     : {result.media_count}")
    print(f"  cost_summary    : {result.cost_summary_path}")
    if result.arc_judgment:
        arc = result.arc_judgment
        print(f"  arc confidence  : {arc.confidence:.2f}")
        print(f"  selected items  : {len(arc.selected_items)}")
        print(f"  arc reasoning   : {arc.arc_reasoning[:200]}...")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
