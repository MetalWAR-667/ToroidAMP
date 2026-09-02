# ToroidAMP - Matrix Rain Visualizer
# Port of the donor PeaceCodeRain (effects.py:2072), re-tuned for real
# AudioFrame sync. Fixes the original velocity bug (donor used px/frame
# with no dt; treating those as px/sec made rain 60x too slow) and adds
# per-column spectral coupling: each column is bound to a spectrum band,
# so its head brightness, fall speed, and flicker rate all visibly follow
# the frequency energy at that horizontal position.

import math
import random

import pygame

from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


class MatrixRainVisualizer(Visualizer):
    """
    Code rain where each column is a live readout of one frequency band.
    A column's head glows white-hot and the whole stream falls faster
    when its spectral bin is hot; treble energy accelerates everything;
    beats ignite a burst; a strong beat dumps a bright cascade.

    Visual thesis: The spectrum itself is raining down in hex.
    """

    HEX_CHARS = "0123456789ABCDEF"
    CHAR_SPACING = 14
    MAX_DROPS = 240

    # Velocity constants (pixels / second, not per frame)
    BASE_VELOCITY = 90.0
    TREBLE_VELOCITY_GAIN = 900.0
    BASS_VELOCITY_GAIN = 250.0
    ROW_VELOCITY_GAIN = 480.0

    # Per-column spectral mapping
    NUM_SPECTRUM_BANDS = 64
    HEAD_TIERS = (
        (230, 255, 230),  # 0: white-hot
        (170, 255, 180),
        (120, 255, 150),
        (70, 210, 110),
        (30, 160, 70),    # 4: dim
    )
    TAIL_ALPHAS = (255, 210, 165, 125, 90, 60, 35)

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self.cols = max(1, self.w // self.CHAR_SPACING)
        self._elapsed_time = 0.0

        self.font = pygame.font.SysFont("consolas", 14, bold=True)

        # Pre-rendered glyph surfaces (no per-frame alpha mutation -> no cross-talk)
        self._body_by_alpha: dict[str, list[pygame.Surface]] = {}
        self._head_by_tier: dict[str, list[pygame.Surface]] = {}
        self._build_cache()

        self._drops: list[dict] = []
        self._init_drops()

        # Per-column smoothed spectral energy [0..1]
        self._col_energy = [0.0] * self.cols

        # Smoothed audio envelopes
        self._bass_smoothed = 0.0
        self._treble_smoothed = 0.0
        self._rms_smoothed = 0.0

        # Beat / strong-beat impulse (fast attack, smooth decay)
        self._beat_impulse = 0.0
        self._strong_impulse = 0.0

    def get_name(self) -> str:
        return "Matrix Rain"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self.cols = max(1, self.w // self.CHAR_SPACING)
        self._col_energy = [0.0] * self.cols
        self._init_drops()

    def _build_cache(self) -> None:
        self._body_by_alpha.clear()
        self._head_by_tier.clear()
        for char in self.HEX_CHARS:
            self._body_by_alpha[char] = [
                self.font.render(char, True, (0, 180, 60)) for _ in range(len(self.TAIL_ALPHAS))
            ]
            self._head_by_tier[char] = [
                self.font.render(char, True, color) for color in self.HEAD_TIERS
            ]

    def _init_drops(self) -> None:
        self._drops.clear()
        for col_idx in range(self.cols):
            self._drops.append(self._make_drop(col_idx, initial=True))

    def _make_drop(self, col_idx: int, initial: bool = False) -> dict:
        return {
            "x": col_idx * self.CHAR_SPACING,
            "y": random.uniform(-self.h, 0) if initial else random.uniform(-120, -10),
            "speed": random.uniform(0.6, 1.4),  # velocity multiplier [0.6..1.4]
            "chars": [random.choice(self.HEX_CHARS) for _ in range(random.randint(6, 18))],
            "is_glitch": False,
        }

    def _energy_for_column(self, col: int) -> float:
        """Map a column index to its spectrum band energy [0..1]."""
        if not self._spectrum:
            return 0.0
        band = (col * self.NUM_SPECTRUM_BANDS) // self.cols
        band = max(0, min(self.NUM_SPECTRUM_BANDS - 1, band))
        return self._spectrum[band]

    def update(self, frame: AudioFrame, dt: float) -> None:
        dt = max(0.0001, min(0.1, dt))
        self._elapsed_time += dt
        self._spectrum = frame.spectrum

        # Smoothed global envelopes
        self._bass_smoothed += (frame.bass - self._bass_smoothed) * min(1.0, dt * 3.0)
        self._treble_smoothed += (frame.treble - self._treble_smoothed) * min(1.0, dt * 4.0)
        self._rms_smoothed += (frame.rms - self._rms_smoothed) * min(1.0, dt * 2.5)

        # Beat impulses (alpha-like fast attack, exponential decay)
        self._beat_impulse *= math.exp(-dt * 7.0)
        self._strong_impulse *= math.exp(-dt * 4.0)
        if frame.beat:
            self._beat_impulse = min(1.0, self._beat_impulse + 0.65)
        if frame.strong_beat:
            self._strong_impulse = min(1.0, self._strong_impulse + 0.9)

        # Per-column spectral energy -> smoothed so heads breathe, not stutter
        for col in range(self.cols):
            target = self._energy_for_column(col)
            self._col_energy[col] += (target - self._col_energy[col]) * min(1.0, dt * 6.0)

        # Global fall velocity (pixels/sec), strongly treble-driven
        velocity = (
            self.BASE_VELOCITY
            + self._treble_smoothed * self.TREBLE_VELOCITY_GAIN
            + self._bass_smoothed * self.BASS_VELOCITY_GAIN
            + self._beat_impulse * self.ROW_VELOCITY_GAIN
            + self._strong_impulse * 300.0
        )

        for drop in self._drops[:]:
            col = drop["x"] // self.CHAR_SPACING
            col_energy = self._col_energy[col] if col < len(self._col_energy) else 0.0

            # Per-column speed: hot columns fall noticeably faster
            drop_speed = velocity * drop["speed"] * (0.45 + col_energy * 1.1)
            drop["y"] += drop_speed * dt

            # Reset when the stream fully clears the screen
            stream_bottom = drop["y"] + len(drop["chars"]) * self.CHAR_SPACING
            if drop["y"] > self.h + len(drop["chars"]) * self.CHAR_SPACING:
                drop = self._reset_drop(drop)

            # Glitch flicker: hot columns flicker their glyphs rapidly
            drop["is_glitch"] = col_energy > 0.72

        # Strong beat: dump a bright cascade of fresh streams near the top
        if self._strong_impulse > 0.35:
            burst = int(self._strong_impulse * 22)
            for _ in range(burst):
                if len(self._drops) >= self.MAX_DROPS:
                    break
                col = random.randint(0, self.cols - 1)
                nd = self._make_drop(col)
                nd["y"] = random.uniform(-self.h * 0.25, -10)
                nd["speed"] = random.uniform(1.0, 1.6)
                nd["chars"] = [random.choice(self.HEX_CHARS) for _ in range(random.randint(8, 24))]
                nd["is_glitch"] = True
                self._drops.append(nd)

        # Beat / bass: replenish ambient streams
        if frame.beat or self._bass_smoothed > 0.4:
            if random.random() < self._bass_smoothed * 0.5 + 0.05:
                col = random.randint(0, self.cols - 1)
                if len(self._drops) < self.MAX_DROPS:
                    self._drops.append(self._make_drop(col))

        # Cap overflow
        if len(self._drops) > self.MAX_DROPS:
            self._drops = self._drops[-self.MAX_DROPS:]

    def _reset_drop(self, drop: dict) -> dict:
        drop["y"] = random.uniform(-self.h * 0.4, -20)
        drop["speed"] = random.uniform(0.6, 1.4)
        drop["chars"] = [random.choice(self.HEX_CHARS) for _ in drop["chars"]]
        return drop

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        # Deep CRT void, subtly breathing with RMS
        bg = int(4 + self._rms_smoothed * 22)
        surface.fill((bg, bg + 3, bg + 6))

        head_alpha = 255
        for drop in self._drops:
            chars = drop["chars"]
            col = drop["x"] // self.CHAR_SPACING
            col_energy = self._col_energy[col] if col < len(self._col_energy) else 0.0

            # Head tier from column energy (hot columns => bright white head)
            tier = int((1.0 - col_energy) * (len(self.HEAD_TIERS) - 1))
            tier = max(0, min(len(self.HEAD_TIERS) - 1, tier))

            for i, char in enumerate(chars):
                y_pos = drop["y"] - i * self.CHAR_SPACING
                if not (0 < y_pos < self.h):
                    continue

                if i == 0:
                    glyph = self._head_by_tier[char][tier]
                else:
                    # Fade tail: near the head brighter, far into stream dimmer
                    alpha_idx = min(len(self.TAIL_ALPHAS) - 1, i - 1)
                    glyph = self._body_by_alpha[char][alpha_idx]
                    # Multiply brightness by column energy (hot column = brighter tail)
                    glyph.set_alpha(int(self.TAIL_ALPHAS[alpha_idx] * (0.5 + col_energy * 0.5)))

                surface.blit(glyph, (drop["x"] - (glyph.get_width() - self.CHAR_SPACING) // 2,
                                     y_pos))

        # Strong beat: white-phosphor sweep + speed-line flares
        if self._strong_impulse > 0.05:
            flash_alpha = int(90 * self._strong_impulse * (0.3 + frame.bass))
            if flash_alpha > 4:
                flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
                flash.fill((255, 255, 255, flash_alpha))
                surface.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

            # Horizontal speed streaks race across the void in sync with the beat
            streak_alpha = int(120 * self._strong_impulse)
            for _ in range(3 + int(self._strong_impulse * 6)):
                sy = random.uniform(0, self.h)
                sx = random.uniform(0, self.w * 0.6)
                slen = random.uniform(60, 220)
                speed_line = pygame.Surface((int(slen), 1), pygame.SRCALPHA)
                speed_line.fill((200, 255, 200, streak_alpha))
                surface.blit(speed_line, (int(sx), int(sy)),
                             special_flags=pygame.BLEND_RGBA_ADD)

        # Beat: sudden column "flicker" jolt at the beat boundary
        if frame.beat and self._beat_impulse > 0.6:
            hot = [c for c in range(self.cols) if self._col_energy[c] > 0.55]
            for col in random.sample(hot, min(3, len(hot))) if hot else []:
                for drop in self._drops:
                    if drop["x"] // self.CHAR_SPACING == col:
                        drop["y"] = random.uniform(-self.h * 0.2, 0)
                        break

    def get_debug_state(self) -> dict:
        return {
            "drop_count": len(self._drops),
            "cols": self.cols,
            "bass_smoothed": self._bass_smoothed,
            "treble_smoothed": self._treble_smoothed,
            "rms_smoothed": self._rms_smoothed,
            "beat_impulse": self._beat_impulse,
            "strong_impulse": self._strong_impulse,
            "avg_col_energy": sum(self._col_energy) / len(self._col_energy) if self._col_energy else 0.0,
            "elapsed": self._elapsed_time,
        }
