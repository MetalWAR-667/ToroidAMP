"""
ToroidAMP - Base Visualizer Interface
"""

from abc import ABC, abstractmethod
import pygame
from ..analysis.audio_frame import AudioFrame


class Visualizer(ABC):
    """
    Internal contract for all ToroidAMP visualizers.
    Consumes normalized AudioFrame, delta time, and an offscreen Pygame surface.
    """

    @abstractmethod
    def resize(self, width: int, height: int) -> None:
        """Called when render surface dimensions change (including fullscreen toggle)."""
        pass

    @abstractmethod
    def update(self, frame: AudioFrame, dt: float) -> None:
        """Updates internal simulation state with the latest AudioFrame metrics."""
        pass

    @abstractmethod
    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        """Renders visualizer graphics directly to the provided Pygame surface."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Returns the human-readable display name of the visualizer."""
        pass

    def reset(self) -> None:
        """Optional hook to reset internal particle/motion state."""
        pass
