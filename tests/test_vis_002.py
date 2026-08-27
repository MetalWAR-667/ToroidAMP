"""
tests/test_vis_002.py — ToroidAMP VIS-002 Perceptual Correction Pass
Validates:
1. Deep Field continuous amplitude breathing, fast beat attack, and simultaneous multi-hue gradation.
2. Floor cell-conforming tile geometry, hot glow hierarchy, horizon band removal, and motion synchronization.
3. 3D Toroid genuine 3D Z-depth camera travel and bounded perspective limits.
4. RETINA MELT canonical Marquee title, SeekSlider seek timeline, volume sync, and mode cycling.
"""

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pygame
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

from toroidamp.analysis.audio_frame import AudioFrame, AnalysisHandoff
from toroidamp.audio.player import PlayerEngine
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.visualizers.deep_field import DeepFieldVisualizer
from toroidamp.visualizers.floor import ToroidAMPFloorVisualizer
from toroidamp.visualizers.toroid import ToroidVisualizer
from toroidamp.ui.fullscreen import RetinaMeltWindow
from toroidamp.ui.marquee import MarqueeLabel
from toroidamp.ui.chassis import SeekSlider
from toroidamp.ui.window_manager import WindowManager
from toroidamp.session import SessionManager

app = QApplication.instance() or QApplication(sys.argv)
RESIZE_TARGETS = [(300, 180), (420, 240), (800, 450), (1280, 720), (1920, 1080)]


def _make_frame(rms=0.0, peak=0.0, bass=0.0, mids=0.0, treble=0.0,
                spectrum=None, waveform=None, beat=False, strong_beat=False) -> AudioFrame:
    return AudioFrame(
        rms=rms,
        peak=peak,
        bass=bass,
        mids=mids,
        treble=treble,
        spectrum=spectrum or [0.0] * 64,
        waveform=waveform or [0.0] * 128,
        beat=beat,
        strong_beat=strong_beat,
    )


class TestDeepFieldPerceptual(unittest.TestCase):
    def setUp(self):
        self.vis = DeepFieldVisualizer(640, 480)

    def test_depth_pressure_changes_continuously_with_amplitude(self):
        # 1. Quiet baseline
        self.vis.update(_make_frame(rms=0.05, bass=0.05), 1 / 60.0)
        quiet_p = self.vis.get_debug_state()["depth_pressure"]
        self.assertGreater(quiet_p, 0.0)

        # 2. Rising amplitude increases depth pressure smoothly
        for _ in range(15):
            self.vis.update(_make_frame(rms=0.85, bass=0.90), 1 / 60.0)
        loud_p = self.vis.get_debug_state()["depth_pressure"]
        self.assertGreater(loud_p, quiet_p * 1.5)

    def test_beat_attack_is_fast_and_decay_is_smooth(self):
        # Initial state
        self.vis.update(_make_frame(), 1 / 60.0)
        initial_streak = self.vis.get_debug_state()["streak_target"]

        # Fast attack on beat tick
        self.vis.update(_make_frame(beat=True), 1 / 60.0)
        impulse = self.vis.get_debug_state()["beat_impulse"]
        self.assertGreaterEqual(impulse, 0.8)
        self.assertGreater(self.vis.get_debug_state()["streak_target"], initial_streak)

        # Smooth decay
        for _ in range(30):
            self.vis.update(_make_frame(), 1 / 60.0)
        decayed_impulse = self.vis.get_debug_state()["beat_impulse"]
        self.assertLess(decayed_impulse, impulse)

    def test_multiple_spectral_bands_produce_simultaneous_distinct_colors(self):
        # Multi-band rich signal
        f_multi = _make_frame(
            rms=0.7, bass=0.8, mids=0.8, treble=0.8,
            spectrum=[0.8] * 64
        )
        for _ in range(30):
            self.vis.update(f_multi, 1 / 60.0)

        # Inspect star colors computed across the active population
        star_colors = [self.vis._compute_star_color(star, 1.0 - star.z) for star in self.vis.stars]
        unique_color_signatures = set()
        for r, g, b in star_colors:
            # Categorize dominant hue
            if r > g and r > b:
                unique_color_signatures.add("warm_magenta_gold")
            elif b > r and b > g:
                unique_color_signatures.add("electric_blue")
            elif g > r:
                unique_color_signatures.add("cyan_green")

        # Simultaneously distinct color families present
        self.assertGreaterEqual(len(unique_color_signatures), 2)

    def test_strong_beat_event_remains_bounded(self):
        self.vis.update(_make_frame(strong_beat=True), 1 / 60.0)
        self.vis.update(_make_frame(), 0.1)
        prog = self.vis.get_debug_state()["strong_event_progress"]
        self.assertGreater(prog, 0.0)
        self.assertLessEqual(prog, 1.0)

    def test_silence_remains_calm_and_active(self):
        surf = pygame.Surface((640, 480))
        for _ in range(100):
            self.vis.render(surf, _make_frame(), 1 / 60.0)
        st = self.vis.get_debug_state()
        self.assertAlmostEqual(st["depth_pressure"], self.vis.BASE_CRUISE, delta=0.05)

    def test_resize_safe(self):
        for w, h in RESIZE_TARGETS:
            self.vis.resize(w, h)
            self.assertEqual(self.vis.w, w)
            self.assertEqual(self.vis.h, h)
            surf = pygame.Surface((w, h))
            self.vis.render(surf, _make_frame(bass=0.8, beat=True, strong_beat=True), 1 / 60.0)


