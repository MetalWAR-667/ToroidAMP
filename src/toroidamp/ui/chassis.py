import time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QSlider, QFrame, QStackedWidget, QApplication, QStyle, QStyleOptionSlider
)
from PySide6.QtCore import Qt, QPoint, Signal, QEvent
from PySide6.QtGui import QMouseEvent, QDragEnterEvent, QDropEvent, QCloseEvent, QPainter, QPen, QColor, QGuiApplication

from .neon import NeonState
from .marquee import MarqueeLabel
from .theme import ThemeManager, ThemeDefinition, disconnect_theme_listener
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
    theme_toggle_requested = Signal()

    prev_clicked = Signal()
    next_clicked = Signal()
    stop_clicked = Signal()
    seek_changed = Signal(int)
    volume_changed = Signal(float)
    toggle_fade_clicked = Signal(bool)
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
        self._theme_manager = ThemeManager.get_instance()
        self._current_theme: ThemeDefinition = self._theme_manager.current_theme

        # BRAND-001: explicit chassis-level icon, defensively — QApplication's
        # icon already applies to any window that doesn't set its own, but
        # the primary owner window sets it explicitly too for certainty
        # regardless of Qt.FramelessWindowHint / platform quirks.
        brand_icon = resolve_branding_icon()
        if brand_icon is not None:
            self.setWindowIcon(brand_icon)

        # RELEASE-BLOCKERS-001: a QGridLayout instead of the previous plain
        # QVBoxLayout -- the NORMAL/MINI stack always occupies (0, 0); the
        # Wayland unified-chassis hosting path (embed_module() below) can
        # place Playlist at (0, 1) and Visualizer at (1, 0), composing them
        # into this SAME single top-level surface. On Windows/X11 nothing
        # is ever added to those cells (Playlist/Visualizer stay
        # independent top-level windows there, as before), so this is a
        # structural no-op on those platforms.
        self.outer_layout = QGridLayout(self)
        self.outer_layout.setContentsMargins(1, 1, 1, 1)
        self.outer_layout.setSpacing(2)

        self.stack = QStackedWidget(self)
        self.outer_layout.addWidget(self.stack, 0, 0, Qt.AlignTop | Qt.AlignLeft)

        # region -> currently-embedded module widget (Wayland hosting only).
        self._embedded_modules: dict[str, QWidget] = {}

        self._init_normal_view()
        self._init_mini_view()

        # Connect theme changes. ThemeManager is a process-wide singleton
        # (ThemeManager.get_instance()), so this connection is the only
        # thing keeping it aware of this window; deleteLater() below
        # already disconnects it for direct deletion, but Qt's own
        # parent-child cascade (e.g. this chassis being destroyed as a
        # child of some other owner) bypasses that Python-level override
        # entirely. Also disconnecting via the QObject-level `destroyed`
        # signal -- guaranteed to fire for every destruction path -- keeps
        # the singleton from ever holding a connection to an already-gone
        # C++ object. Captured as locals (not `self.foo`) so the slot
        # never touches `self` while its C++ side is mid-destruction.
        theme_manager = self._theme_manager
        apply_theme_slot = self.apply_theme
        self.destroyed.connect(
            lambda: disconnect_theme_listener(theme_manager.theme_changed, apply_theme_slot)
        )
        self._theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme(self._current_theme)

        # Default start in NORMAL mode
        self.set_mode("normal", animated=False)

    def apply_theme(self, theme: ThemeDefinition):
        """Applies complete ThemeDefinition across NORMAL and MINI chassis views."""
        self._current_theme = theme
        pal = theme.palette
        typo = theme.typography

        # 1. Update Normal Header Identity & Controls
        disp_font = f"'{typo.display_family}', monospace"
        mono_font = f"'{typo.monospace_family}', monospace"

        # Wordmark vs Textual Identity
        wordmark_pm = theme.assets.get_pixmap("wordmark") if theme.is_image_backed else None
        if wordmark_pm and not wordmark_pm.isNull():
            # Oversized pixel wordmark; preserve aspect ratio with crisp bitmap scaling.
            scaled_wm = wordmark_pm.scaledToHeight(42, Qt.FastTransformation)
            self.normal_wordmark_lbl.setPixmap(scaled_wm)
            self.normal_wordmark_lbl.show()
            self.normal_id_lbl.hide()
            self.normal_version_lbl.show()
        else:
            self.normal_wordmark_lbl.hide()
            self.normal_version_lbl.hide()
            self.normal_id_lbl.show()

        self.normal_btn_thm.setText("⚡ THM" if theme.id == "default" else "⚡ CYBER")
        self.normal_btn_min.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {pal.text_on_chassis_muted}; font-size: 11px; }} QPushButton:hover {{ color: {pal.primary}; }}")
        self.normal_btn_close.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {pal.text_on_chassis_muted}; font-size: 11px; }} QPushButton:hover {{ color: {pal.danger}; }}")

        # 2. Base Programmatic Styling (Fallback and Non-QSS Elements)
        # In Cyber Yellow, track title / marquee uses the canonical red accent (pal.accent); Default uses cyan (pal.text_lcd)
        title_color = pal.accent if theme.id == "cyber_yellow" else pal.text_lcd
        vol_lbl_color = pal.accent if theme.id == "cyber_yellow" else pal.text_on_chassis_muted
        vol_subpage = pal.accent if theme.id == "cyber_yellow" else pal.slider_subpage
        vol_handle_border = pal.accent if theme.id == "cyber_yellow" else pal.slider_handle_border

        base_normal_style = f"""
            QLabel#normalVersion {{
                color: {pal.accent};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
            }}
            QLabel#normalIdentity {{
                color: {pal.text_on_chassis};
                font-family: {disp_font};
                font-size: 10px;
                font-weight: bold;
            }}
            QLabel#normalTrackTitle {{
                color: {title_color};
                font-family: {disp_font};
                font-size: 12px;
                font-weight: bold;
            }}
            QLabel#normalTimeDisplay {{
                color: {pal.text_lcd_time};
                font-family: {mono_font};
                font-size: 11px;
            }}
            QLabel#normalVolumeLabel {{
                color: {vol_lbl_color};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
            }}
            QSlider#normalVolumeSlider::groove:horizontal {{
                height: 3px;
                background: {pal.slider_groove};
                border-radius: 1px;
            }}
            QSlider#normalVolumeSlider::sub-page:horizontal {{
                background: {vol_subpage};
                border-radius: 1px;
            }}
            QSlider#normalVolumeSlider::handle:horizontal {{
                background: {pal.slider_handle};
                border: 1px solid {vol_handle_border};
                width: 6px;
                margin: -2px 0;
                border-radius: 3px;
            }}
            QSlider#normalSeekSlider::groove:horizontal {{
                height: 3px;
                background: {pal.slider_groove};
                border-radius: 1px;
            }}
            QSlider#normalSeekSlider::sub-page:horizontal {{
                background: {pal.slider_subpage};
                border-radius: 1px;
            }}
            QSlider#normalSeekSlider::handle:horizontal {{
                background: {pal.slider_handle};
                border: 1px solid {pal.slider_handle_border};
                width: 8px;
                margin: -3px 0;
                border-radius: 4px;
            }}
            QPushButton#normalBtnTheme, QPushButton#normalBtnMini, QPushButton#normalBtnMelt {{
                background: {pal.bg_control_on_chassis};
                border: 1px solid {pal.border_control_on_chassis};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
                padding: 0 4px;
                border-radius: 2px;
            }}
            QPushButton#normalBtnTheme {{ color: {pal.primary}; }}
            QPushButton#normalBtnTheme:hover {{ border-color: {pal.primary}; }}
            QPushButton#normalBtnMini {{ color: {pal.warning}; }}
            QPushButton#normalBtnMini:hover {{ border-color: {pal.warning}; }}
            QPushButton#normalBtnMelt {{ color: {pal.accent}; }}
            QPushButton#normalBtnMelt:hover {{ border-color: {pal.accent}; }}
            
            QPushButton#normalBtnPrev, QPushButton#normalBtnPlay, QPushButton#normalBtnStop, QPushButton#normalBtnNext {{
                background-color: {pal.bg_control};
                border: 1px solid {pal.border_control_on_chassis};
                border-radius: 2px;
                color: {pal.text_secondary};
                font-family: {mono_font};
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
            }}
            QPushButton#normalBtnPrev:hover, QPushButton#normalBtnPlay:hover, QPushButton#normalBtnStop:hover, QPushButton#normalBtnNext:hover {{
                border-color: {pal.border_control_hover};
                color: {pal.primary};
                background-color: {pal.bg_control_hover};
            }}
            QPushButton#normalBtnPrev:pressed, QPushButton#normalBtnPlay:pressed, QPushButton#normalBtnStop:pressed, QPushButton#normalBtnNext:pressed {{
                background-color: {pal.bg_control_pressed};
                color: {pal.bg_lcd};
                border-color: {pal.primary};
            }}
        """
        
        # Clear widget-local overrides so parent/QSS rules can cascade cleanly
        self.normal_version_lbl.setStyleSheet("")
        self.normal_id_lbl.setStyleSheet("")
        self.normal_title_marquee.setStyleSheet("")
        self.normal_time_display.setStyleSheet("")
        self.normal_vol_lbl.setStyleSheet("")
        self.normal_vol_slider.setStyleSheet("")
        self.normal_seek_slider.setStyleSheet("")
        self.normal_btn_thm.setStyleSheet("")
        self.normal_btn_to_mini.setStyleSheet("")
        self.normal_btn_fs.setStyleSheet("")
        self.normal_btn_prev.setStyleSheet("")
        self.normal_btn_play.setStyleSheet("")
        self.normal_btn_stop.setStyleSheet("")
        self.normal_btn_next.setStyleSheet("")

        # 5. Chips
        chip_fade_style = f"""
            QPushButton {{
                background: {pal.chip_vis_bg};
                border: 1px solid {pal.chip_vis_border};
                color: {pal.chip_vis_text};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 2px;
            }}
            QPushButton:hover {{
                border-color: {pal.primary};
                background-color: {pal.bg_control_hover};
            }}
            QPushButton:checked {{
                background: {pal.chip_vis_active_bg};
                color: {pal.chip_vis_active_text};
                border-color: {pal.primary};
            }}
        """
        self.chip_fade.setStyleSheet(chip_fade_style)
        self.chip_vis.setStyleSheet(chip_fade_style)

        # 6. Apply Combined Base + QSS Override on normal_widget
        combined_qss = base_normal_style + "\n" + (theme.qss_override or "")
        self.normal_widget.setStyleSheet(combined_qss)

        self.chip_pl.setStyleSheet(f"""
            QPushButton {{
                background: {pal.chip_pl_bg};
                border: 1px solid {pal.chip_pl_border};
                color: {pal.chip_pl_text};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 2px;
            }}
            QPushButton:hover {{
                border-color: {pal.accent};
                background-color: {pal.bg_control_hover};
            }}
            QPushButton:checked {{
                background: {pal.chip_pl_active_bg};
                color: {pal.chip_pl_active_text};
                border-color: {pal.accent};
            }}
        """)

        # 6. MINI View Components
        mini_btn_style = f"""
            QPushButton {{
                background-color: {pal.bg_control};
                border: 1px solid {pal.border_control};
                border-radius: 2px;
                color: {pal.text_secondary};
                font-family: {mono_font};
                font-weight: bold;
                font-size: 9px;
                padding: 2px 5px;
            }}
            QPushButton:hover {{
                border-color: {pal.border_control_hover};
                color: {pal.primary};
                background-color: {pal.bg_control_hover};
            }}
            QPushButton:pressed {{
                background-color: {pal.bg_control_pressed};
                color: {pal.bg_lcd};
                border-color: {pal.primary};
            }}
        """
        self.mini_btn_prev.setStyleSheet(mini_btn_style)
        self.mini_btn_play.setStyleSheet(mini_btn_style)
        self.mini_btn_next.setStyleSheet(mini_btn_style)
        self.mini_title_marquee.setStyleSheet(f"color: {pal.text_lcd}; font-family: {disp_font}; font-size: 10px; font-weight: bold;")
        self.mini_time_display.setStyleSheet(f"color: {pal.text_lcd_time}; font-family: {mono_font}; font-size: 9px;")
        self.mini_vol_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {pal.text_lcd}; font-size: 10px; padding: 0; }} QPushButton:hover {{ color: {pal.primary}; }}")

        self.mini_btn_thm.setText("⚡" if theme.id == "default" else "⚡Y")
        self.mini_btn_thm.setStyleSheet(f"""
            QPushButton {{
                background: {pal.bg_surface_alt};
                border: 1px solid {pal.border_control};
                color: {pal.primary};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
                padding: 0 3px;
                border-radius: 2px;
            }}
            QPushButton:hover {{ border-color: {pal.primary}; }}
        """)

        self.mini_btn_to_normal.setStyleSheet(f"""
            QPushButton {{
                background: {pal.bg_surface_alt};
                border: 1px solid {pal.primary};
                color: {pal.primary};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
                padding: 0 4px;
                border-radius: 2px;
            }}
            QPushButton:hover {{ background: {pal.primary}; color: {pal.bg_lcd}; }}
        """)

        self.mini_btn_fs.setStyleSheet(f"""
            QPushButton {{
                background: {pal.bg_surface_alt};
                border: 1px solid {pal.accent};
                color: {pal.accent};
                font-family: {mono_font};
                font-size: 10px;
                font-weight: bold;
                border-radius: 2px;
            }}
            QPushButton:hover {{ background: {pal.accent}; color: #ffffff; }}
        """)

        self.mini_btn_close.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {pal.text_muted}; font-size: 11px; }} QPushButton:hover {{ color: {pal.danger}; }}")

        # Mini Volume Popup
        self.mini_pop_slider.setStyleSheet(f"""
            QSlider::groove:vertical {{ width: 3px; background: {pal.primary}; border-radius: 1px; }}
            QSlider::handle:vertical {{ background: {pal.slider_handle}; border: 1px solid {pal.primary}; height: 8px; margin: 0 -5px; border-radius: 4px; }}
            QSlider::handle:vertical:hover {{ background: {pal.primary}; }}
        """)

        # Re-apply neon frame style
        if self._current_neon:
            self.apply_neon_state(self._current_neon)
        else:
            self.normal_lcd_frame.setStyleSheet(f"background-color: {pal.bg_lcd}; border: 1px solid {pal.border_panel}; border-radius: 3px; padding: 2px 6px;")
            self.mini_lcd_frame.setStyleSheet(f"background-color: {pal.bg_lcd}; border: 1px solid {pal.border_panel}; border-radius: 2px; padding: 1px 4px;")

        self.update()

    def apply_neon_state(self, state: NeonState):
        """Applies dynamic reactive neon colors across borders, panels, and LCD displays."""
        self._current_neon = state

        # Expressive Spectral Track Display (Tier 2/Glow)
        t_col = state.track_glow_color.name()
        bg_col = state.track_bg_color.name(QColor.HexArgb)

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
        """Paints chassis background and crisp, reactive electric neon outer border (Tier 1)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        theme = self._current_theme
        pal = theme.palette

        # Background fill (image-backed texture in Cyber Yellow, solid in Default)
        if theme.is_image_backed:
            pm = theme.assets.get_pixmap("chassis")
            if pm:
                painter.setClipRect(rect)
                painter.drawPixmap(rect, pm)
            else:
                painter.setBrush(pal.bg_chassis)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(rect, 4, 4)
        else:
            painter.setBrush(pal.bg_chassis)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 4, 4)

        painter.setClipping(False)
        painter.setBrush(Qt.NoBrush)

        # Electric Neon Border (Tier 1)
        if self._current_neon:
            border_color = self._current_neon.tier1_chassis_color
            pen = QPen(border_color, 2.0)

            # NORMAL-mode-only soft outer glow halo: the breathing effect's
            # purpose is peripheral-vision presence, but a single crisp
            # ~1.5px line barely registers outside foveal vision. Two
            # progressively wider, more transparent rings drawn behind the
            # crisp line simulate a soft glow bleed -- still driven by the
            # exact same smooth ~3.2s breathing signal, so it stays
            # atmospheric rather than becoming a flashing/strobing effect.
            # MINI keeps its original, deliberately understated presence.
            if self.mode == "normal":
                intensity = self._current_neon.intensity_factor
                for ring_offset, alpha_scale in ((4.0, 0.20), (2.0, 0.35)):
                    glow_color = QColor(border_color)
                    glow_color.setAlpha(int(border_color.alpha() * alpha_scale * intensity))
                    glow_pen = QPen(glow_color, 2.0 + ring_offset)
                    painter.setPen(glow_pen)
                    painter.drawRoundedRect(rect, 4, 4)
        else:
            pen = QPen(pal.border_chassis_default, 1.5)

        painter.setPen(pen)
        painter.drawRoundedRect(rect, 4, 4)
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
        h_layout.setSpacing(6)

        self.normal_wordmark_lbl = QLabel(hdr)
        self.normal_wordmark_lbl.setObjectName("normalWordmark")
        self.normal_wordmark_lbl.hide()
        h_layout.addWidget(self.normal_wordmark_lbl)

        self.normal_id_lbl = QLabel(f"TOROIDAMP // v{__version__}", hdr)
        self.normal_id_lbl.setObjectName("normalIdentity")
        h_layout.addWidget(self.normal_id_lbl)

        self.normal_version_lbl = QLabel(f"v{__version__}", hdr)
        self.normal_version_lbl.setObjectName("normalVersion")
        self.normal_version_lbl.hide()
        h_layout.addWidget(self.normal_version_lbl)

        h_layout.addStretch()

        self.normal_btn_thm = QPushButton("⚡ THM", hdr)
        self.normal_btn_thm.setObjectName("normalBtnTheme")
        self.normal_btn_thm.setToolTip("Toggle Theme (DEFAULT / CYBER YELLOW)")
        self.normal_btn_thm.setFixedHeight(16)
        self.normal_btn_thm.clicked.connect(self.theme_toggle_requested.emit)
        h_layout.addWidget(self.normal_btn_thm)

        self.normal_btn_to_mini = QPushButton("▼ MINI", hdr)
        self.normal_btn_to_mini.setObjectName("normalBtnMini")
        self.normal_btn_to_mini.setFixedHeight(16)
        self.normal_btn_to_mini.clicked.connect(lambda: self.set_mode("mini"))
        h_layout.addWidget(self.normal_btn_to_mini)

        self.normal_btn_fs = QPushButton("⛶ MELT", hdr)
        self.normal_btn_fs.setObjectName("normalBtnMelt")
        self.normal_btn_fs.setFixedHeight(16)
        self.normal_btn_fs.clicked.connect(self.retina_melt_requested.emit)
        h_layout.addWidget(self.normal_btn_fs)

        self.normal_btn_min = QPushButton("─", hdr)
        self.normal_btn_min.setObjectName("normalBtnMinimize")
        self.normal_btn_min.setToolTip("Compact to MINI strip")
        self.normal_btn_min.setFixedSize(16, 16)
        self.normal_btn_min.clicked.connect(self.minimize_requested.emit)
        h_layout.addWidget(self.normal_btn_min)

        self.normal_btn_close = QPushButton("✕", hdr)
        self.normal_btn_close.setObjectName("normalBtnClose")
        self.normal_btn_close.setToolTip("Exit ToroidAMP")
        self.normal_btn_close.setFixedSize(16, 16)
        self.normal_btn_close.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(self.normal_btn_close)

        layout.addWidget(hdr)

        # LCD Display Rack
        self.normal_lcd_frame = QFrame(self.normal_widget)
        self.normal_lcd_frame.setObjectName("normalLcdFrame")
        self.normal_lcd_frame.setFixedHeight(38)
        self.normal_lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 3px; padding: 2px 6px;")
        lcd_layout = QHBoxLayout(self.normal_lcd_frame)
        lcd_layout.setContentsMargins(4, 2, 4, 2)

        self.normal_title_marquee = MarqueeLabel(self.normal_lcd_frame)
        self.normal_title_marquee.setObjectName("normalTrackTitle")
        self.normal_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 12px; font-weight: bold;")
        self.normal_title_marquee.set_marquee_text("♫ No Track Loaded")
        lcd_layout.addWidget(self.normal_title_marquee, stretch=2)

        self.normal_time_display = QLabel("00:00 / 00:00", self.normal_lcd_frame)
        self.normal_time_display.setObjectName("normalTimeDisplay")
        self.normal_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 11px;")
        lcd_layout.addWidget(self.normal_time_display, alignment=Qt.AlignRight)

        layout.addWidget(self.normal_lcd_frame)


        # Progress / Seek Bar — SeekSlider supports both handle-drag and direct groove-click.
        self.normal_seek_slider = SeekSlider(Qt.Horizontal, self.normal_widget)
        self.normal_seek_slider.setObjectName("normalSeekSlider")
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
        self.normal_btn_prev = QPushButton("◄◄", ctrl_bar)
        self.normal_btn_prev.setObjectName("normalBtnPrev")
        self.normal_btn_prev.setToolTip("Previous Track")
        self.normal_btn_prev.clicked.connect(self.prev_clicked.emit)
        c_layout.addWidget(self.normal_btn_prev)

        self.normal_btn_play = QPushButton("►", ctrl_bar)
        self.normal_btn_play.setObjectName("normalBtnPlay")
        self.normal_btn_play.setToolTip("Play / Pause")
        self.normal_btn_play.clicked.connect(self.play_toggled.emit)
        c_layout.addWidget(self.normal_btn_play)

        # v0.666 ("Botón Engendro" investigation): this is a genuine, non-
        # redundant Stop -- unlike the Play/Pause toggle above (which only
        # pauses and resumes, never resets playback position), this fully
        # stops playback and returns to position 0. No other NORMAL-mode
        # control exposes that. Kept; a tooltip was the actual fix needed
        # (it previously had none, unlike every other chassis control),
        # since the complaint was discoverability, not the control itself.
        self.normal_btn_stop = QPushButton("■", ctrl_bar)
        self.normal_btn_stop.setObjectName("normalBtnStop")
        self.normal_btn_stop.setToolTip("Stop Playback (resets position)")
        self.normal_btn_stop.clicked.connect(self.stop_clicked.emit)
        c_layout.addWidget(self.normal_btn_stop)

        self.normal_btn_next = QPushButton("►►", ctrl_bar)
        self.normal_btn_next.setObjectName("normalBtnNext")
        self.normal_btn_next.setToolTip("Next Track")
        self.normal_btn_next.clicked.connect(self.next_clicked.emit)
        c_layout.addWidget(self.normal_btn_next)

        self.normal_vol_lbl = QLabel("VOL", ctrl_bar)
        self.normal_vol_lbl.setObjectName("normalVolumeLabel")
        c_layout.addWidget(self.normal_vol_lbl)

        self.normal_vol_slider = QSlider(Qt.Horizontal, ctrl_bar)
        self.normal_vol_slider.setObjectName("normalVolumeSlider")
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

        # Module / Playback Toggle Chips
        self.chip_fade = QPushButton("FDE", ctrl_bar)
        self.chip_fade.setObjectName("normalBtnFade")
        self.chip_fade.setToolTip("Playback Fade On/Off")
        self.chip_fade.setCheckable(True)
        self.chip_fade.setChecked(True)
        self.chip_fade.toggled.connect(self.toggle_fade_clicked.emit)
        c_layout.addWidget(self.chip_fade)

        self.chip_vis = QPushButton("VIS", ctrl_bar)
        self.chip_vis.setObjectName("normalBtnVis")
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

        self.mini_btn_prev = QPushButton("◄◄", self.mini_widget)
        self.mini_btn_prev.clicked.connect(self.prev_clicked.emit)
        layout.addWidget(self.mini_btn_prev)

        self.mini_btn_play = QPushButton("►", self.mini_widget)
        self.mini_btn_play.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self.mini_btn_play)

        self.mini_btn_next = QPushButton("►►", self.mini_widget)
        self.mini_btn_next.clicked.connect(self.next_clicked.emit)
        layout.addWidget(self.mini_btn_next)

        # Mini LCD Frame (Expressive Track Display)
        self.mini_lcd_frame = QFrame(self.mini_widget)
        self.mini_lcd_frame.setFixedHeight(24)
        self.mini_lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 2px; padding: 1px 4px;")
        mini_lcd_layout = QHBoxLayout(self.mini_lcd_frame)
        mini_lcd_layout.setContentsMargins(4, 0, 4, 0)

        self.mini_title_marquee = MarqueeLabel(self.mini_lcd_frame)
        self.mini_title_marquee.set_marquee_text("♫ No Track Loaded")
        mini_lcd_layout.addWidget(self.mini_title_marquee, stretch=2)

        self.mini_time_display = QLabel("00:00 / 00:00", self.mini_lcd_frame)
        # Fixed minimum width prevents layout jitter as digit count changes.
        self.mini_time_display.setMinimumWidth(90)
        self.mini_time_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mini_lcd_layout.addWidget(self.mini_time_display)

        layout.addWidget(self.mini_lcd_frame, stretch=2)

        # UX-004: the MINI speaker is a real, clickable volume control
        self.mini_vol_btn = QPushButton("🔊", self.mini_widget)
        self.mini_vol_btn.setToolTip("Volume")
        self.mini_vol_btn.setFlat(True)
        self.mini_vol_btn.clicked.connect(self._toggle_mini_volume_popup)
        layout.addWidget(self.mini_vol_btn)

        self._build_mini_volume_popup()

        self.mini_btn_thm = QPushButton("⚡", self.mini_widget)
        self.mini_btn_thm.setToolTip("Toggle Theme")
        self.mini_btn_thm.setFixedHeight(18)
        self.mini_btn_thm.clicked.connect(self.theme_toggle_requested.emit)
        layout.addWidget(self.mini_btn_thm)

        self.mini_btn_to_normal = QPushButton("▲ NORMAL", self.mini_widget)
        self.mini_btn_to_normal.setFixedHeight(18)
        self.mini_btn_to_normal.clicked.connect(lambda: self.set_mode("normal"))
        layout.addWidget(self.mini_btn_to_normal)

        self.mini_btn_fs = QPushButton("⛶", self.mini_widget)
        self.mini_btn_fs.setToolTip("RETINA MELT Fullscreen")
        self.mini_btn_fs.setFixedSize(18, 18)
        self.mini_btn_fs.clicked.connect(self.retina_melt_requested.emit)
        layout.addWidget(self.mini_btn_fs)

        self.mini_btn_close = QPushButton("✕", self.mini_widget)
        self.mini_btn_close.setToolTip("Exit ToroidAMP")
        self.mini_btn_close.setFixedSize(16, 16)
        self.mini_btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.mini_btn_close)

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
            self._apply_stack_size(self.MINI_WIDTH, self.MINI_HEIGHT)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
            self.scale_changed.emit("mini")
        else:
            self.stack.setCurrentWidget(self.normal_widget)
            self._apply_stack_size(self.NORMAL_WIDTH, self.NORMAL_HEIGHT)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
            self.scale_changed.emit("normal")

    def _apply_stack_size(self, stack_w: int, stack_h: int):
        self.stack.setFixedSize(stack_w, stack_h)
        if self._embedded_modules:
            # Wayland unified chassis: this top-level window's own size
            # must not be pinned to the NORMAL/MINI stack's fixed footprint
            # while a module is embedded alongside it -- let the layout
            # grow/shrink the whole window to fit stack + embedded
            # module(s) instead.
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.outer_layout.activate()
            self.adjustSize()
        else:
            self.setFixedSize(stack_w, stack_h)

    def embed_module(self, region: str, widget: Optional[QWidget]) -> None:
        """
        Wayland unified-chassis hosting (RELEASE-BLOCKERS-001): places
        `widget` (a ModuleShell constructed with embedded=True, i.e. a
        plain child widget with no Qt.Window flag of its own) directly
        inside this chassis's single top-level surface -- 'right' for
        Playlist, 'bottom' for Visualizer -- instead of as an independent
        xdg_toplevel, which Wayland's compositor centers unconditionally
        regardless of any client-requested position (see
        realign_docked_modules() in window_manager.py for the full
        protocol-limitation writeup). Passing widget=None detaches
        whatever is currently hosted in that region, collapsing its grid
        cell back to zero size. Never used on Windows/X11 -- those
        platforms keep the existing independent-top-level module windows
        untouched.
        """
        existing = self._embedded_modules.pop(region, None)
        if existing is not None:
            self.outer_layout.removeWidget(existing)
            existing.hide()

        if widget is not None:
            row, col = (0, 1) if region == "right" else (1, 0)
            self.outer_layout.addWidget(widget, row, col, Qt.AlignTop | Qt.AlignLeft)
            self._embedded_modules[region] = widget
            if hasattr(widget, "_user_size"):
                widget.setFixedSize(widget._user_size)

        self._apply_stack_size(self.stack.width(), self.stack.height())

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

        # Playback-state/interaction stabilization: Qt.Popup auto-closes
        # itself on any outside click -- including a second click on the
        # speaker button itself, which is "outside" as far as the popup is
        # concerned. That auto-close happens during the same low-level
        # event dispatch that delivers the press to the button underneath,
        # strictly before this button's own `clicked` signal fires. So a
        # toggle handler that only checks isVisible() when `clicked` fires
        # always sees "already hidden" on that second click and reopens
        # it -- the popup could never actually be dismissed by pressing
        # the speaker again. Catching the popup's own Hide event and
        # debouncing a reopen that arrives immediately afterward (same
        # click) is the standard fix for this well-known Qt popup pattern.
        self._volume_popup_hidden_at: float = 0.0
        self.volume_popup.installEventFilter(self)

    def _on_mini_volume_slider_changed(self, value: int):
        # Keep the NORMAL slider in sync immediately — same single
        # authoritative value, two views/controllers.
        self.normal_vol_slider.setValue(value)
        self.volume_changed.emit(value / 100.0)

    def _toggle_mini_volume_popup(self):
        if self.volume_popup.isVisible():
            self.volume_popup.hide()
            return
        # A second click on the speaker button while the popup is open
        # reaches here with the popup already auto-hidden by Qt (see the
        # eventFilter note in _build_mini_volume_popup) -- reopening it
        # would make that click look like a no-op instead of a close.
        # 300ms comfortably covers the auto-dismiss-then-click_signal gap
        # (both happen within the same physical click, microseconds apart)
        # without being long enough to block a deliberate, separate
        # re-open click shortly after.
        if (time.monotonic() - self._volume_popup_hidden_at) < 0.3:
            return
        # Always resync from the current authoritative value before showing —
        # guards against any drift regardless of how the value last changed.
        self.mini_pop_slider.blockSignals(True)
        self.mini_pop_slider.setValue(self.normal_vol_slider.value())
        self.mini_pop_slider.blockSignals(False)

        self.volume_popup.move(self._compute_volume_popup_pos())
        self.volume_popup.show()

    def eventFilter(self, obj, event):
        if obj is self.volume_popup and event.type() == QEvent.Hide:
            self._volume_popup_hidden_at = time.monotonic()
        return super().eventFilter(obj, event)

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
            # Wayland/interaction stabilization: manually computing a
            # target position from global mouse coordinates and calling
            # move() -- the previous approach here, still used below on
            # X11/Windows where it demonstrably already works -- doesn't
            # work under Wayland. Wayland clients have no general notion
            # of an absolute on-screen position and cannot reposition
            # themselves arbitrarily (compositor security model); a
            # client-driven move() is a silent no-op there. QWindow.
            # startSystemMove() (Qt 5.15+) instead asks the compositor
            # itself to perform the drag using its own native move
            # protocol, which is the portable, Qt-documented mechanism
            # for exactly this and works correctly on X11 and Windows too
            # -- only used here on Wayland specifically because it hands
            # the entire drag over to the compositor, which means our own
            # mouseMoveEvent (and therefore MINI mode's edge-snap-to-
            # screen behavior) never fires again for the rest of this
            # drag; keeping the existing per-pixel path where it already
            # works avoids losing that on platforms where it isn't broken.
            window = self.windowHandle()
            if QGuiApplication.platformName() == "wayland" and window is not None:
                window.startSystemMove()
                event.accept()
                return
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

    def deleteLater(self):
        try:
            self._theme_manager.theme_changed.disconnect(self.apply_theme)
        except Exception:
            pass
        super().deleteLater()


