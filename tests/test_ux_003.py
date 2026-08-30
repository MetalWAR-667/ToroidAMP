"""
tests/test_ux_003.py — UX-003 Resizable Modules & Size Memory

Focused regression tests for:
  1-2. VisualizerModule / PlaylistModule default sizes.
  3-4. Min-size enforcement.
  5. User resize survives NORMAL -> MINI -> NORMAL.
  6. User resize survives dock -> undock.
  7-9. Session serialization: width/height persisted, missing/invalid values
       fall back to defaults/clamp safely.
  10-11. Reset Size restores defaults without moving/docking/closing.
  12. RETINA MELT does not overwrite VisualizerModule size.
  13. Taskbar ownership (Qt parent-as-owner) remains intact structurally.

AUTHORITATIVE PRODUCT RULE under test: USER SIZE IS STATE.
"""

import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
    from PySide6.QtGui import QMouseEvent
    _app = QApplication.instance() or QApplication(sys.argv)
    QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False


def _drag_resize(module, corner_local, delta):
    """
    Simulates a real user edge/corner resize drag via actual QMouseEvents
    (press -> move -> release), not a direct .resize() call — this is the
    only path that should record a docked module's resize into user_size.
    """
    def _mk(local, glob, etype, buttons=Qt.LeftButton):
        return QMouseEvent(etype, QPointF(local), QPointF(glob), Qt.LeftButton, buttons, Qt.NoModifier)

    start_global = module.mapToGlobal(corner_local)
    module.mousePressEvent(_mk(corner_local, start_global, QEvent.MouseButtonPress))
    drag_global = start_global + delta
    module.mouseMoveEvent(_mk(QPoint(0, 0), drag_global, QEvent.MouseMove))
    module.mouseReleaseEvent(_mk(QPoint(0, 0), drag_global, QEvent.MouseButtonRelease, buttons=Qt.NoButton))


def _make_window_manager(session_manager=None):
    """
    Builds a WindowManager against an isolated tempfile-backed session unless
    the caller supplies its own SessionManager — this suite must never read
    or write the real per-user session.json on disk.
    """
    from toroidamp.analysis.audio_frame import AnalysisHandoff
    from toroidamp.audio.player import PlayerEngine
    from toroidamp.audio.playlist import PlaylistManager
    from toroidamp.session import SessionManager
    from toroidamp.ui.window_manager import WindowManager

    if session_manager is None:
        tmp_dir = tempfile.mkdtemp()
        session_manager = SessionManager(custom_path=os.path.join(tmp_dir, "session.json"))

    handoff = AnalysisHandoff(2048)
    player = PlayerEngine(handoff=handoff)
    playlist = PlaylistManager()
    return WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=session_manager)


# ---------------------------------------------------------------------------
# Parts 1-4 — Default & minimum size contract
# ---------------------------------------------------------------------------

