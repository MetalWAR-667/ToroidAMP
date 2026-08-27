"""
Visualizer Lab II — Experiment 3: MATRIX WING COMMANDER

MUSICAL THESIS
    Matrix rain. Spaceships. Music. No further conceptual justification is
    required. The implementation must be musically intelligent: randomness
    provides variation, music provides causality.

DONOR DNA
    MetalWar-Installer effects.py:2072 PeaceCodeRain — pre-rendered
    per-glyph cache technique (16 hex chars x 2 colors, built once),
    reused here. MetalWar-Installer effects.py:2173 PraxisEvent
    (spawn_xwing/draw_xwing_3d, spawn_ywing_squad/draw_ywing_3d) —
    waypoint-route ship flight concept reused; the donor's actual routes
    were hand-authored for a specific installer climax timeline and are
    NOT reused verbatim. Installer narrative coupling (install state,
    bundled PNGs, specific SFX) is entirely discarded.

CATEGORY: BECAUSE WE CAN. Culturally protected — do not remove the ships.

# Why?
# Because we could.
"""

import math
import random

import pygame

from toroidamp.visualizers.base import Visualizer
from toroidamp.analysis.audio_frame import AudioFrame

HEX_CHARS = "0123456789ABCDEF"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class _RainColumn:
    __slots__ = ("x", "y", "speed", "length", "chars")

    def __init__(self, x, y, speed, length, chars):
        self.x, self.y, self.speed, self.length, self.chars = x, y, speed, length, chars


