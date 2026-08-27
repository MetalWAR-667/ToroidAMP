"""
ToroidAMP - Production 3D Torus Visualizer
Directly driven by real-time AudioFrame analysis, genuine 3D Z-depth camera travel,
and historical fckvar compatibility.
"""

import numpy as np
import pygame
from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


class ToroidVisualizer(Visualizer):
    """
    3D Parametric Wireframe Toroid Visualizer with Plasma Color Shifts,
    Waveform Vertex Deformation, True 3D Z-Depth Camera Travel, and Transient Beat Jitter.
    """

    MIN_CAMERA_DIST = 2.05
    MAX_CAMERA_DIST = 4.20
    BASE_CAMERA_DIST = 3.60

    def __init__(self, width: int = 640, height: int = 480):
        self.w = width
        self.h = height
        self.rows = 24
        self.cols = 36

        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.plasma_time = 0.0

        # True 3D Z-Depth Camera Travel dynamics
        self.camera_dist = self.BASE_CAMERA_DIST
        self.target_camera_dist = self.BASE_CAMERA_DIST
        self._bass_smoothed = 0.0
        self._zoom_impulse = 0.0
        self._strong_zoom_progress = 0.0
        self._strong_zoom_t = -999.0
        self._elapsed = 0.0

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
        dt = max(0.0001, min(0.1, dt))
        self._elapsed += dt

        self.plasma_time += dt * (1.0 + frame.mids * 2.5)

        # Smooth bass component for continuous depth pressure
        self._bass_smoothed += (frame.bass - self._bass_smoothed) * min(1.0, dt * 3.5)

        # Fast attack & smooth decay for rhythmic beat zoom impulse
        self._zoom_impulse *= np.exp(-dt * 4.5)
        if frame.beat:
            self._zoom_impulse = min(1.0, self._zoom_impulse + 0.75)

        # Strong beat bounded zoom event
        if frame.strong_beat and (self._elapsed - self._strong_zoom_t) > 1.2:
            self._strong_zoom_t = self._elapsed

        if self._strong_zoom_t >= 0:
            age = self._elapsed - self._strong_zoom_t
            if age < 0.5:
                self._strong_zoom_progress = np.sin((age / 0.5) * np.pi)
            else:
                self._strong_zoom_progress = 0.0

        # True Z-depth target model: moves closer to camera on musical pressure
        z_approach = (self._bass_smoothed * 0.75) + (self._zoom_impulse * 0.50) + (self._strong_zoom_progress * 0.60)
        self.target_camera_dist = self.BASE_CAMERA_DIST - z_approach
        self.target_camera_dist = max(self.MIN_CAMERA_DIST, min(self.MAX_CAMERA_DIST, self.target_camera_dist))

        # Spring interpolation for smooth camera breathing
        self.camera_dist += (self.target_camera_dist - self.camera_dist) * min(1.0, dt * 7.5)

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
        fov = min(self.w, self.h) * 0.95 + (fckvar * 30)
        scale_pulse = 1.0 + (frame.bass * 0.12)

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
            # True 3D Z-depth perspective projection
            divisor = self.camera_dist + rz
            if divisor < 0.1:
                divisor = 0.1
            factor = fov / divisor
            projected.append((int(rx * factor + cx), int(ry * factor + cy)))

        min_z, max_z = min(depths), max(depths)
        z_range = max(0.01, max_z - min_z)
        inv_z_range = 1.0 / z_range
        norm_depths = [1.0 - (d - min_z) * inv_z_range for d in depths]

        r_beat = 100 if frame.strong_beat else 0
        g_mids = frame.mids * 100
        b_val = int(min(255, 180 + frame.treble * 75))
        heat_base = (frame.bass * 0.5) + (fckvar * 0.2)
        strong_beat = frame.strong_beat
        fckvar_14 = fckvar > 1.4

        # Draw wireframe lines
        for p1_idx, p2_idx in self._edges:
            p1 = projected[p1_idx]
            p2 = projected[p2_idx]

            norm_z = (norm_depths[p1_idx] + norm_depths[p2_idx]) * 0.5
            heat = min(1.0, (norm_z * 0.5) + heat_base)
            r = int(min(255, 30 + heat * 225 + r_beat))
            g = int(min(255, 100 + (1.0 - heat) * 155 + g_mids))

            thickness = 3 if fckvar_14 else (2 if (heat > 0.7 or strong_beat) else 1)
            pygame.draw.line(surface, (r, g, b_val), p1, p2, thickness)

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

    def get_debug_state(self) -> dict:
        """Exposes internal state for automated tests — not part of the Visualizer contract."""
        return {
            "camera_dist": self.camera_dist,
            "target_camera_dist": self.target_camera_dist,
            "bass_smoothed": self._bass_smoothed,
            "zoom_impulse": self._zoom_impulse,
            "strong_zoom_progress": self._strong_zoom_progress,
        }
