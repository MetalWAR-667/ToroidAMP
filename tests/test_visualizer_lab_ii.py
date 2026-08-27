"""
tests/test_visualizer_lab_ii.py — Visualizer Lab II: First Experimental Batch

Tests contracts/state/math — NOT pixel-perfect screenshots, per the mission's
explicit instruction. Covers:

  HARNESS/PROFILES
    - all five profiles construct valid AudioFrames;
    - deterministic profile behavior;
    - beat/strong_beat injection.

  DEEP FIELD
    - silence retains slow movement (not a frozen screen);
    - bass influences depth state;
    - treble influences detail independently;
    - beat impulse decays;
    - strong beat produces a bounded (not spammy) event;
    - resize safe.

  TOROIDAMP FLOOR
    - spectrum influences spatial regions;
    - same BPM + different spectrum produces different topology;
    - tile energy decays;
    - beat propagation exists;
    - strong beat differs from ordinary beat;
    - silence approaches a dormant state;
    - resize safe.

  MATRIX WING COMMANDER
    - rain persists at silence, at low intensity;
    - spectral bands affect rain independently (density from treble);
    - ship event timing derives from beat/strong_beat, not pure random;
    - seeded randomness selects deterministic event variants;
    - silence does not spam ships;
    - resize safe.

These experiments are NOT registered in the production visualizer selector —
this test file imports directly from experiments/visualizers/, mirroring how
the harness itself resolves them.
"""

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXPERIMENTS_DIR = os.path.join(REPO_ROOT, "experiments", "visualizers")
if EXPERIMENTS_DIR not in sys.path:
    sys.path.insert(0, EXPERIMENTS_DIR)

try:
    import pygame
    pygame.init()
    pygame.font.init()
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

RESIZE_TARGETS = [(420, 240), (800, 450), (1280, 720), (1920, 1080)]


def _make_surface(w, h):
    return pygame.Surface((w, h))


class LabTestCase(unittest.TestCase):
    def setUp(self):
        if not PYGAME_AVAILABLE:
            self.skipTest("pygame not available")


# ---------------------------------------------------------------------------
# Profiles / harness
# ---------------------------------------------------------------------------

class TestSyntheticProfiles(LabTestCase):
    def test_all_profiles_construct_valid_audioframes(self):
        from profiles import PROFILES
        from toroidamp.analysis.audio_frame import AudioFrame

        for name, cls in PROFILES.items():
            profile = cls()
            for _ in range(10):
                frame = profile.tick(1 / 60.0)
                self.assertIsInstance(frame, AudioFrame, name)
                self.assertEqual(len(frame.spectrum), 64, name)
                self.assertEqual(len(frame.waveform), 128, name)
                for field in (frame.rms, frame.peak, frame.bass, frame.mids, frame.treble):
                    self.assertGreaterEqual(field, 0.0, name)
                    self.assertLessEqual(field, 1.0, name)
                for v in frame.spectrum:
                    self.assertGreaterEqual(v, 0.0, name)
                    self.assertLessEqual(v, 1.0, name)
                for v in frame.waveform:
                    self.assertGreaterEqual(v, -1.0, name)
                    self.assertLessEqual(v, 1.0, name)

    def test_silence_profile_is_actually_silent(self):
        from profiles import PROFILES
        profile = PROFILES["silence"]()
        frame = profile.tick(1 / 60.0)
        self.assertEqual(frame.rms, 0.0)
        self.assertEqual(frame.bass, 0.0)
        self.assertFalse(frame.beat)
        self.assertFalse(frame.strong_beat)

    def test_deterministic_profile_behavior(self):
        """Same seed + same dt sequence -> comparable (here: identical) frame sequence."""
        from profiles import MetalProfile
        p1 = MetalProfile(seed=42)
        p2 = MetalProfile(seed=42)
        seq1 = [p1.tick(1 / 60.0) for _ in range(120)]
        seq2 = [p2.tick(1 / 60.0) for _ in range(120)]
        for f1, f2 in zip(seq1, seq2):
            self.assertAlmostEqual(f1.rms, f2.rms, places=9)
            self.assertAlmostEqual(f1.bass, f2.bass, places=9)
            self.assertEqual(f1.beat, f2.beat)
            self.assertEqual(f1.strong_beat, f2.strong_beat)

    def test_beat_injection(self):
        from profiles import PROFILES
        profile = PROFILES["ambient"]()  # ambient beats are rare — injection must still force one
        frame = profile.tick(1 / 60.0)
        self.assertFalse(frame.beat)
        profile.inject_beat(strong=False)
        frame = profile.tick(1 / 60.0)
        self.assertTrue(frame.beat)
        self.assertFalse(frame.strong_beat)

    def test_strong_beat_injection(self):
        from profiles import PROFILES
        profile = PROFILES["ambient"]()
        profile.inject_beat(strong=True)
        frame = profile.tick(1 / 60.0)
        self.assertTrue(frame.beat)
        self.assertTrue(frame.strong_beat)

    def test_metal_and_electronic_beat_regularly_ambient_rarely(self):
        """Coarse sanity check the profiles actually differentiate rhythmic density."""
        from profiles import PROFILES

        def count_beats(name, ticks=1800):  # 30s at 60fps
            profile = PROFILES[name]()
            return sum(1 for _ in range(ticks) if profile.tick(1 / 60.0).beat)

        self.assertGreater(count_beats("metal"), count_beats("ambient"))
        self.assertGreater(count_beats("electronic"), count_beats("ambient"))
        self.assertEqual(count_beats("silence"), 0)


