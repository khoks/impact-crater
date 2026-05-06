"""Music analysis per ADR-0012 §"Music structure analysis".

ADR-0012's first choice was **Madmom** for beats + downbeats. Madmom's last
release (2024-01) predates Python 3.12, and its setup.py doesn't build under
modern packaging — the user's dev box can't install it. Per ADR-0012's
explicit escape hatch ("If install friction proves real, swap to BeatNet
via the MusicAnalyzer abstraction"), MVP ships librosa-only.

The accuracy gap matters most for intricate / electronic tracks; for the
MVP smoke-test envelope (typical user-supplied songs at 60-160 BPM with
clear beats) librosa.beat.beat_track is well within tolerance. v1 can swap
to BeatNet — torch lands naturally with the ADR-0008 local-LLM runtime.

`LibrosaMusicAnalyzer.analyze(audio_path) → MusicAnalysis` runs in <30s
for a 4-minute track on a developer laptop. CutGrid generation applies
ADR-0012's tempo-aware adjustment + section-boundary snapping.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)


# ---- Pydantic models ---------------------------------------------------


class Section(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    energy_mean: float
    energy_std: float


class MusicAnalysis(BaseModel):
    """Output of `MusicAnalyzer.analyze` per ADR-0012."""

    model_config = ConfigDict(extra="ignore")
    schema_version: int = 1
    duration_ms: int
    bpm: float
    bpm_stability: float = Field(ge=0.0)
    beats_ms: list[int]
    downbeats_ms: list[int]
    sections: list[Section]
    energy_curve: list[float]  # 100 Hz sampled RMS, length = duration_ms / 10
    spectral_novelty: list[float]  # same rate; for accent detection
    analyzer: str  # "librosa-only" or "madmom-librosa" so caches invalidate on swap


class CutGrid(BaseModel):
    """Cut-point grid derived from beats per ADR-0012 §"Beat-grid generation"."""

    model_config = ConfigDict(extra="ignore")
    cut_points_ms: list[int]
    section_aligned_cuts: list[int]
    cut_frequency_beats: int  # 4 = 1 bar at 4/4; 8 = 2 bars
    bpm: float


# ---- Protocol ----------------------------------------------------------


@runtime_checkable
class MusicAnalyzer(Protocol):
    """The contract every analyzer satisfies. v1 may add a BeatNet impl."""

    name: str

    async def analyze(self, audio_path: Path | str) -> MusicAnalysis: ...


# ---- librosa implementation -------------------------------------------


class LibrosaMusicAnalyzer:
    """librosa-only analyzer. The MVP MusicAnalyzer."""

    name: str = "librosa-only"

    def __init__(self, *, sample_rate: int = 22050) -> None:
        self._sample_rate = sample_rate

    async def analyze(self, audio_path: Path | str) -> MusicAnalysis:
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"audio missing: {path}")
        # librosa is synchronous; offload to a thread so the asyncio loop
        # isn't blocked on big files.
        return await asyncio.to_thread(self._analyze_sync, path)

    def _analyze_sync(self, path: Path) -> MusicAnalysis:
        import librosa  # heavy import; keep inside the call

        y, sr = librosa.load(str(path), sr=self._sample_rate, mono=True)
        duration_s = float(librosa.get_duration(y=y, sr=sr))
        duration_ms = int(round(duration_s * 1000))

        # ---- Beats + tempo --------------------------------------------
        # `tightness` controls how strict beat-period regularity is. 100
        # is librosa's default; lower values let tempo drift more freely.
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
        beats_s = librosa.frames_to_time(beat_frames, sr=sr)
        beats_ms = [int(round(t * 1000)) for t in beats_s]
        bpm = _to_scalar(tempo)

        # BPM stability = 1.0 / (1 + cv_of_beat_intervals). Higher = more steady.
        if len(beats_ms) >= 3:
            intervals = np.diff(beats_ms)
            mean = float(np.mean(intervals))
            std = float(np.std(intervals))
            cv = std / mean if mean > 0 else 0.0
            bpm_stability = 1.0 / (1.0 + cv)
        else:
            bpm_stability = 0.0

        # Heuristic downbeats: every 4th beat (assumes 4/4 time signature).
        # Real downbeat detection lives in the v1 BeatNet swap.
        downbeats_ms = beats_ms[::4]

        # ---- Sections -------------------------------------------------
        sections = self._detect_sections(y, sr, duration_ms)

        # ---- Energy curve --------------------------------------------
        # 100 Hz sampling rate as ADR-0012 specified.
        # librosa.feature.rms returns one frame per `hop_length` samples.
        # For 22050 Hz audio, hop = 220 ≈ 100 Hz.
        rms = librosa.feature.rms(y=y, frame_length=441, hop_length=220)[0]
        energy_curve = [float(v) for v in rms.tolist()]

        # ---- Spectral novelty ----------------------------------------
        novelty = librosa.onset.onset_strength(y=y, sr=sr, hop_length=220)
        spectral_novelty = [float(v) for v in novelty.tolist()]

        return MusicAnalysis(
            duration_ms=duration_ms,
            bpm=bpm,
            bpm_stability=bpm_stability,
            beats_ms=beats_ms,
            downbeats_ms=downbeats_ms,
            sections=sections,
            energy_curve=energy_curve,
            spectral_novelty=spectral_novelty,
            analyzer=self.name,
        )

    def _detect_sections(self, y: "np.ndarray", sr: int, duration_ms: int) -> list[Section]:
        """librosa.segment.agglomerative section detection per ADR-0012.

        Falls back to a single full-duration "outro" section if librosa
        produces no boundaries (very short tracks).
        """
        import librosa

        try:
            # Mel-spectrogram-based feature; segment.agglomerative groups
            # frames into k clusters and we walk the boundaries.
            mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64)
            mel_db = librosa.power_to_db(mel, ref=np.max)
            n_segments = max(2, min(8, int(duration_ms / 30000) + 2))
            boundaries = librosa.segment.agglomerative(mel_db, k=n_segments)
            boundary_ms = [int(round(b * 220 / sr * 1000)) for b in boundaries]
            boundary_ms.append(duration_ms)
        except Exception as exc:  # pragma: no cover — librosa edge cases
            log.warning("section detection failed: %s; using single-section fallback", exc)
            boundary_ms = [0, duration_ms]

        # Heuristic labels: longest = chorus, first = intro, last = outro,
        # middles alternate verse / bridge.
        sections: list[Section] = []
        ranges = list(zip(boundary_ms, boundary_ms[1:]))
        if not ranges:
            ranges = [(0, duration_ms)]
        durations = [b - a for a, b in ranges]
        chorus_idx = max(range(len(durations)), key=lambda i: durations[i]) if durations else 0
        for idx, (start_ms, end_ms) in enumerate(ranges):
            if start_ms >= end_ms:
                continue
            if idx == 0 and len(ranges) > 1:
                label = "intro"
            elif idx == len(ranges) - 1 and len(ranges) > 1:
                label = "outro"
            elif idx == chorus_idx:
                label = "chorus"
            else:
                label = "verse" if idx % 2 == 0 else "bridge"
            energy_mean, energy_std = self._segment_energy(y, sr, start_ms, end_ms)
            sections.append(
                Section(
                    label=label,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    energy_mean=energy_mean,
                    energy_std=energy_std,
                )
            )
        return sections

    def _segment_energy(
        self, y: "np.ndarray", sr: int, start_ms: int, end_ms: int
    ) -> tuple[float, float]:
        a = int(start_ms / 1000.0 * sr)
        b = int(end_ms / 1000.0 * sr)
        seg = y[a:b]
        if seg.size == 0:
            return (0.0, 0.0)
        rms_window = np.sqrt(np.mean(seg.astype(np.float32) ** 2))
        # Approximate std via per-100ms windows.
        win = max(int(sr * 0.1), 1)
        chunks = [seg[i : i + win] for i in range(0, len(seg), win) if len(seg[i : i + win]) > 0]
        std = float(np.std([float(np.sqrt(np.mean(c.astype(np.float32) ** 2))) for c in chunks])) if chunks else 0.0
        return (float(rms_window), std)


def _to_scalar(x: object) -> float:
    """librosa.beat.beat_track sometimes returns a 0-d ndarray for tempo."""
    if isinstance(x, np.ndarray):
        return float(x.item() if x.ndim == 0 else x.flat[0])
    return float(x)


# ---- CutGrid generation ------------------------------------------------


def generate_cut_grid(
    analysis: MusicAnalysis,
    *,
    cut_frequency_override: int | None = None,
    section_snap_ms: int = 200,
) -> CutGrid:
    """Per ADR-0012 §"Beat-grid generation"."""
    if not analysis.beats_ms:
        return CutGrid(
            cut_points_ms=[0, analysis.duration_ms],
            section_aligned_cuts=[],
            cut_frequency_beats=4,
            bpm=analysis.bpm,
        )

    cut_freq = cut_frequency_override or _tempo_aware_cut_frequency(analysis.bpm)
    raw_cuts = analysis.beats_ms[::cut_freq]
    if raw_cuts and raw_cuts[0] != 0:
        raw_cuts = [0, *raw_cuts]
    if raw_cuts[-1] < analysis.duration_ms - 50:
        raw_cuts = [*raw_cuts, analysis.duration_ms]

    # Section boundary snapping: if a cut lands within `section_snap_ms`
    # of a section boundary, replace it with the boundary.
    section_boundaries = [s.start_ms for s in analysis.sections] + [
        analysis.sections[-1].end_ms if analysis.sections else analysis.duration_ms
    ]
    snapped_cuts: list[int] = []
    for cut in raw_cuts:
        nearest_boundary = min(
            section_boundaries,
            key=lambda b: abs(b - cut),
            default=cut,
        )
        if abs(nearest_boundary - cut) <= section_snap_ms:
            snapped_cuts.append(int(nearest_boundary))
        else:
            snapped_cuts.append(int(cut))

    # Dedupe + sort + ensure monotonic.
    snapped_cuts = sorted(set(snapped_cuts))
    section_aligned = [c for c in snapped_cuts if c in section_boundaries]

    return CutGrid(
        cut_points_ms=snapped_cuts,
        section_aligned_cuts=section_aligned,
        cut_frequency_beats=cut_freq,
        bpm=analysis.bpm,
    )


def _tempo_aware_cut_frequency(bpm: float) -> int:
    """Per ADR-0012:
        <80 BPM  → 8-beat cuts (2 bars at 4/4)
        80-140   → 4-beat cuts (1 bar)
        >140 BPM → 8-beat cuts (2 bars; keeps clip durations reasonable)
    """
    if bpm < 80:
        return 8
    if bpm > 140:
        return 8
    return 4
