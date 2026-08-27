"""
ToroidAMP - Production Starfield: Deep Field Visualizer
JACK FINAL PERCEPTUAL TUNING: Multi-pass luminous photon trails, depth-dependent
halo/glow layering, hot emissive star heads, and zero center obstruction.
"""

import math
import random

import pygame

from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class _Star:
    __slots__ = ("x", "y", "z", "layer", "band_affinity")

    def __init__(self, x: float, y: float, z: float, layer: int, band_affinity: int):
        self.x = x
        self.y = y
        self.z = z
        self.layer = layer
        self.band_affinity = band_affinity  # 0: Magenta, 1: Blue, 2: Cyan, 3: Green, 4: Gold


class DeepFieldVisualizer(Visualizer):
    """
    3D Cosmic Star Tunnel with Multi-Pass Luminous Photon Trails,
    Emissive Star Heads, and Simultaneous Multi-Family Spectral Color Gradation.
    """

    NEAR_LAYER, MID_LAYER, FAR_LAYER = 0, 1, 2
    SPARKLE_LAYER = 100
    LAYER_COUNTS = {NEAR_LAYER: 110, MID_LAYER: 200, FAR_LAYER: 340}
    MAX_FAR_EXTRA = 260

    BASE_CRUISE = 0.35
    STRONG_EVENT_COOLDOWN = 1.2

    # Vivid demoscene spectral palette families
    PALETTE = (
        (255, 30, 140),   # 0: Neon Magenta / Hot Pink
        (0, 140, 255),    # 1: Electric Cobalt Blue
        (0, 245, 255),    # 2: Laser Cyan
        (40, 255, 120),   # 3: Neon Emerald Green
        (255, 225, 40),   # 4: Electric Gold / Solar Yellow
    )

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self.rng = random.Random(1337)

        # Smoothed inertial state
        self._depth_pressure = self.BASE_CRUISE
        self._lateral_vel = 0.0
        self._camera_angle = 0.0
        self._treble_smoothed = 0.0
        self._rms_smoothed = 0.0

        # Multi-band spectral tracking
        self._bands_smooth = [0.0] * 5

        # Rhythmic streak dynamics (FAST ATTACK, SMOOTH INERTIAL DECAY)
        self._streak_target = 1.0
        self._beat_impulse = 0.0

        # Strong beat hyperspace warp
        self._strong_event_t = -999.0
        self._strong_event_progress = 0.0
        self._elapsed = 0.0

        self._color_bias = 0.0
        self._extra_far_target = 0

        self._vignette_surf: pygame.Surface | None = None
        self._build_vignette()

        self.stars: list[_Star] = []
        self._spawn_initial_stars()

    def get_name(self) -> str:
        return "Deep Field"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self._build_vignette()

    def _build_vignette(self) -> None:
        """Constructs a soft corner vignette that frames depth without touching the center."""
        self._vignette_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        corner_w = max(20, int(self.w * 0.20))
        corner_h = max(20, int(self.h * 0.20))
        for step in range(5):
            inset_x = int(corner_w * (step / 5.0))
            inset_y = int(corner_h * (step / 5.0))
            alpha = int(10 * (5 - step))
            rect = pygame.Rect(inset_x, inset_y, self.w - inset_x * 2, self.h - inset_y * 2)
            pygame.draw.rect(self._vignette_surf, (0, 0, 4, alpha), rect, max(1, corner_w // 5))

    def _spawn_initial_stars(self) -> None:
        self.stars.clear()
        for layer, count in self.LAYER_COUNTS.items():
            for i in range(count):
                self.stars.append(self._new_star(layer, i))

    def _new_star(self, layer: int, index: int = 0) -> _Star:
        x = self.rng.uniform(-1.0, 1.0)
        y = self.rng.uniform(-1.0, 1.0)
        z = self.rng.uniform(0.10, 1.0)
        if layer == self.NEAR_LAYER:
            band = (index % 3)  # Magenta, Blue, Cyan
        elif layer == self.MID_LAYER:
            band = ((index % 4) + 1) % 5  # Blue, Cyan, Green, Gold
        elif layer == self.FAR_LAYER:
            band = ((index % 3) + 2) % 5  # Cyan, Green, Gold
        else:
            band = 4 if (index % 2 == 0) else 2  # Gold or Cyan sparkle
        return _Star(x, y, z, layer, band)

    def update(self, frame: AudioFrame, dt: float) -> None:
        self._elapsed += dt
        dt = max(0.0001, min(0.1, dt))

        # --- Bass -> depth pressure (Smooth forward momentum) ---
        target_pressure = self.BASE_CRUISE + frame.bass * 2.2
        self._depth_pressure = _lerp(self._depth_pressure, target_pressure, 1.0 - math.exp(-dt * 2.8))

        # --- Mids -> lateral drift / camera angle ---
        target_lateral = (frame.mids - 0.3) * 0.75
        self._lateral_vel = _lerp(self._lateral_vel, target_lateral, 1.0 - math.exp(-dt * 2.0))
        self._camera_angle += self._lateral_vel * dt

        # --- Treble -> sparkle density ---
        self._treble_smoothed = _lerp(self._treble_smoothed, frame.treble, 1.0 - math.exp(-dt * 3.5))
        self._extra_far_target = int(self._treble_smoothed * self.MAX_FAR_EXTRA)

        # --- Multi-band spectral tracking ---
        b0 = max(frame.bass, sum(frame.spectrum[0:12]) / 12.0)
        b1 = sum(frame.spectrum[12:24]) / 12.0
        b2 = max(frame.mids, sum(frame.spectrum[24:38]) / 14.0)
        b3 = sum(frame.spectrum[38:50]) / 12.0
        b4 = max(frame.treble, sum(frame.spectrum[50:64]) / 14.0)
        raw_bands = (b0, b1, b2, b3, b4)
        for i in range(5):
            self._bands_smooth[i] = _lerp(self._bands_smooth[i], raw_bands[i], 1.0 - math.exp(-dt * 4.5))

        # --- RMS smoothed envelope ---
        self._rms_smoothed = _lerp(self._rms_smoothed, frame.rms, 1.0 - math.exp(-dt * 2.5))

        # --- Fast beat attack, smooth decay ---
        self._beat_impulse *= math.exp(-dt * 3.8)
        if frame.beat:
            self._beat_impulse = min(1.0, self._beat_impulse + 0.90)

        # Streak target responds immediately to rhythmic energy
        target_streak = 1.0 + (self._depth_pressure * 2.0) + (self._beat_impulse * 4.5)
        self._streak_target = _lerp(self._streak_target, target_streak, min(1.0, dt * 16.0))

        # --- Strong beat hyperspace compression event ---
        if frame.strong_beat and (self._elapsed - self._strong_event_t) > self.STRONG_EVENT_COOLDOWN:
            self._strong_event_t = self._elapsed
        if self._strong_event_t >= 0:
            age = self._elapsed - self._strong_event_t
            EVENT_DURATION = 0.45
            if age < EVENT_DURATION:
                phase = age / EVENT_DURATION
                self._strong_event_progress = math.sin(phase * math.pi)
            else:
                self._strong_event_progress = 0.0

        self._step_stars(dt)

    def _step_stars(self, dt: float) -> None:
        speed = self._depth_pressure + (self._beat_impulse * 1.4) + (self._strong_event_progress * 2.4)
        for idx, star in enumerate(self.stars):
            star.z -= speed * dt * 0.55
            if star.z <= 0.03:
                new = self._new_star(star.layer, idx)
                star.x, star.y, star.z = new.x, new.y, 1.0

        # Dynamic fine sparkle population
        far_extra_current = sum(1 for s in self.stars if s.layer == self.SPARKLE_LAYER)
        while far_extra_current < self._extra_far_target:
            self.stars.append(self._new_star(self.SPARKLE_LAYER, len(self.stars)))
            far_extra_current += 1
        if far_extra_current > self._extra_far_target:
            diff = far_extra_current - self._extra_far_target
            new_stars: list[_Star] = []
            removed = 0
            for s in reversed(self.stars):
                if s.layer == self.SPARKLE_LAYER and removed < diff:
                    removed += 1
                else:
                    new_stars.append(s)
            new_stars.reverse()
            self.stars = new_stars

    def _compute_star_color(self, star: _Star, depth_frac: float) -> tuple[int, int, int]:
        """Derives vibrant multi-hue star color from individual star band affinity."""
        band = star.band_affinity
        base_rgb = self.PALETTE[band]
        band_energy = self._bands_smooth[band]

        brightness = _clamp01(0.40 + 0.60 * self._rms_smoothed + band_energy * 0.50) * (0.25 + 0.75 * depth_frac)

        # High-energy near stars approach a brilliant bright white core
        if band_energy > 0.55 and depth_frac > 0.35:
            hot_frac = (band_energy - 0.55) / 0.45 * 0.85
            r = _lerp(base_rgb[0], 255, hot_frac)
            g = _lerp(base_rgb[1], 255, hot_frac)
            b = _lerp(base_rgb[2], 255, hot_frac)
        else:
            r, g, b = base_rgb

        return (
            int(_clamp01(r / 255.0) * 255 * brightness),
            int(_clamp01(g / 255.0) * 255 * brightness),
            int(_clamp01(b / 255.0) * 255 * brightness),
        )

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        # Deep cosmic void background
        surface.fill((2, 2, 6))
        cx, cy = self.w / 2.0, self.h / 2.0
        fov = min(self.w, self.h) * 0.95

        # -------------------------------------------------------------
        # 3D STAR PROJECTION & MULTI-PASS PHOTON TRAIL RENDERING
        # -------------------------------------------------------------
        cos_a, sin_a = math.cos(self._camera_angle), math.sin(self._camera_angle)
        fringe_active = self._strong_event_progress > 0.08 or (frame.strong_beat and self._beat_impulse > 0.35)
        fringe_offset = int(self._strong_event_progress * 4.0 + self._beat_impulse * 2.2) if fringe_active else 0

        streak_factor = self._streak_target + (self._strong_event_progress * 9.0)

        for star in self.stars:
            rx = star.x * cos_a - star.y * sin_a
            ry = star.x * sin_a + star.y * cos_a

            z = max(0.03, star.z)
            factor = fov / (z * 6.0)
            sx = cx + rx * factor
            sy = cy + ry * factor
            if not (-30 <= sx < self.w + 30 and -30 <= sy < self.h + 30):
                continue

            depth_frac = 1.0 - z
            color = self._compute_star_color(star, depth_frac)
            streak_len = streak_factor * depth_frac * 11.5

            # ---------------------------------------------------------
            # MULTI-PASS PHOTON TRAIL (Emissive Glow + Core + Head)
            # ---------------------------------------------------------
            if streak_len > 1.8 and (0 <= sx < self.w and 0 <= sy < self.h):
                tail_z = min(1.0, z + (0.022 * streak_factor * 0.35))
                tf = fov / (tail_z * 6.0)
                tx, ty = cx + rx * tf, cy + ry * tf

                # Layer 1: Outer Luminous Halo (Demoscene soft line blur)
                if depth_frac > 0.35:
                    halo_r = max(0, color[0] // 3)
                    halo_g = max(0, color[1] // 3)
                    halo_b = max(0, color[2] // 3)
                    halo_col = (halo_r, halo_g, halo_b)
                    halo_width = max(2, int(2.0 + depth_frac * 3.0))
                    pygame.draw.line(surface, halo_col, (tx, ty), (sx, sy), halo_width)

                # Layer 2: Saturated Colored Trail
                trail_width = max(1, int(1.0 + depth_frac * 1.8))
                pygame.draw.line(surface, color, (tx, ty), (sx, sy), trail_width)

                # Layer 3: Hot Emissive Star Head (Light Source Point)
                if depth_frac > 0.30:
                    head_radius = max(1, int(1.0 + depth_frac * 2.2))
                    # Outer soft head glow
                    pygame.draw.circle(surface, color, (int(sx), int(sy)), head_radius + 1)
                    # Hot white/bright inner core
                    white_core = (
                        min(255, color[0] + 120),
                        min(255, color[1] + 120),
                        min(255, color[2] + 120),
                    )
                    pygame.draw.circle(surface, white_core, (int(sx), int(sy)), max(1, head_radius - 1))
                else:
                    surface.set_at((int(sx), int(sy)), color)

                # Layer 4: Chromatic transient fringe on strong beats
                if fringe_offset > 0 and depth_frac > 0.45:
                    red_col = (min(255, color[0] + 100), max(0, color[1] - 40), max(0, color[2] - 40))
                    cyan_col = (max(0, color[0] - 40), min(255, color[1] + 80), min(255, color[2] + 100))
                    pygame.draw.line(surface, red_col, (tx - fringe_offset, ty), (sx - fringe_offset, sy), 1)
                    pygame.draw.line(surface, cyan_col, (tx + fringe_offset, ty), (sx + fringe_offset, sy), 1)
            else:
                # Distant Stars / Sparkles: Crisp, pin-point stars without fog
                if 0 <= sx < self.w and 0 <= sy < self.h:
                    if depth_frac > 0.5:
                        pygame.draw.circle(surface, color, (int(sx), int(sy)), 2)
                    else:
                        surface.set_at((int(sx), int(sy)), color)

        # -------------------------------------------------------------
        # SOFT CORNER VIGNETTE
        # -------------------------------------------------------------
        if self._vignette_surf:
            surface.blit(self._vignette_surf, (0, 0))

    def get_debug_state(self) -> dict:
        """Exposes internal state for automated tests — not part of the Visualizer contract."""
        return {
            "depth_pressure": self._depth_pressure,
            "lateral_vel": self._lateral_vel,
            "camera_angle": self._camera_angle,
            "treble_smoothed": self._treble_smoothed,
            "color_bias": self._color_bias,
            "beat_impulse": self._beat_impulse,
            "streak_target": self._streak_target,
            "bands_smooth": self._bands_smooth,
            "strong_event_progress": self._strong_event_progress,
            "star_count": len(self.stars),
        }
