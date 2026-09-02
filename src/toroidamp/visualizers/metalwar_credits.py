"""
ToroidAMP - Production MetalWar Credits Visualizer (EXP-VISLAB-007)
Demoscene Credits Showcase featuring the iconic MetalWar ToroidAMP emblem,
3D perspective starfield tunnel, audio-reactive plasma glow, equalizer rings,
and classic demoscene scrolling/pulsing credits text.
"""

import math
import random
from pathlib import Path
from typing import List, Tuple, Optional

import pygame

from .base import Visualizer
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class MetalWarCreditsVisualizer(Visualizer):
    """
    Demoscene Credits and Tribute Visualizer featuring:
      - Center floating & pulsing MetalWar ToroidAMP metal emblem
      - Orbiting 3D starfield and hyperspace warp particles
      - Circular equalizer spectrum halo around the emblem
      - Audio-reactive shockwave rings and beat flash
      - Retro demoscene sine-wave scrolling credits / greetings
    """

    CREDITS_TEXT = [
        "TOROIDAMP :: IT REALLY WARPS THE TOROID'S ASS!",
        "PCM GOES IN * QUESTIONABLE DECISIONS COME OUT",
        "CODE BY METALWAR & THE DEMOSCENE UNDERGROUND",
        "SALUTES TO: FUTURE CREW * IGUANA * KEFRENS * SANITY * FARBRAUSCH * FAIRLIGHT * ASD * CONSPIRACY",
        "TOROIDAMP ARCHITECTURE: BORING PLAYBACK * RIDICULOUS VISUALS",
        "...AND TO EVERYONE WHO TURNED CODE INTO ART."
    ]

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._emblem_raw: Optional[pygame.Surface] = None
        self._emblem_scaled: Optional[pygame.Surface] = None
        self._emblem_size = 0
        self._load_emblem()

        self.time = 0.0
        self.scroll_x = float(self.w)
        self.credit_line_idx = 0

        # Starfield tunnel particles (x, y, z, speed, col_idx)
        self.num_stars = 140
        self.stars: List[List[float]] = []
        self._init_stars()

        # Fonts
        pygame.font.init()
        self.font = pygame.font.SysFont("monospace", 14, bold=True)

    def get_id(self) -> str:
        return "metalwar_credits"

    def get_name(self) -> str:
        return "MetalWar Credits"

    def _load_emblem(self):
        """Tolerates a missing display surface: convert_alpha() requires
        one (pygame.display.set_mode() is never called anywhere in
        ToroidAMP -- CPU visualizers render to an off-screen Surface for
        Qt, not an actual pygame window), and unconditionally calling it
        here raised 'No convert format has been set' every time, silently
        swallowed by the bare except below -- so the emblem never
        rendered and the fallback circle always drew instead."""
        emblem_path = resolve_package_asset("assets/images/metalwar.png")
        if emblem_path and emblem_path.exists():
            try:
                raw = pygame.image.load(str(emblem_path))
                if pygame.display.get_surface() is not None:
                    raw = raw.convert_alpha()
                self._emblem_raw = raw
            except Exception:
                self._emblem_raw = None

    def _init_stars(self):
        self.stars.clear()
        for _ in range(self.num_stars):
            ang = random.uniform(0, 6.28318)
            rad = random.uniform(0.1, 1.0)
            x = math.cos(ang) * rad
            y = math.sin(ang) * rad
            z = random.uniform(0.1, 2.0)
            spd = random.uniform(0.4, 1.2)
            col_idx = random.randint(0, 3)
            self.stars.append([x, y, z, spd, float(col_idx)])

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self._emblem_scaled = None
        self._emblem_size = 0

    def update(self, frame: AudioFrame, dt: float) -> None:
        self.time += dt
        speed = 110.0 + frame.bass * 90.0
        self.scroll_x -= dt * speed

        # Cycle credits line when off screen
        current_text = self.CREDITS_TEXT[self.credit_line_idx]
        text_w = len(current_text) * 10
        if self.scroll_x < -text_w - 50:
            self.scroll_x = float(self.w + 20)
            self.credit_line_idx = (self.credit_line_idx + 1) % len(self.CREDITS_TEXT)

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)
        w, h = self.w, self.h
        cx, cy = w // 2, h // 2
        min_dim = min(w, h)

        # Deep space gradient background
        surface.fill((4, 5, 12))

        # 1. 3D Radial Starfield Tunnel
        star_palette = [
            (0, 240, 255),    # Cyan
            (255, 0, 140),    # Magenta
            (255, 200, 40),   # Gold
            (180, 100, 255),  # Violet
        ]
        warp_boost = 1.0 + frame.bass * 2.5 + (2.0 if frame.strong_beat else 0.0)
        for s in self.stars:
            s[2] -= dt * s[3] * warp_boost * 0.8
            if s[2] <= 0.05:
                s[2] = 2.0
                ang = random.uniform(0, 6.28318)
                rad = random.uniform(0.15, 1.0)
                s[0] = math.cos(ang) * rad
                s[1] = math.sin(ang) * rad

            # Project to screen
            proj_scale = (min_dim * 0.65) / s[2]
            sx = int(cx + s[0] * proj_scale)
            sy = int(cy + s[1] * proj_scale)

            if 0 <= sx < w and 0 <= sy < h:
                # Distance brightness and trail
                brightness = max(0.1, min(1.0, 1.8 - s[2]))
                base_c = star_palette[int(s[4]) % len(star_palette)]
                col = (int(base_c[0] * brightness), int(base_c[1] * brightness), int(base_c[2] * brightness))

                # Draw head & warpline
                tail_len = int((1.0 / s[2]) * 8.0 * warp_boost)
                tx = int(sx - s[0] * tail_len)
                ty = int(sy - s[1] * tail_len)
                if tail_len > 2:
                    pygame.draw.line(surface, col, (tx, ty), (sx, sy), max(1, int(brightness * 2.5)))
                else:
                    surface.set_at((sx, sy), col)

        # 2. Circular Audio Spectrum Crown (Halo around the emblem)
        target_emblem_r = int(min_dim * 0.26 * (1.0 + frame.bass * 0.12 + (0.08 if frame.strong_beat else 0.0)))
        num_halo_bars = 48
        for i in range(num_halo_bars):
            ang = (i / num_halo_bars) * 6.2831853 + self.time * 0.4
            spec_idx = int((i / num_halo_bars) * len(frame.spectrum))
            spec_val = frame.spectrum[spec_idx] if spec_idx < len(frame.spectrum) else 0.0
            
            bar_len = int(spec_val * (min_dim * 0.22) * (1.0 + frame.treble * 0.8))
            r_start = target_emblem_r + 4
            r_end = r_start + max(3, bar_len)

            x1 = int(cx + math.cos(ang) * r_start)
            y1 = int(cy + math.sin(ang) * r_start)
            x2 = int(cx + math.cos(ang) * r_end)
            y2 = int(cy + math.sin(ang) * r_end)

            # Color gradient: Cyan on bottom -> Magenta on top
            frac = (math.sin(ang) + 1.0) * 0.5
            bar_col = (
                int(0 * (1 - frac) + 255 * frac),
                int(230 * (1 - frac) + 20 * frac),
                int(255 * (1 - frac) + 180 * frac),
            )
            pygame.draw.line(surface, bar_col, (x1, y1), (x2, y2), max(2, int(min_dim * 0.008)))

        # 3. Floating MetalWar ToroidAMP Emblem
        emblem_diam = target_emblem_r * 2
        if self._emblem_raw:
            if self._emblem_size != emblem_diam or self._emblem_scaled is None:
                self._emblem_size = emblem_diam
                self._emblem_scaled = pygame.transform.smoothscale(
                    self._emblem_raw, (emblem_diam, emblem_diam)
                )

            # Gentle floating oscillation
            float_y = int(math.sin(self.time * 2.0) * (min_dim * 0.02))
            rect = self._emblem_scaled.get_rect(center=(cx, cy + float_y))
            surface.blit(self._emblem_scaled, rect)
        else:
            # Fallback circle if image missing
            pygame.draw.circle(surface, (0, 240, 255), (cx, cy), target_emblem_r, 3)

        # 4. Shockwave Expansion Ring on Strong Beats
        if frame.strong_beat or frame.beat:
            shock_r = int(target_emblem_r * (1.2 + (self.time * 4.0) % 0.8))
            shock_alpha_col = (255, 255, 255) if frame.strong_beat else (255, 0, 140)
            if shock_r < min_dim * 0.7:
                pygame.draw.circle(surface, shock_alpha_col, (cx, cy), shock_r, max(1, int(3 - (shock_r / (min_dim * 0.7)) * 2)))

        # 5. Demoscene Sine-Scroller Banner at Bottom
        banner_y = int(h * 0.90)
        current_text = self.CREDITS_TEXT[self.credit_line_idx]

        # Dark glass ribbon backdrop
        ribbon_h = 28
        ribbon_surf = pygame.Surface((w, ribbon_h), pygame.SRCALPHA)
        ribbon_surf.fill((0, 0, 0, 170))
        pygame.draw.line(ribbon_surf, (0, 240, 255), (0, 0), (w, 0), 1)
        pygame.draw.line(ribbon_surf, (255, 0, 140), (0, ribbon_h - 1), (w, ribbon_h - 1), 1)
        surface.blit(ribbon_surf, (0, banner_y - ribbon_h // 2))

        # Render wavy characters
        char_x = self.scroll_x
        for i, ch in enumerate(current_text):
            if -30 <= char_x <= w + 30:
                # Sine wobble
                wave_y = int(math.sin(self.time * 4.0 + i * 0.28) * 4.5)
                # Neon rainbow color cycle
                c_phase = self.time * 1.5 + i * 0.08
                r_val = int(127 + 127 * math.sin(c_phase))
                g_val = int(127 + 127 * math.sin(c_phase + 2.094))
                b_val = int(127 + 127 * math.sin(c_phase + 4.188))
                col = (max(80, r_val), max(80, g_val), max(80, b_val))

                try:
                    char_surf = self.font.render(ch, True, col)
                    surface.blit(char_surf, (int(char_x), banner_y - 8 + wave_y))
                except Exception:
                    pass
            char_x += 10