# ---------------------------------------------------------------------------
# Deep Field
# ---------------------------------------------------------------------------

class TestDeepField(LabTestCase):
    def _run(self, vis, profile, ticks, w=800, h=450):
        surf = _make_surface(w, h)
        for _ in range(ticks):
            frame = profile.tick(1 / 60.0)
            vis.render(surf, frame, 1 / 60.0)
        return vis.get_debug_state()

    def test_silence_retains_slow_movement(self):
        from deep_field import DeepFieldVisualizer
        from profiles import PROFILES
        vis = DeepFieldVisualizer(800, 450)
        state = self._run(vis, PROFILES["silence"](), 180)
        self.assertAlmostEqual(state["depth_pressure"], vis.BASE_CRUISE, delta=0.05)
        self.assertGreater(state["depth_pressure"], 0.0, "silence must not fully stop the field")

    def test_bass_influences_depth_state(self):
        from deep_field import DeepFieldVisualizer
        from profiles import PROFILES
        low_bass = DeepFieldVisualizer(800, 450)
        high_bass = DeepFieldVisualizer(800, 450)
        self._run(low_bass, PROFILES["ambient"](), 300)   # low bass
        self._run(high_bass, PROFILES["electronic"](), 300)  # dominant bass
        self.assertGreater(
            high_bass.get_debug_state()["depth_pressure"],
            low_bass.get_debug_state()["depth_pressure"],
        )

    def test_treble_influences_detail_independently_of_bass(self):
        """Metal (high bass+treble) vs electronic (high bass, lower treble) must diverge in star_count."""
        from deep_field import DeepFieldVisualizer
        from profiles import PROFILES
        metal_vis = DeepFieldVisualizer(800, 450)
        electronic_vis = DeepFieldVisualizer(800, 450)
        m_state = self._run(metal_vis, PROFILES["metal"](), 300)
        e_state = self._run(electronic_vis, PROFILES["electronic"](), 300)
        # Both have strong bass; only metal's high treble should meaningfully grow star_count.
        self.assertNotEqual(m_state["star_count"], e_state["star_count"])

    def test_beat_impulse_decays(self):
        from deep_field import DeepFieldVisualizer
        from profiles import PROFILES
        vis = DeepFieldVisualizer(800, 450)
        profile = PROFILES["silence"]()
        profile.inject_beat(strong=False)
        surf = _make_surface(800, 450)
        frame = profile.tick(1 / 60.0)
        vis.render(surf, frame, 1 / 60.0)
        impulse_at_beat = vis.get_debug_state()["beat_impulse"]
        self.assertGreater(impulse_at_beat, 0.0)
        for _ in range(60):
            frame = profile.tick(1 / 60.0)
            vis.render(surf, frame, 1 / 60.0)
        impulse_later = vis.get_debug_state()["beat_impulse"]
        self.assertLess(impulse_later, impulse_at_beat)

    def test_strong_beat_produces_bounded_event_not_spam(self):
        from deep_field import DeepFieldVisualizer
        from profiles import PROFILES
        vis = DeepFieldVisualizer(800, 450)
        profile = PROFILES["silence"]()
        surf = _make_surface(800, 450)
        # Fire many strong beats back-to-back — the cooldown must bound how often
        # the event actually re-triggers, and the event itself must always end (return to 0).
        progress_samples = []
        for i in range(180):
            if i % 5 == 0:
                profile.inject_beat(strong=True)
            frame = profile.tick(1 / 60.0)
            vis.render(surf, frame, 1 / 60.0)
            progress_samples.append(vis.get_debug_state()["strong_event_progress"])
        self.assertGreater(max(progress_samples), 0.0)
        # Must return to (near) zero between events rather than staying pinned high forever.
        self.assertTrue(any(p < 0.05 for p in progress_samples[-20:]) or progress_samples[-1] < 0.6)

    def test_resize_safe(self):
        from deep_field import DeepFieldVisualizer
        from profiles import PROFILES
        vis = DeepFieldVisualizer(420, 240)
        profile = PROFILES["metal"]()
        for w, h in RESIZE_TARGETS:
            vis.resize(w, h)
            surf = _make_surface(w, h)
            for _ in range(5):
                frame = profile.tick(1 / 60.0)
                vis.render(surf, frame, 1 / 60.0)
            self.assertEqual(vis.w, w)
            self.assertEqual(vis.h, h)