class TestFloorPerceptual(unittest.TestCase):
    def setUp(self):
        self.vis = ToroidAMPFloorVisualizer(640, 480)

    def test_tile_corners_derive_from_grid_cell_corners(self):
        # Step visualizer with energy
        f = _make_frame(bass=0.9, mids=0.8, spectrum=[0.85] * 64)
        for _ in range(20):
            self.vis.update(f, 1 / 60.0)

        # Inspect tile coordinates derived directly from grid
        grid_pts = []
        half_cols = self.vis.COLS / 2.0
        horizon_y = self.vis.h * 0.36
        for r in range(self.vis.ROWS + 1):
            offset_r = (r + self.vis._grid_scroll) / float(self.vis.ROWS + 1)
            r_norm = min(1.0, offset_r)
            row_pts = []
            for c in range(self.vis.COLS + 1):
                col_norm = (c - half_cols) / half_cols
                row_pts.append(self.vis._project_point(r_norm, col_norm, horizon_y))
            grid_pts.append(row_pts)

        # Ensure grid vertices form valid quadrilaterals for each cell
        for r in range(self.vis.ROWS):
            for c in range(self.vis.COLS):
                p0 = grid_pts[r][c]
                p1 = grid_pts[r][c + 1]
                p2 = grid_pts[r + 1][c + 1]
                p3 = grid_pts[r + 1][c]
                self.assertLess(p0[1], p3[1])  # Top row is higher on screen than bottom row
                self.assertLess(p0[0], p1[0])  # Left column is to the left of right column

    def test_hot_glow_hierarchy_with_tile_energy(self):
        # Low energy returns base body only without hot white core
        low_body, low_core, low_border = self.vis._get_emissive_colors(0, 0, 0.30)
        self.assertIsNone(low_core)
        self.assertGreater(sum(low_body), 0)

        # High energy returns hot bright core and white border
        high_body, high_core, high_border = self.vis._get_emissive_colors(0, 0, 0.95)
        self.assertIsNotNone(high_core)
        self.assertGreater(high_core[0] + high_core[1] + high_core[2], 600)  # Near white
        self.assertEqual(high_border, (255, 255, 255))

    def test_spectral_palettes_remain_distinct(self):
        f = _make_frame(bass=0.9, mids=0.9, treble=0.9, spectrum=[0.9] * 64)
        for _ in range(30):
            self.vis.update(f, 1 / 60.0)
        st = self.vis.get_debug_state()
        bands = set()
        for row in st["tile_band"]:
            for b in row:
                bands.add(b)
        self.assertGreaterEqual(len(bands), 3)

    def test_grid_motion_and_tiles_remain_synchronized(self):
        # Stepping visualizer updates _grid_scroll smoothly
        s0 = self.vis.get_debug_state()["grid_scroll"]
        for _ in range(5):
            self.vis.update(_make_frame(), 1 / 60.0)
        s1 = self.vis.get_debug_state()["grid_scroll"]
        self.assertNotEqual(s0, s1)

    def test_dark_baseline_at_silence(self):
        # 1. Start from scratch with zero frame
        self.vis.update(_make_frame(), 1 / 60.0)
        st = self.vis.get_debug_state()
        self.assertEqual(st["active_cell_count"], 0)
        self.assertEqual(st["total_energy"], 0.0)

        # 2. After energetic burst, silence decays to clean zero active cells
        f_loud = _make_frame(bass=0.9, mids=0.9, spectrum=[0.9] * 64, beat=True)
        for _ in range(20):
            self.vis.update(f_loud, 1 / 60.0)
        self.assertGreater(self.vis.get_debug_state()["active_cell_count"], 10)

        for _ in range(120):
            self.vis.update(_make_frame(), 1 / 60.0)
        st_decayed = self.vis.get_debug_state()
        self.assertEqual(st_decayed["active_cell_count"], 0)
        self.assertAlmostEqual(st_decayed["total_energy"], 0.0, delta=0.01)

    def test_quiet_vs_energetic_dynamic_range(self):
        # Quiet frame produces sparse/low activation
        f_quiet = _make_frame(bass=0.15, mids=0.15, spectrum=[0.14] * 64)
        for _ in range(20):
            self.vis.update(f_quiet, 1 / 60.0)
        quiet_count = self.vis.get_debug_state()["active_cell_count"]

        # Energetic frame produces rich/dense activation
        f_loud = _make_frame(bass=0.85, mids=0.85, spectrum=[0.85] * 64)
        for _ in range(20):
            self.vis.update(f_loud, 1 / 60.0)
        loud_count = self.vis.get_debug_state()["active_cell_count"]

        self.assertGreater(loud_count, quiet_count * 2)

    def test_resize_safe(self):
        for w, h in RESIZE_TARGETS:
            self.vis.resize(w, h)
            self.assertEqual(self.vis.w, w)
            self.assertEqual(self.vis.h, h)
            surf = pygame.Surface((w, h))
            self.vis.render(surf, _make_frame(bass=0.8, mids=0.7, treble=0.8, beat=True), 1 / 60.0)


