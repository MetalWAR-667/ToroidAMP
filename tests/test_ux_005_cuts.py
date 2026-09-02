"""
tests/test_ux_005_cuts.py — Automated Test Suite for UX-005 Cuts (A, B, C, D)

Covers:
  UX-005A — Input & Media Controls (Focused shortcuts, Text-Input safety, Media Keys)
  UX-005B — Enhanced Drag & Drop (Recursive directories, deterministic order, safety)
  UX-005C — Playlist Quick Search (Incremental filter, view-only integrity, canonical mapping)
  UX-005D — Track Change Notification (OSD lifecycle, non-focus-stealing, format tags)
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QWidget, QListWidgetItem
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QKeyEvent

from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.playlist import (
    PlaylistManager, PlaylistItem, SUPPORTED_AUDIO_EXTENSIONS, collect_audio_files
)
from toroidamp.ui.modules.playlist_module import PlaylistModule
from toroidamp.ui.shortcuts import AppShortcutFilter, is_editable_text_widget
from toroidamp.ui.media_keys import (
    WindowsGlobalMediaKeys,
    HOTKEY_ID_PLAY_PAUSE,
    HOTKEY_ID_NEXT,
    HOTKEY_ID_PREV,
    HOTKEY_ID_STOP,
    HOTKEY_ID_MUTE,
    WM_HOTKEY,
    WM_APPCOMMAND,
    APPCOMMAND_MEDIA_PLAY_PAUSE,
    APPCOMMAND_MEDIA_NEXTTRACK,
    APPCOMMAND_MEDIA_PREVIOUSTRACK,
    APPCOMMAND_MEDIA_STOP,
    APPCOMMAND_VOLUME_MUTE,
)
from toroidamp.ui.osd import TrackChangeOSD
from toroidamp.ui.window_manager import WindowManager
from toroidamp.session import SessionManager


class MockWindowManager:
    """Mock WindowManager for testing AppShortcutFilter in isolation."""
    def __init__(self):
        self.play_toggled_count = 0
        self.seek_deltas = []
        self.volume_deltas = []
        self.mute_toggled_count = 0
        self.visualizer_cycled_count = 0
        self.retina_melt_toggled_count = 0
        self.playlist_search_opened_count = 0

    def _toggle_play(self):
        self.play_toggled_count += 1

    def _relative_seek(self, delta: float):
        self.seek_deltas.append(delta)

    def _relative_volume(self, delta: float):
        self.volume_deltas.append(delta)

    def _toggle_mute(self):
        self.mute_toggled_count += 1

    def _cycle_visualizer(self):
        self.visualizer_cycled_count += 1

    def _toggle_retina_melt(self):
        self.retina_melt_toggled_count += 1

    def _open_playlist_search(self):
        self.playlist_search_opened_count += 1


class TestUX005AInputAndMediaControls(unittest.TestCase):
    """UX-005A: Focused application shortcuts and Text-Input Safety."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.wm = MockWindowManager()
        self.filter = AppShortcutFilter(self.wm)
        self.dummy_widget = QWidget()

    def _send_key(self, target, key, modifiers=Qt.NoModifier) -> bool:
        event = QKeyEvent(QEvent.KeyPress, key, modifiers)
        return self.filter.eventFilter(target, event)

    def test_01_space_toggles_playback(self):
        consumed = self._send_key(self.dummy_widget, Qt.Key_Space)
        self.assertTrue(consumed)
        self.assertEqual(self.wm.play_toggled_count, 1)

    def test_02_arrows_seek_and_volume(self):
        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_Left))
        self.assertEqual(self.wm.seek_deltas, [-5.0])

        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_Right))
        self.assertEqual(self.wm.seek_deltas, [-5.0, +5.0])

        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_Up))
        self.assertEqual(self.wm.volume_deltas, [+0.05])

        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_Down))
        self.assertEqual(self.wm.volume_deltas, [+0.05, -0.05])

    def test_03_m_and_v_shortcuts(self):
        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_M))
        self.assertEqual(self.wm.mute_toggled_count, 1)

        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_V))
        self.assertEqual(self.wm.visualizer_cycled_count, 1)

    def test_04_f11_and_ctrl_f(self):
        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_F11))
        self.assertEqual(self.wm.retina_melt_toggled_count, 1)

        self.assertTrue(self._send_key(self.dummy_widget, Qt.Key_F, Qt.ControlModifier))
        self.assertEqual(self.wm.playlist_search_opened_count, 1)

    def test_05_text_input_safety_qlineedit(self):
        line_edit = QLineEdit()
        line_edit.setFocus()

        # Space, M, V, Left, Right, Up, Down should NOT be consumed when typing
        for key in (Qt.Key_Space, Qt.Key_M, Qt.Key_V, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            consumed = self._send_key(line_edit, key)
            self.assertFalse(consumed, f"Key {key} should not be intercepted when typing in QLineEdit")

        self.assertEqual(self.wm.play_toggled_count, 0)
        self.assertEqual(self.wm.mute_toggled_count, 0)
        self.assertEqual(self.wm.visualizer_cycled_count, 0)
        self.assertEqual(len(self.wm.seek_deltas), 0)
        self.assertEqual(len(self.wm.volume_deltas), 0)

    def test_06_text_input_safety_qtextedit(self):
        text_edit = QTextEdit()
        text_edit.setFocus()

        consumed = self._send_key(text_edit, Qt.Key_M)
        self.assertFalse(consumed)
        self.assertEqual(self.wm.mute_toggled_count, 0)

    def test_07_is_editable_text_widget_detection(self):
        le = QLineEdit()
        self.assertTrue(is_editable_text_widget(le))

        le.setReadOnly(True)
        self.assertFalse(is_editable_text_widget(le))

        le.setReadOnly(False)
        le.setEnabled(False)
        self.assertFalse(is_editable_text_widget(le))

        self.assertFalse(is_editable_text_widget(QWidget()))
        self.assertFalse(is_editable_text_widget(None))

    def test_08_windows_global_media_keys_debounce_and_dispatch(self):
        calls = {"play": 0, "next": 0, "prev": 0, "stop": 0, "mute": 0}
        gmk = WindowsGlobalMediaKeys(
            hwnd=1234,
            on_play_pause=lambda: calls.__setitem__("play", calls["play"] + 1),
            on_next=lambda: calls.__setitem__("next", calls["next"] + 1),
            on_prev=lambda: calls.__setitem__("prev", calls["prev"] + 1),
            on_stop=lambda: calls.__setitem__("stop", calls["stop"] + 1),
            on_mute=lambda: calls.__setitem__("mute", calls["mute"] + 1),
        )

        gmk._debounce_and_dispatch(HOTKEY_ID_PLAY_PAUSE, gmk._on_play_pause)
        self.assertEqual(calls["play"], 1)

        # Immediate repeat should be suppressed by debounce (< 100ms)
        gmk._debounce_and_dispatch(HOTKEY_ID_PLAY_PAUSE, gmk._on_play_pause)
        self.assertEqual(calls["play"], 1)

        # Other keys should dispatch fine
        gmk._debounce_and_dispatch(HOTKEY_ID_NEXT, gmk._on_next)
        self.assertEqual(calls["next"], 1)

        gmk._debounce_and_dispatch(HOTKEY_ID_PREV, gmk._on_prev)
        self.assertEqual(calls["prev"], 1)

        gmk._debounce_and_dispatch(HOTKEY_ID_STOP, gmk._on_stop)
        self.assertEqual(calls["stop"], 1)

        gmk._debounce_and_dispatch(HOTKEY_ID_MUTE, gmk._on_mute)
        self.assertEqual(calls["mute"], 1)


class TestUX005BEnhancedDragAndDrop(unittest.TestCase):
    """UX-005B: Recursive directory traversal, deterministic sorting, and safe filtering."""

    def test_01_collect_audio_files_flat_and_sorted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create subdirectories and audio files
            sub_a = os.path.join(tmp_dir, "album_b")
            sub_b = os.path.join(tmp_dir, "album_a")
            os.makedirs(sub_a)
            os.makedirs(sub_b)

            f1 = os.path.join(sub_a, "track_02.mp3")
            f2 = os.path.join(sub_a, "track_01.ogg")
            f3 = os.path.join(sub_b, "song.xm")
            f4 = os.path.join(sub_b, "notes.txt") # Unsupported
            f5 = os.path.join(tmp_dir, "root.wav")

            for f in (f1, f2, f3, f4, f5):
                with open(f, "w") as fp:
                    fp.write("dummy")

            collected = collect_audio_files([tmp_dir])
            
            # Should contain only valid audio files, deterministically ordered
            self.assertEqual(len(collected), 4)
            expected = [
                os.path.normpath(f5),
                os.path.normpath(f3),
                os.path.normpath(f2),
                os.path.normpath(f1),
            ]
            self.assertEqual(collected, expected)

    def test_02_collect_audio_files_mixed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            f1 = os.path.join(tmp_dir, "test.flac")
            f2 = os.path.join(tmp_dir, "invalid.exe")
            with open(f1, "w") as fp:
                fp.write("dummy")
            with open(f2, "w") as fp:
                fp.write("dummy")

            # Mixed file, directory, and non-existent path
            collected = collect_audio_files([f1, f2, "C:/does_not_exist/test.mp3", tmp_dir])
            # f1 individually + f1 from tmp_dir
            self.assertEqual(len(collected), 2)
            self.assertEqual(collected[0], os.path.normpath(f1))
            self.assertEqual(collected[1], os.path.normpath(f1))

    def test_03_supported_audio_extensions_coverage(self):
        self.assertTrue({".mp3", ".ogg", ".wav", ".flac", ".mod", ".xm", ".it", ".s3m"}.issubset(SUPPORTED_AUDIO_EXTENSIONS))


class TestUX005CPlaylistQuickSearch(unittest.TestCase):
    """UX-005C: Incremental search, view-only filtering, canonical mapping."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.manager = PlaylistManager()
        self.manager.add_file("C:/music/01_intro.mod", title="Cyber Intro")
        self.manager.add_file("C:/music/02_synthwave.mp3", title="Neon City")
        self.manager.add_file("C:/music/03_tracker.xm", title="Hyper Toroid")
        self.manager.add_file("C:/music/04_outro.flac", title="Cyber End")
        self.mod = PlaylistModule(self.manager)
        self.mod.show()
        self.mod.refresh()

    def test_01_search_visibility_toggle(self):
        self.assertTrue(self.mod.search_container.isHidden())
        self.mod.show_search()
        self.assertFalse(self.mod.search_container.isHidden())

        self.mod.hide_search()
        self.assertTrue(self.mod.search_container.isHidden())
        self.assertEqual(self.mod._search_query, "")
        self.assertEqual(self.mod.list_widget.count(), 4)



    def test_02_incremental_case_insensitive_filtering(self):
        self.mod.show_search()
        self.mod.search_edit.setText("cyber")
        
        # Matches: "Cyber Intro" (0) and "Cyber End" (3)
        self.assertEqual(self.mod.list_widget.count(), 2)
        item0 = self.mod.list_widget.item(0)
        item1 = self.mod.list_widget.item(1)
        self.assertEqual(item0.data(Qt.UserRole), 0)
        self.assertEqual(item1.data(Qt.UserRole), 3)
        self.assertIn("Cyber Intro", item0.text())
        self.assertIn("Cyber End", item1.text())

    def test_03_clearing_search_restores_complete_canonical_playlist(self):
        self.mod.show_search()
        self.mod.search_edit.setText("neon")
        self.assertEqual(self.mod.list_widget.count(), 1)

        self.mod.hide_search()
        self.assertEqual(self.mod.list_widget.count(), 4)
        self.assertEqual([self.mod.list_widget.item(i).data(Qt.UserRole) for i in range(4)], [0, 1, 2, 3])

    def test_04_double_click_on_filtered_item_maps_to_canonical_index(self):
        double_clicked_indices = []
        self.mod.track_double_clicked.connect(double_clicked_indices.append)

        # Filter for "Hyper" -> matches track 2 (Hyper Toroid)
        self.mod.search_edit.setText("hyper")
        self.assertEqual(self.mod.list_widget.count(), 1)
        
        matching_item = self.mod.list_widget.item(0)
        self.mod._on_item_double_clicked(matching_item)

        self.assertEqual(self.manager.current_index, 2)
        self.assertEqual(double_clicked_indices, [2])

    def test_05_delete_on_filtered_item_removes_correct_canonical_item(self):
        # Filter for "Neon" -> matches track 1
        self.mod.search_edit.setText("neon")
        self.assertEqual(self.mod.list_widget.count(), 1)
        self.mod.list_widget.item(0).setSelected(True)

        self.mod._remove_selected()

        # Manager should have 3 items left: 0 (Cyber Intro), 2 (Hyper Toroid), 3 (Cyber End)
        titles = [item.title for item in self.manager.items]
        self.assertEqual(titles, ["Cyber Intro", "Hyper Toroid", "Cyber End"])


class TestUX005DTrackChangeNotification(unittest.TestCase):
    """UX-005D: Non-intrusive track change OSD."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_01_osd_attributes_and_focus_safety(self):
        osd = TrackChangeOSD()
        self.assertTrue(osd.testAttribute(Qt.WA_ShowWithoutActivating))
        self.assertTrue(osd.testAttribute(Qt.WA_TranslucentBackground))
        self.assertEqual(osd.focusPolicy(), Qt.NoFocus)

    def test_02_show_track_updates_labels_and_restarts_timer(self):
        osd = TrackChangeOSD()
        osd.show_track("Retro Voyage", format_str="XM", artist="Future Crew")

        self.assertEqual(osd.lbl_title.text(), "Retro Voyage")
        self.assertEqual(osd.lbl_format.text(), "XM")
        self.assertEqual(osd.lbl_details.text(), "Future Crew")
        self.assertTrue(osd.lbl_details.isVisible())
        self.assertTrue(osd._hide_timer.isActive())

        # Rapid second call updates without error
        osd.show_track("Next Track", format_str="FLAC")
        self.assertEqual(osd.lbl_title.text(), "Next Track")
        self.assertEqual(osd.lbl_format.text(), "FLAC")
        self.assertFalse(osd.lbl_details.isVisible())

        osd.dismiss()
        self.assertFalse(osd._hide_timer.isActive())


class TestUX005WindowManagerIntegration(unittest.TestCase):
    """Integration test verifying WindowManager canonical bindings for UX-005."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.handoff = AnalysisHandoff()
        self.player = PlayerEngine(self.handoff)
        self.playlist = PlaylistManager()
        self.session_mgr = MagicMock()
        st = MagicMock()
        st.volume = 0.8
        st.fade_enabled = True
        st.shuffle = False
        st.repeat = False
        st.selected_visualizer_idx = 0
        st.playlist_files = []
        st.scale = "normal"
        st.vis_module.is_visible = True
        st.vis_module.width = 420
        st.vis_module.height = 240
        st.vis_module.x = 0
        st.vis_module.y = 0
        st.vis_module.is_docked = True
        st.vis_module.dock_edge = "bottom"
        st.pl_module.is_visible = True
        st.pl_module.width = 270
        st.pl_module.height = 240
        st.pl_module.x = 422
        st.pl_module.y = 0
        st.pl_module.is_docked = True
        st.pl_module.dock_edge = "right"
        st.chassis_pos.x = 0
        st.chassis_pos.y = 0
        self.session_mgr.load.return_value = st

        self.wm = WindowManager(
            player=self.player,
            handoff=self.handoff,
            playlist=self.playlist,
            session_manager=self.session_mgr
        )

    def tearDown(self):
        self.wm.render_timer.stop()
        self.wm.snap_timer.stop()
        try:
            self.wm.osd.dismiss()
            self.wm.global_media_keys.unregister()
        except Exception:
            pass

    def test_01_relative_volume_and_mute(self):
        self.wm._on_volume_changed(0.8)
        self.assertAlmostEqual(self.player.volume, 0.8)

        # Volume +5%
        self.wm._relative_volume(+0.05)
        self.assertAlmostEqual(self.player.volume, 0.85, places=2)

        # Mute toggle
        self.wm._toggle_mute()
        self.assertAlmostEqual(self.player.volume, 0.0)

        # Unmute restore
        self.wm._toggle_mute()
        self.assertAlmostEqual(self.player.volume, 0.85, places=2)

    def test_02_visualizer_cycle(self):
        initial_idx = self.wm.vis_mod.vis_idx
        self.wm._cycle_visualizer()
        self.assertEqual(self.wm.vis_mod.vis_idx, (initial_idx + 1) % len(self.wm.vis_mod.visualizers))

    def test_03_drag_and_drop_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            f1 = os.path.join(tmp_dir, "01_track.mp3")
            f2 = os.path.join(tmp_dir, "02_track.xm")
            with open(f1, "w") as fp:
                fp.write("dummy")
            with open(f2, "w") as fp:
                fp.write("dummy")

            self.wm._on_files_dropped([tmp_dir])
            self.assertEqual(len(self.playlist), 2)
            self.assertEqual(self.playlist.items[0].title, "01_track")
            self.assertEqual(self.playlist.items[1].title, "02_track")


if __name__ == "__main__":
    unittest.main()
