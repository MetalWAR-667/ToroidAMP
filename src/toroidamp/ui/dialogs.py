"""
ToroidAMP - UI Dialog Helpers & Platform Policies
"""
from PySide6.QtWidgets import QFileDialog
from PySide6.QtGui import QGuiApplication


def platform_file_dialog_options(extra_options: QFileDialog.Options = QFileDialog.Options()) -> QFileDialog.Options:
    """
    LINUX-DIALOG-001: Returns platform-appropriate QFileDialog options.

    On Wayland, Qt's native Linux file dialog delegates to the out-of-process
    `org.freedesktop.portal.FileChooser` DBus service. Under GNOME/Mutter, this
    out-of-process portal dialog suffers from:
    1. Unreliable surface parenting / z-order (often opening behind ToroidAMP).
    2. Missing initial focus and sluggish out-of-process file tree enumeration.
    3. Severe latency / timeouts when DBus portal app-ID association is missing.

    Setting `QFileDialog.Option.DontUseNativeDialog` on Wayland forces Qt to render
    the dialog in-process as a standard, Qt-managed QDialog top-level surface.
    This guarantees proper transient-parent stacking directly above the ToroidAMP
    window, instant keyboard focus, and snappy directory navigation.

    On Windows, macOS, and Linux/X11, native dialogs are preserved by returning
    default/extra options unchanged.
    """
    opts = QFileDialog.Options(extra_options)
    if QGuiApplication.platformName() == "wayland":
        opts |= QFileDialog.Option.DontUseNativeDialog
    return opts