class TestDefaultAndMinSizes(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_visualizer_default_size(self):
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        vm = VisualizerModule()
        self.assertEqual((vm.width(), vm.height()), (420, 240))
        vm.close()

    def test_playlist_default_size(self):
        from toroidamp.audio.playlist import PlaylistManager
        from toroidamp.ui.modules.playlist_module import PlaylistModule
        pm = PlaylistModule(PlaylistManager())
        self.assertEqual((pm.width(), pm.height()), (270, 240))
        pm.close()

    def test_visualizer_min_size_enforced(self):
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        vm = VisualizerModule()
        vm.show()
        vm.resize(10, 10)
        self.assertGreaterEqual(vm.width(), VisualizerModule.MIN_SIZE.width())
        self.assertGreaterEqual(vm.height(), VisualizerModule.MIN_SIZE.height())
        vm.close()

    def test_playlist_min_size_enforced(self):
        from toroidamp.audio.playlist import PlaylistManager
        from toroidamp.ui.modules.playlist_module import PlaylistModule
        pm = PlaylistModule(PlaylistManager())
        pm.show()
        pm.resize(10, 10)
        self.assertGreaterEqual(pm.width(), PlaylistModule.MIN_SIZE.width())
        self.assertGreaterEqual(pm.height(), PlaylistModule.MIN_SIZE.height())
        pm.close()


# ---------------------------------------------------------------------------
# Part 5 — MINI / NORMAL size memory
# ---------------------------------------------------------------------------

class TestMiniNormalSizeMemory(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_user_resize_survives_mini_normal_cycle(self):
        wm = _make_window_manager()
        wm._toggle_vis()
        wm._toggle_pl()
        wm.undock_module(wm.vis_mod)
        wm.undock_module(wm.pl_mod)
        wm.vis_mod.resize(680, 400)
        wm.pl_mod.resize(340, 500)

        wm.chassis.set_mode("mini")
        self.assertFalse(wm.vis_mod.isVisible())
        self.assertFalse(wm.pl_mod.isVisible())
        self.assertEqual((wm.vis_mod.width(), wm.vis_mod.height()), (680, 400))
        self.assertEqual((wm.pl_mod.width(), wm.pl_mod.height()), (340, 500))

        wm.chassis.set_mode("normal")
        self.assertEqual((wm.vis_mod.width(), wm.vis_mod.height()), (680, 400))
        self.assertEqual((wm.pl_mod.width(), wm.pl_mod.height()), (340, 500))
        wm.shutdown()


# ---------------------------------------------------------------------------
# Part 6 — Dock / undock size preservation
# ---------------------------------------------------------------------------

class TestDockUndockSizePreservation(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_visualizer_dock_undock_preserves_floating_size(self):
        wm = _make_window_manager()
        wm._toggle_vis()
        wm.undock_module(wm.vis_mod)
        wm.vis_mod.resize(700, 430)

        wm.dock_module(wm.vis_mod, "bottom")
        self.assertEqual(wm.vis_mod.width(), wm.chassis.width(), "docked VIS aligns to chassis width")

        wm.undock_module(wm.vis_mod)
        self.assertEqual((wm.vis_mod.width(), wm.vis_mod.height()), (700, 430))
        wm.shutdown()

    def test_playlist_dock_undock_preserves_floating_size(self):
        wm = _make_window_manager()
        wm._toggle_pl()
        wm.undock_module(wm.pl_mod)
        wm.pl_mod.resize(340, 500)

        wm.dock_module(wm.pl_mod, "right")
        self.assertNotEqual((wm.pl_mod.width(), wm.pl_mod.height()), (0, 0))

        wm.undock_module(wm.pl_mod)
        self.assertEqual((wm.pl_mod.width(), wm.pl_mod.height()), (340, 500))
        wm.shutdown()


# ---------------------------------------------------------------------------
# UX-003 Follow-up — Docked Playlist Vertical Resize
#
# Docking must define ATTACHMENT/POSITION for PlaylistModule, not its size.
# ---------------------------------------------------------------------------

class TestDockedPlaylistVerticalResize(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_docked_playlist_vertical_resize_enabled(self):
        """Part F.1 — dragging PL's bottom edge while docked actually resizes it."""
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        self.assertTrue(pm.is_docked)
        start_h = pm.height()

        _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(30, 380))

        self.assertEqual(pm.height(), start_h + 380)
        wm.shutdown()

    def test_realign_docked_modules_preserves_playlist_height(self):
        """Part F.2 — realign_docked_modules updates x/y only, never PL width/height."""
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(30, 380))
        size_before = (pm.width(), pm.height())

        wm.chassis.move(wm.chassis.x() + 40, wm.chassis.y() + 15)
        wm.realign_docked_modules()

        self.assertEqual((pm.width(), pm.height()), size_before, "realign must not touch PL size")
        self.assertEqual(pm.x(), wm.chassis.geometry().right() + 2, "realign must still move PL x to follow the chassis")
        wm.shutdown()

    def test_custom_docked_height_survives_mini_normal_cycle(self):
        """Part F.3."""
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(30, 380))
        size_before = (pm.width(), pm.height())

        wm.chassis.set_mode("mini")
        wm.chassis.set_mode("normal")

        self.assertEqual((pm.width(), pm.height()), size_before)
        wm.shutdown()

    def test_custom_docked_height_survives_restart(self):
        """Part F.4."""
        from toroidamp.session import SessionManager
        with tempfile.TemporaryDirectory() as td:
            sf = os.path.join(td, "session.json")
            sm = SessionManager(custom_path=sf)
            wm = _make_window_manager(session_manager=sm)
            wm._toggle_pl()
            pm = wm.pl_mod
            _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(40, 400))
            size_before = (pm.width(), pm.height())
            wm.save_current_session()
            wm.shutdown()

            sm2 = SessionManager(custom_path=sf)
            wm2 = _make_window_manager(session_manager=sm2)
            self.assertEqual((wm2.pl_mod.width(), wm2.pl_mod.height()), size_before)
            self.assertTrue(wm2.pl_mod.is_docked)
            wm2.shutdown()

    def test_dock_undock_preserves_docked_custom_height(self):
        """Part F.5 — resizing height *while docked*, then undocking, keeps that height."""
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(30, 380))
        size_before = (pm.width(), pm.height())

        wm.undock_module(pm)

        self.assertEqual((pm.width(), pm.height()), size_before)
        wm.shutdown()

    def test_reset_size_restores_default_docked_height(self):
        """Part F.6."""
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(30, 380))
        self.assertNotEqual((pm.width(), pm.height()), (pm.DEFAULT_SIZE.width(), pm.DEFAULT_SIZE.height()))

        pm.reset_size()

        self.assertEqual((pm.width(), pm.height()), (pm.DEFAULT_SIZE.width(), pm.DEFAULT_SIZE.height()))
        wm.shutdown()

    def test_core_movement_changes_position_not_size(self):
        """Part F.7 — moving the chassis moves docked PL's x/y but never its size."""
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        _drag_resize(pm, QPoint(pm.width() - 2, pm.height() - 2), QPoint(30, 380))
        size_before = (pm.width(), pm.height())
        pos_before = pm.pos()

        wm.chassis.move(wm.chassis.x() + 77, wm.chassis.y() + 33)
        wm.realign_docked_modules()

        self.assertEqual((pm.width(), pm.height()), size_before)
        self.assertNotEqual(pm.pos(), pos_before)
        wm.shutdown()

    def test_docked_playlist_left_and_top_edges_locked(self):
        """Left/top edges are excluded while docked — they anchor PL's position."""
        from toroidamp.ui.modules.playlist_module import PlaylistModule
        wm = _make_window_manager()
        wm._toggle_pl()
        pm = wm.pl_mod
        self.assertEqual(pm._allowed_edges(), {"right", "bottom"})
        wm.shutdown()

    def test_visualizer_dock_locked_edges_unchanged(self):
        """Regression: VIS width-lock behavior (left/right excluded while docked) is intact."""
        wm = _make_window_manager()
        wm._toggle_vis()
        vm = wm.vis_mod
        self.assertEqual(vm._allowed_edges(), {"top", "bottom"})
        wm.shutdown()


