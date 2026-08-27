from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QStackedWidget, QApplication, QStyle, QStyleOptionSlider
)
from PySide6.QtCore import Qt, QPoint, Signal, QEvent
from PySide6.QtGui import QMouseEvent, QDragEnterEvent, QDropEvent, QCloseEvent, QPainter, QPen, QColor

from .neon import NeonState
from .marquee import MarqueeLabel
from .. import __version__
from ..branding import resolve_branding_icon


class SeekSlider(QSlider):
    """
    Click-anywhere-on-groove seek slider.

    Standard QSlider.sliderMoved only fires when the handle is dragged.
    This subclass also converts a direct groove-click into an equivalent
    sliderMoved emission so the seek pathway remains singular — one authority
    for all seek operations, whether the human drags the handle or clicks
    halfway through the damn song.
    """

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            hit = self.style().hitTestComplexControl(
                QStyle.CC_Slider, opt, event.pos(), self
            )
            if hit != QStyle.SC_SliderHandle:
                # Click landed on the groove, not the handle — direct seek.
                groove = self.style().subControlRect(
                    QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self
                )
                handle = self.style().subControlRect(
                    QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self
                )
                # Usable travel = groove width minus one full handle width
                # (half-handle margin on each end).
                half_h = handle.width() // 2
                usable_left = groove.left() + half_h
                usable_width = groove.width() - handle.width()
                if usable_width > 0:
                    offset = max(0, min(usable_width, event.pos().x() - usable_left))
                    ratio = offset / usable_width
                else:
                    ratio = 0.0
                value = int(round(
                    ratio * (self.maximum() - self.minimum()) + self.minimum()
                ))
                self.setValue(value)
                # Emit sliderMoved so the existing seek_changed connection fires.
                self.sliderMoved.emit(value)
                event.accept()
                return
        # Click was on the handle — standard drag handling.
        super().mousePressEvent(event)


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
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.mode = "normal" # 'mini' or 'normal'
        self._drag_pos = QPoint()
        self._is_dragging = False
        self.setAcceptDrops(True)
        self._current_neon: NeonState | None = None

        # BRAND-001: explicit chassis-level icon, defensively — QApplication's
        # icon already applies to any window that doesn't set its own, but
        # the primary owner window sets it explicitly too for certainty
        # regardless of Qt.FramelessWindowHint / platform quirks.
        brand_icon = resolve_branding_icon()
        if brand_icon is not None:
            self.setWindowIcon(brand_icon)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(1, 1, 1, 1)
        self.outer_layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        self.outer_layout.addWidget(self.stack)

        self._init_normal_view()
        self._init_mini_view()

        # Default start in NORMAL mode
        self.set_mode("normal", animated=False)

    def apply_neon_state(self, state: NeonState):
        """Applies dynamic reactive neon colors across borders, panels, and LCD displays."""
        self._current_neon = state

        # Expressive Spectral Track Display (Tier 2/Glow)
        t_col = state.track_glow_color.name()
        bg_col = state.track_bg_color.name(QColor.HexArgb)
        p_col = state.tier2_panel_color.name()

        # Update Normal LCD styling
        self.normal_lcd_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_col};
                border: 1px solid {t_col};
                border-radius: 3px;
                padding: 2px 6px;
            }}
        """)

        # Update Mini LCD styling
        self.mini_lcd_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_col};
                border: 1px solid {t_col};
                border-radius: 2px;
                padding: 1px 4px;
            }}
        """)

        self.update() # Trigger lightweight border repaint


    def paintEvent(self, event):
        """Paints crisp, reactive electric neon outer border (Tier 1)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background fill
        painter.setBrush(QColor(10, 11, 16, 250))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)

        # Electric Neon Border (Tier 1)
        if self._current_neon:
            pen = QPen(self._current_neon.tier1_chassis_color, 1.5)
        else:
            pen = QPen(QColor(0, 240, 255, 220), 1.5)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        painter.end()


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

        id_lbl = QLabel(f"TOROIDAMP // v{__version__} CORE", hdr)
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
        btn_min.setToolTip("Compact to MINI strip")
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
        self.normal_lcd_frame = QFrame(self.normal_widget)
        self.normal_lcd_frame.setFixedHeight(38)
        self.normal_lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 3px; padding: 2px 6px;")
        lcd_layout = QHBoxLayout(self.normal_lcd_frame)
        lcd_layout.setContentsMargins(4, 2, 4, 2)

        self.normal_title_marquee = MarqueeLabel(self.normal_lcd_frame)
        self.normal_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 12px; font-weight: bold;")
        self.normal_title_marquee.set_marquee_text("♫ No Track Loaded")
        lcd_layout.addWidget(self.normal_title_marquee, stretch=2)

        self.normal_time_display = QLabel("00:00 / 00:00", self.normal_lcd_frame)
        self.normal_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 11px;")
        lcd_layout.addWidget(self.normal_time_display, alignment=Qt.AlignRight)

        layout.addWidget(self.normal_lcd_frame)


        # Progress / Seek Bar — SeekSlider supports both handle-drag and direct groove-click.
        self.normal_seek_slider = SeekSlider(Qt.Horizontal, self.normal_widget)
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
                background-color: #12141f;
                border: 1px solid #1f273d;
                border-radius: 2px;
                color: #cbd5e1;
                font-family: monospace;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                border-color: #00f0ff;
                color: #00f0ff;
                background-color: #161c2e;
            }
            QPushButton:pressed {
                background-color: #00f0ff;
                color: #040508;
                border-color: #00f0ff;
            }
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
            QSlider::groove:horizontal { height: 3px; background: #1a1d2e; border-radius: 1px; }
            QSlider::sub-page:horizontal { background: #00f0ff; border-radius: 1px; }
            QSlider::handle:horizontal { background: #ffffff; border: 1px solid #00f0ff; width: 6px; margin: -2px 0; border-radius: 3px; }
        """)
        self.normal_vol_slider.valueChanged.connect(lambda v: self.volume_changed.emit(v / 100.0))
        c_layout.addWidget(self.normal_vol_slider)

        c_layout.addStretch()

        # Module Toggle Chips
        self.chip_vis = QPushButton("VIS", ctrl_bar)
        self.chip_vis.setCheckable(True)
        self.chip_vis.setStyleSheet("""
            QPushButton {
                background: #0d111c;
                border: 1px solid #1f2a40;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 2px;
            }
            QPushButton:hover {
                border-color: #00f0ff;
                background-color: #141f33;
            }
            QPushButton:checked {
                background: #00f0ff;
                color: #040508;
                border-color: #00f0ff;
            }
        """)
        self.chip_vis.clicked.connect(self.toggle_vis_clicked.emit)
        c_layout.addWidget(self.chip_vis)

        self.chip_pl = QPushButton("PL", ctrl_bar)
        self.chip_pl.setCheckable(True)
        self.chip_pl.setStyleSheet("""
            QPushButton {
                background: #140d17;
                border: 1px solid #3d1f2e;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 2px;
            }
            QPushButton:hover {
                border-color: #ff0077;
                background-color: #2b1220;
            }
            QPushButton:checked {
                background: #ff0077;
                color: #ffffff;
                border-color: #ff0077;
            }
        """)
        self.chip_pl.clicked.connect(self.toggle_pl_clicked.emit)
        c_layout.addWidget(self.chip_pl)


        layout.addWidget(ctrl_bar)
        self.stack.addWidget(self.normal_widget)

    def _init_mini_view(self):
        """Constructs the ultra-compact MINI ~460x36 px control strip."""
        self.mini_widget = QWidget()
        layout = QHBoxLayout(self.mini_widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        mini_btn_style = """
            QPushButton {
                background-color: #12141f;
                border: 1px solid #1f273d;
                border-radius: 2px;
                color: #cbd5e1;
                font-family: monospace;
                font-weight: bold;
                font-size: 9px;
                padding: 2px 5px;
            }
            QPushButton:hover {
                border-color: #00f0ff;
                color: #00f0ff;
                background-color: #161c2e;
            }
            QPushButton:pressed {
                background-color: #00f0ff;
                color: #040508;
                border-color: #00f0ff;
            }
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

        # Mini LCD Frame (Expressive Track Display)
        self.mini_lcd_frame = QFrame(self.mini_widget)
        self.mini_lcd_frame.setFixedHeight(24)
        self.mini_lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 2px; padding: 1px 4px;")
        mini_lcd_layout = QHBoxLayout(self.mini_lcd_frame)
        mini_lcd_layout.setContentsMargins(4, 0, 4, 0)

        self.mini_title_marquee = MarqueeLabel(self.mini_lcd_frame)
        self.mini_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 10px; font-weight: bold;")
        self.mini_title_marquee.set_marquee_text("♫ No Track Loaded")
        mini_lcd_layout.addWidget(self.mini_title_marquee, stretch=2)

        self.mini_time_display = QLabel("00:00 / 00:00", self.mini_lcd_frame)
        self.mini_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 9px;")
        # Fixed minimum width prevents layout jitter as digit count changes.
        self.mini_time_display.setMinimumWidth(90)
        self.mini_time_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mini_lcd_layout.addWidget(self.mini_time_display)

        layout.addWidget(self.mini_lcd_frame, stretch=2)

        # UX-004: the MINI speaker is a real, clickable volume control — it
        # opens a small transient popup rather than requiring a trip to
        # NORMAL. Qt.Popup gives correct outside-click dismissal and never
        # creates its own taskbar entry, with no Win32-specific code needed.
        self.mini_vol_btn = QPushButton("🔊", self.mini_widget)
        self.mini_vol_btn.setToolTip("Volume")
        self.mini_vol_btn.setFlat(True)
        self.mini_vol_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #00ffaa; font-size: 10px; padding: 0; } QPushButton:hover { color: #00f0ff; }")
        self.mini_vol_btn.clicked.connect(self._toggle_mini_volume_popup)
        layout.addWidget(self.mini_vol_btn)

        self._build_mini_volume_popup()


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

        btn_mini_close = QPushButton("✕", self.mini_widget)
        btn_mini_close.setToolTip("Exit ToroidAMP")
        btn_mini_close.setFixedSize(16, 16)
        btn_mini_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        btn_mini_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(btn_mini_close)

        self.stack.addWidget(self.mini_widget)


    # Authoritative MINI dimensions — update session geometry compatibility tests when changing.
    MINI_WIDTH = 460
    MINI_HEIGHT = 36
    NORMAL_WIDTH = 420
    NORMAL_HEIGHT = 135

    def set_mode(self, mode: str, animated: bool = True):
        self.mode = mode
        if mode == "mini":
            self.stack.setCurrentWidget(self.mini_widget)
            self.setFixedSize(self.MINI_WIDTH, self.MINI_HEIGHT)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
            self.scale_changed.emit("mini")
        else:
            self.stack.setCurrentWidget(self.normal_widget)
            self.setFixedSize(self.NORMAL_WIDTH, self.NORMAL_HEIGHT)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
            self.scale_changed.emit("normal")

    def update_telemetry(self, title: str, time_str: str, progress_ratio: float, is_playing: bool):
        self.normal_title_marquee.set_marquee_text(title)
        self.mini_title_marquee.set_marquee_text(title)
        self.normal_time_display.setText(time_str)
        # MINI shows full elapsed / total so the human always knows where they are.
        self.mini_time_display.setText(time_str)
        
        if not self.normal_seek_slider.isSliderDown():
            self.normal_seek_slider.setValue(int(progress_ratio * 1000))

        play_icon = "❚❚" if is_playing else "►"
        self.normal_btn_play.setText(play_icon)
        self.mini_btn_play.setText(play_icon)

    def set_volume(self, volume: float):
        self.normal_vol_slider.setValue(int(volume * 100))
        # There is one authoritative volume value; the MINI popup slider is
        # just another view of it, kept in sync whenever it exists.
        self.mini_pop_slider.setValue(int(volume * 100))

    # Nominal footprint of the popup's hit-area (may exceed the visible
    # slider slightly for grabbability — UX-004 follow-up Part D).
    _VOL_POPUP_SLIDER_LEN = 90
    _VOL_POPUP_MARGIN = 8

    def _build_mini_volume_popup(self):
        """
        Builds the transient MINI volume popup: a borderless, translucent
        Qt.Popup holding only a vertical slider — no opaque panel, titlebar,
        or frame. Qt.Popup closes naturally on any outside click/focus loss
        and never registers its own taskbar entry; it does not enlarge
        MINI's authoritative 460x36 footprint.
        """
        self.volume_popup = QWidget(self, Qt.Popup)
        self.volume_popup.setAttribute(Qt.WA_TranslucentBackground)
        self.volume_popup.setStyleSheet("background: transparent; border: none;")
        pop_layout = QVBoxLayout(self.volume_popup)
        pop_layout.setContentsMargins(
            self._VOL_POPUP_MARGIN, self._VOL_POPUP_MARGIN,
            self._VOL_POPUP_MARGIN, self._VOL_POPUP_MARGIN
        )

        self.mini_pop_slider = QSlider(Qt.Vertical, self.volume_popup)
        self.mini_pop_slider.setRange(0, 100)
        self.mini_pop_slider.setValue(80)
        self.mini_pop_slider.setFixedHeight(self._VOL_POPUP_SLIDER_LEN)
        self.mini_pop_slider.setStyleSheet("""
            QSlider::groove:vertical { width: 3px; background: #00f0ff; border-radius: 1px; }
            QSlider::handle:vertical { background: #ffffff; border: 1px solid #00f0ff; height: 8px; margin: 0 -5px; border-radius: 4px; }
            QSlider::handle:vertical:hover { background: #00f0ff; }
        """)
        self.mini_pop_slider.valueChanged.connect(self._on_mini_volume_slider_changed)
        pop_layout.addWidget(self.mini_pop_slider, alignment=Qt.AlignHCenter)

        self.volume_popup.adjustSize()

    def _on_mini_volume_slider_changed(self, value: int):
        # Keep the NORMAL slider in sync immediately — same single
        # authoritative value, two views/controllers.
        self.normal_vol_slider.setValue(value)
        self.volume_changed.emit(value / 100.0)

    def _toggle_mini_volume_popup(self):
        if self.volume_popup.isVisible():
            self.volume_popup.hide()
            return
        # Always resync from the current authoritative value before showing —
        # guards against any drift regardless of how the value last changed.
        self.mini_pop_slider.blockSignals(True)
        self.mini_pop_slider.setValue(self.normal_vol_slider.value())
        self.mini_pop_slider.blockSignals(False)

        self.volume_popup.move(self._compute_volume_popup_pos())
        self.volume_popup.show()

    def _compute_volume_popup_pos(self) -> QPoint:
        """
        Anchors the popup horizontally centered over the speaker icon, with
        its bottom edge just above MINI (the intended primary placement).
        Falls back below the speaker if there isn't room above, and clamps
        to the current screen so it can never land off-screen or detached.
        """
        popup_w = self.volume_popup.width()
        popup_h = self.volume_popup.height()
        gap = 4

        btn_top_left = self.mini_vol_btn.mapToGlobal(QPoint(0, 0))
        btn_center_x = btn_top_left.x() + self.mini_vol_btn.width() // 2

        x = btn_center_x - popup_w // 2
        y = btn_top_left.y() - popup_h - gap  # primary: above the speaker

        screen = self.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            if y < avail.top():
                # Not enough room above — graceful fallback below.
                y = btn_top_left.y() + self.mini_vol_btn.height() + gap
            x = max(avail.left(), min(x, avail.right() - popup_w))
            y = max(avail.top(), min(y, avail.bottom() - popup_h))

        return QPoint(x, y)

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

    def changeEvent(self, event):
        """
        Intercepts native OS minimize (Win+M, taskbar button click, keyboard shortcut).
        Redirects to MINI mode instead of hiding the window — the chassis stays visible.

        Limitation: Win+D (show desktop) is an OS-level operation that bypasses
        Qt's event system; the chassis may be temporarily obscured but is not destroyed.
        """
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                # Cancel the minimize — restore the window state immediately.
                self.setWindowState(Qt.WindowNoState)
                # Compact to MINI if not already there.
                if self.mode != "mini":
                    self.set_mode("mini")
                event.accept()
                return
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent):
        """
        Intercepts all native OS close requests (Taskbar thumbnail X, Alt+F4, WM_CLOSE)
        and routes them strictly to the authoritative shutdown lifecycle.
        """
        event.ignore()
        self.close_requested.emit()


