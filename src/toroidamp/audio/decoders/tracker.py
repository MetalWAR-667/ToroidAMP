"""
ToroidAMP - Tracker Module Decoder (libxmp via ctypes)
Supports MOD, XM, IT, S3M

RC-069-002B: migrated from libmodplug (never actually available in this
project's toolchain — see docs/release/RC_069_002_runtime_hygiene.md) to
libxmp, which pygame-ce already bundles as a real, present Windows DLL
(pygame/libxmp.dll). See docs/release/RC_069_002B_tracker_libxmp.md for the
full feasibility audit, the empirical struct-offset derivation, and real
MOD/XM/IT validation results this migration is based on.
"""

import ctypes
import os
import struct
import numpy as np
from .base import AudioDecoder

# xmp_start_player's format flags argument. 0 = the library default: 16-bit
# signed, stereo, interpolated PCM — exactly ToroidAMP's canonical
# pre-normalization shape, so no format flags are ever combined here.
_XMP_FORMAT_DEFAULT = 0

# xmp_play_buffer's loop-count argument. Empirically verified (RC-069-002B):
# 0 loops indefinitely (a real module never signals EOF); 1 plays through
# exactly once and returns a negative code the call after the module ends —
# the real EOF signal ToroidAMP's decode loop needs.
_XMP_LOOP_NONE = 1

# struct xmp_frame_info field offsets, EMPIRICALLY VERIFIED (not merely
# assumed from a header ToroidAMP doesn't ship) against libxmp 4.6.3 by:
#   1. Locating the export table's data-vs-code section split to identify
#      `xmp_version`/`xmp_vercode` as DATA exports (not callable functions
#      — calling them as functions was the first, real crash this audit
#      hit and diagnosed).
#   2. Reading a freshly-loaded module's raw frame_info bytes before any
#      playback and matching them against libxmp's well-known public
#      field order (pos, pattern, row, num_rows, frame, speed, bpm, time,
#      total_time, ...) — bpm/num_rows/total_time all landed on
#      structurally plausible real values for a real .it file.
#   3. Confirming behaviorally: `time` (offset 28) increased by ~1000ms
#      per requested 1-second buffer across 5 consecutive xmp_play_buffer
#      calls, while `total_time` (offset 32) stayed exactly constant —
#      the two fields cannot be confused with any other by their behavior
#      alone, independent of trusting the assumed field order.
# The struct's true full size (including a 64-entry channel_info[] array)
# is intentionally NOT modeled — `_FRAME_INFO_BUFFER_SIZE` below is a
# generously oversized raw buffer so an unknown true size can never
# overflow it, and only these two verified offsets are ever read.
_FRAME_INFO_TIME_OFFSET = 28
_FRAME_INFO_TOTAL_TIME_OFFSET = 32
_FRAME_INFO_BUFFER_SIZE = 8192  # real struct is a few hundred bytes; this is deliberately far larger


