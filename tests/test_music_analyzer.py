"""Tests for the librosa-only MusicAnalyzer + CutGrid generator."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from impact_crater.media.music import (
    CutGrid,
    LibrosaMusicAnalyzer,
    MusicAnalysis,
    Section,
    generate_cut_grid,
)


def _write_click_wav(path: Path, *, duration_ms: int, bpm: float, sr: int = 22050) -> None:
    """Write a WAV with a short click at every beat — librosa picks this up cleanly.

    Faster than a full multi-tone song; lets the test run in <2s.
    """
    n = int(sr * duration_ms / 1000)
    y = np.zeros(n, dtype=np.float32)
    beat_period_s = 60.0 / bpm
    click_len = int(sr * 0.02)  # 20ms click
    t = 0.0
    while t < duration_ms / 1000.0:
        i = int(t * sr)
        if i + click_len <= n:
            # Decaying-sine click — librosa's onset detector picks it up.
            tt = np.arange(click_len) / sr
            y[i : i + click_len] += (
                0.5 * np.sin(2 * np.pi * 1000 * tt) * np.exp(-tt * 80)
            ).astype(np.float32)
        t += beat_period_s
    samples = (y * 32767).clip(-32767, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(samples.tobytes())


# ---- analyze() tests --------------------------------------------------


async def test_analyze_returns_music_analysis_for_120bpm_track(tmp_path: Path) -> None:
    p = tmp_path / "120.wav"
    _write_click_wav(p, duration_ms=8000, bpm=120)
    out = await LibrosaMusicAnalyzer().analyze(p)
    assert isinstance(out, MusicAnalysis)
    assert out.analyzer == "librosa-only"
    assert 7800 <= out.duration_ms <= 8200
    # 120 BPM ± 8 — beat tracking is approximate on synthetic click tracks.
    assert 110 <= out.bpm <= 130
    # 8 seconds at 120 BPM = 16 beats; allow ±2 for endpoint detection.
    assert 14 <= len(out.beats_ms) <= 18


async def test_analyze_60bpm_track(tmp_path: Path) -> None:
    p = tmp_path / "60.wav"
    _write_click_wav(p, duration_ms=8000, bpm=60)
    out = await LibrosaMusicAnalyzer().analyze(p)
    # librosa often locks to a multiple of the true tempo on slow tracks
    # (60 BPM → 120 BPM is the canonical "octave error"). Accept either.
    assert 50 <= out.bpm <= 130
    assert len(out.beats_ms) >= 4


async def test_analyze_emits_sections_and_energy_curve(tmp_path: Path) -> None:
    p = tmp_path / "long.wav"
    _write_click_wav(p, duration_ms=12000, bpm=120)
    out = await LibrosaMusicAnalyzer().analyze(p)
    assert len(out.sections) >= 1
    for s in out.sections:
        assert 0 <= s.start_ms < s.end_ms <= out.duration_ms
        assert s.label in {"intro", "outro", "chorus", "verse", "bridge"}
    # Energy curve at 100 Hz: ~ duration_ms / 10 entries.
    expected_len = out.duration_ms // 10
    assert abs(len(out.energy_curve) - expected_len) < expected_len * 0.1


async def test_analyze_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await LibrosaMusicAnalyzer().analyze(tmp_path / "nope.wav")


# ---- CutGrid tests ----------------------------------------------------


def _fake_analysis(*, bpm: float, duration_ms: int = 8000, sections: list[Section] | None = None) -> MusicAnalysis:
    beat_period_ms = int(60_000 / bpm)
    beats_ms = list(range(0, duration_ms, beat_period_ms))
    return MusicAnalysis(
        duration_ms=duration_ms,
        bpm=bpm,
        bpm_stability=1.0,
        beats_ms=beats_ms,
        downbeats_ms=beats_ms[::4],
        sections=sections or [],
        energy_curve=[0.1] * (duration_ms // 10),
        spectral_novelty=[0.1] * (duration_ms // 10),
        analyzer="test-fixture",
    )


def test_cut_grid_120bpm_produces_4beat_cuts() -> None:
    analysis = _fake_analysis(bpm=120, duration_ms=8000)
    grid = generate_cut_grid(analysis)
    assert grid.cut_frequency_beats == 4
    # 8s at 120 BPM = 16 beats; cuts every 4 = ~4 cuts (plus 0 + duration).
    assert 4 <= len(grid.cut_points_ms) <= 7


def test_cut_grid_60bpm_produces_8beat_cuts() -> None:
    analysis = _fake_analysis(bpm=60, duration_ms=16000)
    grid = generate_cut_grid(analysis)
    assert grid.cut_frequency_beats == 8


def test_cut_grid_160bpm_produces_8beat_cuts() -> None:
    analysis = _fake_analysis(bpm=160, duration_ms=8000)
    grid = generate_cut_grid(analysis)
    assert grid.cut_frequency_beats == 8


def test_cut_grid_snaps_to_section_boundary_within_200ms() -> None:
    sections = [
        Section(label="intro", start_ms=0, end_ms=2050, energy_mean=0.1, energy_std=0.05),
        Section(label="chorus", start_ms=2050, end_ms=8000, energy_mean=0.2, energy_std=0.05),
    ]
    analysis = _fake_analysis(bpm=120, duration_ms=8000, sections=sections)
    # Force a cut frequency that produces a cut point near the 2050ms boundary.
    grid = generate_cut_grid(analysis, cut_frequency_override=4)
    assert 2050 in grid.cut_points_ms or any(
        abs(c - 2050) <= 50 for c in grid.cut_points_ms
    )
    # Section boundary 2050 should appear in the section_aligned_cuts list.
    assert 2050 in grid.section_aligned_cuts


def test_cut_grid_no_beats_returns_pass_through_grid() -> None:
    analysis = MusicAnalysis(
        duration_ms=5000,
        bpm=0,
        bpm_stability=0,
        beats_ms=[],
        downbeats_ms=[],
        sections=[],
        energy_curve=[],
        spectral_novelty=[],
        analyzer="test",
    )
    grid = generate_cut_grid(analysis)
    assert grid.cut_points_ms == [0, 5000]


def test_cut_grid_override_freq_takes_precedence() -> None:
    analysis = _fake_analysis(bpm=120, duration_ms=8000)  # auto would pick 4
    grid = generate_cut_grid(analysis, cut_frequency_override=8)
    assert grid.cut_frequency_beats == 8


_ = math  # silence ruff F401 — used in real-audio tests if added
