# ToroidAMP - X-Wing Squadron Visualizer
# Extracted from the donor PraxisEvent (effects.py:2173).
# Focuses on the X-Wing/Y-Wing waypoint flight, 3D projection, peace
# sign collision avoidance, 3D grid floor, and rainbow text finale —
# all driven by AudioFrame beats and bass instead of fixed time phases.

import math
import random

import pygame

from .base import Visualizer
from ..analysis.audio_frame import AudioFrame
from ..resources import resolve_package_asset


class XWingSquadronVisualizer(Visualizer):
    """
    Audio-reactive X-Wing/Y-Wing squadron battle over a 3D perspective
    grid floor. Strong beats spawn squadrons; bass drives peace sign
    pulse and grid scroll; treble adds engine glow; sustained high RMS
    transitions to the peace sequence with animated rainbow text.

    Phases are driven by audio energy, not wall-clock time:
    - LOW ENERGY: standby grid + drifting X-Wings
    - HIGH ENERGY (strong beats): full squadron battle
    - SUSTAINED HIGH RMS: peace sign + rainbow text finale
    """

    NUM_BARS = 64
    # Length (seconds) of a full 360-degree barrel-roll manoeuvre.
    BARREL_ROLL_DURATION = 0.85
    NEON_PALETTE = [
        (255, 0, 110),   # Rosa neón
        (0, 240, 255),   # Cian neón
        (180, 0, 255),   # Púrpura neón
        (220, 255, 0),   # Amarillo neón
    ]

    XWING_ROUTES = [
        # All routes converge toward the logo's vanishing point at the
        # horizon center (screen z keeps increasing as they approach).
        # Each route carries at least one full 360-degree barrel roll so
        # the squadron visibly rolls as it attacks the banner.
        # Route 1: sweeping approach from left, brief roll, converge
        [
            {"x": -1200, "y": -260, "z": 1.0, "action": "FLY"},
            {"x": -500,  "y": -80,  "z": 12.0, "action": "CURVE_RIGHT"},
            {"x": -220,  "y": -50,  "z": 22.0, "action": "BARREL_ROLL"},
            {"x": 0,     "y": -30,  "z": 40.0, "action": "FLY"},
        ],
        # Route 2: aggressive zigzag with a roll midway, converge
        [
            {"x": 900,  "y": -240, "z": 1.0, "action": "FLY"},
            {"x": 300,  "y": -100, "z": 14.0, "action": "ZIGZAG"},
            {"x": 80,   "y": -55,  "z": 26.0, "action": "BARREL_ROLL"},
            {"x": -80,  "y": -35,  "z": 38.0, "action": "FLY"},
        ],
        # Route 3: low ground-skimming dash that climbs and rolls to the logo
        [
            {"x": -800, "y": 260, "z": 1.0, "action": "FLY"},
            {"x": -200, "y": 140, "z": 16.0, "action": "CURVE_RIGHT"},
            {"x": 60,   "y": -20,  "z": 30.0, "action": "BARREL_ROLL"},
            {"x": 40,   "y": -40,  "z": 40.0, "action": "DIVE"},
        ],
        # Route 4: high dive, double-roll toward the vanishing point
        [
            {"x": 600,  "y": -380, "z": 1.0, "action": "FLY"},
            {"x": 280,  "y": -220, "z": 12.0, "action": "BARREL_ROLL"},
            {"x": 160,  "y": -160, "z": 18.0, "action": "BARREL_ROLL"},
            {"x": 30,   "y": -30,  "z": 42.0, "action": "FLY"},
        ],
    ]

    YWING_ROUTES = [
        [
            {"x": -500, "y": -180, "z": 2.0, "action": "FLY"},
            {"x": -120, "y": -60, "z": 30.0, "action": "FLY"},
            {"x": 20,   "y": -20, "z": 90.0, "action": "DIVE"},
        ],
        [
            {"x": 400, "y": -160, "z": 2.0, "action": "FLY"},
            {"x": 60,  "y": -70,  "z": 30.0, "action": "FLY"},
            {"x": -10, "y": -25,  "z": 90.0, "action": "DIVE"},
        ],
        [
            {"x": 0, "y": -260, "z": 2.0, "action": "FLY"},
            {"x": 0, "y": -90,  "z": 30.0, "action": "ZIGZAG"},
            {"x": 0, "y": -30,  "z": 110.0, "action": "DIVE"},
        ],
        [
            {"x": -400, "y": 180, "z": 5.0, "action": "FLY"},
            {"x": -100, "y": 60,  "z": 40.0, "action": "BARREL_ROLL"},
            {"x": 20,   "y": -20, "z": 120.0, "action": "EXIT"},
        ],
    ]

    YWING_FORMATION = [
        (0, 0),    # Leader
        (25, -5),  # Right rear
        (-25, -5), # Left rear
        (50, -10), # Far right
        (-50, -10),# Far left
    ]

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self._elapsed_time = 0.0
        self._grid_rows = 50
        self._grid_cols = 31

        self.font_lg = pygame.font.SysFont("courier new", 42, bold=True)
        self.font_sm = pygame.font.SysFont("courier new", 16, bold=False)

        self._squadron: list[dict] = []
        self._ywings: list[dict] = []
        self._ywing_timer = 0

        self._lit_cells: list[list] = []

        self._grid_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        # Horizon: the logo floats here; the grid floor recedes below it,
        # and the X-Wings converge toward it.
        self._horizon_y = int(self.h * 0.42)
        self._logo_surf: pygame.Surface | None = None
        self._logo_half_w = 0
        self._logo_half_h = 0
        self._load_logo()

        self._spawn_initial_xwings(8)

        self._bass_smoothed = 0.0
        self._treble_smoothed = 0.0
        self._rms_smoothed = 0.0
        self._beat_impulse = 0.0
        self._in_peace_mode = False

    def _load_logo(self) -> None:
        """Loads the ToroidAMP title logo, scaled to fit the void horizontally
        at the horizon. Falls back gracefully to a plain banner if missing.
        Tolerates a missing display surface (convert_alpha needs one)."""
        path = resolve_package_asset("assets/images/ToroidAMP_title.png")
        if path:
            try:
                raw = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    raw = raw.convert_alpha()
                # Fit to a fraction of the viewport width, keeping aspect.
                target_w = int(self.w * 0.82)
                if target_w > 10:
                    ratio = target_w / raw.get_width()
                    tw = target_w
                    th = max(1, int(raw.get_height() * ratio))
                    self._logo_surf = pygame.transform.smoothscale(raw, (tw, th))
                    self._logo_half_w = tw // 2
                    self._logo_half_h = th // 2
            except Exception:
                self._logo_surf = None
        if self._logo_surf is None:
            # Fallback banner: text-based horizon title.
            self._logo_surf = self.font_lg.render("TOROIDAMP", True, (0, 229, 255))
            self._logo_half_w = self._logo_surf.get_width() // 2
            self._logo_half_h = self._logo_surf.get_height() // 2

    def get_name(self) -> str:
        return "X-Wing Squadron"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)
        self._grid_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._horizon_y = int(self.h * 0.42)
        self._load_logo()

    def _spawn_initial_xwings(self, count: int) -> None:
        for _ in range(count):
            self._spawn_xwing(initial=True)

    def _spawn_xwing(self, initial: bool = False) -> None:
        route = random.choice(self.XWING_ROUTES)
        offset_x = random.uniform(-50, 50)
        offset_y = random.uniform(-50, 50)
        start_point = route[0]

        self._squadron.append({
            "x": start_point["x"] + offset_x,
            "y": start_point["y"] + offset_y,
            "z": random.uniform(1.0, 10.0) if initial else 0.5,
            "vx": 0.0,
            "vy": 0.0,
            "vz": random.uniform(0.2, 0.35),
            "route": route,
            "wp_idx": 1,
            "roll": 0.0,
            "bank": 0.0,
            "trail": [],
            "offset_x": offset_x,
            "offset_y": offset_y,
            "evading": False,
            # Barrel-roll animation state: t goes 0->1 during the roll,
            # and roll is reset to 0 when it completes.
            "roll_t": 0.0,
            "roll_active": False,
        })

    def _spawn_ywing_squad(self) -> None:
        route = random.choice(self.YWING_ROUTES)
        start_point = route[0]
        squad_offset_x = random.uniform(-100, 100)

        for dx, dy in self.YWING_FORMATION:
            self._ywings.append({
                "x": start_point["x"] + squad_offset_x + dx,
                "y": start_point["y"] + dy,
                "z": start_point["z"],
                "vx": 0.0,
                "vy": 0.0,
                "vz": 0.0,
                "roll": 0.0,
                "bank": 0.0,
                "route": route,
                "wp_idx": 1,
                "squad_dx": dx,
                "squad_dy": dy,
                "offset_x": squad_offset_x,
                "type": "YWING",
                "trail_l": [],
                "trail_r": [],
            })

    def _draw_xwing_3d(self, surface: pygame.Surface, ship: dict,
                       center_x: int, center_y: int) -> None:
        z = max(0.1, ship["z"])
        screen_x = center_x + ship["x"] / z
        screen_y = center_y + ship["y"] / z
        size = 80.0 / z

        if size < 2 or size > 200:
            return

        # Banking (wing tilt from horizontal velocity)
        target_bank = -ship["vx"] * 0.1
        ship["bank"] += (target_bank - ship["bank"]) * 0.1
        total_rot = ship["bank"] + ship["roll"]
        cos_rot, sin_rot = math.cos(total_rot), math.sin(total_rot)

        def rotate(px, py):
            return (screen_x + px * cos_rot - py * sin_rot,
                    screen_y + px * sin_rot + py * cos_rot)

        wing_span = size * 0.8
        wing_h = size * 0.25
        tl = rotate(-wing_span, -wing_h)
        br = rotate(wing_span, wing_h)
        bl = rotate(-wing_span, wing_h)
        tr = rotate(wing_span, -wing_h)

        # Wings (X shape) — color shifts with engine trail
        wing_color = (200, 200, 220)
        if ship["evading"]:
            wing_color = (255, 200, 100)

        line_w = max(1, int(size * 0.08))
        pygame.draw.line(surface, wing_color, tl, br, line_w)
        pygame.draw.line(surface, wing_color, bl, tr, line_w)

        # Engines (bright on beat)
        engine_color = (255, 100, 50)
        engine_brightness = 1.0 + self._bass_smoothed * 0.5 + self._beat_impulse * 0.5
        engine_color = tuple(min(255, int(c * engine_brightness)) for c in engine_color)
        engine_size = max(1, int(size * 0.1))

        for point in [tl, br, bl, tr]:
            pygame.draw.circle(surface, engine_color,
                             (int(point[0]), int(point[1])), engine_size)

        # Fuselage
        ft = rotate(0, -size * 0.5)
        fb = rotate(0, size * 0.4)
        pygame.draw.line(surface, (230, 230, 250), ft, fb,
                        max(1, int(size * 0.12)))

    def _draw_ywing_3d(self, surface: pygame.Surface, ship: dict,
                       center_x: int, center_y: int) -> None:
        z = max(0.1, ship["z"])
        if z > 400:
            return

        scale = 500.0 / z
        screen_x = center_x + ship["x"] * scale
        screen_y = center_y + ship["y"] * scale
        size = scale * 6.0

        if size < 2:
            return

        target_bank = -ship["vx"] * 0.02
        ship["bank"] += (target_bank - ship["bank"]) * 0.1
        total_rot = ship["bank"] + ship["roll"]
        cos_rot, sin_rot = math.cos(total_rot), math.sin(total_rot)

        def rotate(px, py):
            return (screen_x + px * cos_rot - py * sin_rot,
                    screen_y + px * sin_rot + py * cos_rot)

        # Cabin (triangle)
        pygame.draw.polygon(surface, (220, 210, 100), [
            rotate(0, -size * 0.3),
            rotate(-size * 0.1, size * 0.1),
            rotate(size * 0.1, size * 0.1),
        ])

        # Central wing
        pygame.draw.line(surface, (180, 180, 190),
                         rotate(-size * 0.4, size * 0.1),
                         rotate(size * 0.4, size * 0.1),
                         max(1, int(size * 0.08)))

        # Side struts with engines
        for side_x in [-size * 0.4, size * 0.4]:
            pygame.draw.line(surface, (180, 180, 190),
                             rotate(side_x, size * 0.05),
                             rotate(side_x, size * 0.8),
                             max(1, int(size * 0.1)))
            engine_pos = rotate(side_x, size * 0.85)
            engine_glow = 1.0 + self._treble_smoothed * 0.5
            pygame.draw.circle(surface,
                             tuple(min(255, int(c * engine_glow)) for c in (255, 50, 100)),
                             (int(engine_pos[0]), int(engine_pos[1])),
                             max(1, int(size * 0.15)))

    def _draw_rainbow_text(self, surface: pygame.Surface, text: str,
                           center_x: int, center_y: int,
                           time_offset: float) -> None:
        total_w, _ = self.font_lg.size(text)
        start_x = center_x - total_w // 2

        for i, char in enumerate(text):
            hue = (time_offset * 3 + i * 0.3) % (2 * math.pi)
            r = int(127 + 127 * math.sin(hue))
            g = int(127 + 127 * math.sin(hue + 2))
            b = int(127 + 127 * math.sin(hue + 4))

            char_surf = self.font_lg.render(char, True, (r, g, b))
            surface.blit(char_surf, (start_x, center_y))
            start_x += char_surf.get_width()

    def _draw_3d_grid(self, surface: pygame.Surface, dt: float) -> None:
        """3D perspective grid floor, receding from beneath the logo horizon."""
        center_x = self.w // 2
        horizon_y = self._horizon_y
        camera_height = 600.0
        spacing_z = 2.0
        spacing_x = 2.0
        speed_z = 8.0 + self._bass_smoothed * 6.0
        z_shift = (self._elapsed_time * speed_z) % spacing_z

        def project(x_idx: float, z_depth: float) -> tuple[float, float]:
            if z_depth < 0.1:
                z_depth = 0.1
            scale = camera_height / z_depth
            world_x = x_idx * spacing_x
            return (center_x + world_x * scale, horizon_y + scale)

        self._grid_surf.fill((0, 0, 0, 0))

        # Lit cells
        for cell in self._lit_cells[:]:
            cell[3] -= dt * 0.5
            if cell[3] <= 0:
                self._lit_cells.remove(cell)
                continue

            z_idx, x_idx, color, life = cell
            z_near = (z_idx * spacing_z) + (spacing_z - z_shift)
            z_far = ((z_idx + 1) * spacing_z) + (spacing_z - z_shift)

            if z_near > 0.2:
                p1 = project(x_idx, z_near)
                p2 = project(x_idx + 1, z_near)
                p3 = project(x_idx + 1, z_far)
                p4 = project(x_idx, z_far)

                if p1[1] < self.h and p3[1] > horizon_y:
                    rgba = (*color, max(0, min(255, int(180 * life))))
                    pygame.draw.polygon(self._grid_surf, rgba, [p1, p2, p3, p4])
                    if life > 0.6:
                        pygame.draw.polygon(self._grid_surf,
                                           (255, 255, 255, int(100 * life)),
                                           [p1, p2, p3, p4], 1)

        # Grid lines
        for i in range(self._grid_rows):
            z_depth = (i * spacing_z) + (spacing_z - z_shift)
            if z_depth > 0.2:
                p_left = project(-15, z_depth)
                p_right = project(15, z_depth)

                if p_left[1] < self.h and p_left[1] > horizon_y:
                    alpha = max(0, min(255, int(200 * (20.0 / (z_depth + 5.0)))))
                    alpha += int(self._beat_impulse * 50)
                    alpha = min(255, alpha)
                    if alpha > 5:
                        pygame.draw.line(self._grid_surf,
                                        (0, 200, 100, alpha),
                                        (0, int(p_left[1])),
                                        (self.w, int(p_right[1])), 1)

        # Grid verticals
        for i in range(-15, 16):
            if i != 0:
                p_far = project(i, 100.0)
                p_near = project(i, 0.2)
                if p_far[1] < self.h and p_near[1] > horizon_y:
                    pygame.draw.line(self._grid_surf, (0, 150, 80, 40),
                                   p_far, p_near, 1)

        surface.blit(self._grid_surf, (0, 0))

    def update(self, frame: AudioFrame, dt: float) -> None:
        dt = max(0.0001, min(0.1, dt))
        self._elapsed_time += dt
        self._ywing_timer += 1

        self._bass_smoothed += (frame.bass - self._bass_smoothed) * min(1.0, dt * 3.0)
        self._treble_smoothed += (frame.treble - self._treble_smoothed) * min(1.0, dt * 4.0)
        self._rms_smoothed += (frame.rms - self._rms_smoothed) * min(1.0, dt * 2.5)

        self._beat_impulse *= math.exp(-dt * 6.0)
        if frame.beat:
            self._beat_impulse = min(1.0, self._beat_impulse + 0.5 + frame.bass * 0.3)

        # Determine phase based on sustained energy
        self._in_peace_mode = self._rms_smoothed > 0.6

        # Spawn X-Wings on strong beats (a burst when the kick lands)
        if frame.strong_beat:
            for _ in range(2):
                self._spawn_xwing(initial=False)
        elif frame.beat:
            self._spawn_xwing(initial=False)

        # Spawn Y-Wing squadrons periodically when bass is high
        if self._ywing_timer > max(60, 120 - int(self._bass_smoothed * 100)):
            self._spawn_ywing_squad()
            self._ywing_timer = 0

        # Spawn lit cells from spectrum when in peace or high energy
        if frame.bass > 0.3 and random.random() < frame.bass * 0.08:
            lane = random.choice([-1, 0])
            color = random.choice(self.NEON_PALETTE)
            self._lit_cells.append([
                random.randint(5, 40), lane, color, 1.0
            ])

        # Update Y-Wings (background formations)
        center_x, center_y = self.w // 2, self._horizon_y
        for ywing in self._ywings[:]:
            route = ywing["route"]
            target = None

            if ywing["wp_idx"] < len(route):
                waypoint = route[ywing["wp_idx"]]
                target = {
                    "x": waypoint["x"] + ywing["offset_x"] + ywing["squad_dx"],
                    "y": waypoint["y"] + ywing["squad_dy"],
                    "z": waypoint["z"],
                }
                action = waypoint.get("action")
                if action == "BARREL_ROLL":
                    ywing["roll"] += 0.05
                elif action == "ZIGZAG":
                    ywing["x"] += math.sin(self._elapsed_time * 4) * 5
                elif action == "DIVE":
                    ywing["y"] += 2.0
            else:
                last_point = route[-1]
                target = {
                    "x": last_point["x"] + ywing["squad_dx"],
                    "y": last_point["y"] + ywing["squad_dy"] + 2000,
                    "z": last_point["z"] + 500,
                }

            dx = target["x"] - ywing["x"]
            dy = target["y"] - ywing["y"]
            dz = target["z"] - ywing["z"]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            if dist < 40.0:
                ywing["wp_idx"] += 1
            else:
                speed = 2.5 + (ywing["z"] * 0.08)
                ywing["vx"] += ((dx / dist) * speed - ywing["vx"]) * 0.05
                ywing["vy"] += ((dy / dist) * speed - ywing["vy"]) * 0.05
                ywing["vz"] += ((dz / dist) * speed - ywing["vz"]) * 0.05

            ywing["x"] += ywing["vx"]
            ywing["y"] += ywing["vy"]
            ywing["z"] += ywing["vz"]

            if ywing["z"] > 400:
                self._ywings.remove(ywing)

        # Update X-Wings (foreground squadron)
        self._squadron.sort(key=lambda s: s["z"], reverse=True)

        for ship in self._squadron[:]:
            route = ship["route"]
            target_point = None

            if ship["wp_idx"] < len(route):
                waypoint = route[ship["wp_idx"]]
                target_point = (
                    waypoint["x"] + ship["offset_x"],
                    waypoint["y"] + ship["offset_y"],
                    waypoint["z"],
                )

                action = waypoint.get("action")
                if action == "BARREL_ROLL":
                    # Kick off a full 360-degree roll exactly once (if we are
                    # not already mid-roll), driven by a timing envelope.
                    if not ship["roll_active"]:
                        ship["roll_active"] = True
                        ship["roll_t"] = 0.0
                elif action == "ZIGZAG":
                    ship["x"] += math.sin(self._elapsed_time * 4) * 5
                    ship["roll"] = math.sin(self._elapsed_time * 4) * 0.5
            else:
                target_point = (ship["x"], ship["y"], ship["z"] + 100)

            # Advance the barrel-roll window and ease it out to upright.
            if ship["roll_active"]:
                ship["roll_t"] += dt / self.BARREL_ROLL_DURATION
                if ship["roll_t"] >= 1.0:
                    ship["roll_t"] = 1.0
                    ship["roll_active"] = False
                # 360 deg with ease-in-out: starts and ends level.
                ease = ship["roll_t"] * ship["roll_t"] * (3.0 - 2.0 * ship["roll_t"])
                ship["roll"] = ease * 2.0 * math.pi
            elif ship["roll"] != 0.0:
                ship["roll"] = 0.0  # snapped level after any finished roll

            dx = target_point[0] - ship["x"]
            dy = target_point[1] - ship["y"]
            dz = target_point[2] - ship["z"]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            if dist < 10.0:
                ship["wp_idx"] += 1
            else:
                vx_t = (dx / dist) * 3.5
                vy_t = (dy / dist) * 3.5
                ship["vx"] += (vx_t - ship["vx"]) * 0.05
                ship["vy"] += (vy_t - ship["vy"]) * 0.05

            ship["x"] += ship["vx"]
            ship["y"] += ship["vy"]
            ship["z"] += ship["vz"]

            # Trail
            sx = center_x + ship["x"] / max(0.1, ship["z"])
            sy = center_y + ship["y"] / max(0.1, ship["z"])
            ship["trail"].append((sx, sy))
            if len(ship["trail"]) > 8:
                ship["trail"].pop(0)

            if ship["z"] > 80:
                self._squadron.remove(ship)
                self._spawn_xwing(initial=False)

        # Replenish squadron so a stream always converges toward the logo
        if len(self._squadron) < 10:
            self._spawn_xwing(initial=True)

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        self.update(frame, dt)

        # Background
        bg_brightness = int(5 + self._rms_smoothed * 30)
        surface.fill((bg_brightness, bg_brightness, bg_brightness + 5))

        center_x = self.w // 2
        center_y = self._horizon_y

        # --- LOGO HORIZON BANNER (the X-Wings' destination) ---
        self._draw_3d_grid(surface, dt)
        if self._logo_surf:
            # Soft additive aureole behind the logo, pulsing gently with bass.
            # Drawn as a radial-ish glow so it reads as light, not an outline ring.
            g_w = self._logo_surf.get_width()
            g_h = self._logo_surf.get_height()
            glow_alpha = int(30 + self._bass_smoothed * 50)
            glow = pygame.Surface((g_w + 120, g_h + 120), pygame.SRCALPHA)
            glow_rect = pygame.Rect(60, 60, g_w, g_h)
            pygame.draw.ellipse(glow, (0, 120, 255, glow_alpha), glow_rect.inflate(120, 120), 3)
            pygame.draw.ellipse(glow, (0, 70, 180, glow_alpha // 2), glow_rect.inflate(220, 220), 3)
            surface.blit(glow, (center_x - glow.get_width() // 2,
                                center_y - glow.get_height() // 2),
                         special_flags=pygame.BLEND_RGBA_ADD)
            surface.blit(self._logo_surf,
                         (center_x - self._logo_half_w,
                          center_y - self._logo_half_h))

        if self._in_peace_mode:
            # --- PEACE SEQUENCE (calm drift around the logo) ---
            # Rainbow text
            text_y_offset = math.sin(self._elapsed_time * 1.5) * 5
            self._draw_rainbow_text(surface, "> THIS WAR IS OVER!",
                                   center_x, self._horizon_y + self._logo_half_h + 30 + int(text_y_offset),
                                   self._elapsed_time)

            # Credits
            credits = self.font_sm.render(
                "TOROIDAMP // CODE: Former Future Crew // AKA: WAR",
                True, (0, 200, 200))
            surface.blit(credits, (center_x - credits.get_width() // 2, self.h - 30))

            # Peace sequence also shows some X-Wings flying through
            for ship in self._squadron[:]:
                trail_color = (255, 50, 50) if ship["evading"] else (100, 255, 150)
                if len(ship["trail"]) > 1:
                    pygame.draw.lines(surface, trail_color, False, ship["trail"], 2)
                self._draw_xwing_3d(surface, ship, center_x, center_y)

        else:
            # --- BATTLE SEQUENCE ---
            for ywing in self._ywings:
                draw_z = ywing["z"]
                if draw_z < 0.5:
                    continue

                scale = 500.0 / draw_z
                sx = center_x + (ywing["x"] + ywing["squad_dx"]) * scale
                sy = center_y + (ywing["y"] + ywing["squad_dy"]) * scale

                engine_offset = 35 * (scale / 90.0) * 1.5
                ywing["trail_l"].append((sx - engine_offset, sy))
                ywing["trail_r"].append((sx + engine_offset, sy))

                if len(ywing["trail_l"]) > 10:
                    ywing["trail_l"].pop(0)
                    ywing["trail_r"].pop(0)

                if len(ywing["trail_l"]) > 1:
                    pygame.draw.lines(surface, (100, 200, 255),
                                     False, ywing["trail_l"], 2)
                    pygame.draw.lines(surface, (100, 200, 255),
                                     False, ywing["trail_r"], 2)

                ship_copy = ywing.copy()
                ship_copy["x"] = ywing["x"] + ywing["squad_dx"]
                ship_copy["y"] = ywing["y"] + ywing["squad_dy"]
                self._draw_ywing_3d(surface, ship_copy, center_x, center_y)

            # Draw X-Wing squadron (foreground)
            for ship in self._squadron:
                trail_color = (255, 50, 50) if ship["evading"] else (100, 255, 150)
                if len(ship["trail"]) > 1:
                    pygame.draw.lines(surface, trail_color, False, ship["trail"], 2)
                self._draw_xwing_3d(surface, ship, center_x, center_y)

    def get_debug_state(self) -> dict:
        return {
            "phase": "PEACE" if self._in_peace_mode else "BATTLE",
            "xwing_count": len(self._squadron),
            "ywing_count": len(self._ywings),
            "lit_cells": len(self._lit_cells),
            "bass_smoothed": self._bass_smoothed,
            "treble_smoothed": self._treble_smoothed,
            "rms_smoothed": self._rms_smoothed,
            "beat_impulse": self._beat_impulse,
            "elapsed": self._elapsed_time,
        }
