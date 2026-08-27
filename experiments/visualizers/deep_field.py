"""
Visualizer Lab II — Experiment 1: STARFIELD: DEEP FIELD

MUSICAL THESIS
    The music changes SPACE, DEPTH, MOMENTUM, and ATMOSPHERE — not merely
    speed. This is a musical environment with inertia, not a screensaur
    with an RMS-driven speed knob.

DONOR DNA
    MetalWar-Installer effects.py:38 Starfield — 3D star-tunnel projection
    (factor = fov / z), camera-plane rotation, exponential warp smoothing.
    The projection math is reused; every driver is rebuilt from scratch —
    the donor's `bpm_data`/fake `intensity` are gone entirely.

Do not import PySide6 here — pure Pygame/math, matching the production
Visualizer contract (subclassed for interface parity; NOT registered in
the production visualizer selector).
"""

import math
import random

import pygame

from toroidamp.visualizers.base import Visualizer
from toroidamp.analysis.audio_frame import AudioFrame


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class _Star:
    __slots__ = ("x", "y", "z", "layer")

    def __init__(self, x, y, z, layer):
        self.x, self.y, self.z, self.layer = x, y, z, layer


class DeepFieldVisualizer(Visualizer):
    """
    A 3D star tunnel where camera PRESSURE (not raw speed) carries the
    musical signal. Three star layers (near/mid/far) let treble control
    fine-detail density independently of the bass-driven depth pressure.
    """

    NEAR_LAYER, MID_LAYER, FAR_LAYER = 0, 1, 2
    LAYER_COUNTS = {NEAR_LAYER: 90, MID_LAYER: 160, FAR_LAYER: 250}  # far/treble grows dynamically
    MAX_FAR_EXTRA = 220  # treble can add up to this many extra fine/sparkle stars

    BASE_CRUISE = 0.35  # silence: slow inertial drift, never a hard stop
    STRONG_EVENT_COOLDOWN = 1.4  # seconds — strong_beat compression events can't spam

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self.rng = random.Random(1337)

        # Smoothed (inertial) state — never jumps directly to a raw AudioFrame value.
        self._depth_pressure = self.BASE_CRUISE   # smoothed bass -> forward accel baseline
        self._lateral_vel = 0.0                    # smoothed mids -> angular drift velocity
        self._camera_angle = 0.0                    # integrated lateral_vel
        self._treble_smoothed = 0.0
        self._rms_smoothed = 0.0

        # Fast impulse + decay state (beat / strong_beat are events, not levels).
        self._beat_impulse = 0.0
        self._strong_event_t = -999.0     # last strong event time, seconds since start
        self._strong_event_progress = 0.0  # 0 idle, ramps 0->1->0 over the event
        self._elapsed = 0.0

        # Spectral color bias — low bins bias near stars warm, high bins bias far stars cool.
        self._color_bias = 0.0  # smoothed [-1..1], negative=warm/bass-heavy, positive=cool/treble-heavy

        self._extra_far_target = 0

        self.stars: list[_Star] = []
        self._spawn_initial_stars()

    def get_name(self) -> str:
        return "Deep Field (experimental)"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def _spawn_initial_stars(self):
        self.stars.clear()
        for layer, count in self.LAYER_COUNTS.items():
            for _ in range(count):
                self.stars.append(self._new_star(layer))

    def _new_star(self, layer: int) -> _Star:
        x = self.rng.uniform(-1.0, 1.0)
        y = self.rng.uniform(-1.0, 1.0)
        z = self.rng.uniform(0.2, 1.0)
        return _Star(x, y, z, layer)

    def update(self, frame: AudioFrame, dt: float) -> None:
        self._elapsed += dt
        dt = max(0.0001, min(0.1, dt))  # guard against huge dt spikes (e.g. tab switch)

        # --- bass -> depth pressure (SMOOTH: exponential toward target) ---
        target_pressure = self.BASE_CRUISE + frame.bass * 1.8
        smooth_k = 1.0 - math.exp(-dt * 2.2)
        self._depth_pressure = _lerp(self._depth_pressure, target_pressure, smooth_k)

        # --- mids -> lateral drift / rotational tendency (SMOOTH) ---
        target_lateral = (frame.mids - 0.3) * 0.6  # centered so low mids drift gently either way
        self._lateral_vel = _lerp(self._lateral_vel, target_lateral, 1.0 - math.exp(-dt * 1.5))
        self._camera_angle += self._lateral_vel * dt

        # --- treble -> fine star density / sparkle (SMOOTH) ---
        self._treble_smoothed = _lerp(self._treble_smoothed, frame.treble, 1.0 - math.exp(-dt * 3.0))
        self._extra_far_target = int(self._treble_smoothed * self.MAX_FAR_EXTRA)

        # --- spectrum -> spatial/color character (SLOW evolving state) ---
        low_energy = sum(frame.spectrum[:16]) / 16.0
        high_energy = sum(frame.spectrum[48:]) / 16.0
        target_bias = _clamp01(high_energy) - _clamp01(low_energy)  # [-1..1]-ish
        self._color_bias = _lerp(self._color_bias, target_bias, 1.0 - math.exp(-dt * 0.4))

        # --- rms -> restrained global energy envelope, NOT the primary driver ---
        self._rms_smoothed = _lerp(self._rms_smoothed, frame.rms, 1.0 - math.exp(-dt * 2.0))

        # --- beat -> short acceleration impulse (FAST impulse + decay) ---
        self._beat_impulse *= math.exp(-dt * 5.0)  # fast decay
        if frame.beat:
            self._beat_impulse = min(1.0, self._beat_impulse + 0.6)

        # --- strong_beat -> rare hyperspace/compression event (gated, bounded) ---
        if frame.strong_beat and (self._elapsed - self._strong_event_t) > self.STRONG_EVENT_COOLDOWN:
            self._strong_event_t = self._elapsed
        if self._strong_event_t >= 0:
            age = self._elapsed - self._strong_event_t
            EVENT_DURATION = 0.45
            if age < EVENT_DURATION:
                # smooth rise/fall envelope, bounded in time — never a full-screen strobe
                phase = age / EVENT_DURATION
                self._strong_event_progress = math.sin(phase * math.pi)
            else:
                self._strong_event_progress = 0.0

        self._step_stars(dt)

    def _step_stars(self, dt: float):
        speed = self._depth_pressure + self._beat_impulse * 0.9 + self._strong_event_progress * 1.6
        for star in self.stars:
            star.z -= speed * dt * 0.5
            if star.z <= 0.05:
                new = self._new_star(star.layer)
                star.x, star.y, star.z = new.x, new.y, 1.0

        # Grow/shrink the treble-driven fine-detail (far) layer toward its target.
        far_extra_current = sum(1 for s in self.stars if s.layer == self.FAR_LAYER + 100)
        while far_extra_current < self._extra_far_target:
            self.stars.append(self._new_star(self.FAR_LAYER + 100))  # tagged sparkle layer
            far_extra_current += 1
        if far_extra_current > self._extra_far_target:
            for s in list(self.stars):
                if s.layer == self.FAR_LAYER + 100 and far_extra_current > self._extra_far_target:
                    self.stars.remove(s)
                    far_extra_current -= 1

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        surface.fill((3, 2, 8))
        cx, cy = self.w / 2.0, self.h / 2.0
        fov = min(self.w, self.h) * 0.9

        cos_a, sin_a = math.cos(self._camera_angle), math.sin(self._camera_angle)

        # Warm/cool base palette driven by spectral color bias — not a fixed 4-color cycle.
        warm = (255, 120, 60)
        cool = (90, 180, 255)
        bias01 = (self._color_bias + 1.0) * 0.5

        for star in self.stars:
            # camera lateral rotation (roll-ish drift, not a hard reorientation)
            rx = star.x * cos_a - star.y * sin_a
            ry = star.x * sin_a + star.y * cos_a

            z = max(0.05, star.z)
            factor = fov / (z * 6.0)
            sx = cx + rx * factor
            sy = cy + ry * factor
            if not (0 <= sx < self.w and 0 <= sy < self.h):
                continue

            depth_frac = 1.0 - z  # near stars -> 1.0, far -> 0.0
            near_bias = bias01 if star.layer in (self.NEAR_LAYER,) else 1.0 - bias01
            r = int(_lerp(warm[0], cool[0], near_bias) * (0.4 + 0.6 * depth_frac))
            g = int(_lerp(warm[1], cool[1], near_bias) * (0.4 + 0.6 * depth_frac))
            b = int(_lerp(warm[2], cool[2], near_bias) * (0.4 + 0.6 * depth_frac))
            brightness = _clamp01(0.5 + 0.5 * self._rms_smoothed)
            color = (int(r * brightness), int(g * brightness), int(b * brightness))

            radius = max(1, int(1.0 + depth_frac * 2.5))

            # near-field streak length grows with bass depth pressure — a trail, not a flash.
            streak = (self._depth_pressure + self._strong_event_progress * 2.0) * depth_frac * 10.0
            if streak > 1.5:
                tail_z = min(1.0, z + 0.04)
                tf = fov / (tail_z * 6.0)
                tx, ty = cx + rx * tf, cy + ry * tf
                pygame.draw.line(surface, color, (tx, ty), (sx, sy), max(1, radius - 1))
            else:
                surface.set_at((int(sx), int(sy)), color) if radius <= 1 else \
                    pygame.draw.circle(surface, color, (int(sx), int(sy)), radius)

    def get_debug_state(self) -> dict:
        """Exposes internal smoothed state for automated tests — not part of the Visualizer contract."""
        return {
            "depth_pressure": self._depth_pressure,
            "lateral_vel": self._lateral_vel,
            "camera_angle": self._camera_angle,
            "treble_smoothed": self._treble_smoothed,
            "color_bias": self._color_bias,
            "beat_impulse": self._beat_impulse,
            "strong_event_progress": self._strong_event_progress,
            "star_count": len(self.stars),
        }