# ---------------------------------------------------------------------------
# Parts 7-9 — Session schema
# ---------------------------------------------------------------------------

class TestSessionSizeSchema(unittest.TestCase):
    def test_serialize_includes_width_height(self):
        from toroidamp.session import SessionManager, ModulePosition
        with tempfile.TemporaryDirectory() as td:
            sf = os.path.join(td, "session.json")
            sm = SessionManager(custom_path=sf)
            sm.state.vis_module = ModulePosition(x=1, y=2, width=680, height=400)
            sm.state.pl_module = ModulePosition(x=3, y=4, width=340, height=500)
            sm.save()

            data = json.loads(open(sf, encoding="utf-8").read())
            self.assertEqual(data["vis_module"]["width"], 680)
            self.assertEqual(data["vis_module"]["height"], 400)
            self.assertEqual(data["pl_module"]["width"], 340)
            self.assertEqual(data["pl_module"]["height"], 500)

    def test_old_session_without_dimensions_loads_safely(self):
        from toroidamp.session import SessionManager
        with tempfile.TemporaryDirectory() as td:
            sf = os.path.join(td, "session.json")
            legacy = {
                "version": 1, "scale": "normal", "volume": 0.8,
                "chassis_pos": {"x": 1, "y": 2, "w": 420, "h": 135},
                "vis_module": {"x": 5, "y": 6, "is_docked": True, "dock_edge": "bottom", "is_visible": False},
                "pl_module": {"x": 7, "y": 8, "is_docked": True, "dock_edge": "right", "is_visible": False},
            }
            with open(sf, "w", encoding="utf-8") as f:
                json.dump(legacy, f)

            sm = SessionManager(custom_path=sf)
            st = sm.load()
            self.assertEqual(st.vis_module.width, 0)
            self.assertEqual(st.vis_module.height, 0)
            self.assertEqual(st.pl_module.width, 0)
            self.assertEqual(st.pl_module.height, 0)

    def test_invalid_dimensions_clamp_safely(self):
        from toroidamp.session import SessionManager
        with tempfile.TemporaryDirectory() as td:
            sf = os.path.join(td, "session.json")
            bad = {
                "version": 1, "scale": "normal", "volume": 0.8,
                "vis_module": {"x": 5, "y": 6, "width": -50, "height": "nonsense", "is_docked": True, "dock_edge": "bottom", "is_visible": False},
                "pl_module": {"x": 7, "y": 8, "width": 0, "height": -1, "is_docked": True, "dock_edge": "right", "is_visible": False},
            }
            with open(sf, "w", encoding="utf-8") as f:
                json.dump(bad, f)

            sm = SessionManager(custom_path=sf)
            st = sm.load()
            self.assertEqual(st.vis_module.width, 0)
            self.assertEqual(st.vis_module.height, 0)
            self.assertEqual(st.pl_module.width, 0)
            self.assertEqual(st.pl_module.height, 0)