class _ShipPass:
    """One scripted waypoint flight, launched by strong_beat, never by free timer/random."""
    __slots__ = ("route", "progress", "speed_mul", "ship_kind", "offsets")

    def __init__(self, route, speed_mul, ship_kind, ship_count):
        self.route = route
        self.progress = 0.0
        self.speed_mul = speed_mul
        self.ship_kind = ship_kind
        # small formation offsets (fractional screen units) so a "pass" reads as a group
        self.offsets = [((-0.06 * (i - ship_count // 2)), 0.03 * (i % 2)) for i in range(ship_count)]


# Waypoint routes in fractional (x, y, z) space — z is a depth/scale factor (perspective 1/z),
# not pixels, so every route survives arbitrary resize unchanged.
ROUTES = {
    "diagonal_pass": [(-0.15, 0.15, 3.0), (0.5, 0.5, 1.0), (1.15, 0.85, 3.0)],
    "arc_barrel": [(-0.1, 0.75, 3.5), (0.35, 0.15, 1.4), (0.7, 0.35, 1.0), (1.1, 0.6, 3.0)],
    "formation_v": [(-0.1, 0.4, 3.5), (0.5, 0.55, 0.9), (1.1, 0.35, 3.5)],
    "crossing": [(1.15, 0.2, 3.0), (0.5, 0.5, 1.0), (-0.15, 0.8, 3.0)],
}
ROUTE_NAMES = list(ROUTES.keys())


class MatrixWingCommanderVisualizer(Visualizer):
    COLUMN_TARGET_BASE = 18   # silence: sparse minimal drift, never fully stops
    COLUMN_TARGET_MAX_EXTRA = 46  # treble grows density up to this many extra columns
    PASS_COOLDOWN = 1.2  # seconds — strong_beat formation passes can't overlap/spam
    PASS_DURATION = 2.6  # seconds for one waypoint route to complete

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self.rng = random.Random(2049)

        self._glyph_cache: dict[tuple[str, tuple], pygame.Surface] = {}
        self._font = pygame.font.SysFont("consolas", 16) if pygame.font.get_init() else None
        self._build_glyph_cache()

        self.columns: list[_RainColumn] = []
        self._spawn_columns(self.COLUMN_TARGET_BASE)

        self._fall_speed_smoothed = 0.4
        self._density_smoothed = 0.0
        self._distortion_smoothed = 0.0
        self._beat_flash = 0.0

        self._elapsed = 0.0
        self._last_pass_t = -999.0
        self._passes: list[_ShipPass] = []

    def get_name(self) -> str:
        return "Matrix Wing Commander (experimental)"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    # -- rain -----------------------------------------------------------

    def _build_glyph_cache(self):
        if self._font is None:
            return
        for ch in HEX_CHARS:
            for color in ((60, 255, 120), (200, 255, 220)):  # body, bright head
                self._glyph_cache[(ch, color)] = self._font.render(ch, False, color)

    def _spawn_columns(self, count: int):
        for _ in range(count):
            self.columns.append(self._new_column())

    def _new_column(self) -> _RainColumn:
        x = self.rng.uniform(0.0, 1.0)
        y = self.rng.uniform(-1.0, 0.0)
        speed = self.rng.uniform(0.25, 0.55)
        length = self.rng.randint(4, 14)
        chars = [self.rng.choice(HEX_CHARS) for _ in range(length)]
        return _RainColumn(x, y, speed, length, chars)

    def _update_rain(self, frame: AudioFrame, dt: float):
        # mids -> fall velocity (SMOOTH)
        target_speed = 0.35 + frame.mids * 1.4
        self._fall_speed_smoothed += (target_speed - self._fall_speed_smoothed) * min(1.0, dt * 2.5)

        # treble -> character density / highlight probability (SMOOTH)
        self._density_smoothed += (frame.treble - self._density_smoothed) * min(1.0, dt * 2.0)
        target_columns = self.COLUMN_TARGET_BASE + int(self._density_smoothed * self.COLUMN_TARGET_MAX_EXTRA)
        while len(self.columns) < target_columns:
            self.columns.append(self._new_column())
        while len(self.columns) > target_columns:
            self.columns.pop()

        # bass -> subtle depth-pressure horizontal distortion per column (SMOOTH)
        self._distortion_smoothed += (frame.bass - self._distortion_smoothed) * min(1.0, dt * 1.5)

        # beat -> short luminance/velocity impulse (FAST impulse + decay)
        self._beat_flash *= math.exp(-dt * 6.0)
        if frame.beat:
            self._beat_flash = min(1.0, self._beat_flash + 0.5)

        for i, col in enumerate(self.columns):
            # spectrum -> regional column behavior: each column samples one spectrum bin,
            # so columns are NOT identical — a bass-heavy song and a treble-heavy song at
            # the same fall speed still light up different columns.
            bin_i = i % 64
            band_energy = frame.spectrum[bin_i]
            col.y += (col.speed + self._fall_speed_smoothed * 0.6 + self._beat_flash * 0.6) * dt * (0.6 + band_energy)
            if col.y - col.length * 0.02 > 1.0:
                new = self._new_column()
                col.x, col.y, col.speed, col.length, col.chars = new.x, new.y, new.speed, new.length, new.chars

    # -- ships ------------------------------------------------------------

    def _update_ships(self, frame: AudioFrame, dt: float):
        self._elapsed += dt

        # Why?
        # Because we could.
        if frame.strong_beat and (self._elapsed - self._last_pass_t) > self.PASS_COOLDOWN:
            self._last_pass_t = self._elapsed
            route_name = self.rng.choice(ROUTE_NAMES)   # music decides WHEN, randomness decides WHICH
            ship_kind = self.rng.choice(("xwing", "ywing"))
            ship_count = self.rng.randint(2, 4)
            self._passes.append(_ShipPass(ROUTES[route_name], speed_mul=1.0, ship_kind=ship_kind, ship_count=ship_count))

        # beat -> maneuver impulse: nudges existing passes forward faster, does not spawn new ones
        maneuver_boost = 1.6 if frame.beat else 1.0
        # rms -> baseline cruise energy for how briskly an active pass proceeds
        cruise = 0.55 + frame.rms * 0.6

        alive: list[_ShipPass] = []
        for p in self._passes:
            p.progress += (dt / self.PASS_DURATION) * cruise * maneuver_boost
            if p.progress < 1.0:
                alive.append(p)
        self._passes = alive

    def update(self, frame: AudioFrame, dt: float) -> None:
        dt = max(0.0001, min(0.1, dt))
        self._update_rain(frame, dt)
        self._update_ships(frame, dt)

    # -- render -----------------------------------------------------------

    def _route_point(self, route, progress: float):
        progress = _clamp01(progress)
        n = len(route) - 1
        seg = min(n - 1, int(progress * n))
        local_t = (progress * n) - seg
        x0, y0, z0 = route[seg]
        x1, y1, z1 = route[seg + 1]
        x = x0 + (x1 - x0) * local_t
        y = y0 + (y1 - y0) * local_t
        z = z0 + (z1 - z0) * local_t
        return x, y, z

    def _draw_ship(self, surface, x_px, y_px, scale, kind, flash):
        color = (200, 220, 255) if kind == "xwing" else (255, 200, 140)
        s = max(3, scale)
        if kind == "xwing":
            pygame.draw.line(surface, color, (x_px - s, y_px - s), (x_px + s, y_px + s), 2)
            pygame.draw.line(surface, color, (x_px - s, y_px + s), (x_px + s, y_px - s), 2)
            pygame.draw.line(surface, color, (x_px - s * 1.4, y_px), (x_px + s * 1.4, y_px), 1)
        else:
            pygame.draw.polygon(surface, color, [
                (x_px, y_px - s), (x_px - s, y_px + s), (x_px + s, y_px + s),
            ], 1)
            pygame.draw.line(surface, color, (x_px - s * 1.2, y_px + s), (x_px + s * 1.2, y_px + s), 1)
        if flash > 0.05:
            glow = int(120 * flash)
            pygame.draw.circle(surface, (glow, glow, glow), (int(x_px), int(y_px)), int(s * 2), 1)

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        surface.fill((2, 4, 3))

        # -- rain --
        bg_flash = int(20 * self._beat_flash)
        if bg_flash:
            surface.fill((bg_flash // 3, bg_flash, bg_flash // 3), special_flags=pygame.BLEND_ADD)

        for i, col in enumerate(self.columns):
            wobble = math.sin(self._elapsed * 1.3 + i) * self._distortion_smoothed * self.w * 0.02
            px = col.x * self.w + wobble
            for k, ch in enumerate(col.chars):
                py = (col.y - k * 0.02) * self.h
                if py < -20 or py > self.h + 20:
                    continue
                alpha_frac = 1.0 - (k / max(1, col.length))
                bright = (200, 255, 220) if k == 0 else (60, 255, 120)
                glyph = self._glyph_cache.get((ch, bright))
                if glyph is None:
                    continue
                if k > 0 and alpha_frac < 0.98:
                    glyph = glyph.copy()
                    glyph.set_alpha(int(255 * max(0.08, alpha_frac)))
                surface.blit(glyph, (px, py))

        # -- ships (event-driven only — never a free-running spawn timer) --
        for p in self._passes:
            for dx, dy in p.offsets:
                fx, fy, fz = self._route_point(p.route, p.progress)
                fx += dx
                fy += dy
                bass_scale_pressure = 1.0 + frame.bass * 0.6
                scale = (60.0 / max(0.4, fz)) * bass_scale_pressure * (min(self.w, self.h) / 640.0)
                px = fx * self.w
                py = fy * self.h
                self._draw_ship(surface, px, py, scale, p.ship_kind, self._beat_flash)

    def get_debug_state(self) -> dict:
        """Exposes internal state for automated tests — not part of the Visualizer contract."""
        return {
            "column_count": len(self.columns),
            "fall_speed_smoothed": self._fall_speed_smoothed,
            "density_smoothed": self._density_smoothed,
            "active_passes": len(self._passes),
            "last_pass_t": self._last_pass_t,
        }
