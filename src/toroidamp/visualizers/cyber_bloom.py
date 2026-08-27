"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Cyber Bloom)
"""

from pathlib import Path
from typing import Dict, Optional
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame


class CyberBloomVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    official GPU visualizer: Cyber Bloom.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()

    def get_id(self) -> str:
        return "cyber_bloom"

    def get_name(self) -> str:
        return "Cyber Bloom (GPU)"

    def is_gpu(self) -> bool:
        return True

    def is_retina_only(self) -> bool:
        return True

    def get_shader_path(self) -> Optional[Path]:
        return self._shader_path

    def get_metadata(self) -> Optional[ShaderMetadata]:
        return self._metadata

    def _resolve_shader_path(self) -> Optional[Path]:
        pkg_dir = Path(__file__).resolve().parent.parent
        shader_file = pkg_dir / "assets" / "official_shaders" / "cyber_bloom.frag"
        return shader_file if shader_file.exists() else None

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                with open(self._shader_path, "r", encoding="utf-8") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Cyber Bloom",
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
        # Offscreen CPU rendering fallback when displayed in CPU modules / non-GL viewports
        surface.fill((8, 10, 16))
        w, h = surface.get_size()
        cx, cy = w // 2, h // 2
        radius = int(min(w, h) * 0.35 * (1.0 + frame.bass * 0.2))
        
        # Emissive concentric multi-color fallback rings
        import pygame
        pygame.draw.circle(surface, (0, 229, 255), (cx, cy), max(2, radius), 2)
        pygame.draw.circle(surface, (255, 0, 119), (cx, cy), max(2, int(radius * 0.7)), 2)
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), max(1, int(radius * 0.2)), 0)
