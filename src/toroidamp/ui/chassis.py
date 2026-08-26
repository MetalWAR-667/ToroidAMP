"""
ToroidAMP - Production Unified Chassis Window
Operates in:
1. MINI MODE (~380 x 36 px always-on-top control strip with screen edge snapping)
2. NORMAL MODE (420 x 135 px modular core instrument)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QStackedWidget, QApplication
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QDragEnterEvent, QDropEvent


class UnifiedChassis(QWidget):
    """
    Primary Unified Player Window Chassis.
    """
    scale_changed = Signal(str) # 'mini', 'normal'
    retina_melt_requested = Signal()
    minimize_requested = Signal()
    close_requested = Signal()
    play_toggled = Signal()


    prev_clicked = Signal()
    next_clicked = Signal()
    stop_clicked = Signal()
    seek_changed = Signal(int)
    volume_changed = Signal(float)
    toggle_vis_clicked = Signal()
    toggle_pl_clicked = Signal()
    files_dropped = Signal(list)

    EDGE_SNAP_THRESHOLD = 25 # pixels

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.mode = "normal" # 'mini' or 'normal'
        self._drag_pos = QPoint()
        self._is_dragging = False
        self.setAcceptDrops(True)

        self.setStyleSheet("""
            UnifiedChassis {
                background-color: #0a0b10;
                border: 2px solid #00f0ff;
                border-radius: 4px;
            }
        """)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        self.outer_layout.addWidget(self.stack)

        self._init_normal_view()
        self._init_mini_view()

        # Default start in NORMAL mode
        self.set_mode("normal", animated=False)

    def _init_normal_view(self):
        """Constructs the NORMAL 420x135 px modular core view."""
        self.normal_widget = QWidget()
        layout = QVBoxLayout(self.normal_widget)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        # Header: Identity & Window Controls
        hdr = QWidget(self.normal_widget)
        hdr.setFixedHeight(18)
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)

        id_lbl = QLabel("TOROIDAMP // v0.1 CORE", hdr)
        id_lbl.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold;")
        h_layout.addWidget(id_lbl)

        h_layout.addStretch()

        btn_to_mini = QPushButton("▼ MINI", hdr)
        btn_to_mini.setFixedHeight(16)
        btn_to_mini.setStyleSheet("""
            QPushButton {
                background: #141724;
                border: 1px solid #28304a;
                color: #ffaa00;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 0 4px;
                border-radius: 2px;
            }
            QPushButton:hover { border-color: #ffaa00; }
        """)
        btn_to_mini.clicked.connect(lambda: self.set_mode("mini"))
        h_layout.addWidget(btn_to_mini)

        btn_fs = QPushButton("⛶ MELT", hdr)
        btn_fs.setFixedHeight(16)
        btn_fs.setStyleSheet("""
            QPushButton {
                background: #141724;
                border: 1px solid #28304a;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 0 4px;
                border-radius: 2px;
            }
            QPushButton:hover { border-color: #ff0077; }
        """)
        btn_fs.clicked.connect(self.retina_melt_requested.emit)
        h_layout.addWidget(btn_fs)

        btn_min = QPushButton("─", hdr)
        btn_min.setToolTip("Minimize to Tray (Keep Playing)")
        btn_min.setFixedSize(16, 16)
        btn_min.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #00f0ff; }")
        btn_min.clicked.connect(self.minimize_requested.emit)
        h_layout.addWidget(btn_min)

        btn_close = QPushButton("✕", hdr)
        btn_close.setToolTip("Exit ToroidAMP")
        btn_close.setFixedSize(16, 16)
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        btn_close.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(btn_close)



        layout.addWidget(hdr)

        # LCD Display Rack
        lcd_frame = QFrame(self.normal_widget)
        lcd_frame.setFixedHeight(38)
        lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 3px; padding: 2px 6px;")
        lcd_layout = QHBoxLayout(lcd_frame)
        lcd_layout.setContentsMargins(4, 2, 4, 2)

        self.normal_title_marquee = QLabel("♫ No Track Loaded", lcd_frame)
        self.normal_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 12px; font-weight: bold;")
        lcd_layout.addWidget(self.normal_title_marquee, stretch=2)

        self.normal_time_display = QLabel("00:00 / 00:00", lcd_frame)
        self.normal_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 11px;")
        lcd_layout.addWidget(self.normal_time_display, alignment=Qt.AlignRight)

        layout.addWidget(lcd_frame)

        # Progress / Seek Bar
        self.normal_seek_slider = QSlider(Qt.Horizontal, self.normal_widget)
        self.normal_seek_slider.setRange(0, 1000)
        self.normal_seek_slider.setValue(0)
        self.normal_seek_slider.setFixedHeight(12)
        self.normal_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 3px; background: #1a1d2e; border-radius: 1px; }
            QSlider::sub-page:horizontal { background: #00f0ff; border-radius: 1px; }
            QSlider::handle:horizontal { background: #ffffff; border: 1px solid #00f0ff; width: 8px; margin: -3px 0; border-radius: 4px; }
        """)
        self.normal_seek_slider.sliderMoved.connect(self.seek_changed.emit)
        layout.addWidget(self.normal_seek_slider)

        # Transport & Module Bar
        ctrl_bar = QWidget(self.normal_widget)
        c_layout = QHBoxLayout(ctrl_bar)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)

        btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #28304a;
                border-radius: 2px;
                color: #e2e8f0;
                font-family: monospace;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
            }
            QPushButton:hover { border-color: #00f0ff; color: #00f0ff; }
            QPushButton:pressed { background-color: #00f0ff; color: #000000; }
        """
        btn_prev = QPushButton("◄◄", ctrl_bar)
        btn_prev.setStyleSheet(btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        c_layout.addWidget(btn_prev)

        self.normal_btn_play = QPushButton("►", ctrl_bar)
        self.normal_btn_play.setStyleSheet(btn_style)
        self.normal_btn_play.clicked.connect(self.play_toggled.emit)
        c_layout.addWidget(self.normal_btn_play)

        btn_stop = QPushButton("■", ctrl_bar)
        btn_stop.setStyleSheet(btn_style)
        btn_stop.clicked.connect(self.stop_clicked.emit)
        c_layout.addWidget(btn_stop)

        btn_next = QPushButton("►►", ctrl_bar)
        btn_next.setStyleSheet(btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        c_layout.addWidget(btn_next)

        vol_lbl = QLabel("VOL", ctrl_bar)
        vol_lbl.setStyleSheet("color: #64748b; font-family: monospace; font-size: 9px; font-weight: bold;")
        c_layout.addWidget(vol_lbl)

        self.normal_vol_slider = QSlider(Qt.Horizontal, ctrl_bar)
        self.normal_vol_slider.setRange(0, 100)
        self.normal_vol_slider.setValue(80)
        self.normal_vol_slider.setFixedWidth(50)
        self.normal_vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 3px; background: #1a1d2e; }
            QSlider::sub-page:horizontal { background: #00ffaa; }
            QSlider::handle:horizontal { background: #ffffff; width: 6px; margin: -2px 0; }
        """)
        self.normal_vol_slider.valueChanged.connect(lambda v: self.volume_changed.emit(v / 100.0))
        c_layout.addWidget(self.normal_vol_slider)

        c_layout.addStretch()

        # Module Toggle Chips
        self.chip_vis = QPushButton("VIS", ctrl_bar)
        self.chip_vis.setCheckable(True)
        self.chip_vis.setStyleSheet("""
            QPushButton { background: #0f1320; border: 1px solid #00f0ff; color: #00f0ff; font-family: monospace; font-size: 9px; font-weight: bold; padding: 3px 6px; border-radius: 2px; }
            QPushButton:checked { background: #00f0ff; color: #000000; }
        """)
        self.chip_vis.clicked.connect(self.toggle_vis_clicked.emit)
        c_layout.addWidget(self.chip_vis)

        self.chip_pl = QPushButton("PL", ctrl_bar)
        self.chip_pl.setCheckable(True)
        self.chip_pl.setStyleSheet("""
            QPushButton { background: #0f1320; border: 1px solid #ff0077; color: #ff0077; font-family: monospace; font-size: 9px; font-weight: bold; padding: 3px 6px; border-radius: 2px; }
            QPushButton:checked { background: #ff0077; color: #000000; }
        """)
        self.chip_pl.clicked.connect(self.toggle_pl_clicked.emit)
        c_layout.addWidget(self.chip_pl)

        layout.addWidget(ctrl_bar)
        self.stack.addWidget(self.normal_widget)

    def _init_mini_view(self):
        """Constructs the ultra-compact MINI ~380x36 px control strip."""
        self.mini_widget = QWidget()
        layout = QHBoxLayout(self.mini_widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        mini_btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #28304a;
                border-radius: 2px;
                color: #e2e8f0;
                font-family: monospace;
                font-weight: bold;
                font-size: 9px;
                padding: 2px 5px;
            }
            QPushButton:hover { border-color: #00f0ff; color: #00f0ff; }
        """
        btn_prev = QPushButton("◄◄", self.mini_widget)
        btn_prev.setStyleSheet(mini_btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        layout.addWidget(btn_prev)

        self.mini_btn_play = QPushButton("►", self.mini_widget)
        self.mini_btn_play.setStyleSheet(mini_btn_style)
        self.mini_btn_play.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self.mini_btn_play)

        btn_next = QPushButton("►►", self.mini_widget)
        btn_next.setStyleSheet(mini_btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        layout.addWidget(btn_next)

        self.mini_title_marquee = QLabel("♫ No Track Loaded", self.mini_widget)
        self.mini_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.mini_title_marquee, stretch=2)

        self.mini_time_display = QLabel("00:00", self.mini_widget)
        self.mini_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 9px;")
        layout.addWidget(self.mini_time_display)

        vol_ico = QLabel("🔊", self.mini_widget)
        vol_ico.setStyleSheet("color: #00ffaa; font-size: 10px;")
        layout.addWidget(vol_ico)

        btn_to_normal = QPushButton("▲ NORMAL", self.mini_widget)
        btn_to_normal.setFixedHeight(18)
        btn_to_normal.setStyleSheet("""
            QPushButton {
                background: #141724;
                border: 1px solid #00f0ff;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 0 4px;
                border-radius: 2px;
            }
            QPushButton:hover { background: #00f0ff; color: #000000; }
        """)
        btn_to_normal.clicked.connect(lambda: self.set_mode("normal"))
        layout.addWidget(btn_to_normal)

        btn_fs = QPushButton("⛶", self.mini_widget)
        btn_fs.setToolTip("RETINA MELT Fullscreen")
        btn_fs.setFixedSize(18, 18)
        btn_fs.setStyleSheet("""
            QPushButton {
                background: #141724;
                border: 1px solid #ff0077;
                color: #ff0077;
                font-family: monospace;
                font-size: 10px;
                font-weight: bold;
                border-radius: 2px;
            }
            QPushButton:hover { background: #ff0077; color: #ffffff; }
        """)
        btn_fs.clicked.connect(self.retina_melt_requested.emit)
        layout.addWidget(btn_fs)

        btn_mini_hide = QPushButton("─", self.mini_widget)
        btn_mini_hide.setToolTip("Minimize to Tray (Keep Playing)")
        btn_mini_hide.setFixedSize(16, 16)
        btn_mini_hide.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #00f0ff; }")
        btn_mini_hide.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(btn_mini_hide)

        btn_mini_close = QPushButton("✕", self.mini_widget)
        btn_mini_close.setToolTip("Exit ToroidAMP")
        btn_mini_close.setFixedSize(16, 16)
        btn_mini_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        btn_mini_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(btn_mini_close)

        self.stack.addWidget(self.mini_widget)


    def set_mode(self, mode: str, animated: bool = True):
        self.mode = mode
        if mode == "mini":
            self.stack.setCurrentWidget(self.mini_widget)
            self.setFixedSize(380, 36)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
            self.scale_changed.emit("mini")
        else:
            self.stack.setCurrentWidget(self.normal_widget)
            self.setFixedSize(420, 135)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
            self.scale_changed.emit("normal")

    def update_telemetry(self, title: str, time_str: str, progress_ratio: float, is_playing: bool):
        self.normal_title_marquee.setText(title)
        self.mini_title_marquee.setText(title)
        self.normal_time_display.setText(time_str)
        self.mini_time_display.setText(time_str.split(" / ")[0] if " / " in time_str else time_str)
        
        if not self.normal_seek_slider.isSliderDown():
            self.normal_seek_slider.setValue(int(progress_ratio * 1000))

        play_icon = "❚❚" if is_playing else "►"
        self.normal_btn_play.setText(play_icon)
        self.mini_btn_play.setText(play_icon)

    def set_volume(self, volume: float):
        self.normal_vol_slider.setValue(int(volume * 100))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            
            if self.mode == "mini":
                screen_geom = self.screen().availableGeometry()
                # Snap to Top
                if abs(new_pos.y() - screen_geom.top()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setY(screen_geom.top())
                # Snap to Bottom
                elif abs((new_pos.y() + self.height()) - screen_geom.bottom()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setY(screen_geom.bottom() - self.height())
                # Snap to Left
                if abs(new_pos.x() - screen_geom.left()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setX(screen_geom.left())
                # Snap to Right
                elif abs((new_pos.x() + self.width()) - screen_geom.right()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setX(screen_geom.right() - self.width())

            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if files:
            self.files_dropped.emit(files)
        event.acceptProposedAction()