# ---------------------------------------------------------------------------
# ToroidAMP Floor
# ---------------------------------------------------------------------------

class TestToroidAMPFloor(LabTestCase):
    def _run(self, vis, profile, ticks, w=800, h=450):
        surf = _make_surface(w, h)
        for _ in range(ticks):
            frame = profile.tick(1 / 60.0)
            vis.render(surf, frame, 1 / 60.0)
        return vis.get_debug_state()

    def test_spectrum_influences_spatial_regions(self):
        """Bass-heavy energy must land in inner rings; treble-heavy energy in outer rings."""
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis = ToroidAMPFloorVisualizer(800, 450)
        self._run(vis, PROFILES["electronic"](), 180)  # bass-dominant
        state = vis.get_debug_state()
        tile_energy = state["tile_energy"]
        inner_energy = sum(sum(row) for row in tile_energy[:3])
        outer_energy = sum(sum(row) for row in tile_energy[-2:])
        self.assertGreater(inner_energy, outer_energy)

    def test_same_bpm_different_spectrum_produces_different_topology(self):
        """The core signature claim: metal vs electronic at comparable beat rate must differ structurally."""
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis_metal = ToroidAMPFloorVisualizer(800, 450)
        vis_electronic = ToroidAMPFloorVisualizer(800, 450)
        state_metal = self._run(vis_metal, PROFILES["metal"](), 180)
        state_electronic = self._run(vis_electronic, PROFILES["electronic"](), 180)

        te_m = state_metal["tile_energy"]
        te_e = state_electronic["tile_energy"]
        total_diff = sum(
            abs(te_m[r][s] - te_e[r][s])
            for r in range(len(te_m)) for s in range(len(te_m[0]))
        )
        self.assertGreater(total_diff, 10.0, "same-BPM profiles with different spectra must diverge structurally")

    def test_tile_energy_decays(self):
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis = ToroidAMPFloorVisualizer(800, 450)
        self._run(vis, PROFILES["metal"](), 120)
        energy_loud = vis.get_debug_state()["total_energy"]
        self._run(vis, PROFILES["silence"](), 300)
        energy_after_silence = vis.get_debug_state()["total_energy"]
        self.assertLess(energy_after_silence, energy_loud)

    def test_beat_produces_propagation_pulse(self):
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis = ToroidAMPFloorVisualizer(800, 450)
        profile = PROFILES["silence"]()
        surf = _make_surface(800, 450)
        profile.inject_beat(strong=False)
        frame = profile.tick(1 / 60.0)
        vis.render(surf, frame, 1 / 60.0)
        self.assertGreaterEqual(vis.get_debug_state()["active_pulses"], 1)

    def test_strong_beat_differs_from_ordinary_beat(self):
        """A strong_beat must launch a larger event (more simultaneous pulses) than a plain beat."""
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis_beat = ToroidAMPFloorVisualizer(800, 450)
        vis_strong = ToroidAMPFloorVisualizer(800, 450)
        surf = _make_surface(800, 450)

        p1 = PROFILES["silence"]()
        p1.inject_beat(strong=False)
        vis_beat.render(surf, p1.tick(1 / 60.0), 1 / 60.0)

        p2 = PROFILES["silence"]()
        p2.inject_beat(strong=True)
        vis_strong.render(surf, p2.tick(1 / 60.0), 1 / 60.0)

        self.assertGreater(
            vis_strong.get_debug_state()["active_pulses"],
            vis_beat.get_debug_state()["active_pulses"],
        )

    def test_silence_approaches_dormant_state(self):
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis = ToroidAMPFloorVisualizer(800, 450)
        self._run(vis, PROFILES["metal"](), 120)
        self._run(vis, PROFILES["silence"](), 600)  # 10s of silence
        self.assertLess(vis.get_debug_state()["total_energy"], 5.0)

    def test_resize_safe(self):
        from toroidamp_floor import ToroidAMPFloorVisualizer
        from profiles import PROFILES
        vis = ToroidAMPFloorVisualizer(420, 240)
        profile = PROFILES["metal"]()
        for w, h in RESIZE_TARGETS:
            vis.resize(w, h)
            surf = _make_surface(w, h)
            for _ in range(5):
                frame = profile.tick(1 / 60.0)
                vis.render(surf, frame, 1 / 60.0)
            self.assertEqual(vis.w, w)
            self.assertEqual(vis.h, h)