class TrackerDecoder(AudioDecoder):
    """
    Decodes classic tracker modules (MOD, XM, IT, S3M) into normalized
    float32 stereo PCM using native libxmp.
    """

    def __init__(self, lib_path: str | None = None):
        self._dll_path = lib_path or self._discover_libxmp()
        if not self._dll_path or not os.path.exists(self._dll_path):
            raise RuntimeError(
                f"libxmp native library could not be located at '{self._dll_path}'. "
                "Ensure pygame-ce is installed — it bundles libxmp on Windows."
            )

        self._xmp = ctypes.CDLL(self._dll_path)
        self._bind_functions()

        self._ctx = self._xmp.xmp_create_context()
        if not self._ctx:
            raise RuntimeError("libxmp: xmp_create_context() returned a null context")

        self._module_loaded = False
        self._player_started = False
        self._sr: int = 44100
        self._duration: float = 0.0
        self._title: str = ""
        self._info_buf = ctypes.create_string_buffer(_FRAME_INFO_BUFFER_SIZE)

    @staticmethod
    def is_available() -> bool:
        """
        Probes whether the native libxmp library can be located, without
        constructing a decoder (which raises if it can't). Tracker playback
        is a real ToroidAMP feature — this exists so tests/tooling can detect
        a genuinely missing optional native dependency and skip explicitly,
        rather than treating it as production behavior to weaken.
        """
        path = TrackerDecoder._discover_libxmp()
        return bool(path and os.path.exists(path))

    @staticmethod
    def _discover_libxmp() -> str | None:
        """
        Finds libxmp DLL/.so within Python packages or system library paths.
        Same discovery SHAPE the prior libmodplug decoder used (checked
        pygame's own install directory first, since that is where pygame-ce
        actually bundles this exact library on Windows) — only the target
        filenames changed. Safe across a source checkout, an installed
        package, and (per docs/release/RC_069_002B_tracker_libxmp.md's
        packaging-implications section) a future PyInstaller build, since it
        never hardcodes a developer-machine-specific absolute path.
        """
        try:
            import pygame
            pkg_dir = os.path.dirname(pygame.__file__)
            for candidate in ["libxmp.dll", "libxmp-4.dll", "libxmp.so.4", "libxmp.so"]:
                p = os.path.join(pkg_dir, candidate)
                if os.path.exists(p):
                    return p
        except ImportError:
            pass

        import ctypes.util
        system_lib = ctypes.util.find_library("xmp")
        if system_lib:
            return system_lib

        for candidate in ["libxmp.dll", "/usr/lib/libxmp.so.4", "/usr/local/lib/libxmp.so"]:
            if os.path.exists(candidate):
                return candidate
        return None

    def _bind_functions(self) -> None:
        x = self._xmp

        x.xmp_create_context.restype = ctypes.c_void_p
        x.xmp_create_context.argtypes = []

        x.xmp_free_context.restype = None
        x.xmp_free_context.argtypes = [ctypes.c_void_p]

        x.xmp_load_module_from_memory.restype = ctypes.c_int
        x.xmp_load_module_from_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]

        x.xmp_release_module.restype = None
        x.xmp_release_module.argtypes = [ctypes.c_void_p]

        x.xmp_scan_module.restype = None
        x.xmp_scan_module.argtypes = [ctypes.c_void_p]

        x.xmp_start_player.restype = ctypes.c_int
        x.xmp_start_player.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

        x.xmp_end_player.restype = None
        x.xmp_end_player.argtypes = [ctypes.c_void_p]

        x.xmp_play_buffer.restype = ctypes.c_int
        x.xmp_play_buffer.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

        x.xmp_get_frame_info.restype = None
        x.xmp_get_frame_info.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        x.xmp_seek_time.restype = ctypes.c_int
        x.xmp_seek_time.argtypes = [ctypes.c_void_p, ctypes.c_int]

        x.xmp_restart_module.restype = None
        x.xmp_restart_module.argtypes = [ctypes.c_void_p]

    def load(self, filepath: str) -> None:
        self._close_module()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Tracker file not found: {filepath}")

        # Reads the file ourselves (proper Unicode path handling via
        # Python's own open()) and hands libxmp only raw bytes via
        # xmp_load_module_from_memory — avoids ever passing a path string
        # across the ctypes boundary at all, sidestepping any native
        # char*/codepage path-encoding pitfall entirely. Same pattern the
        # prior libmodplug decoder used for the same reason.
        with open(filepath, "rb") as f:
            data = f.read()

        ret = self._xmp.xmp_load_module_from_memory(self._ctx, data, len(data))
        if ret != 0:
            raise RuntimeError(f"libxmp failed to parse tracker module (code {ret}): {filepath}")
        self._module_loaded = True

        self._xmp.xmp_scan_module(self._ctx)

        start_ret = self._xmp.xmp_start_player(self._ctx, self._sr, _XMP_FORMAT_DEFAULT)
        if start_ret != 0:
            self._xmp.xmp_release_module(self._ctx)
            self._module_loaded = False
            raise RuntimeError(f"libxmp failed to start playback (code {start_ret}): {filepath}")
        self._player_started = True

        self._xmp.xmp_get_frame_info(self._ctx, self._info_buf)
        _time_ms, total_time_ms = struct.unpack_from(
            "<ii", self._info_buf.raw, _FRAME_INFO_TIME_OFFSET
        )
        self._duration = max(0.0, total_time_ms / 1000.0)

        self._title = os.path.splitext(os.path.basename(filepath))[0]

    def read_frames(self, num_frames: int) -> np.ndarray:
        if not self._player_started:
            return np.zeros((0, 2), dtype=np.float32)

        # 16-bit interleaved stereo = 2 channels * 2 bytes/sample = 4 bytes per frame
        bytes_needed = num_frames * 4
        buf = ctypes.create_string_buffer(bytes_needed)
        ret = self._xmp.xmp_play_buffer(self._ctx, buf, bytes_needed, _XMP_LOOP_NONE)
        if ret != 0:
            # Empirically confirmed EOF/error signal (RC-069-002B): with
            # loop=1, xmp_play_buffer returns a negative code once the
            # module has finished — never a partial/garbage buffer.
            return np.zeros((0, 2), dtype=np.float32)

        int16_arr = np.frombuffer(buf.raw, dtype=np.int16)
        float32_pcm = (int16_arr.astype(np.float32) / 32768.0).reshape(-1, 2)
        return float32_pcm

    def seek(self, position_seconds: float) -> None:
        if self._player_started:
            target_ms = max(0, int(position_seconds * 1000.0))
            self._xmp.xmp_seek_time(self._ctx, target_ms)

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return self._title

    def get_sample_rate(self) -> int:
        return self._sr

    def close(self) -> None:
        self._close_module()

    def _close_module(self) -> None:
        """Releases the currently loaded module (if any), keeping the underlying context/library binding alive for reuse across multiple load() calls on the same TrackerDecoder instance — matches PlayerEngine's existing lazy-singleton usage pattern."""
        if self._player_started:
            self._xmp.xmp_end_player(self._ctx)
            self._player_started = False
        if self._module_loaded:
            self._xmp.xmp_release_module(self._ctx)
            self._module_loaded = False

    def __del__(self):
        try:
            self._close_module()
            ctx = getattr(self, "_ctx", None)
            if ctx:
                self._xmp.xmp_free_context(ctx)
        except Exception:
            pass
