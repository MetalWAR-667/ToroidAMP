"""
ToroidAMP - LINUX-DIALOG-001 Test Suite
Validation of Wayland File Dialog Reliability, Ownership, Platform Policy,
and Playlist ADD / M3U / RETINA / Lab Dialog Stabilization.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtGui import QGuiApplication

# Ensure application instance exists
_app = QApplication.instance() or QApplication(sys.argv)

from toroidamp.ui.dialogs import platform_file_dialog_options
from toroidamp.ui.modules.playlist_module import PlaylistModule
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.ui.theme import ThemeManager


class TestPlatformFileDialogOptions(unittest.TestCase):
    """Tests the canonical platform_file_dialog_options helper."""

    def test_01_wayland_platform_returns_dont_use_native_dialog(self):
        with patch("toroidamp.ui.dialogs.QGuiApplication.platformName", return_value="wayland"):
            opts = platform_file_dialog_options()
        self.assertTrue(bool(opts & QFileDialog.Option.DontUseNativeDialog))

    def test_02_non_wayland_platforms_preserve_native_dialog(self):
        for plat in ("windows", "xcb", "cocoa", "offscreen"):
            with self.subTest(platform=plat):
                with patch("toroidamp.ui.dialogs.QGuiApplication.platformName", return_value=plat):
                    opts = platform_file_dialog_options()
                self.assertFalse(bool(opts & QFileDialog.Option.DontUseNativeDialog))

    def test_03_extra_options_preserved_with_wayland(self):
        extra = QFileDialog.Option.ReadOnly | QFileDialog.Option.ShowDirsOnly
        with patch("toroidamp.ui.dialogs.QGuiApplication.platformName", return_value="wayland"):
            opts = platform_file_dialog_options(extra)
        self.assertTrue(bool(opts & QFileDialog.Option.DontUseNativeDialog))
        self.assertTrue(bool(opts & QFileDialog.Option.ReadOnly))
        self.assertTrue(bool(opts & QFileDialog.Option.ShowDirsOnly))

    def test_04_extra_options_preserved_without_wayland(self):
        extra = QFileDialog.Option.ReadOnly | QFileDialog.Option.ShowDirsOnly
        with patch("toroidamp.ui.dialogs.QGuiApplication.platformName", return_value="windows"):
            opts = platform_file_dialog_options(extra)
        self.assertFalse(bool(opts & QFileDialog.Option.DontUseNativeDialog))
        self.assertTrue(bool(opts & QFileDialog.Option.ReadOnly))
        self.assertTrue(bool(opts & QFileDialog.Option.ShowDirsOnly))


class TestPlaylistModuleDialogInteractions(unittest.TestCase):
    """Tests PlaylistModule file dialog invocation, parenting, options, and semantics."""

    def setUp(self):
        self.playlist_mgr = PlaylistManager()
        self.module = PlaylistModule(self.playlist_mgr)

    def tearDown(self):
        self.module.close()

    def test_05_browse_add_files_passes_self_and_platform_options(self):
        with patch("toroidamp.ui.modules.playlist_module.platform_file_dialog_options", return_value=QFileDialog.Option.DontUseNativeDialog) as mock_opts,              patch.object(QFileDialog, "getOpenFileNames", return_value=([], "")) as mock_dialog:
            self.module._browse_add_files()

        mock_opts.assert_called_once()
        self.assertEqual(mock_dialog.call_args.args[0], self.module)
        self.assertEqual(mock_dialog.call_args.args[1], "Add Audio Tracks to Playlist")
        self.assertIn("*.mp3", mock_dialog.call_args.args[3])
        self.assertEqual(mock_dialog.call_args.kwargs.get("options"), QFileDialog.Option.DontUseNativeDialog)

    def test_06_browse_add_files_multi_file_selection_populates_playlist(self):
        sample_paths = ["/music/track1.mp3", "/music/track2.xm", "/music/track3.flac"]
        with patch("toroidamp.ui.modules.playlist_module.platform_file_dialog_options", return_value=QFileDialog.Option.DontUseNativeDialog), \
             patch.object(QFileDialog, "getOpenFileNames", return_value=(sample_paths, "Audio Files (*.mp3 ...)")), \
             patch("os.path.isfile", return_value=True):
            self.module._browse_add_files()

        self.assertEqual(len(self.playlist_mgr.items), 3)
        self.assertEqual(self.playlist_mgr.items[0].filepath, os.path.abspath("/music/track1.mp3"))
        self.assertEqual(self.playlist_mgr.items[1].filepath, os.path.abspath("/music/track2.xm"))
        self.assertEqual(self.playlist_mgr.items[2].filepath, os.path.abspath("/music/track3.flac"))
        self.assertEqual(self.module.list_widget.count(), 3)

    def test_07_browse_add_files_cancel_preserves_existing_state(self):
        with patch("os.path.isfile", return_value=True):
            self.playlist_mgr.add_files(["/music/existing.mp3"])
        self.module.refresh()
        self.assertEqual(len(self.playlist_mgr.items), 1)

        with patch("toroidamp.ui.modules.playlist_module.platform_file_dialog_options", return_value=QFileDialog.Option.DontUseNativeDialog), \
             patch.object(QFileDialog, "getOpenFileNames", return_value=([], "")):
            self.module._browse_add_files()

        self.assertEqual(len(self.playlist_mgr.items), 1)
        self.assertEqual(self.module.list_widget.count(), 1)


class TestRetinaAndLabDialogInteractions(unittest.TestCase):
    """Tests RetinaMeltWindow and LabApp dialog consistency."""

    def test_08_retina_load_shader_dialog_passes_self_and_platform_options(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        win = RetinaMeltWindow(session_manager=SessionManager())
        try:
            with patch("toroidamp.ui.fullscreen.platform_file_dialog_options", return_value=QFileDialog.Option.DontUseNativeDialog) as mock_opts,                  patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as mock_dialog:
                win._load_local_shader_dialog()

            mock_opts.assert_called_once()
            self.assertEqual(mock_dialog.call_args.args[0], win)
            self.assertEqual(mock_dialog.call_args.kwargs.get("options"), QFileDialog.Option.DontUseNativeDialog)
        finally:
            win.close()

    def test_09_retina_preset_dialogs_pass_self_and_platform_options(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        win = RetinaMeltWindow(session_manager=SessionManager())
        win.gpu_canvas.metadata = MagicMock(parameters={"u_speed": MagicMock()})
        try:
            with patch("toroidamp.ui.fullscreen.platform_file_dialog_options", return_value=QFileDialog.Option.DontUseNativeDialog),                  patch.object(QFileDialog, "getSaveFileName", return_value=("", "")) as mock_save:
                win._save_lab_preset_dialog()
            self.assertEqual(mock_save.call_args.args[0], win)
            self.assertEqual(mock_save.call_args.kwargs.get("options"), QFileDialog.Option.DontUseNativeDialog)

            with patch("toroidamp.ui.fullscreen.platform_file_dialog_options", return_value=QFileDialog.Option.DontUseNativeDialog),                  patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as mock_load:
                win._load_lab_preset_dialog()
            self.assertEqual(mock_load.call_args.args[0], win)
            self.assertEqual(mock_load.call_args.kwargs.get("options"), QFileDialog.Option.DontUseNativeDialog)
        finally:
            win.close()

    def test_10_lab_app_file_dialog_options_delegates_to_canonical_helper(self):
        import importlib.util
        repo_root = Path(__file__).resolve().parent.parent
        lab_app_path = repo_root / "experiments" / "gpu_visualizers" / "lab_app.py"
        spec = importlib.util.spec_from_file_location("lab_app_dialog_test", lab_app_path)
        lab_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab_app)

        with patch("toroidamp.ui.dialogs.QGuiApplication.platformName", return_value="wayland"):
            opts = lab_app._file_dialog_options()
        self.assertTrue(bool(opts & QFileDialog.Option.DontUseNativeDialog))

        with patch("toroidamp.ui.dialogs.QGuiApplication.platformName", return_value="windows"):
            opts = lab_app._file_dialog_options()
        self.assertFalse(bool(opts & QFileDialog.Option.DontUseNativeDialog))


if __name__ == "__main__":
    unittest.main()
