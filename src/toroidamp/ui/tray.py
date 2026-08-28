"""
ToroidAMP - Production System Tray Icon Subsystem
Provides background presence, quick transport controls, track status,
and clean separation between HIDE and EXIT.
"""

import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

from ..branding import resolve_branding_icon
from .theme import ThemeManager, ThemeDefinition

logger = logging.getLogger("toroidamp.tray")


class ToroidTrayIcon(QSystemTrayIcon):
    """
    System Tray Icon for ToroidAMP.
    """
    restore_requested = Signal()
    play_toggled = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # BRAND-001: official checkerboard toroid replaces the procedural
        # cyan/magenta ring. The procedural generator remains as an internal
        # fallback — if the branding asset is ever missing/unreadable, the
        # tray still gets a usable icon instead of none at all.
        official_icon = resolve_branding_icon()
        self.setIcon(official_icon if official_icon is not None else self._create_procedural_icon())
        self.setToolTip("ToroidAMP // Modular Audio Player")

        self._theme_manager = ThemeManager.get_instance()
        self._menu = QMenu()
        self._theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme(self._theme_manager.current_theme)

    def apply_theme(self, theme: ThemeDefinition):
        pal = theme.palette
        typo = theme.typography
        mono_font = f"'{typo.monospace_family}', monospace"

        self._menu.setStyleSheet(f"""
            QMenu {{
                background-color: {pal.bg_surface};
                color: {pal.text_primary};
                border: 1px solid {pal.primary};
                font-family: {mono_font};
                font-size: 11px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 4px 16px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {pal.bg_surface_alt};
                color: {pal.primary};
            }}
            QMenu::separator {{
                height: 1px;
                background: {pal.border_panel};
                margin: 4px 8px;
            }}
        """)

        # Track Status Title Action
        self.action_title = self._menu.addAction("♫ ToroidAMP")
        self.action_title.setEnabled(False)
        self._menu.addSeparator()

        # Transport Actions
        self.action_play = self._menu.addAction("► Play")
        self.action_play.triggered.connect(self.play_toggled.emit)

        self.action_prev = self._menu.addAction("◄◄ Previous")
        self.action_prev.triggered.connect(self.prev_requested.emit)

        self.action_next = self._menu.addAction("►► Next")
        self.action_next.triggered.connect(self.next_requested.emit)

        self._menu.addSeparator()

        # Show / Restore Action
        self.action_restore = self._menu.addAction("⇱ Restore Player")
        self.action_restore.triggered.connect(self.restore_requested.emit)

        self._menu.addSeparator()

        # Exit Application Action
        self.action_exit = self._menu.addAction("✕ Exit ToroidAMP")
        self.action_exit.triggered.connect(self.exit_requested.emit)

        self.setContextMenu(self._menu)
        self.activated.connect(self._on_tray_activated)

        logger.info("System Tray Icon created")

    @staticmethod
    def _create_procedural_icon() -> QIcon:
        """Generates a crisp cyan/magenta torus ring icon procedurally."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Outer Neon Ring
        painter.setPen(QColor(0, 240, 255))
        painter.drawEllipse(3, 3, 26, 26)

        # Inner Core Ring
        painter.setPen(QColor(255, 0, 119))
        painter.drawEllipse(9, 9, 14, 14)

        # Center Torus Dot
        painter.setBrush(QColor(0, 255, 200))
        painter.drawEllipse(13, 13, 6, 6)

        painter.end()
        return QIcon(pixmap)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        # Left click or Double click restores window
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_requested.emit()

    def update_status(self, title: str, is_playing: bool):
        """Updates tray context menu labels and tooltip."""
        clean_title = title.replace("♫ ", "").strip()
        self.action_title.setText(f"♫ {clean_title}" if clean_title else "♫ ToroidAMP")
        self.setToolTip(f"ToroidAMP :: {clean_title}" if clean_title else "ToroidAMP")
        self.action_play.setText("❚❚ Pause" if is_playing else "► Play")
