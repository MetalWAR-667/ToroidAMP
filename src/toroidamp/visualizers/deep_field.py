"""
ToroidAMP - Production Starfield: Deep Field Visualizer
Hyperspace warp tunnel. Stars are projected as a radial 3D field: each
star owns a fixed screen-space direction and a depth that falls toward
the viewer, so it accelerates outward with a long luminous warpline.
Beat energy surges the warp, and strong beats unfold a hyperspace
"jump" flash with chromatic fringe. Silence keeps a steady cruise —
the field must not fully stop.
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
    Hyperspace star tunnel with long radial warplines, emissive star
    heads, and multi-family spectral color gradation. The field always
    cruises; music pushes it into warp; strong beats trigger jumps.
    """

    NEAR_LAYER, MID_LAYER, FAR_LAYER = 0, 1, 2
    SPARKLE_LAYER = 100
    LAYER_COUNTS = {NEAR_LAYER: 64, MID_LAYER: 120, FAR_LAYER: 220}
    MAX_FAR_EXTRA = 120

    BASE_CRUISE = 0.35
    STRONG_EVENT_COOLDOWN = 1.2

    # Trail sampling window (seconds of depth-ahead the warpline spans)
    WARP_TRAIL_TIME = 0.14

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

        # Pre-rendered radial warp "speed lines" glow and focal radial bloom for jump flash
        self._warp_rays: pygame.Surface | None = None
        self._radial_flash_surf: pygame.Surface | None = None

        self._vignette_surf: pygame.Surface | None = None
        self._build_vignette()
        self._build_warp_rays()
        self._build_jump_flash()

        self.stars: list[_Star] = []
        self._spawn_initial_stars()

    def get_name(self) -> str:
        return "Deep Field"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self._build_vignette()
        self._build_warp_rays()
        self._build_jump_flash()

    def _build_jump_flash(self) -> None:
        """Pre-renders a soft concentric radial bloom centered at the vanishing point."""
        w, h = self.w, self.h
        self._radial_flash_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w / 2.0, h / 2.0
        max_r = math.hypot(cx, cy) * 0.75
        steps = 16
        for step in range(steps, 0, -1):
            t = step / float(steps)
            r = max_r * t
            # Hot core (electric cyan/white) that falls off quickly toward the edges
            alpha = int(12 * (1.0 - t) ** 1.8)
            col = (
                int(_lerp(120, 240, (1.0 - t) ** 2)),
                int(_lerp(180, 255, (1.0 - t) ** 2)),
                255,
                alpha,
            )
            pygame.draw.circle(self._radial_flash_surf, col, (int(cx), int(cy)), int(r))

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

    def _build_warp_rays(self) -> None:
        """Radial hyperspace ray overlay used only during a strong-beat jump."""
        w, h = self.w, self.h
        self._warp_rays = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w / 2.0, h / 2.0
        half = max(w, h) * 0.5
        rays = 72
        for i in range(rays):
            ang = (i / rays) * 2.0 * math.pi
            length = half * self.rng.uniform(0.75, 1.0)
            # Converge slightly toward center for a tunnel feel
            ex = cx + math.cos(ang) * length * 0.92
            ey = cy + math.sin(ang) * length * 0.92
            alpha = self.rng.randint(30, 70)
            pygame.draw.line(self._warp_rays, (120, 200, 255, alpha),
                             (cx, cy), (ex, ey), 1)

    def _spawn_initial_stars(self) -> None:
        self.stars.clear()
        for layer, count in self.LAYER_COUNTS.items():
            for i in range(count):
                self.stars.append(self._new_star(layer, i))

    def _new_star(self, layer: int, index: int = 0) -> _Star:
        """Uniform disc placement so the far field is a field, not a blob."""
        ang = self.rng.uniform(0.0, 2.0 * math.pi)
        r = math.sqrt(self.rng.random())          # uniform over the disc
        x = math.cos(ang) * r
        y = math.sin(ang) * r
        z = self.rng.uniform(0.06, 1.0)
        if layer == self.NEAR_LAYER:
            band = (index % 3)
        elif layer == self.MID_LAYER:
            band = ((index % 4) + 1) % 5
        elif layer == self.FAR_LAYER:
            band = ((index % 3) + 2) % 5
        else:
            band = 4 if (index % 2 == 0) else 2
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
            self._beat_impulse = min(1.0, self._beat_impulse + 0.95)

        # Streak target responds immediately to rhythmic energy
        target_streak = 1.0 + (self._depth_pressure * 2.0) + (self._beat_impulse * 5.0)
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
        # Forward warp speed (depth-units/sec). Beats and jumps push harder.
        speed = self._depth_pressure + (self._beat_impulse * 1.6) + (self._strong_event_progress * 2.8)
        for idx, star in enumerate(self.stars):
            star.z -= speed * dt * 0.55
            if star.z <= 0.03:
                new = self._new_star(star.layer, idx)
                # Recycle to the far plane with a fresh direction
                star.x, star.y, star.z = new.x, new.y, 1.0

        # Dynamic fine sparkle population (density from treble)
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

        # Deep cosmic void background (hidden flash handled below)
        surface.fill((2, 2, 6))
        cx, cy = self.w / 2.0, self.h / 2.0
        fov = min(self.w, self.h) * 0.5

        cos_a, sin_a = math.cos(self._camera_angle), math.sin(self._camera_angle)
        fringe_offset = int(self._strong_event_progress * 4.0 + self._beat_impulse * 2.2)
        has_fringe = fringe_offset > 0

        # Warp speed in depth-units/sec (reuse the step maths so trail matches motion)
        warp_speed = self._depth_pressure + (self._beat_impulse * 1.6) + (self._strong_event_progress * 2.8)
        trail_depth = min(0.6, warp_speed * self.WARP_TRAIL_TIME)
        streak_factor = self._streak_target + (self._strong_event_progress * 9.0)

        # Stable rotation basis
        rot_cos_a, rot_sin_a = cos_a, sin_a

        for star in self.stars:
            rx = star.x * rot_cos_a - star.y * rot_sin_a
            ry = star.x * rot_sin_a + star.y * rot_cos_a

            z = max(0.03, star.z)
            factor = fov / (z * 4.0)
            sx = cx + rx * factor
            sy = cy + ry * factor
            if not (-40 <= sx < self.w + 40 and -40 <= sy < self.h + 40):
                continue

            depth_frac = 1.0 - z
            color = self._compute_star_color(star, depth_frac)
            # Nearer stars leave longer, brighter warplines
            warp_len = streak_factor * depth_frac * fov * 0.42

            # ---------------------------------------------------------
            # WARP LINE + EMISSIVE HEAD
            # ---------------------------------------------------------
            near = 0 <= sx < self.w and 0 <= sy < self.h

            if warp_len > 2.0 and near:
                # Compute a head further "in front" along the same direction.
                z_head = max(0.03, z - trail_depth * 0.5)
                hf = fov / (z_head * 4.0)
                hx, hy = cx + rx * hf, cy + ry * hf

                # Clamp to screen to avoid runaway tails
                tx, ty = sx, sy
                dx, dy = hx - sx, hy - sy
                seg_len = math.hypot(dx, dy)
                if seg_len > 1e-6:
                    # Only take the segment that stays on screen (short tail)
                    take = min(1.0, warp_len / max(1.0, seg_len)) if seg_len > 0 else 1.0
                    tx = sx + dx * take
                    ty = sy + dy * take

                # Layer 1: Outer luminous halo (soft defocused glow)
                if depth_frac > 0.30:
                    halo_col = (color[0] // 3, color[1] // 3, color[2] // 3)
                    halo_w = max(2, int(2.0 + depth_frac * 3.0))
                    pygame.draw.line(surface, halo_col, (tx, ty), (sx, sy), halo_w)

                # Layer 2: Saturated colored warpline
                trail_w = max(1, int(1.0 + depth_frac * 2.0))
                pygame.draw.line(surface, color, (tx, ty), (sx, sy), trail_w)

                # Chromatic fringe on strong beats (RGB split glitch)
                if has_fringe and depth_frac > 0.35:
                    red_col = (min(255, color[0] + 100), max(0, color[1] - 40), max(0, color[2] - 40))
                    cyan_col = (max(0, color[0] - 40), min(255, color[1] + 80), min(255, color[2] + 100))
                    pygame.draw.line(surface, red_col, (tx - fringe_offset, ty), (sx - fringe_offset, sy), 1)
                    pygame.draw.line(surface, cyan_col, (tx + fringe_offset, ty), (sx + fringe_offset, sy), 1)

                # Layer 3: Hot emissive star head
                if depth_frac > 0.30:
                    head_r = max(1, int(1.0 + depth_frac * 2.2))
                    pygame.draw.circle(surface, color, (int(sx), int(sy)), head_r + 1)
                    white_core = (
                        min(255, color[0] + 120),
                        min(255, color[1] + 120),
                        min(255, color[2] + 120),
                    )
                    pygame.draw.circle(surface, white_core, (int(sx), int(sy)), max(1, head_r - 1))
                else:
                    surface.set_at((int(sx), int(sy)), color)
            else:
                # Distant / far stars: crisp pin-points
                if near:
                    if depth_frac > 0.5:
                        pygame.draw.circle(surface, color, (int(sx), int(sy)), 2)
                    elif depth_frac > 0.15:
                        surface.set_at((int(sx), int(sy)), color)

        # -------------------------------------------------------------
        # HYPERSPACE JUMP FLASH & SHOCKWAVE (strong beat)
        # -------------------------------------------------------------
        if self._strong_event_progress > 0.02:
            # 1. Soft focal radial bloom centered at vanishing point (cached surface, zero per-frame allocs)
            if self._radial_flash_surf:
                flash_alpha = int(220 * (self._strong_event_progress ** 1.3))
                if flash_alpha > 0:
                    bloom = self._radial_flash_surf.copy()
                    bloom.set_alpha(flash_alpha)
                    surface.blit(bloom, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

            # 2. Expanding shockwave ring that rushes outward from vanishing point
            ring_phase = self._strong_event_progress  # 0.0 -> 1.0 -> 0.0
            max_radius = math.hypot(cx, cy) * 0.95
            ring_r = int(max_radius * (ring_phase ** 0.85))
            if ring_r > 3:
                ring_alpha = int(180 * math.sin(ring_phase * math.pi))
                ring_thick = max(1, int(3.0 * (1.0 - ring_phase) + 1.0))
                ring_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
                ring_color = (130, 220, 255, ring_alpha)
                pygame.draw.circle(ring_surf, ring_color, (int(cx), int(cy)), ring_r, ring_thick)
                surface.blit(ring_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

            # 3. Hyperspace speed line rays
            if self._warp_rays and self._strong_event_progress > 0.10:
                ray_alpha = int(180 * self._strong_event_progress)
                rays = self._warp_rays.copy()
                rays.set_alpha(ray_alpha)
                surface.blit(rays, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

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
