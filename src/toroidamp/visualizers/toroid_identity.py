"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Toroid Identity)
"""

from pathlib import Path
from typing import Dict, Optional
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame


class ToroidIdentityVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    first official GPU visualizer: Toroid Identity.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()

    def get_id(self) -> str:
        return "toroid_identity"

    def get_name(self) -> str:
        return "Toroid Identity (GPU)"

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
        shader_file = pkg_dir / "assets" / "official_shaders" / "toroid_identity.frag"
        return shader_file if shader_file.exists() else None

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                with open(self._shader_path, "r", encoding="utf-8") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Toroid Identity",
                    is_shadertoy_style=False,
                    description="Official ToroidAMP GPU Visualizer",
                    parameters=params,
                    uses_texture=True
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
        radius = int(min(w, h) * 0.3 * (1.0 + frame.bass * 0.25))
        
        # Emissive concentric cyan/magenta identity rings
        pygame.draw.circle(surface, (0, 240, 255), (cx, cy), max(2, radius), 2)
        inner_r = max(2, int(radius * 0.65 * (1.0 + frame.mids * 0.2)))
        pygame.draw.circle(surface, (255, 0, 119), (cx, cy), inner_r, 2)
        
        # Center glow node
        center_r = max(2, int(radius * 0.25 * (1.0 + frame.treble * 0.4)))
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), center_r, 0)
