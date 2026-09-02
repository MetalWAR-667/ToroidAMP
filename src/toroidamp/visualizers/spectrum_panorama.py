"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Spectrum Panorama CRT)
"""

from pathlib import Path
from typing import Dict, Optional
import pygame
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class SpectrumPanoramaVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    official GPU visualizer: Spectrum Panorama CRT.

    The GPU path renders a demoscene spectrum analyzer: receding spectral
    bands over a 4-color palette with CRT scanlines and phosphor vignette,
    driven by the full AudioFrame contract. The CPU path renders a simpler
    emissive bar/panorama fallback for non-GL viewports.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()

    def get_id(self) -> str:
        return "spectrum_panorama"

    def get_name(self) -> str:
        return "Spectrum Panorama (GPU)"

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
        return resolve_package_asset("assets/official_shaders/spectrum_panorama.frag")

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                # utf-8-sig: same bug class as gpu_canvas.py's pre-BOM-fix
                # loader (v0.666) -- fixed here too, see toroid_identity.py.
                with open(self._shader_path, "r", encoding="utf-8-sig") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Spectrum Panorama",
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
        # Offscreen CPU rendering fallback when displayed in CPU modules / non-GL viewports.
        # Mirrors the shader's demoscene panorama character (bands + horizon + phosphor).
        import math
        w, h = surface.get_size()
        surface.fill((6, 6, 14))
        cx = w // 2

        horizon_y = int(h * (0.30 + frame.bass * 0.15))
        band_h = max(2, int(h * 0.02 * (1.0 + frame.treble)))

        # Receding spectral bands toward a bass-lifted horizon.
        for i in range(56):
            spec = frame.spectrum[i] if i < len(frame.spectrum) else 0.0
            if spec < 0.02:
                continue
            band_y = int(horizon_y - i * (h * 0.006))
            if band_y < 0:
                break
            band_w = int(w * 0.10 * (0.4 + spec + i / 56.0))
            # Demoscene palette: hue cycles across the spectrum with mids phase.
            hue = (i / 56.0 + frame.mids * 0.8) % 1.0
            r = int(255 * (0.5 + 0.5 * math.cos(6.2832 * (hue + 0.0))))
            g = int(255 * (0.5 + 0.5 * math.cos(6.2832 * (hue + 0.33))))
            b = int(255 * (0.5 + 0.5 * math.cos(6.2832 * (hue + 0.66))))
            pygame.draw.rect(surface, (r, g, b),
                             (cx - band_w, band_y, band_w * 2, band_h))

        # CRT scanlines
        for y in range(0, h, 3):
            pygame.draw.line(surface, (0, 0, 0), (0, y), (w, y), 1)

        # Beat/peak flash
        if frame.strong_beat or frame.peak > 0.6:
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((255, 245, 255, 26))
            surface.blit(flash, (0, 0))
