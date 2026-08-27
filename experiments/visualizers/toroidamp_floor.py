"""
Visualizer Lab II — Experiment 2: TOROIDAMP FLOOR (SIGNATURE candidate)

MUSICAL THESIS
    Music has entered a physical grid. Frequency structure becomes spatial
    structure; rhythm propagates through it. Two tracks with similar BPM
    but different spectral content must produce visibly different topology
    — that is the entire point of this experiment.

DONOR DNA
    MetalWar-Installer effects.py:1905 RetroGrid.lit_cells — donor
    mechanism confirmed (Lab I audit) to be a FLAT random-spawn-on-kick
    model with independent per-cell decay and NO propagation, NO spatial
    meaning. That flatness is exactly what's rejected here: this version
    replaces random spawn with spectrum-driven spatial placement and adds
    genuine ring-to-ring propagation the donor never had.

PRESENTATION
    A top-down radial field (rings x sectors) rather than the donor's
    perspective floor — chosen deliberately for musical readability
    (Lab I §11 / this mission's explicit instruction that readability
    matters more than gratuitous camera motion). Low spectrum bins map to
    inner rings, high bins to outer rings — literally "structural core to
    edge highlight."
"""

import math

import pygame

from toroidamp.visualizers.base import Visualizer
from toroidamp.analysis.audio_frame import AudioFrame


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class _Pulse:
    """A propagating ring-wave, launched by a beat, traveling outward from an origin ring."""
    __slots__ = ("origin_ring", "sector", "radius", "speed", "strength", "width")

    def __init__(self, origin_ring: float, sector: int, speed: float, strength: float, width: float):
        self.origin_ring = origin_ring
        self.sector = sector
        self.radius = 0.0
        self.speed = speed
        self.strength = strength
        self.width = width


