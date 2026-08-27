"""
Visualizer Lab II — Synthetic AudioFrame Profiles

Deterministic (seeded) stand-ins for real music, used to validate that an
experimental visualizer's CHARACTER — not just its intensity — actually
differs across musical situations, per the audit's authoritative principle:

    DIFFERENT MUSIC -> DIFFERENT CHARACTER
    MORE MUSIC != MORE BLINKING

Each profile is a small state machine producing one AudioFrame per tick()
call. Running the same profile twice with the same dt sequence produces
comparable musical behavior (same beat timing, same envelope shape) — exact
noise texture may differ only where a profile intentionally reseeds.

Human evaluation with real music remains authoritative; these profiles are
for development validation only.
"""

import math
import random
from dataclasses import replace

from toroidamp.analysis.audio_frame import AudioFrame

EMPTY_SPECTRUM = tuple([0.0] * 64)
EMPTY_WAVEFORM = tuple([0.0] * 128)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SyntheticProfile:
    """Base: deterministic synthetic AudioFrame generator driven by elapsed time."""

    name = "base"
    seed = 0

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed if seed is not None else self.seed)
        self.t = 0.0
        self._next_beat_t = 0.0
        self._manual_beat = False
        self._manual_strong_beat = False

    def inject_beat(self, strong: bool = False) -> None:
        """Manual beat trigger (harness SPACE/ENTER) — merged into the next tick()."""
        self._manual_beat = True
        if strong:
            self._manual_strong_beat = True

    def tick(self, dt: float) -> AudioFrame:
        self.t += dt
        frame = self._compute(self.t, dt)
        if self._manual_beat:
            frame = replace(frame, beat=True, strong_beat=frame.strong_beat or self._manual_strong_beat)
            self._manual_beat = False
            self._manual_strong_beat = False
        return frame

    def _compute(self, t: float, dt: float) -> AudioFrame:
        raise NotImplementedError

    # -- shared helpers -----------------------------------------------

    def _spectrum_from_bands(self, bass: float, mids: float, treble: float, spread: float = 0.18) -> tuple:
        """Builds a plausible 64-bin spectrum from three band energies plus light seeded texture."""
        bins = []
        for i in range(64):
            frac = i / 63.0
            low = bass * math.exp(-((frac - 0.08) ** 2) / (2 * spread ** 2))
            mid = mids * math.exp(-((frac - 0.45) ** 2) / (2 * (spread * 1.4) ** 2))
            high = treble * math.exp(-((frac - 0.9) ** 2) / (2 * spread ** 2))
            noise = self.rng.random() * 0.05
            bins.append(_clamp01(low + mid + high + noise))
        return tuple(bins)

    def _waveform_from_energy(self, rms: float, freq_hz: float) -> tuple:
        pts = []
        for i in range(128):
            phase = (i / 128.0) * 2 * math.pi * 4 + self.t * freq_hz
            pts.append(max(-1.0, min(1.0, math.sin(phase) * rms + (self.rng.random() - 0.5) * rms * 0.1)))
        return tuple(pts)


class SilenceProfile(SyntheticProfile):
    """True silence — nothing playing. The visualizer's idle/silence behavior is what's under test here."""
    name = "silence"
    seed = 1

    def _compute(self, t, dt):
        return AudioFrame(
            rms=0.0, peak=0.0, bass=0.0, mids=0.0, treble=0.0,
            spectrum=EMPTY_SPECTRUM, waveform=EMPTY_WAVEFORM,
            beat=False, strong_beat=False,
        )


class OrchestralProfile(SyntheticProfile):
    """Sustained mids, broad slow dynamics, sparse transients."""
    name = "orchestral"
    seed = 2
    BEAT_INTERVAL = (3.0, 5.5)  # sparse, jittered

    def __init__(self, seed=None):
        super().__init__(seed)
        self._next_beat_t = self.rng.uniform(*self.BEAT_INTERVAL)

    def _compute(self, t, dt):
        swell = 0.5 + 0.5 * math.sin(t * 0.12)  # slow ~52s broad dynamic arc
        rms = _clamp01(0.22 + 0.28 * swell)
        bass = _clamp01(0.12 + 0.10 * math.sin(t * 0.07 + 1.0))
        mids = _clamp01(0.32 + 0.28 * swell)
        treble = _clamp01(0.12 + 0.10 * math.sin(t * 0.09 + 2.0))

        beat = False
        strong = False
        if t >= self._next_beat_t:
            beat = True
            strong = self.rng.random() < 0.2  # rare
            self._next_beat_t = t + self.rng.uniform(*self.BEAT_INTERVAL)

        spectrum = self._spectrum_from_bands(bass, mids, treble, spread=0.24)
        waveform = self._waveform_from_energy(rms, freq_hz=2.0)
        return AudioFrame(
            rms=rms, peak=min(1.0, rms * 1.3), bass=bass, mids=mids, treble=treble,
            spectrum=spectrum, waveform=waveform, beat=beat, strong_beat=strong,
        )


