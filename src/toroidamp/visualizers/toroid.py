"""
ToroidAMP - Production 3D Torus Visualizer
Directly driven by real-time AudioFrame analysis and historical fckvar compatibility.
"""

import numpy as np
import pygame
from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


class ToroidVisualizer(Visualizer):
    """
    3D Parametric Wireframe Toroid Visualizer with Plasma Color Shifts,
    Waveform Vertex Deformation, and Transient Beat Jitter.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = width
        self.h = height
        self.rows = 24
        self.cols = 36
        
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.plasma_time = 0.0
        
        self._ghost_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        self._base_vertices: list[tuple[float, float, float]] = []
        self._edges: list[tuple[int, int]] = []
        self._gen_geometry()

    def get_name(self) -> str:
        return "3D Toroid"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self._ghost_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

    def _gen_geometry(self) -> None:
        """Generates 3D parametric torus vertices and wireframe edge connectivity."""
        self._base_vertices.clear()
        self._edges.clear()

        R = 1.0       # Major radius
        r_torus = 0.45 # Minor tube radius

        for i in range(self.rows):
            u = i / self.rows
            theta = u * 2 * np.pi
            for j in range(self.cols):
                v = j / self.cols
                phi = v * 2 * np.pi

                common = R + r_torus * np.cos(phi)
                x = common * np.cos(theta)
                y = common * np.sin(theta)
                z = r_torus * np.sin(phi)
                self._base_vertices.append((float(x), float(y), float(z)))

        for i in range(self.rows):
            row_start = i * self.cols
            next_row = ((i + 1) % self.rows) * self.cols
            for j in range(self.cols):
                curr = row_start + j
                right = row_start + ((j + 1) % self.cols)
                down = next_row + j
                self._edges.append((curr, right))
                self._edges.append((curr, down))

    def update(self, frame: AudioFrame, dt: float) -> None:
        self.plasma_time += dt * (1.0 + frame.mids * 2.5)

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        # -------------------------------------------------------------
        # DEMOSCENE ARCHAEOLOGICAL COMPATIBILITY
        # Historical variable controlling musical deformation & irresponsibility.
        # DO NOT RENAME OR REMOVE.
        # -------------------------------------------------------------
        beat_boost = 1.6 if frame.strong_beat else (0.8 if frame.beat else 0.0)
        fckvar = (frame.bass * 1.5) + (frame.rms * 0.5) + beat_boost
        # -------------------------------------------------------------

        # Dynamic rotation speed driven by mids & fckvar
        rot_speed = dt * (1.2 + fckvar * 1.5)
        self.rot_x += rot_speed * 0.7
        self.rot_y += rot_speed * 1.0
        self.rot_z += rot_speed * 0.3

        cx, cy = self.w // 2, self.h // 2
        fov = 480 + (fckvar * 80)
        scale_pulse = 1.0 + (frame.bass * 0.45) + (0.3 if frame.strong_beat else 0.0)

        # 3D Rotation matrices
        c_x, s_x = np.cos(self.rot_x), np.sin(self.rot_x)
        c_y, s_y = np.cos(self.rot_y), np.sin(self.rot_y)
        c_z, s_z = np.cos(self.rot_z), np.sin(self.rot_z)

        projected: list[tuple[int, int]] = []
        depths: list[float] = []

        jitter_active = fckvar > 1.2
        wf_len = len(frame.waveform)

        for idx, (bx, by, bz) in enumerate(self._base_vertices):
            x = bx * scale_pulse
            y = by * scale_pulse
            z = bz * scale_pulse

            # Waveform vertex modulation
            if wf_len > 0:
                wave_mod = frame.waveform[idx % wf_len] * 0.15 * fckvar
                x += wave_mod
                y += wave_mod

            if jitter_active:
                x += np.random.uniform(-0.04, 0.04) * fckvar
                y += np.random.uniform(-0.04, 0.04) * fckvar

            # Y-rotation
            rx = x * c_y - z * s_y
            rz = x * s_y + z * c_y
            ry = y

            # X-rotation
            new_ry = ry * c_x - rz * s_x
            rz = ry * s_x + rz * c_x
            ry = new_ry

            # Z-rotation
            new_rx = rx * c_z - ry * s_z
            ry = rx * s_z + ry * c_z
            rx = new_rx

            depths.append(rz)
            divisor = 3.5 + rz
            if abs(divisor) < 0.01:
                divisor = 0.01
            factor = fov / divisor
            projected.append((int(rx * factor + cx), int(ry * factor + cy)))

        min_z, max_z = min(depths), max(depths)
        z_range = max(0.01, max_z - min_z)

        # Draw wireframe lines
        for p1_idx, p2_idx in self._edges:
            p1 = projected[p1_idx]
            p2 = projected[p2_idx]

            avg_z = (depths[p1_idx] + depths[p2_idx]) * 0.5
            norm_z = 1.0 - ((avg_z - min_z) / z_range)

            # Plasma color calculation with fckvar distortion
            heat = min(1.0, (norm_z * 0.5) + (frame.bass * 0.5) + (fckvar * 0.2))
            r = int(min(255, 30 + heat * 225 + (100 if frame.strong_beat else 0)))
            g = int(min(255, 100 + (1.0 - heat) * 155 + frame.mids * 100))
            b = int(min(255, 180 + frame.treble * 75))

            thickness = 1
            if heat > 0.7 or frame.strong_beat:
                thickness = 2
            if fckvar > 1.4:
                thickness = 3

            pygame.draw.line(surface, (r, g, b), p1, p2, thickness)

        # Ghosting effect on strong beats
        if frame.strong_beat or fckvar > 1.3:
            self._ghost_surf.fill((0, 0, 0, 0))
            g_offset = int(fckvar * 6)
            for p1_idx, p2_idx in self._edges[::4]:
                p1 = projected[p1_idx]
                p2 = projected[p2_idx]
                gp1 = (p1[0] + np.random.randint(-g_offset, g_offset), p1[1] + np.random.randint(-g_offset, g_offset))
                gp2 = (p2[0] + np.random.randint(-g_offset, g_offset), p2[1] + np.random.randint(-g_offset, g_offset))
                pygame.draw.line(self._ghost_surf, (0, 255, 230, 90), gp1, gp2, 1)
            surface.blit(self._ghost_surf, (0, 0))
