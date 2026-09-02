"""
ToroidAMP - Application Keyboard Shortcuts and Text-Input Safety
Coordinates single-key and global application keyboard shortcuts while
guaranteeing complete input isolation for editable text widgets.
"""

from typing import Optional
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import (
    QApplication, QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QWidget
)


def is_editable_text_widget(widget: Optional[QWidget]) -> bool:
    """Returns True if the widget is an actively editable text widget."""
    if widget is None or not isinstance(widget, QWidget):
        return False
    if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
        if getattr(widget, "isReadOnly", lambda: False)():
            return False
        if not getattr(widget, "isEnabled", lambda: True)():
            return False
        return True
    if hasattr(widget, "isReadOnly") and not widget.isReadOnly():
        if getattr(widget, "isEnabled", lambda: True)():
            return True
    return False


class AppShortcutFilter(QObject):
    """
    Global application event filter for ToroidAMP.
    Dispatches focused shortcuts to WindowManager while ensuring
    single-key playback shortcuts do not fire when typing inside text inputs.
    """

    def __init__(self, window_manager, parent: Optional[QObject] = None):
        super().__init__(parent if isinstance(parent, QObject) else (window_manager if isinstance(window_manager, QObject) else None))
        self.wm = window_manager

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.KeyPress:
            key = event.key()
            mods = event.modifiers()
            focus_w = QApplication.focusWidget()
            is_text = is_editable_text_widget(obj) or is_editable_text_widget(focus_w)

            # Ctrl+F: Open/Focus Playlist Search (always safe)
            if key == Qt.Key_F and (mods & Qt.ControlModifier):
                self.wm._open_playlist_search()
                return True

            # F11: RETINA MELT toggle (always safe)
            if key == Qt.Key_F11:
                self.wm._toggle_retina_melt()
                return True

            # If user is editing text in an input field, suppress single-key shortcuts
            if is_text:
                return super().eventFilter(obj, event)

            # Modifiers guard: ignore if Alt, Ctrl, or Meta is held (except normal Shift if needed)
            has_ctrl = bool(mods & Qt.ControlModifier)
            has_alt = bool(mods & Qt.AltModifier)
            has_meta = bool(mods & Qt.MetaModifier)

            if not has_ctrl and not has_alt and not has_meta:
                if key == Qt.Key_Space:
                    self.wm._toggle_play()
                    return True
                elif key == Qt.Key_Left:
                    self.wm._relative_seek(-5.0)
                    return True
                elif key == Qt.Key_Right:
                    self.wm._relative_seek(+5.0)
                    return True
                elif key == Qt.Key_Up:
                    self.wm._relative_volume(+0.05)
                    return True
                elif key == Qt.Key_Down:
                    self.wm._relative_volume(-0.05)
                    return True
                elif key == Qt.Key_M:
                    self.wm._toggle_mute()
                    return True
                elif key == Qt.Key_V:
                    self.wm._cycle_visualizer()
                    return True

        return super().eventFilter(obj, event)
