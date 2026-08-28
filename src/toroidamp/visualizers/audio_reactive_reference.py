"""
ToroidAMP - Production Official GPU Visualizer Descriptor (Audio Reactive Reference)
"""

from pathlib import Path
from typing import Dict, Optional
from .base import Visualizer
from .gpu_compiler import ShaderMetadata, ShaderParameter, parse_shader_parameters
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class AudioReactiveReferenceVisualizer(Visualizer):
    """
    Production descriptor and CPU fallback representation for ToroidAMP's
    official GPU visualizer: Audio Reactive Reference — the GPU-AUDIO-003
    discovered-parameter-binding demonstration shader, reachable through the
    normal visualizer cycle like any other official visualizer.

    Its five authoring parameters (u_zoom, u_speed, u_glow, u_twist,
    u_detail) intentionally carry NO automatic audio binding — the shader
    exists to demonstrate manual discovered-parameter binding through LAB,
    not to ship pre-wired musical behavior. At default state it animates
    neutrally on its own (native u_time-driven motion only).
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._shader_path = self._resolve_shader_path()
        self._metadata: Optional[ShaderMetadata] = None
        self._load_metadata()

    def get_id(self) -> str:
        return "audio_reactive_reference"

    def get_name(self) -> str:
        return "Audio Reactive Reference (GPU)"

    def is_gpu(self) -> bool:
        return True

    def is_retina_only(self) -> bool:
        return True

    def get_shader_path(self) -> Optional[Path]:
        return self._shader_path

    def get_metadata(self) -> Optional[ShaderMetadata]:
        return self._metadata

    def _resolve_shader_path(self) -> Optional[Path]:
        return resolve_package_asset("assets/official_shaders/audio_reactive_reference.frag")

    def _load_metadata(self):
        if self._shader_path and self._shader_path.exists():
            try:
                with open(self._shader_path, "r", encoding="utf-8") as f:
                    code = f.read()
                params = parse_shader_parameters(code)
                self._metadata = ShaderMetadata(
                    name="Audio Reactive Reference",
                    is_shadertoy_style=False,
                    description="Official ToroidAMP GPU Visualizer — GPU-AUDIO-003 discovered-parameter demo",
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
        # Offscreen CPU rendering fallback when displayed in CPU modules /
        # non-GL viewports — a simple static echo of the shader's abstract
        # petal-ring identity, not a full software port of the GLSL.
        import pygame
        surface.fill((6, 8, 14))
        w, h = surface.get_size()
        cx, cy = w // 2, h // 2
        radius = int(min(w, h) * 0.32)
        pygame.draw.circle(surface, (0, 242, 255), (cx, cy), max(2, radius), 2)
        pygame.draw.circle(surface, (255, 13, 153), (cx, cy), max(2, int(radius * 0.6)), 2)
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), max(1, int(radius * 0.12)), 0)
