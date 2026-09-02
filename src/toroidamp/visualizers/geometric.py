# ToroidAMP - 3D Geometric Morphing Visualizer
# Evolved from the donor GeometricTransformer3D (effects.py:222).
# Full 4-shape morphing (SPHERE -> TORUS -> KNOT -> CYLINDER) with plasma/heatmap
# vertex coloring, particle spark ejection on transients, and
# ghost-trail transients.

import math
import random
import colorsys

import pygame
import numpy as np

from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


class GeometricShapesVisualizer(Visualizer):
    """
    3D Wireframe Mesh Morphing visualizer with parametric shape blending,
    plasma-colored edges, particle spark ejection on transients, and
    ghost-trail distortion on strong beats.

    Musical thesis: The camera *breathes through* geometric topology —
    each shape is a room the music moves between. Bass drives mesh pulse
    and scale expansion; mids drive rotation speed and inter-shape
    transition velocity; treble drives vertex jitter and sparkle edge
    thickness; spectrum modulates the plasma color phase across the mesh
    surface; beats trigger shape transitions; strong beats trigger
    particle sparks and ghost-trail bursts.
    """

    SHAPES = ("SPHERE", "TORUS", "KNOT", "CYLINDER")

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self.rows = 24
        self.cols = 30

        self.rng = random.Random(1337)

        self._curr_shape = 0
        self._morph_progress = 0.0  # 0.0 = at curr, 1.0 = transitioning to next
        self._elapsed = 0.0

        # Rotation state (auto-driven by mids)
        self._rot_x = 0.0
        self._rot_y = 0.0
        self._rot_z = 0.0
        self._dragging = False
        self._last_mouse = (0, 0)

        # Smoothed audio envelopes
        self._bass_smoothed = 0.0
        self._mids_smoothed = 0.0
        self._treble_smoothed = 0.0
        self._rms_smoothed = 0.0
        self._beat_impulse = 0.0
        self._strong_event_t = -999.0
        self._strong_event_progress = 0.0

        # Heavy Bass Mechanics: Topological deformation & shockwave ripple phase
        self._bass_shock_phase = 0.0
        self._bass_shock_intensity = 0.0
        self._topological_warp = 0.0

        # Coherent musical energy scalar (the Toroid's "one number drives
        # everything" model) + spring-smoothed zoom pressure. This is what
        # makes the whole surface breathe as a single body in the pocket.
        self._shape_energy = 0.0
        self._camera_zoom = 1.0
        self._target_zoom = 1.0
        self.MIN_ZOOM = 0.92
        self.MAX_ZOOM = 1.16

        # Plasma / color state
        self._plasma_time = 0.0

        # 5-band smoothed spectral energy, used for star colors.
        self._bands_smooth = [0.0] * 5

        # Coherent starfield: stars line a receding tunnel of spectrum
        # bands. Each star is bound to a band (real causality), colored by
        # that band, and streams outward with musical energy.
        self._star_bands = (0, 1, 2, 3, 4)  # palette index per star
        self._stars: list[dict] = []
        self._spawn_starfield()

    def _spawn_starfield(self) -> None:
        self._stars.clear()
        stars = 260
        for i in range(stars):
            ang = (i / stars) * 2.0 * math.pi + self.rng.uniform(-0.05, 0.05)
            radius = self.rng.uniform(0.05, 1.0)
            z = self.rng.uniform(0.05, 1.0)
            band = i % 5
            self._stars.append({
                "angle": ang,
                "radius": radius,
                "z": z,
                "band": band,
                "twinkle": self.rng.uniform(0.0, 2.0 * math.pi),
                "size": self.rng.uniform(1.2, 3.2),
            })

        # Ghost surface (persistent for trail effects)
        self._ghost_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        # Geometry generation
        self._shape_vertices: dict[str, list[tuple[float, float, float]]] = {}
        self._edges: list[tuple[int, int]] = []
        self._gen_geometry()

    def get_name(self) -> str:
        return "Geometric Morph"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self._ghost_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

    def _gen_geometry(self) -> None:
        """Generate parametric vertices for all four shapes + wireframe edges."""
        self._shape_vertices.clear()
        self._edges.clear()

        cols = self.cols
        rows = self.rows

        # Edge connectivity (grid topology)
        for i in range(rows):
            row_offset = i * cols
            next_row_offset = (i + 1) * cols
            for j in range(cols):
                current = row_offset + j
                self._edges.append((current, row_offset + (j + 1) % cols))
                if i < rows - 1:
                    self._edges.append((current, next_row_offset + j))

        # Generate vertices and store parametric UV for each shape
        self._shape_uvs: list[tuple[float, float, float, float]] = []
        for i in range(rows):
            u = i / (rows - 1) if rows > 1 else 0.0
            for j in range(cols):
                v_param = j / cols
                theta = v_param * 2.0 * math.pi
                phi = u * math.pi
                self._shape_uvs.append((u, v_param, theta, phi))

        for shape_name in self.SHAPES:
            vertices: list[tuple[float, float, float]] = []
            for u, v_param, theta, phi in self._shape_uvs:
                x, y, z = self._parametric_point(shape_name, u, v_param, theta, phi)
                vertices.append((x, y, z))
            self._shape_vertices[shape_name] = vertices

    def _parametric_point(self, shape: str, u: float, v_param: float, theta: float, phi: float,
                          bass_warp: float = 0.0):
        """Compute a single parametric point on the given shape with bass-driven topological warp."""
        if shape == "SPHERE":
            # Bass adds high-impact radial harmonics (plasma orb effect)
            radius = 1.0 + bass_warp * (0.28 * math.sin(theta * 3.0 + phi * 2.0) + 0.15 * math.cos(theta * 2.0))
            sin_phi = math.sin(phi)
            x = radius * sin_phi * math.cos(theta)
            y = radius * math.cos(phi)
            z = radius * sin_phi * math.sin(theta)
        elif shape == "TORUS":
            # Bass inflates the torus tube radius and ripples the ring
            R = 1.0 + bass_warp * 0.15 * math.sin(theta * 4.0)
            r_torus = 0.40 + bass_warp * (0.26 + 0.12 * math.cos(theta * 2.0))
            a = u * 2.0 * math.pi
            common = R + r_torus * math.cos(a)
            x = common * math.cos(theta)
            y = common * math.sin(theta)
            z = r_torus * math.sin(a)
        elif shape == "CYLINDER":
            # Bass creates a pulsing equatorial waist / barrel bulge
            barrel = 1.0 + bass_warp * 0.45 * math.sin(u * math.pi)
            x = math.cos(theta) * barrel
            z = math.sin(theta) * barrel
            y = (u - 0.5) * (2.5 + bass_warp * 0.4)
        elif shape == "KNOT":
            # Bass twists knot windings and expands radial loops
            p, q = 2, 3
            r = (0.5 + 0.2 * math.cos(phi)) * (1.0 + bass_warp * 0.35)
            twist = bass_warp * 0.5 * math.sin(theta * 3.0)
            common = (2.0 + math.cos(p * theta + twist)) * 0.5
            x = r * math.cos(q * theta) * common
            y = r * math.sin(q * theta) * common
            z = r * math.sin(p * theta + twist) * (1.0 + bass_warp * 0.30)
        else:
            x, y, z = 0.0, 0.0, 0.0
        return x, y, z

    def get_plasma_color(self, x: float, y: float, z: float, time_val: float, intensity: float):
        """4-sine plasma color field — direct port of donor get_plasma_color."""
        v = (
            math.sin(x * 1.5 + time_val * 0.8)
            + math.sin(y * 2.3 + time_val * 1.2)
            + math.sin(z * 3.1 + time_val * 0.5)
            + math.sin((x + y + z) * 0.7 + time_val * 2.0)
        ) * 0.25

        plasma_val = (v + 1) * 0.5
        plasma_val = min(1.0, plasma_val + intensity * 0.3)

        if plasma_val < 0.5:
            if plasma_val < 0.25:
                r = int(1020 * plasma_val)
                g = int(200 * plasma_val)
                b = int(255 * (0.5 + plasma_val))
            else:
                f = (plasma_val - 0.25) * 4
                r = int(255 * (1 - f * 0.5))
                g = int(255 * f)
                b = int(150 * (1 - plasma_val))
        else:
            if plasma_val < 0.75:
                r = int(200 + 55 * math.sin(time_val * 3))
                g = int(100 + 155 * plasma_val)
                b = int(255 * (plasma_val - 0.5) * 2)
            else:
                f = (plasma_val - 0.75) * 4
                r = 255
                g = int(255 * (1 - f))
                b = int(255 * f)

        boost = intensity * 0.8 * 255
        if boost > 1:
            r = min(255, int(r + boost * 0.23))
            g = min(255, int(g + boost * 0.15))
            b = min(255, int(b + boost * 0.31))

        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    def get_heatmap_color(self, val: float):
        """HSV-based heatmap: blue (high) -> red (low) -> white (peak)."""
        val = max(0.0, min(1.0, val))
        hue = 0.7 - (val * 0.7)
        saturation = 1.0
        value = 1.0
        if val > 0.9:
            saturation = max(0.0, 1.0 - ((val - 0.9) * 10.0))
            hue = 0.0
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        return (int(r * 255), int(g * 255), int(b * 255))

    def update(self, frame: AudioFrame, dt: float) -> None:
        dt = max(0.0001, min(0.1, dt))
        self._elapsed += dt

        # Smooth audio envelopes (exponential moving average)
        self._bass_smoothed += (frame.bass - self._bass_smoothed) * min(1.0, dt * 3.5)
        self._mids_smoothed += (frame.mids - self._mids_smoothed) * min(1.0, dt * 3.0)
        self._treble_smoothed += (frame.treble - self._treble_smoothed) * min(1.0, dt * 4.0)
        self._rms_smoothed += (frame.rms - self._rms_smoothed) * min(1.0, dt * 2.5)

        # Beat impulse (fast attack, smooth decay)
        self._beat_impulse *= math.exp(-dt * 5.0)
        if frame.beat:
            self._beat_impulse = min(1.0, self._beat_impulse + 0.75)

        # --- Heavy Bass Mechanics: Topological warp & Shockwave Ripple ---
        # 1. Topological warp tracks bass with explosive attack and snappy elastic bounce
        target_warp = frame.bass * 1.35 + (0.45 if frame.beat else 0.0) + (0.75 if frame.strong_beat else 0.0)
        warp_speed = 12.0 if target_warp > self._topological_warp else 4.5
        self._topological_warp += (target_warp - self._topological_warp) * min(1.0, dt * warp_speed)

        # 2. Shockwave ripple wave traveling across mesh topology on kicks / high bass
        self._bass_shock_phase += dt * 4.2
        if frame.beat or frame.bass > 0.65:
            self._bass_shock_intensity = min(1.0, self._bass_shock_intensity + 0.85)
        else:
            self._bass_shock_intensity *= math.exp(-dt * 4.0)

        # --- 5-band spectral energy (causes star colors/tunneling) ---
        for band in range(5):
            lo = band * 13
            hi = min(64, lo + 13)
            if frame.spectrum and hi > lo:
                val = sum(frame.spectrum[lo:hi]) / (hi - lo)
            else:
                val = 0.0
            self._bands_smooth[band] += (val - self._bands_smooth[band]) * min(1.0, dt * 4.0)

        # Strong beat event (cooldown-gated hyperspace warp)
        if frame.strong_beat and (self._elapsed - self._strong_event_t) > 2.0:
            self._strong_event_t = self._elapsed
        if self._strong_event_t >= 0:
            age = self._elapsed - self._strong_event_t
            duration = 0.35
            if age < duration:
                phase = age / duration
                self._strong_event_progress = math.sin(phase * math.pi)
            else:
                self._strong_event_progress = 0.0

        # --- COHERENT MUSICAL ENERGY (Toroid-style "one number") ---
        beat_step = 1.6 if frame.strong_beat else (0.8 if frame.beat else 0.0)
        raw_energy = (frame.bass * 1.1) + (frame.rms * 0.5) + (self._beat_impulse * 0.6) + beat_step * 0.3
        self._shape_energy += (raw_energy - self._shape_energy) * min(1.0, dt * (6.0 if raw_energy > self._shape_energy else 3.2))

        # Spring-smoothed zoom pressure (camera breathing with heavy bass thrust)
        pressure = (self._bass_smoothed * 0.90) + (self._beat_impulse * 0.50) + (self._strong_event_progress * 0.60)
        self._target_zoom = self.MIN_ZOOM + pressure * (self.MAX_ZOOM - self.MIN_ZOOM)
        self._target_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self._target_zoom))
        self._camera_zoom += (self._target_zoom - self._camera_zoom) * min(1.0, dt * 7.5)

        # Plasma time advances with mids + bass vibration
        self._plasma_time += dt * (1.0 + self._mids_smoothed * 2.5 + self._topological_warp * 0.8)

        # --- Beat-locked shape morphing ---
        if frame.beat:
            self._morph_progress += 0.42 + self._beat_impulse * 0.35
        else:
            self._morph_progress += dt * (0.12 + self._shape_energy * 0.10)

        if self._morph_progress >= 1.0:
            self._morph_progress = 0.0
            self._curr_shape = (self._curr_shape + 1) % len(self.SHAPES)

        # --- Beat-reactive rotation: one coherent energy drives all axes ---
        rot_speed = dt * (0.3 + self._shape_energy * 1.4)
        self._rot_y += rot_speed * 1.0
        self._rot_x += rot_speed * 0.5
        self._rot_z += rot_speed * 0.2

        # Starfield drift: stars stream outward along their radius as the
        # shape energy rises, and recycle toward the far plane.
        drift = dt * (0.25 + self._shape_energy * 0.55 + self._topological_warp * 0.35)
        for star in self._stars:
            star["z"] -= drift
            if star["z"] <= 0.04:
                star["z"] = 1.0
                star["radius"] = self.rng.uniform(0.02, 1.0)
                star["angle"] = self.rng.uniform(0, 2.0 * math.pi)
                star["twinkle"] = self.rng.uniform(0.0, 2.0 * math.pi)

    def _star_palette(self, band: int) -> tuple[int, int, int]:
        """Coherent, musically-bound star color from a spectral band."""
        palettes = (
            (255, 120, 220),   # 0: bass -> hot magenta
            (120, 190, 255),   # 1: low-mid -> cobalt
            (120, 245, 255),   # 2: mid -> cyan
            (120, 255, 160),   # 3: high-mid -> emerald
            (255, 244, 160),   # 4: treble -> gold
        )
        return palettes[band % len(palettes)]

    def _draw_starfield(self, surface: pygame.Surface, cx: float, cy: float) -> None:
        """Draws the spectrum-bound star tunnel behind the morphing mesh with bass gravity resonance."""
        w, h = self.w, self.h
        max_r = max(w, h) * 0.52
        bass_repel = self._topological_warp * 0.18 + self._bass_shock_intensity * 0.14
        for star in self._stars:
            z = max(0.04, star["z"])
            depth_frac = 1.0 - z
            band = star["band"]
            band_energy = self._bands_smooth[band] if self._bands_smooth else 0.0

            twinkle = 0.5 + 0.5 * math.sin(self._plasma_time * 3.0 + star["twinkle"])
            brightness = 0.42 + band_energy * 0.88
            brightness *= (0.30 + 0.70 * depth_frac)
            brightness *= (0.65 + 0.35 * twinkle * (0.4 + self._treble_smoothed * 1.4))

            base = self._star_palette(band)
            r = int(min(255, base[0] * brightness))
            g = int(min(255, base[1] * brightness))
            b = int(min(255, base[2] * brightness))
            if brightness < 0.05:
                continue

            # Heavy Bass Star Gravity: Repel stars outward on massive bass drops
            star_rad = star["radius"] * (1.0 + bass_repel * (1.0 - depth_frac * 0.5))
            factor = (0.18 + 0.82 * depth_frac) * max_r
            sx = cx + math.cos(star["angle"]) * star_rad * factor
            sy = cy + math.sin(star["angle"]) * star_rad * factor
            if not (-10 <= sx < w + 10 and -10 <= sy < h + 10):
                continue

            size = max(1, int(star["size"] * (0.6 + depth_frac * 1.6)))
            if size > 1:
                halo = max(2, int(size * 1.7))
                pygame.draw.circle(surface, (r // 2, g // 3, b // 3), (int(sx), int(sy)), halo)
            pygame.draw.circle(surface, (r, g, b), (int(sx), int(sy)), max(1, size))
            if depth_frac > 0.5 and band_energy > 0.5:
                pygame.draw.circle(surface, (255, 255, 255), (int(sx), int(sy)), max(1, size // 2))

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        # Cosmic void background
        bg_brightness = int(4 + self._rms_smoothed * 12 + self._topological_warp * 8)
        surface.fill((bg_brightness, bg_brightness, bg_brightness + 2))

        cx, cy = self.w // 2, self.h // 2

        # Spectrum-bound star tunnel
        self._draw_starfield(surface, cx, cy)

        # Coherent FOV
        fov = min(self.w, self.h) * (0.75 + self._shape_energy * 0.10)

        # Audio-derived rendering parameters
        treble_jitter = self._treble_smoothed * 0.08
        jitter_active = (self._treble_smoothed > 0.3 or self._strong_event_progress > 0.05)
        jitter_range = treble_jitter if jitter_active else 0.0

        scale_pulse = (1.0 + (self._shape_energy * 0.06) + (self._topological_warp * 0.12)) * 0.62
        pulse = scale_pulse * self._camera_zoom

        beat_flash = self._beat_impulse

        wf_len = len(frame.waveform)

        # Smoothstep for morph transition
        et = self._morph_progress * self._morph_progress * (3.0 - 2.0 * self._morph_progress)

        # Rotation matrices
        c_x, s_x = math.cos(self._rot_x), math.sin(self._rot_x)
        c_y, s_y = math.cos(self._rot_y), math.sin(self._rot_y)
        c_z, s_z = math.cos(self._rot_z), math.sin(self._rot_z)

        current_shape = self.SHAPES[self._curr_shape]
        next_shape = self.SHAPES[(self._curr_shape + 1) % len(self.SHAPES)]

        projected: list[tuple[int, int]] = []
        depths: list[float] = []
        vertex_3d: list[tuple[float, float, float]] = []

        bass_warp = self._topological_warp
        shock_int = self._bass_shock_intensity
        shock_ph = self._bass_shock_phase

        for idx, (u, v_param, theta, phi) in enumerate(self._shape_uvs):
            # Dynamic parametric topology computed with bass warp
            p1 = self._parametric_point(current_shape, u, v_param, theta, phi, bass_warp)
            p2 = self._parametric_point(next_shape, u, v_param, theta, phi, bass_warp)

            # Morph interpolation
            x = p1[0] + (p2[0] - p1[0]) * et
            y = p1[1] + (p2[1] - p1[1]) * et
            z = p1[2] + (p2[2] - p1[2]) * et

            # Radial Shockwave Ripple across mesh surface on heavy bass hits
            if shock_int > 0.01:
                dist = math.sqrt(x * x + y * y + z * z)
                ripple = math.sin(dist * 6.2 - shock_ph * 3.5) * shock_int * 0.14
                if dist > 1e-5:
                    inv_d = 1.0 + ripple / dist
                    x *= inv_d
                    y *= inv_d
                    z *= inv_d

            if jitter_active:
                jitter_f = jitter_range * (1.0 + self._strong_event_progress + self._shape_energy)
                x += random.uniform(-jitter_f, jitter_f)
                y += random.uniform(-jitter_f, jitter_f)
                z += random.uniform(-jitter_f, jitter_f)

            # Waveform vertex modulation
            if wf_len > 0:
                wave_mod = frame.waveform[idx % wf_len] * 0.12 * self._shape_energy
                x += wave_mod
                y += wave_mod

            x *= pulse
            y *= pulse
            z *= pulse

            # 3D rotation: Y -> X -> Z
            rx = x * c_y - z * s_y
            rz = x * s_y + z * c_y
            ry = y

            new_ry = ry * c_x - rz * s_x
            rz = ry * s_x + rz * c_x
            ry = new_ry

            new_rx = rx * c_z - ry * s_z
            ry = rx * s_z + ry * c_z
            rx = new_rx

            vertex_3d.append((rx, ry, rz))
            depths.append(rz)

            divisor = (4.0 + rz) / self._camera_zoom
            if divisor < 0.1:
                divisor = 0.1
            factor = fov / divisor
            projected.append((int(rx * factor + cx), int(ry * factor + cy)))

        # Depth normalization
        min_z, max_z = min(depths), max(depths)
        z_range = max_z - min_z if max_z != min_z else 1.0

        # Determine color mode
        use_plasma = self._bass_smoothed > 0.2 or self._mids_smoothed > 0.4
        intensity = 0.25 + self._shape_energy * 0.55 + beat_flash * 0.30 + self._strong_event_progress * 0.2 + bass_warp * 0.25
        bpm_heat_boost = self._strong_event_progress * 0.3

        draw_line = pygame.draw.line
        wl, wh = self.w + 100, self.h + 100

        for start_idx, end_idx in self._edges:
            p1 = projected[start_idx]
            p2 = projected[end_idx]

            if not (-100 < p1[0] < wl and -100 < p1[1] < wh):
                continue

            avg_z = (depths[start_idx] + depths[end_idx]) * 0.5
            norm_z = 1.0 - ((avg_z - min_z) / z_range)

            heat_val = min(1.0, (norm_z * 0.35) + (intensity * 0.85) + bpm_heat_boost)

            if use_plasma:
                v3_start = vertex_3d[start_idx]
                v3_end = vertex_3d[end_idx]
                mid_x = (v3_start[0] + v3_end[0]) * 0.5
                mid_y = (v3_start[1] + v3_end[1]) * 0.5
                mid_z = (v3_start[2] + v3_end[2]) * 0.5
                color = self.get_plasma_color(mid_x, mid_y, mid_z, self._plasma_time,
                                              intensity + bpm_heat_boost)
            else:
                color = self.get_heatmap_color(heat_val)

            # Beat flash & Bass Thermal pop: brighten edges on high sub-bass tension
            color = tuple(min(255, int(c + beat_flash * 60 + bass_warp * 40)) for c in color)

            thickness = 1
            if heat_val > 0.55 or bass_warp > 0.4:
                thickness = 2
            if heat_val > 0.80 or bass_warp > 0.7:
                thickness = 3
            if intensity > 0.95 or (bass_warp > 0.9 and beat_flash > 0.4):
                thickness = 4
            if beat_flash > 0.5:
                thickness += 1

            draw_line(surface, color, p1, p2, thickness)

            # White highlight on very hot edges, strong beats, or heavy bass kicks
            if heat_val > 0.85 or self._strong_event_progress > 0.1 or beat_flash > 0.6 or bass_warp > 0.85:
                draw_line(surface, (255, 255, 255), p1, p2, 1)

        # Ghost trail on strong beats
        special_effect = intensity > 0.95 or self._strong_event_progress > 0.1 or bass_warp > 0.95
        if special_effect:
            self._ghost_surf.fill((0, 0, 0, 0))
            offset = intensity * 8 + (4 if self._strong_event_progress > 0.1 else 0)
            ghost_color = (100, 255, 100, 120) if self._strong_event_progress > 0.1 else (255, 100, 100, 80)

            for i in range(0, len(self._edges), 3):
                start_idx, end_idx = self._edges[i]
                p1 = projected[start_idx]
                p2 = projected[end_idx]
                offset_x = random.uniform(-offset, offset)
                offset_y = random.uniform(-offset, offset)
                gp1 = (p1[0] + offset_x, p1[1] + offset_y)
                gp2 = (p2[0] + offset_x, p2[1] + offset_y)
                pygame.draw.line(self._ghost_surf, ghost_color, gp1, gp2, 1)

            surface.blit(self._ghost_surf, (0, 0))

    def get_debug_state(self) -> dict:
        return {
            "current_shape": self.SHAPES[self._curr_shape],
            "morph_progress": self._morph_progress,
            "bass_smoothed": self._bass_smoothed,
            "mids_smoothed": self._mids_smoothed,
            "treble_smoothed": self._treble_smoothed,
            "beat_impulse": self._beat_impulse,
            "strong_event_progress": self._strong_event_progress,
            "shape_energy": self._shape_energy,
            "camera_zoom": self._camera_zoom,
            "target_zoom": self._target_zoom,
            "rot_x": self._rot_x,
            "rot_y": self._rot_y,
            "star_count": len(self._stars),
            "bands_smooth": self._bands_smooth,
            "topological_warp": self._topological_warp,
            "bass_shock_intensity": self._bass_shock_intensity,
            "bass_shock_phase": self._bass_shock_phase,
        }
