"""
ToroidAMP - Production ToroidAMP Floor Visualizer
JACK FINAL PERCEPTUAL TUNING: Dark baseline at silence/low energy, shaped non-linear
activation curve, true emissive cell hierarchy (saturated body + hot white core + white border),
and explosive dynamic range under real musical drive.
"""

import math

import pygame

from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_pt(p1: tuple[int, int], p2: tuple[int, int], t: float) -> tuple[int, int]:
    return (int(p1[0] + (p2[0] - p1[0]) * t), int(p1[1] + (p2[1] - p1[1]) * t))


class _Pulse:
    """A propagating grid-wave, launched by a beat, traveling outward from an origin cell."""
    __slots__ = ("origin_row", "origin_col", "radius", "speed", "strength", "width")

    def __init__(self, origin_row: float, origin_col: float, speed: float, strength: float, width: float):
        self.origin_row = origin_row
        self.origin_col = origin_col
        self.radius = 0.0
        self.speed = speed
        self.strength = strength
        self.width = width


class ToroidAMPFloorVisualizer(Visualizer):
    """
    3D Perspective Wireframe Floor with Dark Silence Baseline, Shaped Musical
    Activation, Emissive Layered Tiles, and Synchronous Forward Grid Motion.
    """

    ROWS = 18
    COLS = 22
    DECAY_PER_SEC = 2.80      # organic natural phosphor fade to clean black baseline
    ATTACK_RATE = 18.0        # punchy instantaneous attack
    PULSE_SPEED = 6.0         # grid units / second
    PULSE_WIDTH = 2.4         # wave width in grid units
    MAX_ACTIVE_PULSES = 6

    # Authoritative neon spectral palette
    PALETTE = (
        (255, 10, 140),   # 0: Sub/Bass -> Hot Neon Magenta / Crimson
        (0, 140, 255),    # 1: Low-Mid -> Electric Cobalt Blue
        (0, 245, 255),    # 2: Mids -> Laser Cyan
        (40, 255, 100),   # 3: Upper-Mid -> Fluorescent Green
        (255, 235, 35),   # 4: Treble -> Electric Solar Yellow
    )

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)

        # tile_energy[row][col] — persistent illumination state (0.0 = dark baseline)
        self.tile_energy = [[0.0 for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.tile_target = [[0.0 for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.tile_band = [[0 for _ in range(self.COLS)] for _ in range(self.ROWS)]

        self._pulses: list[_Pulse] = []
        self._bass_smoothed = 0.0
        self._mids_smoothed = 0.0
        self._treble_smoothed = 0.0
        self._beat_impulse = 0.0
        self._elapsed = 0.0
        self._grid_scroll = 0.0

    def get_name(self) -> str:
        return "ToroidAMP Floor"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def _shape_activation(self, value: float, threshold: float = 0.10, power: float = 1.35) -> float:
        """Applies a noise-floor dead zone and shaped non-linear activation response."""
        if value <= threshold:
            return 0.0
        norm = (value - threshold) / (1.0 - threshold)
        return float(norm ** power)

    def _spectrum_to_targets(self, frame: AudioFrame) -> None:
        """
        Maps 64 spectrum bins to floor targets with a strict noise floor.
        Silence or near-silence produces strictly 0.0 across all cells.
        """
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self.tile_target[r][c] = 0.0

        half_cols = self.COLS // 2

        # 1. 64-Bin FFT Spectral Distribution with Shaped Activation
        for i, raw_mag in enumerate(frame.spectrum):
            mag = self._shape_activation(raw_mag, threshold=0.12, power=1.35)
            if mag <= 0.005:
                continue

            if i < 14:
                band = 0
                row = self.ROWS - 1 - int((i / 13.0) * (self.ROWS // 2))
                spread = ((i * 2) % 7) - 3
                col = max(0, min(self.COLS - 1, half_cols + spread))
            elif i < 28:
                band = 1
                row = self.ROWS // 2 + int(((i - 14) / 14.0) * (self.ROWS // 3))
                spread = ((i * 3) % 11) - 5
                col = max(0, min(self.COLS - 1, half_cols + spread))
            elif i < 44:
                band = 2
                row = self.ROWS // 3 + int(((i - 28) / 16.0) * (self.ROWS // 2))
                spread = ((i * 5) % (self.COLS - 2)) - (self.COLS // 2 - 1)
                col = max(0, min(self.COLS - 1, half_cols + spread))
            elif i < 54:
                band = 3
                row = int(((i - 44) / 10.0) * (self.ROWS // 2))
                col = (i * 7) % self.COLS
            else:
                band = 4
                row = int(((i - 54) / 9.0) * (self.ROWS // 2))
                side = (i % 2)
                col = (i % 4) if side == 0 else (self.COLS - 1 - (i % 4))

            self.tile_band[row][col] = band
            self.tile_target[row][col] = max(self.tile_target[row][col], mag)

            # Neighbor resonance only for strong energetic peaks
            if mag > 0.25:
                for dc in (-1, 1):
                    nc = col + dc
                    if 0 <= nc < self.COLS:
                        self.tile_target[row][nc] = max(self.tile_target[row][nc], mag * 0.50)
                        self.tile_band[row][nc] = band

        # 2. Near-Field Bass Presence (Only on Real Bass Energy)
        bass_shaped = self._shape_activation(frame.bass, threshold=0.18, power=1.4)
        if bass_shaped > 0.01:
            near_start = self.ROWS // 2
            for r in range(near_start, self.ROWS):
                depth_weight = (r - near_start) / max(1, (self.ROWS - 1 - near_start))
                cell_bass = bass_shaped * (0.45 + 0.55 * depth_weight)
                for c in range(half_cols - 4, half_cols + 4):
                    if 0 <= c < self.COLS:
                        self.tile_target[r][c] = max(self.tile_target[r][c], cell_bass)
                        if cell_bass > 0.20:
                            self.tile_band[r][c] = 0

        # 3. Mid-Field Melodic Body (Only on Real Mids Energy)
        mids_shaped = self._shape_activation(frame.mids, threshold=0.22, power=1.4)
        if mids_shaped > 0.01:
            mid_lo, mid_hi = self.ROWS // 4, (3 * self.ROWS) // 4
            for r in range(mid_lo, mid_hi):
                cell_mids = mids_shaped * 0.70
                for c in range(half_cols - 6, half_cols + 6):
                    if 0 <= c < self.COLS:
                        self.tile_target[r][c] = max(self.tile_target[r][c], cell_mids)
                        if cell_mids > 0.25 and self.tile_band[r][c] == 0:
                            self.tile_band[r][c] = 2

        # 4. Flank & Horizon Sparkle Accents (Only on Real Treble Energy)
        treble_shaped = self._shape_activation(frame.treble, threshold=0.28, power=1.5)
        if treble_shaped > 0.01:
            accent_count = int(treble_shaped * 10)
            phase = int(self._elapsed * 10) % self.ROWS
            for k in range(accent_count):
                r = (phase + k * 2) % self.ROWS
                left_c = k % 4
                right_c = self.COLS - 1 - (k % 4)
                accent_val = treble_shaped * 0.95
                self.tile_target[r][left_c] = max(self.tile_target[r][left_c], accent_val)
                self.tile_target[r][right_c] = max(self.tile_target[r][right_c], accent_val)
                self.tile_band[r][left_c] = 4
                self.tile_band[r][right_c] = 4

    def _peak_bin_position(self, frame: AudioFrame) -> tuple[float, float]:
        peak_i = max(range(64), key=lambda i: frame.spectrum[i])
        frac = peak_i / 63.0
        row = (1.0 - frac) * (self.ROWS - 1)
        half_cols = self.COLS // 2
        col = half_cols + ((peak_i % 7) - 3)
        return float(row), float(max(0, min(self.COLS - 1, col)))

    def update(self, frame: AudioFrame, dt: float) -> None:
        dt = max(0.0001, min(0.1, dt))
        self._elapsed += dt

        # Smooth continuous signals
        self._bass_smoothed = _lerp(self._bass_smoothed, frame.bass, 1.0 - math.exp(-dt * 3.0))
        self._mids_smoothed = _lerp(self._mids_smoothed, frame.mids, 1.0 - math.exp(-dt * 2.0))
        self._treble_smoothed = _lerp(self._treble_smoothed, frame.treble, 1.0 - math.exp(-dt * 3.5))

        # Synchronous forward grid motion
        scroll_speed = 0.55 + self._mids_smoothed * 0.95 + self._bass_smoothed * 0.45
        self._grid_scroll = (self._grid_scroll + dt * scroll_speed) % 1.0

        self._beat_impulse *= math.exp(-dt * 4.5)
        if frame.beat:
            self._beat_impulse = min(1.0, self._beat_impulse + 0.70)

        self._spectrum_to_targets(frame)

        # Beat -> local propagating wave pulse
        if frame.beat and len(self._pulses) < self.MAX_ACTIVE_PULSES:
            origin_row, origin_col = self._peak_bin_position(frame)
            self._pulses.append(_Pulse(origin_row, origin_col, self.PULSE_SPEED, strength=1.10, width=self.PULSE_WIDTH))

        # Strong beat -> multi-origin traveling wave burst
        if frame.strong_beat:
            half_c = self.COLS / 2.0
            self._pulses = self._pulses[-(self.MAX_ACTIVE_PULSES - 3):]
            self._pulses.append(_Pulse(self.ROWS - 1, half_c, self.PULSE_SPEED * 1.45, strength=1.55, width=self.PULSE_WIDTH * 1.6))
            self._pulses.append(_Pulse(self.ROWS // 2, 1.0, self.PULSE_SPEED * 1.30, strength=1.20, width=self.PULSE_WIDTH))
            self._pulses.append(_Pulse(self.ROWS // 2, self.COLS - 2.0, self.PULSE_SPEED * 1.30, strength=1.20, width=self.PULSE_WIDTH))

        # Advance pulses with physical wave attenuation
        alive_pulses: list[_Pulse] = []
        max_dist = math.hypot(self.ROWS, self.COLS)
        for pulse in self._pulses:
            pulse.radius += pulse.speed * dt
            pulse.strength *= math.exp(-dt * 2.2)
            if pulse.radius <= max_dist + pulse.width and pulse.strength > 0.02:
                alive_pulses.append(pulse)
                min_r = max(0, int(pulse.origin_row - pulse.radius - pulse.width))
                max_r = min(self.ROWS, int(pulse.origin_row + pulse.radius + pulse.width + 1))
                for r in range(min_r, max_r):
                    for c in range(self.COLS):
                        dist = math.hypot(r - pulse.origin_row, c - pulse.origin_col)
                        diff = abs(dist - pulse.radius)
                        if diff <= pulse.width:
                            falloff = 1.0 - (diff / pulse.width)
                            self.tile_target[r][c] = max(self.tile_target[r][c], pulse.strength * falloff)
        self._pulses = alive_pulses

        # Attack / Decay memory with clean decay to dark baseline
        for r in range(self.ROWS):
            for c in range(self.COLS):
                target = self.tile_target[r][c]
                cur = self.tile_energy[r][c]
                if target > cur:
                    cur += (target - cur) * min(1.0, dt * self.ATTACK_RATE)
                else:
                    cur *= math.exp(-dt * self.DECAY_PER_SEC)
                if cur < 0.01:
                    cur = 0.0
                self.tile_energy[r][c] = cur

    def _get_emissive_colors(self, r: int, c: int, energy: float) -> tuple[tuple[int, int, int], tuple[int, int, int] | None, tuple[int, int, int]]:
        """
        Emissive visual hierarchy:
        Returns: (body_color, hot_core_color_or_None, border_color)
        """
        band = self.tile_band[r][c]
        base_col = self.PALETTE[min(4, max(0, band))]
        color_energy = _clamp01(energy)

        # 1. Saturated base body fill (zero floor at silence)
        brightness = color_energy ** 0.85
        body_r = int(_clamp01(base_col[0] / 255.0) * 255 * brightness)
        body_g = int(_clamp01(base_col[1] / 255.0) * 255 * brightness)
        body_b = int(_clamp01(base_col[2] / 255.0) * 255 * brightness)
        body_color = (body_r, body_g, body_b)

        # 2. Hot bright core for energetic cells
        if color_energy > 0.45:
            white_frac = (color_energy - 0.45) / 0.55
            core_r = int(_lerp(base_col[0], 255, white_frac * 0.95))
            core_g = int(_lerp(base_col[1], 255, white_frac * 0.95))
            core_b = int(_lerp(base_col[2], 255, white_frac * 0.95))
            hot_core = (core_r, core_g, core_b)
        else:
            hot_core = None

        # 3. Crisp outline border
        if color_energy > 0.60:
            border_col = (255, 255, 255)
        else:
            border_brightness = color_energy
            border_col = (
                int(base_col[0] * border_brightness),
                int(base_col[1] * border_brightness),
                int(base_col[2] * border_brightness),
            )

        return body_color, hot_core, border_col

    def _project_point(self, row_norm: float, col_norm: float, horizon_y: float) -> tuple[int, int]:
        """Projects a 3D perspective grid point onto 2D screen coordinates."""
        cx = self.w / 2.0
        floor_h = self.h - horizon_y

        depth_y = (max(0.0, min(1.0, row_norm)) ** 1.75) * floor_h
        screen_y = horizon_y + depth_y

        depth_ratio = max(0.01, depth_y / max(1.0, floor_h))
        top_span = self.w * 0.18
        bottom_span = self.w * 1.10
        span = _lerp(top_span, bottom_span, depth_ratio)

        screen_x = cx + col_norm * (span / 2.0)
        return int(screen_x), int(screen_y)

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        # Deep synthwave void background
        surface.fill((2, 2, 7))

        # Dynamic subtle horizon breathing
        base_horizon = self.h * 0.36
        horizon_y = base_horizon - (self._bass_smoothed * self.h * 0.035)

        # -------------------------------------------------------------
        # SYNCHRONIZED PERSPECTIVE GRID VERTICES (Motion-Locked)
        # -------------------------------------------------------------
        half_cols = self.COLS / 2.0
        grid_pts: list[list[tuple[int, int]]] = []
        for r in range(self.ROWS + 1):
            offset_r = (r + self._grid_scroll) / float(self.ROWS + 1)
            r_norm = min(1.0, offset_r)
            row_pts = []
            for c in range(self.COLS + 1):
                col_norm = (c - half_cols) / half_cols
                row_pts.append(self._project_point(r_norm, col_norm, horizon_y))
            grid_pts.append(row_pts)

        # -------------------------------------------------------------
        # 1. RENDER TRUE EMISSIVE REACTIVE TILES (Layered Glow)
        # -------------------------------------------------------------
        for r in range(self.ROWS):
            for c in range(self.COLS):
                energy = self.tile_energy[r][c]
                if energy <= 0.008:
                    continue

                # Exact grid cell corners
                p0 = grid_pts[r][c]
                p1 = grid_pts[r][c + 1]
                p2 = grid_pts[r + 1][c + 1]
                p3 = grid_pts[r + 1][c]

                # Center of the quad
                q_cx = (p0[0] + p1[0] + p2[0] + p3[0]) // 4
                q_cy = (p0[1] + p1[1] + p2[1] + p3[1]) // 4
                q_center = (q_cx, q_cy)

                # 5% Inset for clean cell framing
                ip0 = _lerp_pt(p0, q_center, 0.05)
                ip1 = _lerp_pt(p1, q_center, 0.05)
                ip2 = _lerp_pt(p2, q_center, 0.05)
                ip3 = _lerp_pt(p3, q_center, 0.05)

                body_color, hot_core, border_color = self._get_emissive_colors(r, c, energy)
                points = [ip0, ip1, ip2, ip3]

                # 1. Base saturated neon body
                pygame.draw.polygon(surface, body_color, points)

                # 2. Hot bright inner core for emissive punch
                if hot_core:
                    cp0 = _lerp_pt(ip0, q_center, 0.35)
                    cp1 = _lerp_pt(ip1, q_center, 0.35)
                    cp2 = _lerp_pt(ip2, q_center, 0.35)
                    cp3 = _lerp_pt(ip3, q_center, 0.35)
                    pygame.draw.polygon(surface, hot_core, [cp0, cp1, cp2, cp3])

                # 3. Crisp outline border
                pygame.draw.polygon(surface, border_color, points, 1)

        # -------------------------------------------------------------
        # 2. RENDER PERSPECTIVE WIREFRAME GRID (Dormant Clean Structure)
        # -------------------------------------------------------------
        grid_base_color = (0, 240, 255)

        # Perspective column lines
        for c in range(self.COLS + 1):
            top_pt = grid_pts[0][c]
            bot_pt = grid_pts[self.ROWS][c]

            col_dist = abs(c - half_cols) / half_cols
            brightness = max(0.12, 0.45 - col_dist * 0.25 + self._bass_smoothed * 0.20)
            c_rgb = (int(grid_base_color[0] * brightness),
                     int(grid_base_color[1] * brightness),
                     int(grid_base_color[2] * brightness))
            pygame.draw.line(surface, c_rgb, top_pt, bot_pt, 1)

        # Perspective horizontal row lines (synchronized with moving grid)
        for r in range(self.ROWS + 1):
            offset_r = (r + self._grid_scroll) / float(self.ROWS + 1)
            r_norm = min(1.0, offset_r)
            left_pt = grid_pts[r][0]
            right_pt = grid_pts[r][self.COLS]

            depth_brightness = (r_norm ** 1.3) * (0.45 + self._beat_impulse * 0.25)
            r_rgb = (int(grid_base_color[0] * depth_brightness),
                     int(grid_base_color[1] * depth_brightness),
                     int(grid_base_color[2] * depth_brightness))
            if depth_brightness > 0.04:
                pygame.draw.line(surface, r_rgb, left_pt, right_pt, 1)

    def get_debug_state(self) -> dict:
        """Exposes internal state for automated tests — not part of the Visualizer contract."""
        total_energy = sum(sum(row) for row in self.tile_energy)
        near_field_energy = sum(sum(row) for row in self.tile_energy[self.ROWS // 2:])
        horizon_energy = sum(sum(row) for row in self.tile_energy[:self.ROWS // 4])
        active_cell_count = sum(1 for row in self.tile_energy for e in row if e > 0.01)
        return {
            "total_energy": total_energy,
            "near_field_energy": near_field_energy,
            "horizon_energy": horizon_energy,
            "active_cell_count": active_cell_count,
            "active_pulses": len(self._pulses),
            "tile_energy": self.tile_energy,
            "tile_band": self.tile_band,
            "grid_scroll": self._grid_scroll,
            "bass_smoothed": self._bass_smoothed,
            "mids_smoothed": self._mids_smoothed,
            "treble_smoothed": self._treble_smoothed,
        }
