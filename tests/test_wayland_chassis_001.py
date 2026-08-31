"""
ToroidAMP - LINUX-CHASSIS-001 Test Suite
Validation of Wayland Unified Chassis Auxiliary Module Resize, Layout Stability,
and NORMAL <-> MINI Transitions.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QSize, QPoint, QRect, QEvent
from PySide6.QtGui import QGuiApplication, QMouseEvent

_app = QApplication.instance() or QApplication(sys.argv)

from toroidamp.ui.chassis import UnifiedChassis
from toroidamp.ui.modules.playlist_module import PlaylistModule
from toroidamp.ui.modules.visualizer_module import VisualizerModule
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.session import SessionManager, SessionState, ModulePosition


class TestWaylandChassisEmbeddedResize(unittest.TestCase):
    """Tests interactive sizing and layout behavior of embedded modules in UnifiedChassis."""

    def setUp(self):
        self.chassis = UnifiedChassis()
        self.pl_mgr = PlaylistManager()
        self.pl_mod = PlaylistModule(self.pl_mgr, parent=self.chassis, embedded=True)
        self.vis_mod = VisualizerModule(parent=self.chassis, embedded=True)
        self.chassis.show()

    def tearDown(self):
        self.chassis.close()

    def test_01_embedded_modules_have_fixed_default_sizes_initially(self):
        self.assertEqual(self.pl_mod.size(), self.pl_mod.DEFAULT_SIZE)
        self.assertEqual(self.vis_mod.size(), self.vis_mod.DEFAULT_SIZE)

    def test_02_playlist_right_edge_drag_resizes_width(self):
        self.chassis.embed_module("right", self.pl_mod)
        self.pl_mod.show()

        initial_chassis_w = self.chassis.width()
        initial_pl_w = self.pl_mod.width()

        # Simulate mouse press on right edge of PlaylistModule
        press_pos = QPoint(self.pl_mod.width() - 2, 50)
        press_ev = QMouseEvent(QEvent.Type.MouseButtonPress, press_pos, self.pl_mod.mapToGlobal(press_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.pl_mod.mousePressEvent(press_ev)

        self.assertTrue(self.pl_mod._resizing)
        self.assertIn("right", self.pl_mod._resize_edges)

        # Drag +80px to the right
        drag_pos = self.pl_mod.mapToGlobal(press_pos + QPoint(80, 0))
        move_ev = QMouseEvent(QEvent.Type.MouseMove, press_pos + QPoint(80, 0), drag_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.pl_mod.mouseMoveEvent(move_ev)

        # Release
        rel_ev = QMouseEvent(QEvent.Type.MouseButtonRelease, press_pos + QPoint(80, 0), drag_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.pl_mod.mouseReleaseEvent(rel_ev)

        self.assertFalse(self.pl_mod._resizing)
        self.assertEqual(self.pl_mod.width(), initial_pl_w + 80)
        self.assertEqual(self.pl_mod.user_size.width(), initial_pl_w + 80)
        self.assertEqual(self.chassis.width(), initial_chassis_w + 80)

    def test_03_visualizer_bottom_edge_drag_resizes_height(self):
        self.chassis.embed_module("bottom", self.vis_mod)
        self.vis_mod.show()

        initial_chassis_h = self.chassis.height()
        initial_vis_h = self.vis_mod.height()

        # Simulate mouse press on bottom edge of VisualizerModule
        press_pos = QPoint(100, self.vis_mod.height() - 2)
        press_ev = QMouseEvent(QEvent.Type.MouseButtonPress, press_pos, self.vis_mod.mapToGlobal(press_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.vis_mod.mousePressEvent(press_ev)

        self.assertTrue(self.vis_mod._resizing)
        self.assertIn("bottom", self.vis_mod._resize_edges)

        # Drag +60px down
        drag_pos = self.vis_mod.mapToGlobal(press_pos + QPoint(0, 60))
        move_ev = QMouseEvent(QEvent.Type.MouseMove, press_pos + QPoint(0, 60), drag_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.vis_mod.mouseMoveEvent(move_ev)

        rel_ev = QMouseEvent(QEvent.Type.MouseButtonRelease, press_pos + QPoint(0, 60), drag_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.vis_mod.mouseReleaseEvent(rel_ev)

        self.assertFalse(self.vis_mod._resizing)
        self.assertEqual(self.vis_mod.height(), initial_vis_h + 60)
        self.assertEqual(self.vis_mod.user_size.height(), initial_vis_h + 60)
        self.assertEqual(self.chassis.height(), initial_chassis_h + 60)

    def test_04_resize_respects_minimum_size_constraints(self):
        self.chassis.embed_module("right", self.pl_mod)
        self.pl_mod.show()

        # Attempt to drag left by -500px (far below MIN_SIZE)
        press_pos = QPoint(self.pl_mod.width() - 2, 50)
        press_ev = QMouseEvent(QEvent.Type.MouseButtonPress, press_pos, self.pl_mod.mapToGlobal(press_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.pl_mod.mousePressEvent(press_ev)

        drag_pos = self.pl_mod.mapToGlobal(press_pos + QPoint(-500, 0))
        move_ev = QMouseEvent(QEvent.Type.MouseMove, press_pos + QPoint(-500, 0), drag_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.pl_mod.mouseMoveEvent(move_ev)

        self.assertEqual(self.pl_mod.width(), self.pl_mod.MIN_SIZE.width())

    def test_05_reset_size_button_restores_default_dimensions(self):
        self.chassis.embed_module("right", self.pl_mod)
        self.pl_mod.show()

        self.pl_mod.set_user_size(360, 300)
        self.assertEqual(self.pl_mod.size(), QSize(360, 300))

        # Click reset button
        self.pl_mod.btn_reset.click()
        self.assertEqual(self.pl_mod.size(), self.pl_mod.DEFAULT_SIZE)
        self.assertEqual(self.pl_mod.user_size, self.pl_mod.DEFAULT_SIZE)


class TestNormalMiniTransitions(unittest.TestCase):
    """Tests NORMAL <-> MINI mode transitions with embedded modules."""

    def test_06_ten_normal_mini_cycles_preserve_geometry_without_drift(self):
        chassis = UnifiedChassis()
        pl_mgr = PlaylistManager()
        pl = PlaylistModule(pl_mgr, parent=chassis, embedded=True)
        vis = VisualizerModule(parent=chassis, embedded=True)
        chassis.show()

        chassis.embed_module("right", pl)
        pl.show()
        chassis.embed_module("bottom", vis)
        vis.show()

        # Set custom sizes
        pl.set_user_size(320, 240)
        vis.set_user_size(420, 220)

        initial_normal_size = chassis.size()

        for _ in range(10):
            # To MINI
            chassis.embed_module("right", None)
            pl.hide()
            chassis.embed_module("bottom", None)
            vis.hide()
            chassis.set_mode("mini")
            self.assertEqual(chassis.size(), QSize(chassis.MINI_WIDTH, chassis.MINI_HEIGHT))

            # Back to NORMAL
            chassis.set_mode("normal")
            chassis.embed_module("right", pl)
            pl.show()
            chassis.embed_module("bottom", vis)
            vis.show()
            self.assertEqual(chassis.size(), initial_normal_size)
            self.assertEqual(pl.size(), QSize(320, 240))
            self.assertEqual(vis.size(), QSize(420, 220))

        chassis.close()


class TestFloatingModeIsolation(unittest.TestCase):
    """Tests that non-embedded (Windows / X11 floating) mode remains completely unaffected."""

    def test_07_floating_module_uses_resize_and_geometry(self):
        pl_mgr = PlaylistManager()
        floating_pl = PlaylistModule(pl_mgr, parent=None, embedded=False)
        self.assertFalse(floating_pl.embedded)
        self.assertTrue(bool(floating_pl.windowFlags() & Qt.Window))

        floating_pl.set_user_size(300, 250)
        self.assertEqual(floating_pl.user_size, QSize(300, 250))
        self.assertEqual(floating_pl.size(), QSize(300, 250))
        floating_pl.close()


if __name__ == "__main__":
    unittest.main()
