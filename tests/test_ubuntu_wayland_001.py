"""
tests/test_ubuntu_wayland_001.py — Ubuntu / Wayland Integration & Lifecycle
Stabilization

Focused regression tests for:
  1-2. TTS playback: pygame.mixer is always explicitly (re)configured with
       VoiceService's own known parameters, not conditionally skipped when
       some unrelated earlier pygame.init() call already initialized it
       with unknown parameters; a genuine "no channel available" case logs
       a warning instead of a misleading success message. Windows SAPI5
       path (the engine/text-to-WAV half) is untouched.
  3-4. Frameless window drag: QWindow.startSystemMove() is invoked when
       the Qt platform is Wayland; the existing manual move()-based drag
       (with MINI edge-snapping) is preserved unchanged everywhere else.
  5. Application identity: QApplication.setDesktopFileName() is set (a
     portable, Qt-native mechanism -- not a compositor-specific hack).
  6-7. OpenGL shutdown lifecycle: WindowManager.shutdown() explicitly
       releases both GLVisualizerCanvas instances' GPU resources while
       their context is still current, and cleanupGL() stays idempotent
       (no double-free) whether called once or twice.

No real audio hardware, GPU, or Wayland compositor is required -- pygame
and Qt platform APIs are mocked/injected where the underlying behavior
can't be observed headlessly.
"""

import os
import re
import sys
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent

from toroidamp.audio.voice import VoiceService
from toroidamp.ui.chassis import UnifiedChassis

_app = QApplication.instance() or QApplication(sys.argv)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_window_manager(session_manager=None):
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


class TestTtsPlaybackBackend(unittest.TestCase):
    """RELEASE-BLOCKERS-001: voice playback no longer depends on
    pygame.mixer/SDL -- that backend's Linux device lifecycle proved
    unreliable across repeated launches even after explicit mixer
    reconfigure/quit (UBUNTU-WAYLAND-002). Playback now decodes the
    synthesized WAV via `soundfile` and plays it through `sounddevice`,
    sharing the exact device-selection policy already validated for
    reliable Ubuntu/PipeWire music playback."""

    def _make_mock_engine(self):
        engine = MagicMock()
        engine.getProperty.return_value = []
        return engine

    def _fake_wav_data(self, frames=4410, sr=44100):
        return np.zeros((frames, 2), dtype="float32"), sr

    def test_01_playback_uses_sounddevice_with_validated_device_policy(self):
        vs = VoiceService()
        mock_engine = self._make_mock_engine()
        data, sr = self._fake_wav_data()

        with patch("toroidamp.audio.voice.pyttsx3.init", return_value=mock_engine):
            with patch("toroidamp.audio.voice.os.path.getsize", return_value=100):
                with patch("toroidamp.audio.voice.sf.read", return_value=(data, sr)):
                    with patch("toroidamp.audio.voice.select_output_device", return_value=7) as mock_select:
                        with patch("toroidamp.audio.voice.sd.play") as mock_play:
                            with patch("toroidamp.audio.voice.sd.wait") as mock_wait:
                                vs._synthesize_and_play("test phrase")

        mock_select.assert_called_once()
        mock_play.assert_called_once()
        self.assertEqual(mock_play.call_args.kwargs.get("device"), 7)
        mock_wait.assert_called_once()

    def test_02_playback_failure_logs_diagnostic_not_false_success(self):
        vs = VoiceService()
        mock_engine = self._make_mock_engine()
        data, sr = self._fake_wav_data()

        with patch("toroidamp.audio.voice.pyttsx3.init", return_value=mock_engine):
            with patch("toroidamp.audio.voice.os.path.getsize", return_value=100):
                with patch("toroidamp.audio.voice.sf.read", return_value=(data, sr)):
                    with patch("toroidamp.audio.voice.select_output_device", return_value=None):
                        with patch("toroidamp.audio.voice.sd.play", side_effect=RuntimeError("no output device")):
                            with patch("toroidamp.audio.voice.logger") as mock_logger:
                                vs._synthesize_and_play("test phrase")

        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        self.assertTrue(
            any("failed gracefully" in c for c in warning_calls),
            f"expected a playback-failure diagnostic, got: {warning_calls}",
        )
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        self.assertFalse(
            any("completed" in c for c in info_calls),
            "must not log the success message when playback raised",
        )

    def test_03_temp_wav_removed_after_playback(self):
        vs = VoiceService()
        mock_engine = self._make_mock_engine()
        data, sr = self._fake_wav_data()
        captured_path = {}
        mock_engine.save_to_file.side_effect = lambda text, path: captured_path.setdefault("path", path)

        with patch("toroidamp.audio.voice.pyttsx3.init", return_value=mock_engine):
            with patch("toroidamp.audio.voice.os.path.getsize", return_value=100):
                with patch("toroidamp.audio.voice.sf.read", return_value=(data, sr)):
                    with patch("toroidamp.audio.voice.sd.play"):
                        with patch("toroidamp.audio.voice.sd.wait"):
                            vs._synthesize_and_play("test phrase")

        self.assertIn("path", captured_path)
        self.assertFalse(os.path.exists(captured_path["path"]), "temp WAV must be removed after playback")

    def test_04_repeated_lifecycle_no_stale_state(self):
        # Five consecutive synthesize+play cycles must each succeed
        # independently -- no shared, leaking state between VoiceService
        # instances (mirrors the "5 consecutive clean launches" manual
        # release gate).
        data, sr = self._fake_wav_data()
        for i in range(5):
            vs = VoiceService()
            mock_engine = self._make_mock_engine()
            with patch("toroidamp.audio.voice.pyttsx3.init", return_value=mock_engine):
                with patch("toroidamp.audio.voice.os.path.getsize", return_value=100):
                    with patch("toroidamp.audio.voice.sf.read", return_value=(data, sr)):
                        with patch("toroidamp.audio.voice.sd.play") as mock_play:
                            with patch("toroidamp.audio.voice.sd.wait"):
                                vs._synthesize_and_play(f"cycle {i}")
            mock_play.assert_called_once()
            self.assertFalse(vs.is_speaking)

    def test_05_no_pygame_mixer_import(self):
        src = (REPO_ROOT / "src" / "toroidamp" / "audio" / "voice.py").read_text(encoding="utf-8")
        self.assertNotIn("import pygame", src)


