"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Spectrum Magma)
"""

from pathlib import Path
from typing import Dict, Optional
import pygame
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class SpectrumBarsVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    official GPU visualizer: Spectrum Magma.

    The GPU path renders a three-layer audio-reactive spectacle (organic
    plasma backdrop, central reactive toroidal structure via SDF, and
    radial energy beams/sparks) driven by the full AudioFrame contract.
    The CPU path renders an emissive magma-globe fallback for non-GL
    viewports so the visualizer degrades gracefully, never silently.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()
        # Peak hold caps and smoothed spectrum state for fluid animation
        self.num_bars = 32
        self.peaks = [0.0] * self.num_bars
        self.peak_speeds = [0.0] * self.num_bars
        self.smoothed_spectrum = [0.0] * self.num_bars

    def get_id(self) -> str:
        return "spectrum_magma"

    def get_name(self) -> str:
        return "Spectrum Magma (GPU)"

    def is_gpu(self) -> bool:
        return True

    def is_retina_only(self) -> bool:
        # GLSL Everywhere cut: official GPU visualizers are first-class
        # NORMAL-mode visualizers too -- see toroid_identity.py.
        return False

    def get_shader_path(self) -> Optional[Path]:
        return self._shader_path

    def get_metadata(self) -> Optional[ShaderMetadata]:
        return self._metadata

    def _resolve_shader_path(self) -> Optional[Path]:
        return resolve_package_asset("assets/official_shaders/spectrum_magma.frag")

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                # utf-8-sig: same bug class as gpu_canvas.py's pre-BOM-fix
                # loader (v0.666) -- fixed here too, see toroid_identity.py.
                with open(self._shader_path, "r", encoding="utf-8-sig") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Spectrum Magma",
                    is_shadertoy_style=False,
                    description="Official ToroidAMP GPU Visualizer",
                    parameters=params,
                    uses_texture=False
                )
            except Exception:
                pass

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def update(self, frame: AudioFrame, dt: float) -> None:
        pass

    def render(self, surface, frame: AudioFrame, dt: float) -> None:
        # High-performance demoscene segmented spectrum analyzer with floating peak caps & reflection
        w, h = surface.get_size()
        energy = (frame.bass + frame.mids + frame.treble) / 3.0
        
        # Deep dark background with subtle radial glow
        base_col = (8, 9, 16)
        surface.fill(base_col)
        
        num_bars = self.num_bars
        if len(self.peaks) != num_bars:
            self.peaks = [0.0] * num_bars
            self.peak_speeds = [0.0] * num_bars
            self.smoothed_spectrum = [0.0] * num_bars
            
        margin_x = max(10, int(w * 0.05))
        usable_w = w - 2 * margin_x
        bar_gap = max(2, int(usable_w / (num_bars * 5)))
        bar_w = max(3, (usable_w - (num_bars - 1) * bar_gap) // num_bars)
        
        # Baseline positioned at 75% height to leave 25% for mirror reflection
        baseline_y = int(h * 0.74)
        max_bar_h = int(h * 0.62)
        
        # Segment configuration
        seg_h = max(2, int(h * 0.016))
        seg_gap = 1
        
        # 1. Update and draw bars
        for i in range(num_bars):
            # Downsample / average 64 bins into num_bars
            src_idx = int((i / num_bars) * len(frame.spectrum))
            src_idx2 = min(len(frame.spectrum) - 1, int(((i + 1) / num_bars) * len(frame.spectrum)))
            if src_idx2 > src_idx:
                raw_val = sum(frame.spectrum[src_idx:src_idx2]) / (src_idx2 - src_idx)
            else:
                raw_val = frame.spectrum[src_idx] if src_idx < len(frame.spectrum) else 0.0
                
            # Equalization curve (boost higher frequencies slightly for visual balance)
            eq_boost = 1.0 + (i / num_bars) * 1.5
            raw_val = min(1.0, raw_val * eq_boost * (1.2 + frame.bass * 0.3))
            
            # Smooth attack & decay
            if raw_val > self.smoothed_spectrum[i]:
                self.smoothed_spectrum[i] = raw_val
            else:
                self.smoothed_spectrum[i] = max(0.0, self.smoothed_spectrum[i] - dt * 2.2)
                
            val = self.smoothed_spectrum[i]
            
            # Peak hold physics (floating caps with gravity acceleration)
            if val >= self.peaks[i]:
                self.peaks[i] = val
                self.peak_speeds[i] = 0.0
            else:
                self.peak_speeds[i] += dt * 3.5  # gravity
                self.peaks[i] = max(0.0, self.peaks[i] - self.peak_speeds[i] * dt)
                
            x = margin_x + i * (bar_w + bar_gap)
            current_h = int(val * max_bar_h)
            num_segs = max(1, current_h // (seg_h + seg_gap)) if current_h > 0 else 0
            
            # Draw segmented LED blocks (Cyan -> Gold -> Hot Magenta gradient)
            for s in range(num_segs):
                frac = s / max(1, (max_bar_h // (seg_h + seg_gap)))
                # Gradient color interpolation
                if frac < 0.5:
                    t = frac * 2.0
                    col = (int(0 * (1-t) + 255 * t), int(240 * (1-t) + 200 * t), int(255 * (1-t) + 20 * t))
                else:
                    t = (frac - 0.5) * 2.0
                    col = (int(255 * (1-t) + 255 * t), int(200 * (1-t) + 30 * t), int(20 * (1-t) + 120 * t))
                    
                sy = baseline_y - (s + 1) * (seg_h + seg_gap)
                pygame.draw.rect(surface, col, (x, sy, bar_w, seg_h))
                
                # Mirror reflection (faded)
                refl_y = baseline_y + 4 + s * (seg_h + seg_gap)
                if refl_y + seg_h < h:
                    refl_col = (col[0] // 5, col[1] // 5, col[2] // 5)
                    pygame.draw.rect(surface, refl_col, (x, refl_y, bar_w, seg_h))
                    
            # Draw floating peak cap
            if self.peaks[i] > 0.02:
                peak_y = baseline_y - int(self.peaks[i] * max_bar_h) - seg_h - 2
                peak_col = (255, 255, 255) if (frame.strong_beat and i % 4 == 0) else (255, 230, 100)
                pygame.draw.rect(surface, peak_col, (x, peak_y, bar_w, max(2, seg_h // 2)))
                
        # Baseline neon rule
        pygame.draw.line(surface, (0, 180, 255), (margin_x - 4, baseline_y + 2), (w - margin_x + 4, baseline_y + 2), 2)
