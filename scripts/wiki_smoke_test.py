"""Real-world smoke test — downloads CC-licensed Wikimedia Commons
photos for a chosen Wikipedia topic, generates a click-track audio
clip, and runs the full M1+M2 pipeline against real Anthropic + Google
APIs and real ffmpeg.

Uses a fresh temp IMPACT_CRATER_HOME so it doesn't touch the user's
real install. API keys come from system env vars.

Configure via env vars:
  SMOKE_TOPIC      Wikipedia article title (default "Paris")
  SMOKE_BRIEF      User brief for the curator (default = generic city tour)
  SMOKE_PHOTO_MAX  Max photos to keep (default 50)
  SMOKE_DURATION   Target video duration seconds (default 18)
  SMOKE_BPM        Click track BPM (default 96)

Examples:
  SMOKE_TOPIC="Times Square" SMOKE_BRIEF="strolling in Times Square"
  SMOKE_TOPIC="Tokyo"        SMOKE_BRIEF="quiet morning walk in Tokyo"
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import struct
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import wave
from pathlib import Path

# Set up isolated home BEFORE any impact_crater import.
_TOPIC = os.environ.get("SMOKE_TOPIC", "Paris")
_topic_slug = re.sub(r"[^a-z0-9]+", "-", _TOPIC.lower()).strip("-")
TEMP_ROOT = Path(tempfile.mkdtemp(prefix=f"ic-{_topic_slug}-"))
os.environ["IMPACT_CRATER_HOME"] = str(TEMP_ROOT)


def fetch_image_urls(topic: str, *, max_count: int, width: int = 800) -> list[str]:
    """Pull a Wikipedia article's media-list (REST API) and return the
    current canonical thumb URLs. Robust to file renames because we
    re-query every run.

    Falls back to the Commons categorymembers API when the article has
    too few images for the requested max_count — useful for topics
    like "Times Square" where the article carries fewer images than a
    50-photo smoke test wants.
    """
    primary = _media_list(topic, width=width)
    if len(primary) >= max_count:
        return primary[:max_count]
    # Top up via Commons category search.
    extra = _commons_search(topic, max_count=max_count - len(primary), width=width)
    seen: set[str] = set()
    out: list[str] = []
    for url in primary + extra:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= max_count:
            break
    return out


def _media_list(article: str, *, width: int) -> list[str]:
    api = (
        "https://en.wikipedia.org/api/rest_v1/page/media-list/"
        + urllib.parse.quote(article)
    )
    headers = {"User-Agent": "ImpactCraterSmokeTest/0.1"}
    req = urllib.request.Request(api, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  media-list fetch failed: {exc}")
        return []

    out: list[str] = []
    for item in data.get("items", []):
        if item.get("type") != "image":
            continue
        chosen = _pick_thumb(item.get("srcset") or [], width)
        if chosen:
            out.append(chosen)
    return out


def _commons_search(topic: str, *, max_count: int, width: int) -> list[str]:
    """Fall back to Wikimedia Commons file search via MediaWiki API."""
    if max_count <= 0:
        return []
    api = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=6"
        f"&gsrsearch={urllib.parse.quote(topic + ' filemime:image/jpeg')}"
        f"&gsrlimit={max_count * 3}"  # over-fetch then filter
        "&prop=imageinfo&iiprop=url&iiurlwidth=" + str(width)
    )
    headers = {"User-Agent": "ImpactCraterSmokeTest/0.1"}
    req = urllib.request.Request(api, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  commons search failed: {exc}")
        return []

    out: list[str] = []
    pages = (data.get("query", {}) or {}).get("pages", {}) or {}
    for _, page in pages.items():
        ii = page.get("imageinfo") or []
        if not ii:
            continue
        thumb = ii[0].get("thumburl") or ii[0].get("url")
        if thumb and thumb.startswith("http"):
            out.append(thumb)
        if len(out) >= max_count:
            break
    return out


def _pick_thumb(srcset: list[dict], width: int) -> str | None:
    chosen: str | None = None
    for entry in srcset:
        src = entry.get("src", "")
        if src.startswith("//"):
            src = "https:" + src
        if src:
            chosen = src
            if f"/{width}px-" in src or f"/{width * 2}px-" in src:
                break
    return chosen


def download_photos(dest: Path, urls: list[str]) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    headers = {
        "User-Agent": "ImpactCraterSmokeTest/0.1 (https://github.com/khoks/impact-crater)"
    }
    # Wikipedia rate-limits hostile-looking traffic at ~50 req/sec; we
    # throttle to ~2 req/sec to stay polite. With backoff on 429.
    inter_delay_s = 0.4
    for i, url in enumerate(urls):
        name = f"img-{i:03d}.jpg"
        path = dest / name
        if path.is_file():
            out.append(path)
            continue
        backoff = inter_delay_s
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    blob = resp.read()
                if not blob.startswith(b"\xff\xd8"):
                    break  # skip non-JPEGs
                path.write_bytes(blob)
                out.append(path)
                if (i + 1) % 10 == 0:
                    print(f"    downloaded {i + 1}/{len(urls)}")
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 3:
                    sleep_s = backoff * (2 ** attempt)
                    print(f"    url[{i}] 429 → sleeping {sleep_s:.1f}s and retrying")
                    time.sleep(sleep_s)
                    continue
                print(f"    skipped url[{i}] ({exc})")
                break
            except Exception as exc:
                print(f"    skipped url[{i}] ({exc})")
                break
        time.sleep(inter_delay_s)
    return out


def write_audio(path: Path, *, duration_ms: int, bpm: float) -> None:
    """Simple click track at `bpm`."""
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
    topic = os.environ.get("SMOKE_TOPIC", "Paris")
    brief = os.environ.get(
        "SMOKE_BRIEF",
        f"A short cinematic tour of {topic}. Open with a wide establishing "
        "shot; build through varied views; close on a quiet, evocative beat.",
    )
    photo_max = int(os.environ.get("SMOKE_PHOTO_MAX", "50"))
    duration = int(os.environ.get("SMOKE_DURATION", "18"))
    bpm = float(os.environ.get("SMOKE_BPM", "96"))

    print(f"Temp home: {TEMP_ROOT}")
    print(f"Topic:     {topic}")
    print(f"Brief:     {brief}")
    print(f"Max photos: {photo_max}, target duration: {duration}s, BPM: {bpm}")
    print(f"Anthropic key: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'MISSING'}")
    print(f"Google key:    {'set' if os.environ.get('GOOGLE_API_KEY') else 'MISSING'}")

    print(f"\n[1/4] Pulling images for '{topic}' from Wikipedia + Commons...")
    urls = fetch_image_urls(topic, max_count=photo_max, width=800)
    print(f"  -> {len(urls)} candidate URLs")

    print("\n[1.5/4] Downloading...")
    photos = download_photos(TEMP_ROOT / "photos", urls)
    if len(photos) < 4:
        print(f"  ERROR: only got {len(photos)} photos; need at least 4")
        return 1
    total_kb = sum(p.stat().st_size for p in photos) / 1024
    print(f"  downloaded {len(photos)} photos, total {total_kb:.0f} KB")

    print(f"\n[2/4] Generating click-track audio ({bpm} BPM, {duration + 2}s)...")
    audio_path = TEMP_ROOT / "song.wav"
    write_audio(audio_path, duration_ms=(duration + 2) * 1000, bpm=bpm)
    print(f"  wrote {audio_path.stat().st_size / 1024:.0f} KB")

    print("\n[3/4] Setting spend cap + running pipeline...")
    from impact_crater.pipeline.runner import (
        FullJobConfig,
        build_router_from_settings,
        run_full_pipeline,
    )
    from impact_crater.storage import settings as ss
    from impact_crater.storage.migrations import run_pending_migrations

    await run_pending_migrations()
    await ss.set_value(ss.KEY_TOTAL_CAP_USD, "30.00")  # plenty for a 50-photo job

    router = await build_router_from_settings()
    config = FullJobConfig(
        media_paths=photos,
        brief=brief,
        target_duration_seconds=duration,
        audio_path=audio_path,
        mode="standard",
    )

    print("  -> run_full_pipeline (Stages 1-7)")
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
        print(f"  arc reasoning   : {arc.arc_reasoning[:300]}...")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