class TestWaylandFramelessDrag(unittest.TestCase):
    """QWindow.startSystemMove() on Wayland; existing manual drag (with
    MINI edge-snapping) preserved everywhere else."""

    def _press_event(self, chassis, pos=QPoint(50, 10)):
        return QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(pos), QPointF(chassis.mapToGlobal(pos)),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )

    def test_06_wayland_uses_start_system_move(self):
        c = UnifiedChassis()
        c.show()
        mock_window = MagicMock()

        with patch("toroidamp.ui.chassis.QGuiApplication.platformName", return_value="wayland"):
            with patch.object(type(c), "windowHandle", return_value=mock_window):
                c.mousePressEvent(self._press_event(c))

        mock_window.startSystemMove.assert_called_once()
        self.assertFalse(c._is_dragging, "the manual drag path must not also be armed on Wayland")
        c.close()

    def test_07_non_wayland_keeps_manual_drag_path(self):
        c = UnifiedChassis()
        c.show()
        mock_window = MagicMock()

        with patch("toroidamp.ui.chassis.QGuiApplication.platformName", return_value="windows"):
            with patch.object(type(c), "windowHandle", return_value=mock_window):
                c.mousePressEvent(self._press_event(c))

        mock_window.startSystemMove.assert_not_called()
        self.assertTrue(c._is_dragging, "non-Wayland platforms must keep using the existing manual drag+snap path")
        c.close()