class MetalProfile(SyntheticProfile):
    """Dense mids, frequent transients, sustained high energy, regular ~120bpm kick."""
    name = "metal"
    seed = 3
    BEAT_INTERVAL = 0.5  # ~120bpm

    def __init__(self, seed=None):
        super().__init__(seed)
        self._next_beat_t = self.BEAT_INTERVAL

    def _compute(self, t, dt):
        rms = _clamp01(0.72 + 0.08 * math.sin(t * 3.3) + (self.rng.random() - 0.5) * 0.05)
        bass = _clamp01(0.55 + 0.15 * math.sin(t * 3.3))
        mids = _clamp01(0.68 + 0.12 * self.rng.random())
        treble = _clamp01(0.52 + 0.18 * self.rng.random())

        beat = False
        strong = False
        if t >= self._next_beat_t:
            beat = True
            strong = bass > 0.55
            self._next_beat_t = t + self.BEAT_INTERVAL + self.rng.uniform(-0.03, 0.03)

        spectrum = self._spectrum_from_bands(bass, mids, treble, spread=0.32)
        waveform = self._waveform_from_energy(rms, freq_hz=8.0)
        return AudioFrame(
            rms=rms, peak=min(1.0, rms * 1.2), bass=bass, mids=mids, treble=treble,
            spectrum=spectrum, waveform=waveform, beat=beat, strong_beat=strong,
        )


class ElectronicProfile(SyntheticProfile):
    """Dominant bass, mechanically regular four-on-the-floor beat, build/drop energy cycle."""
    name = "electronic"
    seed = 4
    BEAT_INTERVAL = 0.5  # 120bpm, no jitter — mechanically regular
    CYCLE_S = 16.0

    def __init__(self, seed=None):
        super().__init__(seed)
        self._next_beat_t = self.BEAT_INTERVAL

    def _compute(self, t, dt):
        cycle_pos = (t % self.CYCLE_S) / self.CYCLE_S
        is_drop = cycle_pos < 0.05
        build = cycle_pos
        energy = 1.0 if is_drop else 0.3 + 0.5 * build

        rms = _clamp01(energy)
        bass = _clamp01(0.55 + (0.4 if is_drop else 0.2 * build))
        mids = _clamp01(0.22 + 0.15 * build)
        treble = _clamp01(0.38 + 0.2 * self.rng.random())

        beat = False
        strong = False
        if t >= self._next_beat_t:
            beat = True
            strong = bass > 0.65
            self._next_beat_t = t + self.BEAT_INTERVAL  # regular — no jitter

        spectrum = self._spectrum_from_bands(bass, mids, treble, spread=0.12)
        waveform = self._waveform_from_energy(rms, freq_hz=1.0)
        return AudioFrame(
            rms=rms, peak=min(1.0, rms * 1.1), bass=bass, mids=mids, treble=treble,
            spectrum=spectrum, waveform=waveform, beat=beat, strong_beat=strong,
        )


class AmbientProfile(SyntheticProfile):
    """Low RMS, very slow spectral evolution, few strong beats."""
    name = "ambient"
    seed = 5
    BEAT_INTERVAL = (10.0, 20.0)

    def __init__(self, seed=None):
        super().__init__(seed)
        self._next_beat_t = self.rng.uniform(*self.BEAT_INTERVAL)

    def _compute(self, t, dt):
        rms = _clamp01(0.08 + 0.05 * math.sin(t * 0.03))
        bass = _clamp01(0.05 + 0.05 * math.sin(t * 0.02 + 0.5))
        mids = _clamp01(0.10 + 0.05 * math.sin(t * 0.017 + 1.5))
        treble = _clamp01(0.04 + 0.03 * math.sin(t * 0.025 + 2.5))

        beat = False
        strong = False
        if t >= self._next_beat_t:
            beat = True
            strong = self.rng.random() < 0.1  # rarely strong
            self._next_beat_t = t + self.rng.uniform(*self.BEAT_INTERVAL)

        spectrum = self._spectrum_from_bands(bass, mids, treble, spread=0.35)
        waveform = self._waveform_from_energy(rms, freq_hz=0.5)
        return AudioFrame(
            rms=rms, peak=min(1.0, rms * 1.4), bass=bass, mids=mids, treble=treble,
            spectrum=spectrum, waveform=waveform, beat=beat, strong_beat=strong,
        )


PROFILES: dict[str, type[SyntheticProfile]] = {
    "silence": SilenceProfile,
    "orchestral": OrchestralProfile,
    "metal": MetalProfile,
    "electronic": ElectronicProfile,
    "ambient": AmbientProfile,
}

PROFILE_ORDER = ["silence", "orchestral", "metal", "electronic", "ambient"]  # keys 1-5
