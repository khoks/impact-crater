"""ffmpeg / ffprobe path resolver + invocation helper per ADR-0010 + ADR-0012.

Resolution order:
  1. `IMPACT_CRATER_FFMPEG` / `IMPACT_CRATER_FFPROBE` env var override
  2. `shutil.which` (PATH lookup)
  3. Standard winget install path on Windows
     (`%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_*\\ffmpeg-*-full_build\\bin\\`)

Subprocess execution lives here so render-stage code never shells out
directly. The worker pool's `register_subprocess` lets `cancel()`
SIGTERM in-flight ffmpeg children with a grace period before SIGKILL.

Audio probe (`probe_audio`) is the only ffprobe consumer at M2; the
M4 music-analysis pipeline will use Madmom + librosa instead and only
fall back to ffprobe for ingest-time metadata.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)


class FFmpegNotFound(RuntimeError):
    """Raised when no ffmpeg / ffprobe binary can be located."""


@dataclass(frozen=True)
class AudioProbe:
    """Subset of ffprobe's audio metadata that the render path uses."""

    path: str
    duration_ms: int
    sample_rate: int
    channels: int
    codec: str
    bit_rate: int | None = None


# ---- Public API --------------------------------------------------------


@lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    """Return an absolute path to the ffmpeg binary or raise."""
    return _resolve_binary(
        env_key="IMPACT_CRATER_FFMPEG",
        binary_name="ffmpeg",
    )


@lru_cache(maxsize=1)
def ffprobe_path() -> str:
    """Return an absolute path to the ffprobe binary or raise."""
    return _resolve_binary(
        env_key="IMPACT_CRATER_FFPROBE",
        binary_name="ffprobe",
    )


def has_ffmpeg() -> bool:
    """Best-effort check used by tests to skip when ffmpeg is unavailable."""
    try:
        ffmpeg_path()
        return True
    except FFmpegNotFound:
        return False


def clear_path_cache() -> None:
    """Reset the lru_cache. Tests use this after monkey-patching env vars."""
    ffmpeg_path.cache_clear()
    ffprobe_path.cache_clear()


def run_ffmpeg(
    args: list[str],
    *,
    capture_output: bool = True,
    check: bool = True,
    timeout_s: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run ffmpeg with `args` (the binary name itself is prepended).

    Synchronous; intended for short-lived helper invocations (e.g. probe).
    The render path uses `run_ffmpeg_async` so the worker pool can register
    the subprocess for cancellation.
    """
    cmd = [ffmpeg_path(), *args]
    log.debug("ffmpeg cmd: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        check=check,
        timeout=timeout_s,
    )


def run_ffprobe(
    args: list[str],
    *,
    timeout_s: float | None = 30.0,
) -> subprocess.CompletedProcess[bytes]:
    cmd = [ffprobe_path(), *args]
    log.debug("ffprobe cmd: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        check=True,
        timeout=timeout_s,
    )


async def run_ffmpeg_async(
    args: list[str],
    *,
    on_subprocess_started: "callable[[asyncio.subprocess.Process], None] | None" = None,
    timeout_s: float | None = None,
) -> tuple[int, bytes, bytes]:
    """Run ffmpeg as an asyncio subprocess.

    `on_subprocess_started` is called with the live `Process` so callers can
    register it with the worker pool for cancellation.

    Returns (returncode, stdout, stderr).
    """
    cmd = [ffmpeg_path(), *args]
    log.debug("ffmpeg async cmd: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if on_subprocess_started is not None:
        on_subprocess_started(proc)
    try:
        if timeout_s is None:
            stdout, stderr = await proc.communicate()
        else:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            proc.kill()
        raise
    return (proc.returncode or 0, stdout, stderr)


def probe_audio(path: Path | str) -> AudioProbe:
    """Probe an audio file and return duration / sample-rate / channels / codec."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"audio path missing: {path}")
    cp = run_ffprobe(
        [
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-print_format",
            "json",
            str(path),
        ]
    )
    payload = json.loads(cp.stdout.decode("utf-8", errors="replace"))
    audio_stream = next(
        (s for s in payload.get("streams", []) if s.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise ValueError(f"no audio stream in {path}")
    fmt = payload.get("format", {})
    duration_s = float(fmt.get("duration") or audio_stream.get("duration") or 0.0)
    return AudioProbe(
        path=str(path),
        duration_ms=int(duration_s * 1000),
        sample_rate=int(audio_stream.get("sample_rate") or 0),
        channels=int(audio_stream.get("channels") or 0),
        codec=str(audio_stream.get("codec_name") or "unknown"),
        bit_rate=int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
    )


# ---- Internal ---------------------------------------------------------


def _resolve_binary(*, env_key: str, binary_name: str) -> str:
    override = os.environ.get(env_key)
    if override:
        p = Path(override).expanduser()
        if p.is_file():
            return str(p)
        raise FFmpegNotFound(
            f"{env_key} points at {override!r} which is not a file"
        )

    on_path = shutil.which(binary_name)
    if on_path:
        return on_path

    if sys.platform == "win32":
        winget_hit = _scan_winget_ffmpeg(binary_name)
        if winget_hit is not None:
            return winget_hit

    raise FFmpegNotFound(
        f"could not locate {binary_name!r} — set {env_key} or install ffmpeg "
        f"(Windows: `winget install Gyan.FFmpeg`)"
    )


def _scan_winget_ffmpeg(binary_name: str) -> str | None:
    """Look for the winget-installed `Gyan.FFmpeg` package on Windows.

    Pattern: `%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_*\\ffmpeg-*-full_build\\bin\\<binary>.exe`
    """
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    root = Path(base) / "Microsoft" / "WinGet" / "Packages"
    if not root.is_dir():
        return None
    suffix = ".exe"
    for pkg_dir in root.glob("Gyan.FFmpeg_*"):
        for build_dir in pkg_dir.glob("ffmpeg-*-full_build"):
            candidate = build_dir / "bin" / f"{binary_name}{suffix}"
            if candidate.is_file():
                return str(candidate)
    return None