# ---------------------------------------------------------------------------
# Matrix Wing Commander
# ---------------------------------------------------------------------------

class TestMatrixWingCommander(LabTestCase):
    def _run(self, vis, profile, ticks, w=800, h=450):
        surf = _make_surface(w, h)
        for _ in range(ticks):
            frame = profile.tick(1 / 60.0)
            vis.render(surf, frame, 1 / 60.0)
        return vis.get_debug_state()

    def test_rain_persists_at_silence_at_low_intensity(self):
        from matrix_wing_commander import MatrixWingCommanderVisualizer
        from profiles import PROFILES
        vis = MatrixWingCommanderVisualizer(800, 450)
        state = self._run(vis, PROFILES["silence"](), 180)
        self.assertGreaterEqual(state["column_count"], vis.COLUMN_TARGET_BASE)
        self.assertLess(state["column_count"], vis.COLUMN_TARGET_BASE + 5, "silence must stay near the sparse baseline")

    def test_treble_increases_column_density(self):
        from matrix_wing_commander import MatrixWingCommanderVisualizer
        from profiles import PROFILES
        low_treble_vis = MatrixWingCommanderVisualizer(800, 450)
        high_treble_vis = MatrixWingCommanderVisualizer(800, 450)
        self._run(low_treble_vis, PROFILES["ambient"](), 300)
        self._run(high_treble_vis, PROFILES["metal"](), 300)
        self.assertGreater(
            high_treble_vis.get_debug_state()["column_count"],
            low_treble_vis.get_debug_state()["column_count"],
        )

    def test_ship_events_derive_from_beat_not_pure_random(self):
        """With strong_beat forced permanently absent, no ship pass should ever spawn, however long we run."""
        from matrix_wing_commander import MatrixWingCommanderVisualizer
        from profiles import SyntheticProfile, EMPTY_SPECTRUM, EMPTY_WAVEFORM
        from toroidamp.analysis.audio_frame import AudioFrame

        class NoBeatLoudProfile(SyntheticProfile):
            """High energy, but beat/strong_beat are hardcoded False — isolates the causality claim."""
            name = "no_beat_loud"
            seed = 99

            def _compute(self, t, dt):
                return AudioFrame(
                    rms=0.8, peak=0.9, bass=0.8, mids=0.8, treble=0.8,
                    spectrum=tuple([0.8] * 64), waveform=EMPTY_WAVEFORM,
                    beat=False, strong_beat=False,
                )

        vis = MatrixWingCommanderVisualizer(800, 450)
        state = self._run(vis, NoBeatLoudProfile(), 600)  # 10s of loud-but-eventless audio
        self.assertEqual(state["active_passes"], 0)
        self.assertEqual(state["last_pass_t"], -999.0, "no strong_beat ever fired -> no pass ever launched")

    def test_seeded_randomness_selects_deterministic_event_variant(self):
        """Same seed -> same sequence of route/ship-kind choices when strong_beat fires identically."""
        from matrix_wing_commander import MatrixWingCommanderVisualizer
        from profiles import PROFILES

        def run_and_collect_routes():
            vis = MatrixWingCommanderVisualizer(800, 450)
            surf = _make_surface(800, 450)
            profile = PROFILES["silence"]()
            routes_seen = []
            for i in range(300):
                if i % 100 == 0:
                    profile.inject_beat(strong=True)
                frame = profile.tick(1 / 60.0)
                vis.render(surf, frame, 1 / 60.0)
                routes_seen.append(tuple(id(p.route) for p in vis._passes))
            return [r.ship_kind for r in vis._passes] if vis._passes else []

        # vis is constructed with a fixed internal seed (2049) — two independent instances
        # driven by the identical injected-beat sequence must make the identical choices.
        import matrix_wing_commander as mwc
        vis1 = mwc.MatrixWingCommanderVisualizer(800, 450)
        vis2 = mwc.MatrixWingCommanderVisualizer(800, 450)
        surf = _make_surface(800, 450)
        p1 = PROFILES["silence"]()
        p2 = PROFILES["silence"]()
        kinds1, kinds2 = [], []
        for i in range(400):
            if i % 90 == 0:
                p1.inject_beat(strong=True)
                p2.inject_beat(strong=True)
            f1 = p1.tick(1 / 60.0)
            f2 = p2.tick(1 / 60.0)
            before1 = len(vis1._passes)
            before2 = len(vis2._passes)
            vis1.render(surf, f1, 1 / 60.0)
            vis2.render(surf, f2, 1 / 60.0)
            if len(vis1._passes) > before1:
                kinds1.append(vis1._passes[-1].ship_kind)
            if len(vis2._passes) > before2:
                kinds2.append(vis2._passes[-1].ship_kind)
        self.assertTrue(kinds1, "expected at least one ship pass to spawn")
        self.assertEqual(kinds1, kinds2)

    def test_silence_does_not_spam_ships(self):
        from matrix_wing_commander import MatrixWingCommanderVisualizer
        from profiles import PROFILES
        vis = MatrixWingCommanderVisualizer(800, 450)
        state = self._run(vis, PROFILES["silence"](), 900)  # 15s
        self.assertEqual(state["active_passes"], 0)

    def test_resize_safe(self):
        from matrix_wing_commander import MatrixWingCommanderVisualizer
        from profiles import PROFILES
        vis = MatrixWingCommanderVisualizer(420, 240)
        profile = PROFILES["metal"]()
        for w, h in RESIZE_TARGETS:
            vis.resize(w, h)
            surf = _make_surface(w, h)
            for _ in range(5):
                frame = profile.tick(1 / 60.0)
                vis.render(surf, frame, 1 / 60.0)
            self.assertEqual(vis.w, w)
            self.assertEqual(vis.h, h)


