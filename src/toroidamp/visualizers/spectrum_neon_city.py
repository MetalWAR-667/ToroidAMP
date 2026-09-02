"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Neon City Spectrum)
"""

from pathlib import Path
from typing import Dict, Optional
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class SpectrumNeonCityVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    official GPU visualizer: Neon City Spectrum (3D Cyberpunk Metropolis).
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()

    def get_id(self) -> str:
        return "spectrum_neon_city"

    def get_name(self) -> str:
        return "Neon City Spectrum (GPU)"

    def is_gpu(self) -> bool:
        return True

    def is_retina_only(self) -> bool:
        return False

    def get_shader_path(self) -> Optional[Path]:
        return self._shader_path

    def get_metadata(self) -> Optional[ShaderMetadata]:
        return self._metadata

    def _resolve_shader_path(self) -> Optional[Path]:
        return resolve_package_asset("assets/official_shaders/spectrum_neon_city.frag")

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                with open(self._shader_path, "r", encoding="utf-8-sig") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Neon City Spectrum",
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
        pass
