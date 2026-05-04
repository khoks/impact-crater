"""Tests for the ffmpeg/ffprobe path resolver + audio probe."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from impact_crater.media import ffmpeg as ff


@pytest.fixture
def reset_resolver_cache() -> None:
    ff.clear_path_cache()
    yield
    ff.clear_path_cache()


def test_env_override_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reset_resolver_cache: None,
) -> None:
    fake = tmp_path / "fake-ffmpeg.exe"
    fake.write_bytes(b"\x00")
    monkeypatch.setenv("IMPACT_CRATER_FFMPEG", str(fake))
    assert ff.ffmpeg_path() == str(fake)


def test_env_override_pointing_at_missing_file_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reset_resolver_cache: None,
) -> None:
    monkeypatch.setenv("IMPACT_CRATER_FFMPEG", str(tmp_path / "nope.exe"))
    with pytest.raises(ff.FFmpegNotFound, match="not a file"):
        ff.ffmpeg_path()


def test_no_binary_anywhere_raises(
    monkeypatch: pytest.MonkeyPatch,
    reset_resolver_cache: None,
) -> None:
    monkeypatch.delenv("IMPACT_CRATER_FFMPEG", raising=False)
    monkeypatch.delenv("IMPACT_CRATER_FFPROBE", raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    with pytest.raises(ff.FFmpegNotFound):
        ff.ffmpeg_path()


def test_has_ffmpeg_returns_false_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    reset_resolver_cache: None,
) -> None:
    monkeypatch.delenv("IMPACT_CRATER_FFMPEG", raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert ff.has_ffmpeg() is False


@pytest.mark.skipif(not ff.has_ffmpeg(), reason="ffmpeg binary not installed")
def test_path_lookup_finds_real_binary(reset_resolver_cache: None) -> None:
    """When ffmpeg is on PATH (or winget-installed on Windows), we resolve it."""
    p = ff.ffmpeg_path()
    assert Path(p).is_file()
    # Sanity-check: running it with -version returns 0.
    cp = ff.run_ffmpeg(["-version"], timeout_s=10.0)
    assert cp.returncode == 0
    assert b"ffmpeg version" in cp.stdout


def _write_synthetic_wav(path: Path, *, duration_ms: int = 500, sample_rate: int = 8000) -> None:
    """Write a 1-channel 16-bit WAV of `duration_ms` ms of silence."""
    n_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<%dh" % n_samples, *([0] * n_samples)))


@pytest.mark.skipif(not ff.has_ffmpeg(), reason="ffmpeg binary not installed")
def test_probe_audio_returns_expected_metadata(
    tmp_path: Path,
    reset_resolver_cache: None,
) -> None:
    wav = tmp_path / "tone.wav"
    _write_synthetic_wav(wav, duration_ms=500, sample_rate=8000)
    probe = ff.probe_audio(wav)
    assert probe.path == str(wav)
    assert 400 <= probe.duration_ms <= 600  # ±100ms tolerance
    assert probe.sample_rate == 8000
    assert probe.channels == 1
    assert probe.codec.startswith("pcm")


def test_probe_audio_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ff.probe_audio(tmp_path / "nope.wav")