class TestSessionSizeRestoreIntegration(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_restart_restores_module_sizes(self):
        from toroidamp.session import SessionManager
        with tempfile.TemporaryDirectory() as td:
            sf = os.path.join(td, "session.json")
            sm = SessionManager(custom_path=sf)
            wm = _make_window_manager(session_manager=sm)
            wm._toggle_vis()
            wm._toggle_pl()
            wm.undock_module(wm.vis_mod)
            wm.undock_module(wm.pl_mod)
            wm.vis_mod.resize(680, 400)
            wm.pl_mod.resize(340, 500)
            wm.save_current_session()
            wm.shutdown()

            sm2 = SessionManager(custom_path=sf)
            wm2 = _make_window_manager(session_manager=sm2)
            self.assertEqual((wm2.vis_mod.width(), wm2.vis_mod.height()), (680, 400))
            self.assertEqual((wm2.pl_mod.width(), wm2.pl_mod.height()), (340, 500))
            wm2.shutdown()


# ---------------------------------------------------------------------------
# Parts 10-11 — Reset Size control
# ---------------------------------------------------------------------------

class TestResetSizeControl(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_reset_size_restores_default_dimensions(self):
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        vm = VisualizerModule()
        vm.resize(700, 430)
        vm.reset_size()
        self.assertEqual((vm.width(), vm.height()), (420, 240))
        vm.close()

    def test_reset_size_does_not_move_dock_or_close(self):
        wm = _make_window_manager()
        wm._toggle_vis()
        wm.undock_module(wm.vis_mod)
        wm.vis_mod.move(123, 456)
        wm.vis_mod.resize(700, 430)
        pos_before = wm.vis_mod.pos()
        docked_before = wm.vis_mod.is_docked
        visible_before = wm.vis_mod.isVisible()

        wm.vis_mod.reset_size()

        self.assertEqual(wm.vis_mod.pos(), pos_before)
        self.assertEqual(wm.vis_mod.is_docked, docked_before)
        self.assertEqual(wm.vis_mod.isVisible(), visible_before)
        self.assertEqual((wm.vis_mod.width(), wm.vis_mod.height()), (420, 240))
        wm.shutdown()

    def test_reset_size_button_exists_and_is_wired(self):
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        vm = VisualizerModule()
        self.assertTrue(hasattr(vm, "btn_reset"))
        self.assertIn("reset", vm.btn_reset.toolTip().lower())
        vm.close()


# ---------------------------------------------------------------------------
# Part 12 — RETINA MELT isolation
# ---------------------------------------------------------------------------

class TestRetinaMeltDoesNotOverwriteVisSize(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_retina_melt_roundtrip_preserves_vis_module_size(self):
        wm = _make_window_manager()
        wm._toggle_vis()
        wm.undock_module(wm.vis_mod)
        wm.vis_mod.resize(700, 430)

        wm._enter_retina_melt()
        wm._exit_retina_melt()

        self.assertEqual((wm.vis_mod.width(), wm.vis_mod.height()), (700, 430))
        wm.shutdown()


# ---------------------------------------------------------------------------
# Part 13 — Taskbar ownership structurally intact
# ---------------------------------------------------------------------------

class TestTaskbarOwnershipIntact(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_modules_remain_owned_windows_of_chassis(self):
        wm = _make_window_manager()
        self.assertTrue(bool(wm.vis_mod.windowFlags() & Qt.Window))
        self.assertTrue(bool(wm.pl_mod.windowFlags() & Qt.Window))
        self.assertIs(wm.vis_mod.parentWidget(), wm.chassis)
        self.assertIs(wm.pl_mod.parentWidget(), wm.chassis)
        wm.shutdown()

    def test_retina_melt_is_also_an_owned_window_of_chassis(self):
        # v0.666: RETINA MELT previously had no Qt parent at all, so it got
        # no owned-window/WM_TRANSIENT_FOR taskbar-grouping hint on either
        # platform (Task 6) -- it should follow the same pattern as the
        # dockable modules above.
        wm = _make_window_manager()
        self.assertTrue(bool(wm.retina_melt.windowFlags() & Qt.Window))
        self.assertIs(wm.retina_melt.parentWidget(), wm.chassis)
        wm.shutdown()


if __name__ == "__main__":
    unittest.main()
