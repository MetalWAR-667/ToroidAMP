"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Hyper Torus Raymarcher)
"""

from pathlib import Path
from typing import Dict, Optional
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class HyperTorusRaymarchVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    official GPU visualizer: Hyper Torus Raymarcher. A true 3D SDF
    raymarched torus with volume halo, surface ripple, and audio-reactive
    twist/bass-pulse.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()

    def get_id(self) -> str:
        return "hyper_torus_raymarch"

    def get_name(self) -> str:
        return "Hyper Torus Raymarch (GPU)"

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
        return resolve_package_asset("assets/official_shaders/hyper_torus_raymarch.frag")

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                # utf-8-sig: same bug class as gpu_canvas.py's pre-BOM-fix
                # loader (v0.666) -- fixed here too, see toroid_identity.py.
                with open(self._shader_path, "r", encoding="utf-8-sig") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Hyper Torus Raymarch",
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
        # Mirrors the shader's neon torus character without a GPU context.
        import pygame
        surface.fill((5, 6, 14))
        w, h = surface.get_size()
        cx, cy = w // 2, h // 2
        radius = int(min(w, h) * 0.28 * (1.0 + frame.bass * 0.2))

        # Emissive raymarch-torus fallback: layered neon rings + hot core
        pygame.draw.circle(surface, (0, 60, 140), (cx, cy), max(2, radius + 4), 2)
        pygame.draw.circle(surface, (0, 190, 255), (cx, cy), max(2, radius), 2)
        pygame.draw.circle(surface, (255, 20, 150), (cx, cy), max(2, int(radius * 0.66)), 2)
        if frame.treble > 0.3:
            pygame.draw.circle(surface, (255, 255, 255), (cx, cy), max(1, int(radius * 0.3)), 0)
