"""
tests/test_vis_001.py — ToroidAMP VIS-001 Production Promotion Tests
Validates production promotion of Deep Field and ToroidAMP Floor, selector
index persistence & compatibility, and lifecycle invariants.
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

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.base import Visualizer
from toroidamp.visualizers.toroid import ToroidVisualizer
from toroidamp.visualizers.ribbon import WaveformRibbonVisualizer
from toroidamp.visualizers.deep_field import DeepFieldVisualizer
from toroidamp.visualizers.floor import ToroidAMPFloorVisualizer
from toroidamp.ui.modules.visualizer_module import VisualizerModule
from toroidamp.ui.fullscreen import RetinaMeltWindow
from toroidamp.session import SessionState, SessionManager

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


class TestDeepFieldProduction(unittest.TestCase):
    def setUp(self):
        self.vis = DeepFieldVisualizer(640, 480)

    def test_registered_in_production(self):
        self.assertIsInstance(self.vis, Visualizer)
        self.assertEqual(self.vis.get_name(), "Deep Field")

    def test_consumes_live_audioframe(self):
        surf = pygame.Surface((640, 480))
        frame = _make_frame(rms=0.8, bass=0.9, mids=0.7, treble=0.85, beat=True)
        self.vis.render(surf, frame, 1 / 60.0)
        state = self.vis.get_debug_state()
        self.assertGreater(state["depth_pressure"], self.vis.BASE_CRUISE)
        self.assertGreater(state["beat_impulse"], 0.0)

    def test_silence_remains_alive(self):
        surf = pygame.Surface((640, 480))
        frame_silence = _make_frame()
        for _ in range(120):
            self.vis.render(surf, frame_silence, 1 / 60.0)
        state = self.vis.get_debug_state()
        self.assertAlmostEqual(state["depth_pressure"], self.vis.BASE_CRUISE, delta=0.05)
        self.assertGreater(state["depth_pressure"], 0.0)

    def test_beat_impulse_decays(self):
        frame_beat = _make_frame(beat=True)
        self.vis.update(frame_beat, 1 / 60.0)
        impulse_start = self.vis.get_debug_state()["beat_impulse"]

        frame_idle = _make_frame()
        self.vis.update(frame_idle, 0.2)
        impulse_decayed = self.vis.get_debug_state()["beat_impulse"]
        self.assertLess(impulse_decayed, impulse_start)

    def test_strong_beat_bounded(self):
        frame_strong = _make_frame(strong_beat=True)
        self.vis.update(frame_strong, 1 / 60.0)
        # Verify event activates and then completes within bounded time
        self.vis.update(_make_frame(), 0.2)
        mid_prog = self.vis.get_debug_state()["strong_event_progress"]
        self.assertGreater(mid_prog, 0.0)

        self.vis.update(_make_frame(), 0.5)
        end_prog = self.vis.get_debug_state()["strong_event_progress"]
        self.assertEqual(end_prog, 0.0)

    def test_resize_safe(self):
        for w, h in RESIZE_TARGETS:
            self.vis.resize(w, h)
            self.assertEqual(self.vis.w, w)
            self.assertEqual(self.vis.h, h)
            surf = pygame.Surface((w, h))
            self.vis.render(surf, _make_frame(bass=0.5, beat=True), 1 / 60.0)

    def test_production_code_has_no_donor_or_experiment_imports(self):
        file_path = os.path.join(REPO_ROOT, "src", "toroidamp", "visualizers", "deep_field.py")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("MetalWar", content.split("DONOR DNA")[0])
        self.assertNotIn("import experiments", content)
        self.assertNotIn("from experiments", content)


class TestFloorProduction(unittest.TestCase):
    def setUp(self):
        self.vis = ToroidAMPFloorVisualizer(640, 480)

    def test_registered_in_production(self):
        self.assertIsInstance(self.vis, Visualizer)
        self.assertEqual(self.vis.get_name(), "ToroidAMP Floor")

    def test_spectrum_changes_tile_topology(self):
        # Bass-heavy spectrum vs treble-heavy spectrum
        spec_bass = [0.9 if i < 10 else 0.05 for i in range(64)]
        spec_treble = [0.9 if i > 50 else 0.05 for i in range(64)]

        vis1 = ToroidAMPFloorVisualizer(640, 480)
        vis2 = ToroidAMPFloorVisualizer(640, 480)

        f1 = _make_frame(bass=0.9, treble=0.1, spectrum=spec_bass)
        f2 = _make_frame(bass=0.1, treble=0.9, spectrum=spec_treble)

        for _ in range(30):
            vis1.update(f1, 1 / 60.0)
            vis2.update(f2, 1 / 60.0)

        grid1 = vis1.get_debug_state()["tile_energy"]
        grid2 = vis2.get_debug_state()["tile_energy"]

        # Low-frequency rows/center columns should have more energy in grid1
        diff = sum(abs(grid1[r][c] - grid2[r][c]) for r in range(vis1.ROWS) for c in range(vis1.COLS))
        self.assertGreater(diff, 5.0)

    def test_same_bpm_different_spectrum_remains_distinguishable(self):
        vis_metal = ToroidAMPFloorVisualizer(640, 480)
        vis_elec = ToroidAMPFloorVisualizer(640, 480)

        # Both firing beat at 120 bpm (every 30 frames at 60fps), but different spectrum
        for step in range(120):
            beat = (step % 30 == 0)
            spec_m = [0.8 if 15 <= i <= 45 else 0.3 for i in range(64)]
            spec_e = [0.9 if i <= 10 else 0.1 for i in range(64)]
            f_m = _make_frame(bass=0.6, mids=0.9, treble=0.7, spectrum=spec_m, beat=beat)
            f_e = _make_frame(bass=0.95, mids=0.3, treble=0.4, spectrum=spec_e, beat=beat)

            vis_metal.update(f_m, 1 / 60.0)
            vis_elec.update(f_e, 1 / 60.0)

        grid_m = vis_metal.get_debug_state()["tile_energy"]
        grid_e = vis_elec.get_debug_state()["tile_energy"]

        diff = sum(abs(grid_m[r][c] - grid_e[r][c]) for r in range(vis_metal.ROWS) for c in range(vis_metal.COLS))
        self.assertGreater(diff, 10.0)

    def test_tile_energy_decays(self):
        f_active = _make_frame(bass=0.9, mids=0.8, spectrum=[0.8] * 64, beat=False)
        for _ in range(60):
            self.vis.update(f_active, 1 / 60.0)
        e_active = self.vis.get_debug_state()["total_energy"]

        f_silence = _make_frame()
        for _ in range(300):
            self.vis.update(f_silence, 1 / 60.0)
        e_decayed = self.vis.get_debug_state()["total_energy"]
        self.assertLess(e_decayed, e_active)

    def test_wireframe_structure_and_render(self):
        surf = pygame.Surface((640, 480))
        frame = _make_frame(bass=0.7, mids=0.6, treble=0.5, spectrum=[0.5] * 64, beat=True)
        self.vis.render(surf, frame, 1 / 60.0)
        # Ensure render executed without error and modified the surface
        non_zero = False
        for x in (100, 320, 540):
            for y in (200, 350, 450):
                if surf.get_at((x, y))[:3] != (0, 0, 0):
                    non_zero = True
                    break
        self.assertTrue(non_zero)

    def test_ordinary_beat_and_strong_beat_differ(self):
        vis1 = ToroidAMPFloorVisualizer(640, 480)
        vis2 = ToroidAMPFloorVisualizer(640, 480)

        vis1.update(_make_frame(beat=True, strong_beat=False), 1 / 60.0)
        vis2.update(_make_frame(beat=True, strong_beat=True), 1 / 60.0)

        self.assertEqual(vis1.get_debug_state()["active_pulses"], 1)
        self.assertGreater(vis2.get_debug_state()["active_pulses"], 1)

    def test_silence_approaches_dormant_state(self):
        # Charge up
        for _ in range(60):
            self.vis.update(_make_frame(bass=0.9, spectrum=[0.9] * 64, beat=True), 1 / 60.0)
        # Fade out
        for _ in range(500):
            self.vis.update(_make_frame(), 1 / 60.0)
        self.assertLess(self.vis.get_debug_state()["total_energy"], 5.0)
        self.assertEqual(self.vis.get_debug_state()["active_pulses"], 0)

    def test_resize_safe(self):
        for w, h in RESIZE_TARGETS:
            self.vis.resize(w, h)
            self.assertEqual(self.vis.w, w)
            self.assertEqual(self.vis.h, h)
            surf = pygame.Surface((w, h))
            self.vis.render(surf, _make_frame(bass=0.6, mids=0.5, spectrum=[0.5] * 64, beat=True), 1 / 60.0)

    def test_production_code_has_no_donor_or_experiment_imports(self):
        file_path = os.path.join(REPO_ROOT, "src", "toroidamp", "visualizers", "floor.py")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("import experiments", content)
        self.assertNotIn("from experiments", content)


class TestSelectorAndSessionCompatibility(unittest.TestCase):
    def test_visualizer_ordering_and_indices(self):
        vis_mod = VisualizerModule()
        self.assertEqual(len(vis_mod.visualizers), 4)
        self.assertIsInstance(vis_mod.visualizers[0], ToroidVisualizer)
        self.assertIsInstance(vis_mod.visualizers[1], WaveformRibbonVisualizer)
        self.assertIsInstance(vis_mod.visualizers[2], DeepFieldVisualizer)
        self.assertIsInstance(vis_mod.visualizers[3], ToroidAMPFloorVisualizer)

    def test_switching_cycles_cleanly_through_all_visualizers(self):
        vis_mod = VisualizerModule()
        names = ["3D TOROID", "WAVEFORM RIBBON", "DEEP FIELD", "TOROIDAMP FLOOR"]
        for idx, expected_name in enumerate(names):
            self.assertEqual(vis_mod.vis_idx, idx)
            # Cycle to next
            vis_mod._switch_vis_mode()
        self.assertEqual(vis_mod.vis_idx, 0)

    def test_retina_melt_has_identical_visualizer_family(self):
        melt = RetinaMeltWindow()
        self.assertEqual(len(melt.visualizers), 4)
        self.assertIsInstance(melt.visualizers[0], ToroidVisualizer)
        self.assertIsInstance(melt.visualizers[1], WaveformRibbonVisualizer)
        self.assertIsInstance(melt.visualizers[2], DeepFieldVisualizer)
        self.assertIsInstance(melt.visualizers[3], ToroidAMPFloorVisualizer)

    def test_session_state_index_compatibility(self):
        state_old_0 = SessionState(selected_visualizer_idx=0)
        state_old_1 = SessionState(selected_visualizer_idx=1)
        state_new_2 = SessionState(selected_visualizer_idx=2)
        state_new_3 = SessionState(selected_visualizer_idx=3)

        vis_mod = VisualizerModule()

        vis_mod.vis_idx = state_old_0.selected_visualizer_idx
        self.assertIsInstance(vis_mod.current_visualizer, ToroidVisualizer)

        vis_mod.vis_idx = state_old_1.selected_visualizer_idx
        self.assertIsInstance(vis_mod.current_visualizer, WaveformRibbonVisualizer)

        vis_mod.vis_idx = state_new_2.selected_visualizer_idx
        self.assertIsInstance(vis_mod.current_visualizer, DeepFieldVisualizer)

        vis_mod.vis_idx = state_new_3.selected_visualizer_idx
        self.assertIsInstance(vis_mod.current_visualizer, ToroidAMPFloorVisualizer)


class TestLifecycleAndIsolation(unittest.TestCase):
    def test_hidden_visualizer_does_not_render(self):
        vis_mod = VisualizerModule()
        vis_mod.hide()
        initial_surf = vis_mod.surface.copy()
        frame = _make_frame(bass=0.9, beat=True)
        vis_mod.render_frame(frame, 1 / 60.0)
        # Surface pixels should remain unchanged because isVisible() is False
        self.assertEqual(vis_mod.surface.get_at((10, 10)), initial_surf.get_at((10, 10)))

    def test_retina_melt_transition_syncs_visualizer_index(self):
        vis_mod = VisualizerModule()
        melt = RetinaMeltWindow()

        vis_mod.vis_idx = 2  # Deep Field
        melt.set_visualizer_index(vis_mod.vis_idx)
        self.assertEqual(melt.vis_idx, 2)
        self.assertIsInstance(melt.visualizers[melt.vis_idx], DeepFieldVisualizer)

        vis_mod.vis_idx = 3  # ToroidAMP Floor
        melt.set_visualizer_index(vis_mod.vis_idx)
        self.assertEqual(melt.vis_idx, 3)
        self.assertIsInstance(melt.visualizers[melt.vis_idx], ToroidAMPFloorVisualizer)


if __name__ == "__main__":
    unittest.main()
