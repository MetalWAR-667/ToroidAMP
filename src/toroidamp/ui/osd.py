"""
ToroidAMP - Track Change On-Screen Display (OSD)
Provides a compact, non-intrusive transient overlay when the active track changes.
Never steals focus, does not interrupt playback, and cleans up deterministically.
"""

from typing import Optional
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QColor

from .theme import ThemeManager, ThemeDefinition, disconnect_theme_listener


class TrackChangeOSD(QWidget):
    """
    Transient, non-focus-stealing HUD notification for active track changes.
    """

    DISPLAY_DURATION_MS = 2500

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self._theme_manager = ThemeManager.get_instance()
        self._current_theme: ThemeDefinition = self._theme_manager.current_theme

        # Outer layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        # Card container
        self.card = QFrame(self)
        self.card.setObjectName("osdCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(2)

        # Header row: Status indicator + Format tag
        hdr = QWidget(self.card)
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self.lbl_now_playing = QLabel("♫ NOW PLAYING", hdr)
        self.lbl_now_playing.setObjectName("osdNowPlaying")
        h_layout.addWidget(self.lbl_now_playing)

        h_layout.addStretch()

        self.lbl_format = QLabel("AUDIO", hdr)
        self.lbl_format.setObjectName("osdFormat")
        h_layout.addWidget(self.lbl_format)
        card_layout.addWidget(hdr)

        # Title Label
        self.lbl_title = QLabel("No Track Loaded", self.card)
        self.lbl_title.setObjectName("osdTitle")
        self.lbl_title.setWordWrap(False)
        card_layout.addWidget(self.lbl_title)

        # Artist / Details Label
        self.lbl_details = QLabel("", self.card)
        self.lbl_details.setObjectName("osdDetails")
        self.lbl_details.hide()
        card_layout.addWidget(self.lbl_details)

        outer_layout.addWidget(self.card)

        # Theme connection with clean destruction slot
        theme_manager = self._theme_manager
        apply_theme_slot = self.apply_theme
        self.destroyed.connect(
            lambda: disconnect_theme_listener(theme_manager.theme_changed, apply_theme_slot)
        )
        self._theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme(self._current_theme)

        # Auto-hide timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def apply_theme(self, theme: ThemeDefinition):
        """Applies theme typography and neon colors."""
        self._current_theme = theme
        pal = theme.palette
        typo = theme.typography

        disp_font = f"'{typo.display_family}', monospace"
        mono_font = f"'{typo.monospace_family}', monospace"

        accent_color = pal.accent if theme.id == "cyber_yellow" else pal.primary
        title_color = pal.accent if theme.id == "cyber_yellow" else pal.text_lcd

        self.card.setStyleSheet(f"""
            QFrame#osdCard {{
                background-color: {pal.bg_surface}F0;
                border: 1px solid {accent_color};
                border-radius: 4px;
            }}
            QLabel#osdNowPlaying {{
                color: {pal.text_muted};
                font-family: {mono_font};
                font-size: 8px;
                font-weight: bold;
            }}
            QLabel#osdFormat {{
                color: {pal.bg_lcd};
                background-color: {accent_color};
                font-family: {mono_font};
                font-size: 8px;
                font-weight: bold;
                padding: 1px 4px;
                border-radius: 2px;
            }}
            QLabel#osdTitle {{
                color: {title_color};
                font-family: {disp_font};
                font-size: 11px;
                font-weight: bold;
            }}
            QLabel#osdDetails {{
                color: {pal.text_dim};
                font-family: {mono_font};
                font-size: 9px;
            }}
        """)

    def show_track(self, title: str, format_str: str = "AUDIO", artist: str = "", reference_widget: Optional[QWidget] = None):
        """
        Updates and displays the OSD.
        Re-uses the existing window to prevent accumulation of stale popups.
        """
        if not title:
            return

        self.lbl_title.setText(title)
        self.lbl_format.setText(format_str.upper() if format_str else "AUDIO")

        if artist:
            self.lbl_details.setText(artist)
            self.lbl_details.show()
        else:
            self.lbl_details.hide()

        self.adjustSize()

        # Position calculation: anchor comfortably near reference widget or top-right of screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            if reference_widget and reference_widget.isVisible():
                r_geom = reference_widget.frameGeometry()
                # Position just above the reference chassis
                x = r_geom.left()
                y = r_geom.top() - self.height() - 8
                if y < avail.top():
                    y = r_geom.bottom() + 8
            else:
                # Top-right corner with 24px padding
                x = avail.right() - self.width() - 24
                y = avail.top() + 24

            # Clamp safely within available screen geometry
            x = max(avail.left(), min(x, avail.right() - self.width()))
            y = max(avail.top(), min(y, avail.bottom() - self.height()))
            self.move(x, y)

        self.show()
        self._hide_timer.start(self.DISPLAY_DURATION_MS)

    def dismiss(self):
        """Immediately hides the OSD and stops timer."""
        self._hide_timer.stop()
        self.hide()
