"""
ToroidAMP - Windows Global Media Keys Integration
Provides global multimedia key support (Play/Pause, Next, Previous, Stop, Mute)
on Windows via RegisterHotKey and QAbstractNativeEventFilter without third-party dependencies.
"""

import sys
import time
import logging
from typing import Callable, Optional
from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

logger = logging.getLogger("toroidamp.media_keys")

# Windows Virtual-Key codes
VK_VOLUME_MUTE = 0xAD
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# Windows Messages
WM_HOTKEY = 0x0312
WM_APPCOMMAND = 0x0319

# APPCOMMAND values
APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
APPCOMMAND_MEDIA_STOP = 13
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
APPCOMMAND_VOLUME_MUTE = 8

# Hotkey IDs
HOTKEY_ID_PLAY_PAUSE = 0x8001
HOTKEY_ID_NEXT = 0x8002
HOTKEY_ID_PREV = 0x8003
HOTKEY_ID_STOP = 0x8004
HOTKEY_ID_MUTE = 0x8005

MOD_NOREPEAT = 0x4000


class WindowsGlobalMediaKeys(QAbstractNativeEventFilter):
    """
    Windows-native global multimedia key listener.
    Cleanly handles Play/Pause, Next, Previous, Stop, Mute while ToroidAMP
    is unfocused, minimized, or in background.
    """

    def __init__(
        self,
        hwnd: int,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_prev: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_mute: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._hwnd = hwnd
        self._on_play_pause = on_play_pause
        self._on_next = on_next
        self._on_prev = on_prev
        self._on_stop = on_stop
        self._on_mute = on_mute

        self._registered_ids: list[int] = []
        self._is_active = False
        self._last_trigger_time: dict[int, float] = {}

    def register(self) -> bool:
        """Registers global hotkeys on Windows."""
        if sys.platform != "win32" or not self._hwnd:
            return False

        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            hotkeys = [
                (HOTKEY_ID_PLAY_PAUSE, VK_MEDIA_PLAY_PAUSE),
                (HOTKEY_ID_NEXT, VK_MEDIA_NEXT_TRACK),
                (HOTKEY_ID_PREV, VK_MEDIA_PREV_TRACK),
                (HOTKEY_ID_STOP, VK_MEDIA_STOP),
                (HOTKEY_ID_MUTE, VK_VOLUME_MUTE),
            ]

            registered = []
            for hk_id, vk in hotkeys:
                # MOD_NOREPEAT (0x4000) prevents key auto-repeat storms
                res = user32.RegisterHotKey(
                    wintypes.HWND(self._hwnd),
                    hk_id,
                    MOD_NOREPEAT,
                    vk
                )
                if not res:
                    # Fallback without MOD_NOREPEAT on older OS
                    res = user32.RegisterHotKey(
                        wintypes.HWND(self._hwnd),
                        hk_id,
                        0,
                        vk
                    )
                if res:
                    registered.append(hk_id)
                else:
                    logger.debug(f"Could not register global hotkey id {hex(hk_id)} (VK {hex(vk)})")

            self._registered_ids = registered
            self._is_active = True

            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self)

            logger.info(f"Registered {len(registered)} Windows global media keys successfully")
            return len(registered) > 0
        except Exception as e:
            logger.warning(f"Failed to register Windows global media keys: {e}")
            return False

    def unregister(self) -> None:
        """Unregisters all global hotkeys and removes the native event filter."""
        if sys.platform != "win32" or not self._is_active:
            return

        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            for hk_id in self._registered_ids:
                try:
                    user32.UnregisterHotKey(wintypes.HWND(self._hwnd), hk_id)
                except Exception:
                    pass
            self._registered_ids.clear()
            self._is_active = False

            app = QApplication.instance()
            if app is not None:
                try:
                    app.removeNativeEventFilter(self)
                except Exception:
                    pass

            logger.info("Unregistered Windows global media keys")
        except Exception as e:
            logger.warning(f"Error unregistering Windows global media keys: {e}")

    def _debounce_and_dispatch(self, key_id: int, callback: Optional[Callable[[], None]]) -> None:
        """Guards against duplicate/bounced hardware events."""
        if not callback:
            return
        now = time.monotonic()
        last = self._last_trigger_time.get(key_id, 0.0)
        if (now - last) < 0.100:  # 100ms debounce
            return
        self._last_trigger_time[key_id] = now
        try:
            callback()
        except Exception as e:
            logger.error(f"Error executing media key callback for {hex(key_id)}: {e}")

    def nativeEventFilter(self, event_type, message):
        """Intercepts Windows native messages for WM_HOTKEY and WM_APPCOMMAND."""
        if event_type == b"windows_generic_MSG" and self._is_active:
            try:
                import ctypes
                from ctypes import wintypes

                class MSG(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("message", wintypes.UINT),
                        ("wParam", wintypes.WPARAM),
                        ("lParam", wintypes.LPARAM),
                        ("time", wintypes.DWORD),
                        ("pt", wintypes.POINT),
                    ]

                msg = MSG.from_address(int(message))

                if msg.message == WM_HOTKEY:
                    hk_id = int(msg.wParam)
                    if hk_id == HOTKEY_ID_PLAY_PAUSE:
                        self._debounce_and_dispatch(hk_id, self._on_play_pause)
                        return True, 0
                    elif hk_id == HOTKEY_ID_NEXT:
                        self._debounce_and_dispatch(hk_id, self._on_next)
                        return True, 0
                    elif hk_id == HOTKEY_ID_PREV:
                        self._debounce_and_dispatch(hk_id, self._on_prev)
                        return True, 0
                    elif hk_id == HOTKEY_ID_STOP:
                        self._debounce_and_dispatch(hk_id, self._on_stop)
                        return True, 0
                    elif hk_id == HOTKEY_ID_MUTE:
                        self._debounce_and_dispatch(hk_id, self._on_mute)
                        return True, 0

                elif msg.message == WM_APPCOMMAND:
                    cmd = (int(msg.lParam) >> 16) & ~0xF000
                    if cmd == APPCOMMAND_MEDIA_PLAY_PAUSE:
                        self._debounce_and_dispatch(HOTKEY_ID_PLAY_PAUSE, self._on_play_pause)
                        return True, 1
                    elif cmd == APPCOMMAND_MEDIA_NEXTTRACK:
                        self._debounce_and_dispatch(HOTKEY_ID_NEXT, self._on_next)
                        return True, 1
                    elif cmd == APPCOMMAND_MEDIA_PREVIOUSTRACK:
                        self._debounce_and_dispatch(HOTKEY_ID_PREV, self._on_prev)
                        return True, 1
                    elif cmd == APPCOMMAND_MEDIA_STOP:
                        self._debounce_and_dispatch(HOTKEY_ID_STOP, self._on_stop)
                        return True, 1
                    elif cmd == APPCOMMAND_VOLUME_MUTE:
                        self._debounce_and_dispatch(HOTKEY_ID_MUTE, self._on_mute)
                        return True, 1
            except Exception as e:
                logger.debug(f"Exception in nativeEventFilter: {e}")

        return False, 0
