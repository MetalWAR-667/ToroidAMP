"""
ToroidAMP - Experimental Waveform Ribbon Visualizer
Authoring validation test for 'visualizer-authoring' skill.
"""

import math
import numpy as np
import pygame
from toroidamp.visualizers.base import Visualizer
from toroidamp.analysis.audio_frame import AudioFrame


class WaveformRibbonVisualizer(Visualizer):
    """
    Experimental ribbon visualizer that renders a fluid neon oscilloscope ribbon
    using AudioFrame.waveform, AudioFrame.bass, and AudioFrame.mids.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = width
        self.h = height
        self.phase = 0.0

    def get_name(self) -> str:
        return "Waveform Ribbon"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def update(self, frame: AudioFrame, dt: float) -> None:
        self.phase += dt * (1.5 + frame.mids * 3.0)

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        cy = self.h // 2
        amplitude = (self.h * 0.35) * (0.4 + frame.bass * 0.6)
        points_top: list[tuple[int, int]] = []
        points_bottom: list[tuple[int, int]] = []

        wf = frame.waveform
        num_points = len(wf)
        if num_points < 2:
            return

        for i, val in enumerate(wf):
            x = int((i / (num_points - 1)) * self.w)
            sine_wave = math.sin(self.phase + (i * 0.08)) * 15.0 * frame.mids
            y_center = cy + int(val * amplitude + sine_wave)
            
            thickness = max(2, int(4 + frame.rms * 12))
            points_top.append((x, y_center - thickness))
            points_bottom.append((x, y_center + thickness))

        # Render layered glowing neon ribbon
        color_core = (255, 255, 255)
        color_glow = (
            int(min(255, 40 + frame.bass * 215)),
            int(min(255, 120 + frame.mids * 135)),
            int(min(255, 220 + frame.treble * 35))
        )

        # Draw glowing polygon ribbon
        poly_points = points_top + list(reversed(points_bottom))
        if len(poly_points) > 3:
            pygame.draw.polygon(surface, color_glow, poly_points)

        # Draw center spine line
        spine_points = [((t[0] + b[0]) // 2, (t[1] + b[1]) // 2) for t, b in zip(points_top, points_bottom)]
        if len(spine_points) > 1:
            pygame.draw.lines(surface, color_core, False, spine_points, 2)