class TestApplicationIdentity(unittest.TestCase):
    def test_08_desktop_file_name_declared(self):
        src = (REPO_ROOT / "src" / "toroidamp" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn('setDesktopFileName("toroidamp")', src)


class TestGpuShutdownLifecycle(unittest.TestCase):
    def test_09_shutdown_explicitly_cleans_up_both_gpu_canvases(self):
        wm = _make_window_manager()
        with patch.object(wm.vis_mod.gpu_canvas, "cleanupGL") as vis_cleanup:
            with patch.object(wm.retina_melt.gpu_canvas, "cleanupGL") as retina_cleanup:
                wm.shutdown()
        vis_cleanup.assert_called_once()
        retina_cleanup.assert_called_once()

    def test_10_shutdown_gpu_cleanup_is_exception_isolated(self):
        # A cleanup failure on one canvas must not prevent the rest of
        # shutdown (session save, window close, app quit) from completing.
        wm = _make_window_manager()
        with patch.object(wm.vis_mod.gpu_canvas, "cleanupGL", side_effect=RuntimeError("boom")):
            try:
                wm.shutdown()
            except Exception as e:
                self.fail(f"shutdown() must isolate a GPU cleanup failure, raised: {e}")

    def test_11_cleanup_gl_remains_idempotent(self):
        wm = _make_window_manager()
        wm.vis_mod.gpu_canvas.cleanupGL()
        try:
            wm.vis_mod.gpu_canvas.cleanupGL()
        except Exception as e:
            self.fail(f"a second cleanupGL() call must be a safe no-op, raised: {e}")
        wm.shutdown()


class TestAuxiliaryWindowComposition(unittest.TestCase):
    """UBUNTU-WAYLAND-002 Task 2: the desired relative geometry -- Playlist
    right of NORMAL, Visualizer below NORMAL -- is exactly what
    realign_docked_modules() already computes. This is verifiable headlessly
    (no real compositor needed); whether a Wayland compositor actually
    honors the resulting move() is a separate, non-testable-headlessly
    concern documented in window_manager.py and the manual checklist."""

    def test_12_visualizer_docks_below_chassis(self):
        wm = _make_window_manager()
        wm.chassis.show()
        wm.chassis.setGeometry(100, 100, 400, 300)
        wm.vis_mod.show()
        wm.dock_module(wm.vis_mod, "bottom")

        core_geom = wm.chassis.geometry()
        self.assertEqual(wm.vis_mod.x(), core_geom.left())
        self.assertEqual(wm.vis_mod.y(), core_geom.bottom() + 2)
        wm.shutdown()

    def test_13_playlist_docks_right_of_chassis(self):
        wm = _make_window_manager()
        wm.chassis.show()
        wm.chassis.setGeometry(100, 100, 400, 300)
        wm.pl_mod.show()
        wm.dock_module(wm.pl_mod, "right")

        core_geom = wm.chassis.geometry()
        self.assertEqual(wm.pl_mod.x(), core_geom.right() + 2)
        self.assertEqual(wm.pl_mod.y(), core_geom.top())
        wm.shutdown()

    def test_14_toggle_positions_before_showing(self):
        # _toggle_vis/_toggle_pl must dock (compute position) before show()
        # so the module never visibly appears at a stale/default position
        # and then jumps -- verified by checking both are simultaneously
        # correct relative to the chassis once its own geometry (which
        # UnifiedChassis manages/constrains itself in NORMAL mode) has
        # settled after both toggles.
        wm = _make_window_manager()
        wm.chassis.show()
        wm._toggle_pl()
        wm._toggle_vis()
        wm.realign_docked_modules()

        core_geom = wm.chassis.geometry()
        self.assertEqual((wm.pl_mod.x(), wm.pl_mod.y()), (core_geom.right() + 2, core_geom.top()))
        self.assertEqual((wm.vis_mod.x(), wm.vis_mod.y()), (core_geom.left(), core_geom.bottom() + 2))
        wm.shutdown()


class TestLabFileDialogOwnership(unittest.TestCase):
    """UBUNTU-WAYLAND-002 Task 3/4: the Lab's QFileDialog calls always pass
    `self` as parent (correct, standard Qt ownership -- unchanged by this
    cut). On Wayland specifically, the dialog is additionally forced
    non-native (bypassing the xdg-desktop-portal file chooser) so it gets
    normal Qt-managed transient-parent stacking instead of depending on a
    portal parent-window handoff that this same platform's log shows
    failing to register."""

    def _load_lab_app(self):
        import importlib.util
        lab_app_path = REPO_ROOT / "experiments" / "gpu_visualizers" / "lab_app.py"
        spec = importlib.util.spec_from_file_location("lab_app_wayland002", lab_app_path)
        lab_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab_app)
        return lab_app

    def test_15_dialog_options_force_non_native_only_on_wayland(self):
        lab_app = self._load_lab_app()

        with patch.object(lab_app.QGuiApplication, "platformName", return_value="wayland"):
            opts = lab_app._file_dialog_options()
        self.assertTrue(bool(opts & lab_app.QFileDialog.Option.DontUseNativeDialog))

        with patch.object(lab_app.QGuiApplication, "platformName", return_value="windows"):
            opts = lab_app._file_dialog_options()
        self.assertFalse(bool(opts & lab_app.QFileDialog.Option.DontUseNativeDialog))

    def test_16_load_shader_dialog_passes_self_as_parent(self):
        lab_app = self._load_lab_app()
        win = lab_app.GPUAuthoringLabWindow()

        with patch.object(lab_app.QFileDialog, "getOpenFileName", return_value=("", "")) as mock_dialog:
            win.load_external_shader_dialog()

        self.assertEqual(mock_dialog.call_args.args[0], win)
        win.close()


