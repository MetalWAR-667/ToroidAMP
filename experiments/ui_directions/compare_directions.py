"""
ToroidAMP - UI Directions Executable Mockups
Demonstrates Direction A (Retro Instrument), Direction B (Reactive Minimal), and Direction C (Demoscene Console)
"""

import sys
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QProgressBar, QListWidget, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor


class MockupRetroInstrument(QWidget):
    """Direction A: Retro Instrument Mockup"""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #1a1a24; color: #e0e0e0; font-family: 'Segoe UI', sans-serif;")
        layout = QVBoxLayout(self)

        # Header Info Rack
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #12121a; border: 2px solid #333344; border-radius: 4px; padding: 6px;")
        info_layout = QHBoxLayout(info_frame)

        meta_layout = QVBoxLayout()
        title_lbl = QLabel("♫ Burn The World Waltz")
        title_lbl.setStyleSheet("color: #00ffcc; font-weight: bold; font-size: 14px;")
        artist_lbl = QLabel("ARTIST: Mihwe / Master   [MP3 44.1kHz]")
        artist_lbl.setStyleSheet("color: #8888aa; font-size: 11px;")
        time_lbl = QLabel("TIME: 02:15 / 03:20")
        time_lbl.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 12px;")
        meta_layout.addWidget(title_lbl)
        meta_layout.addWidget(artist_lbl)
        meta_layout.addWidget(time_lbl)
        info_layout.addLayout(meta_layout, stretch=2)

        # Mini VU Bars
        vu_layout = QVBoxLayout()
        self.vu_l = QProgressBar()
        self.vu_l.setRange(0, 100)
        self.vu_l.setValue(65)
        self.vu_l.setTextVisible(False)
        self.vu_l.setStyleSheet("QProgressBar::chunk { background-color: #00ffaa; }")
        self.vu_r = QProgressBar()
        self.vu_r.setRange(0, 100)
        self.vu_r.setValue(72)
        self.vu_r.setTextVisible(False)
        self.vu_r.setStyleSheet("QProgressBar::chunk { background-color: #00ffaa; }")
        vu_layout.addWidget(QLabel("L:"))
        vu_layout.addWidget(self.vu_l)
        vu_layout.addWidget(QLabel("R:"))
        vu_layout.addWidget(self.vu_r)
        info_layout.addLayout(vu_layout, stretch=1)

        layout.addWidget(info_frame)

        # Visualizer Bezel
        vis_bezel = QLabel("[ 3D TORUS VIEWPORT - INSTRUMENT BEZEL ]")
        vis_bezel.setAlignment(Qt.AlignCenter)
        vis_bezel.setStyleSheet("background-color: #000008; border: 2px inset #444455; color: #00ffff; height: 180px; font-weight: bold;")
        layout.addWidget(vis_bezel)

        # Tactile Transport Controls
        btn_layout = QHBoxLayout()
        for btn_text in ["◄◄ PREV", "► PLAY", "❚❚ PAUSE", "■ STOP", "►► NEXT"]:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a3a;
                    border: 2px outset #555566;
                    border-radius: 3px;
                    color: #ffffff;
                    font-weight: bold;
                    padding: 6px 12px;
                }
                QPushButton:pressed {
                    background-color: #1a1a28;
                    border: 2px inset #444455;
                }
            """)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)


class MockupReactiveMinimal(QWidget):
    """Direction B: Reactive Minimal Mockup"""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0e0f14; color: #f0f0f5; font-family: 'Segoe UI', sans-serif;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Track Title Minimal
        title_lbl = QLabel("Burn The World Waltz — Mihwe")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 300; color: #ffffff; letter-spacing: 1px;")
        layout.addWidget(title_lbl)

        # Hero Visualizer
        vis_hero = QLabel("[ BORDERLESS HERO VISUALIZER CANVAS ]")
        vis_hero.setAlignment(Qt.AlignCenter)
        vis_hero.setStyleSheet("background-color: #06070a; border-radius: 8px; color: #a0a5c0; height: 200px;")
        layout.addWidget(vis_hero)

        # Minimal Progress Slider
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(45)
        progress.setTextVisible(False)
        progress.setFixedHeight(4)
        progress.setStyleSheet("QProgressBar { background: #20222e; border: none; border-radius: 2px; } QProgressBar::chunk { background: #6366f1; }")
        layout.addWidget(progress)

        # Clean Floating Controls
        ctrl_layout = QHBoxLayout()
        time_lbl = QLabel("01:30 / 03:20")
        time_lbl.setStyleSheet("color: #71717a; font-size: 11px;")
        ctrl_layout.addWidget(time_lbl)

        ctrl_layout.addStretch()
        for icon in ["⏮", "▶", "⏸", "⏭"]:
            b = QPushButton(icon)
            b.setFixedSize(36, 36)
            b.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; color: #ffffff; } QPushButton:hover { color: #6366f1; }")
            ctrl_layout.addWidget(b)
        ctrl_layout.addStretch()

        vol_lbl = QLabel("🔊 80%")
        vol_lbl.setStyleSheet("color: #71717a; font-size: 11px;")
        ctrl_layout.addWidget(vol_lbl)

        layout.addLayout(ctrl_layout)


class MockupDemosceneConsole(QWidget):
    """Direction C: Demoscene Console Mockup"""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #050811; color: #00ffcc; font-family: 'Consolas', monospace;")
        layout = QVBoxLayout(self)

        # Cyber Header
        hdr = QLabel("// TOROIDAMP_CONSOLE :: [SYS_ONLINE]  FREQ=44.1kHz  CH=2")
        hdr.setStyleSheet("color: #00ffcc; font-weight: bold; font-size: 12px; border-bottom: 1px dashed #008877; padding-bottom: 4px;")
        layout.addWidget(hdr)

        # Multi-panel telemetry
        panel_layout = QHBoxLayout()
        
        telemetry = QLabel("> TRK: dalezy-lotus.xm\n> TYP: AMIGA_MOD [4CH]\n> BAS: [████████░░] 0.82\n> MID: [█████░░░░░] 0.45\n> TRB: [█████████░] 0.91\n> FCK: [1.45] *ACTIVE*\n> BEAT: [ *KICK* ]")
        telemetry.setStyleSheet("background-color: #020408; border: 1px solid #00ffcc; padding: 8px; color: #00ffaa; font-size: 11px;")
        panel_layout.addWidget(telemetry, stretch=1)

        vis_radar = QLabel("[ RADAR VIEWPORT :: 3D TORUS ]\n\nFCKVAR_DISTORTION = ON")
        vis_radar.setAlignment(Qt.AlignCenter)
        vis_radar.setStyleSheet("background-color: #000000; border: 1px solid #ff0077; color: #ff0077; font-weight: bold;")
        panel_layout.addWidget(vis_radar, stretch=2)

        layout.addLayout(panel_layout)

        # Vector Chip Buttons
        chip_layout = QHBoxLayout()
        for chip in ["[◄◄ REV]", "[► EXEC]", "[❚❚ HOLD]", "[■ HALT]", "[►► FWD]", "[⛶ FULL]"]:
            cb = QPushButton(chip)
            cb.setStyleSheet("""
                QPushButton {
                    background-color: #08111e;
                    border: 1px solid #00aaff;
                    color: #00ddff;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #00aaff;
                    color: #000000;
                }
            """)
            chip_layout.addWidget(cb)
        layout.addLayout(chip_layout)


class UIComparisonWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ToroidAMP — Production Cut 1A: UI Direction Explorations")
        self.resize(750, 480)

        tabs = QTabWidget(self)
        tabs.setStyleSheet("QTabBar::tab { font-weight: bold; padding: 8px 16px; }")
        tabs.addTab(MockupRetroInstrument(), "Direction A: Retro Instrument")
        tabs.addTab(MockupReactiveMinimal(), "Direction B: Reactive Minimal")
        tabs.addTab(MockupDemosceneConsole(), "Direction C: Demoscene Console")

        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = UIComparisonWindow()
    win.show()
    sys.exit(app.exec())