class ToroidAMPFloorVisualizer(Visualizer):
    RINGS = 10
    SECTORS = 28
    DECAY_PER_SEC = 0.6      # residual glow fade rate
    ATTACK_RATE = 14.0       # how fast a tile rises toward its target illumination
    PULSE_SPEED = 4.0        # rings/second a propagation wave travels
    PULSE_WIDTH = 1.4        # how many rings wide a traveling pulse's leading edge is

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)

        # tile_energy[ring][sector] — persistent, decaying illumination state (the floor's memory).
        self.tile_energy = [[0.0 for _ in range(self.SECTORS)] for _ in range(self.RINGS)]
        self.tile_target = [[0.0 for _ in range(self.SECTORS)] for _ in range(self.RINGS)]

        self._pulses: list[_Pulse] = []
        self._bass_smoothed = 0.0
        self._mids_smoothed = 0.0
        self._elapsed = 0.0

    def get_name(self) -> str:
        return "ToroidAMP Floor (experimental)"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def _spectrum_to_targets(self, frame: AudioFrame):
        """
        Maps spectrum[64] into (ring, sector) space: low bins -> inner rings
        (structural core), high bins -> outer rings (peripheral highlights).
        This is the piece that makes two same-BPM songs look structurally
        different — the SHAPE of illumination, not just its rate.
        """
        for r in range(self.RINGS):
            for s in range(self.SECTORS):
                self.tile_target[r][s] *= 0.0  # reset target accumulation this frame

        for i, mag in enumerate(frame.spectrum):
            ring = min(self.RINGS - 1, int((i / 63.0) * self.RINGS))
            sector = (i * 5) % self.SECTORS  # spread bins across sectors, not a raw 1:1 crowd
            self.tile_target[ring][sector] = max(self.tile_target[ring][sector], mag)

        # bass -> central/low-ring sustained structural illumination floor
        for r in range(min(3, self.RINGS)):
            core_floor = frame.bass * (1.0 - r / 3.0) * 0.8
            for s in range(self.SECTORS):
                self.tile_target[r][s] = max(self.tile_target[r][s], core_floor)

        # mids -> structural continuity across a mid-band ring region
        mid_lo, mid_hi = self.RINGS // 3, (2 * self.RINGS) // 3
        for r in range(mid_lo, mid_hi):
            body = frame.mids * 0.5
            for s in range(self.SECTORS):
                self.tile_target[r][s] = max(self.tile_target[r][s], body)

        # treble -> sharp peripheral accents (only a handful of outer tiles, not the whole ring)
        outer_ring = self.RINGS - 1
        accent_count = int(frame.treble * self.SECTORS * 0.4)
        if accent_count > 0:
            # deterministic-but-varied selection driven by elapsed time, not free random spam
            phase = int(self._elapsed * 7) % self.SECTORS
            for k in range(accent_count):
                s = (phase + k * 3) % self.SECTORS
                self.tile_target[outer_ring][s] = max(self.tile_target[outer_ring][s], frame.treble)

    def _peak_bin_position(self, frame: AudioFrame) -> tuple[float, int]:
        """Finds the (ring, sector) of the current spectral peak — pulse propagation origin."""
        peak_i = max(range(64), key=lambda i: frame.spectrum[i])
        ring = (peak_i / 63.0) * self.RINGS
        sector = (peak_i * 5) % self.SECTORS
        return ring, sector

    def update(self, frame: AudioFrame, dt: float) -> None:
        dt = max(0.0001, min(0.1, dt))
        self._elapsed += dt
        self._bass_smoothed += (frame.bass - self._bass_smoothed) * min(1.0, dt * 3.0)
        self._mids_smoothed += (frame.mids - self._mids_smoothed) * min(1.0, dt * 2.0)

        self._spectrum_to_targets(frame)

        # beat -> local propagation pulse from the current spectral peak
        if frame.beat:
            origin_ring, sector = self._peak_bin_position(frame)
            self._pulses.append(_Pulse(origin_ring, sector, self.PULSE_SPEED, strength=0.9, width=self.PULSE_WIDTH))

        # strong_beat -> larger geometric event: a full-field multi-origin pulse burst
        if frame.strong_beat:
            for k in range(4):
                sector = int((k / 4.0) * self.SECTORS)
                self._pulses.append(_Pulse(0.0, sector, self.PULSE_SPEED * 1.4, strength=1.3, width=self.PULSE_WIDTH * 1.8))

        # advance pulses, apply their energy to tiles they currently touch, retire finished ones
        alive: list[_Pulse] = []
        for pulse in self._pulses:
            pulse.radius += pulse.speed * dt
            if pulse.radius <= self.RINGS + pulse.width:
                alive.append(pulse)
                front = pulse.origin_ring + pulse.radius
                for r in range(self.RINGS):
                    if abs(r - front) <= pulse.width:
                        falloff = 1.0 - abs(r - front) / pulse.width
                        for ds in range(-2, 3):
                            s = (pulse.sector + ds) % self.SECTORS
                            self.tile_target[r][s] = max(self.tile_target[r][s], pulse.strength * falloff)
        self._pulses = alive

        # attack/decay: tiles rise fast toward target, fade slowly — the floor's residual memory
        for r in range(self.RINGS):
            for s in range(self.SECTORS):
                target = self.tile_target[r][s]
                cur = self.tile_energy[r][s]
                if target > cur:
                    cur += (target - cur) * min(1.0, dt * self.ATTACK_RATE)
                else:
                    cur *= math.exp(-dt * self.DECAY_PER_SEC)
                self.tile_energy[r][s] = cur

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        surface.fill((4, 3, 10))
        cx, cy = self.w / 2.0, self.h / 2.0
        max_radius = min(self.w, self.h) * 0.46
        ring_step = max_radius / self.RINGS
        sector_angle = (2 * math.pi) / self.SECTORS

        for r in range(self.RINGS):
            inner = r * ring_step
            outer = inner + ring_step * 0.92
            for s in range(self.SECTORS):
                energy = self.tile_energy[r][s]
                if energy < 0.02:
                    continue
                # Pulses (esp. strong_beat) can push energy above 1.0 by design (a visible
                # "hot" overshoot as the wave passes) — clamp only at the final color stage
                # so the overshoot still reads as brighter without ever producing an invalid
                # (>255) color channel.
                color_energy = _clamp01(energy)
                a0 = s * sector_angle
                a1 = a0 + sector_angle * 0.88

                # spectral position -> hue: inner=warm/bass, outer=cool/treble
                depth_frac = r / max(1, self.RINGS - 1)
                red = int(_clamp01(1.0 - depth_frac * 0.7) * 255 * color_energy)
                green = int(_clamp01(0.3 + depth_frac * 0.3) * 255 * color_energy)
                blue = int(_clamp01(depth_frac) * 255 * color_energy)
                color = (red, green, blue)

                points = [
                    (cx + inner * math.cos(a0), cy + inner * math.sin(a0)),
                    (cx + outer * math.cos(a0), cy + outer * math.sin(a0)),
                    (cx + outer * math.cos(a1), cy + outer * math.sin(a1)),
                    (cx + inner * math.cos(a1), cy + inner * math.sin(a1)),
                ]
                pygame.draw.polygon(surface, color, points)

    def get_debug_state(self) -> dict:
        """Exposes internal state for automated tests — not part of the Visualizer contract."""
        total_energy = sum(sum(row) for row in self.tile_energy)
        return {
            "total_energy": total_energy,
            "active_pulses": len(self._pulses),
            "tile_energy": self.tile_energy,
        }