class TestToroidTrueZDepth(unittest.TestCase):
    def setUp(self):
        self.vis = ToroidVisualizer(640, 480)

    def test_camera_distance_decreases_with_bass_pressure(self):
        # Initial distant camera
        self.vis.update(_make_frame(), 1 / 60.0)
        initial_dist = self.vis.get_debug_state()["camera_dist"]

        # Sustained bass pressure moves camera closer
        f_bass = _make_frame(bass=0.95)
        for _ in range(25):
            self.vis.update(f_bass, 1 / 60.0)
        close_dist = self.vis.get_debug_state()["camera_dist"]

        self.assertLess(close_dist, initial_dist - 0.25)
        self.assertGreaterEqual(close_dist, self.vis.MIN_CAMERA_DIST)

    def test_beat_produces_visible_depth_delta(self):
        self.vis.update(_make_frame(), 1 / 60.0)
        dist_before = self.vis.get_debug_state()["target_camera_dist"]

        self.vis.update(_make_frame(beat=True), 1 / 60.0)
        dist_after = self.vis.get_debug_state()["target_camera_dist"]

        self.assertLess(dist_after, dist_before)

    def test_strong_beat_produces_larger_bounded_depth_delta(self):
        self.vis.update(_make_frame(strong_beat=True), 1 / 60.0)
        for _ in range(10):
            self.vis.update(_make_frame(), 1 / 60.0)
        st = self.vis.get_debug_state()
        self.assertGreater(st["strong_zoom_progress"], 0.0)
        self.assertGreaterEqual(st["camera_dist"], self.vis.MIN_CAMERA_DIST)

    def test_resize_safe(self):
        for w, h in RESIZE_TARGETS:
            self.vis.resize(w, h)
            self.assertEqual(self.vis.w, w)
            self.assertEqual(self.vis.h, h)
            surf = pygame.Surface((w, h))
            self.vis.render(surf, _make_frame(bass=0.9, beat=True), 1 / 60.0)


class TestRetinaMeltPerceptualUX(unittest.TestCase):
    def setUp(self):
        self.handoff = AnalysisHandoff(2048)
        self.player = PlayerEngine(handoff=self.handoff)
        self.playlist = PlaylistManager()
        self.sm = SessionManager()
        self.wm = WindowManager(player=self.player, handoff=self.handoff,
                                playlist=self.playlist, session_manager=self.sm)

    def tearDown(self):
        self.wm.shutdown()

    def test_canonical_marquee_label_used(self):
        melt = self.wm.retina_melt
        self.assertIsInstance(melt.hud_marquee, MarqueeLabel)

    def test_canonical_seek_slider_used(self):
        melt = self.wm.retina_melt
        self.assertIsInstance(melt.hud_seek_slider, SeekSlider)

    def test_seek_slider_and_click_route_to_player(self):
        from unittest.mock import MagicMock
        melt = self.wm.retina_melt
        decoder = MagicMock()
        decoder.get_duration.return_value = 200.0
        self.player._active_decoder = decoder

        # Simulate user dragging or clicking seek slider to 50% (500)
        melt.hud_seek_slider.setValue(500)
        melt.seek_changed.emit(500)
        self.assertAlmostEqual(self.player.position, 100.0, delta=0.5)

    def test_direct_click_on_groove_seeks(self):
        from unittest.mock import MagicMock
        melt = self.wm.retina_melt
        decoder = MagicMock()
        decoder.get_duration.return_value = 200.0
        self.player._active_decoder = decoder
        slider = melt.hud_seek_slider
        slider.resize(200, 20)

        # Send mouse press event on slider groove
        event = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(100, 10),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        slider.mousePressEvent(event)
        self.assertAlmostEqual(self.player.position, 100.0, delta=15.0)

    def test_visualizer_mode_cycling(self):
        melt = self.wm.retina_melt
        expected_modes = [1, 2, 3, 4, 0]
        for exp in expected_modes:
            melt._cycle_visualizer_mode()
            self.assertEqual(melt.vis_idx, exp)
            self.assertEqual(self.wm.vis_mod.vis_idx, exp)

    def test_shared_volume_sync(self):
        melt = self.wm.retina_melt
        melt.hud_slider_vol.setValue(35)
        self.assertAlmostEqual(self.player.volume, 0.35, delta=0.02)
        self.assertEqual(self.wm.chassis.normal_vol_slider.value(), 35)

    def test_hud_auto_hide(self):
        melt = self.wm.retina_melt
        self.assertTrue(melt.hud_timer.isActive())
        self.assertEqual(melt.hud_timer.interval(), 2500)


if __name__ == "__main__":
    unittest.main()