# ---------------------------------------------------------------------------
# Production isolation
# ---------------------------------------------------------------------------

class TestProductionIsolation(LabTestCase):
    def test_unpromoted_experiments_not_registered_in_visualizer_module(self):
        vis_module_path = os.path.join(REPO_ROOT, "src", "toroidamp", "ui", "modules", "visualizer_module.py")
        with open(vis_module_path, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("MatrixWingCommanderVisualizer", source)

    def test_unpromoted_experiments_not_registered_in_fullscreen(self):
        fullscreen_path = os.path.join(REPO_ROOT, "src", "toroidamp", "ui", "fullscreen.py")
        with open(fullscreen_path, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("MatrixWingCommanderVisualizer", source)

    def test_experiments_do_not_import_from_donor_repo(self):
        """
        Attribution comments naming MetalWar-Installer (documenting donor DNA,
        as required by the mission) are expected and fine. What must never
        appear is an actual coupling: an import, sys.path manipulation, or
        filesystem reference that would make experiments/ depend on the
        donor repo at runtime.
        """
        exp_dir = os.path.join(REPO_ROOT, "experiments", "visualizers")
        forbidden_substrings = (
            "import Metalwar",
            "import MetalWar",
            "from Metalwar",
            "from MetalWar",
            "MetalWar-Installer\\",
            "MetalWar-Installer/",
            "Metalwar-Installer\\",
            "Metalwar-Installer/",
        )
        for fname in ("deep_field.py", "toroidamp_floor.py", "matrix_wing_commander.py", "harness.py", "profiles.py"):
            with open(os.path.join(exp_dir, fname), "r", encoding="utf-8") as f:
                source = f.read()
            for forbidden in forbidden_substrings:
                self.assertNotIn(forbidden, source, f"{fname} appears coupled to the donor repo via {forbidden!r}")


if __name__ == "__main__":
    unittest.main()