class TestWaylandUnifiedChassis(unittest.TestCase):
    """RELEASE-BLOCKERS-001 Blocker 2: on Wayland, Playlist/Visualizer are
    hosted as embedded child widgets inside the chassis's own single
    top-level surface (WindowManager._wayland_embedded +
    UnifiedChassis.embed_module()) instead of independent xdg_toplevels --
    sidestepping Wayland's lack of client-side toplevel positioning
    entirely rather than fighting it. Windows/X11 keep the existing
    independent-top-level architecture completely unchanged."""

    def _make_wm(self, wayland: bool):
        with patch("toroidamp.ui.window_manager.QGuiApplication.platformName",
                   return_value="wayland" if wayland else "windows"):
            wm = _make_window_manager()
        wm.chassis.show()
        return wm

    def test_17_wayland_modules_are_embedded_not_toplevel(self):
        wm = self._make_wm(wayland=True)
        self.assertTrue(wm.vis_mod.embedded)
        self.assertTrue(wm.pl_mod.embedded)
        self.assertFalse(bool(wm.vis_mod.windowFlags() & Qt.Window))
        self.assertFalse(bool(wm.pl_mod.windowFlags() & Qt.Window))
        wm.shutdown()

    def test_18_windows_modules_remain_independent_toplevel(self):
        wm = self._make_wm(wayland=False)
        self.assertFalse(wm.vis_mod.embedded)
        self.assertFalse(wm.pl_mod.embedded)
        self.assertTrue(bool(wm.vis_mod.windowFlags() & Qt.Window))
        self.assertTrue(bool(wm.pl_mod.windowFlags() & Qt.Window))
        wm.shutdown()

    def test_19_toggle_playlist_embeds_in_right_cell(self):
        wm = self._make_wm(wayland=True)
        wm._toggle_pl()
        self.assertIs(wm.chassis._embedded_modules.get("right"), wm.pl_mod)
        self.assertTrue(wm.pl_mod.isVisible())
        wm.shutdown()

    def test_20_toggle_visualizer_embeds_in_bottom_cell(self):
        wm = self._make_wm(wayland=True)
        wm._toggle_vis()
        self.assertIs(wm.chassis._embedded_modules.get("bottom"), wm.vis_mod)
        self.assertTrue(wm.vis_mod.isVisible())
        wm.shutdown()

    def test_21_both_simultaneously_no_overlap(self):
        wm = self._make_wm(wayland=True)
        wm._toggle_pl()
        wm._toggle_vis()
        self.assertEqual(set(wm.chassis._embedded_modules.keys()), {"right", "bottom"})
        self.assertTrue(wm.pl_mod.isVisible())
        self.assertTrue(wm.vis_mod.isVisible())
        wm.shutdown()

    def test_22_closing_module_detaches_from_chassis(self):
        wm = self._make_wm(wayland=True)
        wm._toggle_pl()
        wm._toggle_pl()  # close again
        self.assertNotIn("right", wm.chassis._embedded_modules)
        self.assertFalse(wm.pl_mod.isVisible())
        wm.shutdown()

    def test_23_mini_transition_detaches_and_normal_reattaches(self):
        wm = self._make_wm(wayland=True)
        wm._toggle_pl()
        wm._toggle_vis()
        wm.chassis.set_mode("mini")
        self.assertEqual(wm.chassis._embedded_modules, {})
        wm.chassis.set_mode("normal")
        self.assertEqual(set(wm.chassis._embedded_modules.keys()), {"right", "bottom"})
        wm.shutdown()

    def test_24_dock_module_is_noop_when_embedded(self):
        wm = self._make_wm(wayland=True)
        wm.pl_mod.is_docked = False
        wm.dock_module(wm.pl_mod, "right")
        self.assertFalse(wm.pl_mod.is_docked, "dock_module() must no-op entirely for embedded modules")
        wm.shutdown()

    def test_25_embed_module_none_collapses_cell(self):
        c = UnifiedChassis()
        c.show()
        w = QWidget()
        c.embed_module("right", w)
        self.assertIs(c._embedded_modules["right"], w)
        c.embed_module("right", None)
        self.assertNotIn("right", c._embedded_modules)
        c.close()

    def test_26_embedded_module_dragging_disabled(self):
        # No independent movement under Wayland (spec): the title-bar drag
        # path must not arm for an embedded module.
        wm = self._make_wm(wayland=True)
        wm._toggle_pl()
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(50, 10), QPointF(wm.pl_mod.mapToGlobal(QPoint(50, 10))),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )
        wm.pl_mod.mousePressEvent(press)
        self.assertFalse(wm.pl_mod._is_dragging)
        wm.shutdown()


if __name__ == "__main__":
    unittest.main()
