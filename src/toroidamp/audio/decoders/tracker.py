"""
ToroidAMP - Tracker Module Decoder (libmodplug via ctypes)
Supports MOD, XM, IT, S3M
"""

import os
import sys
import ctypes
import ctypes.util
import numpy as np
from .base import AudioDecoder


class TrackerDecoder(AudioDecoder):
    """
    Decodes classic tracker modules (MOD, XM, IT, S3M) into normalized
    float32 stereo PCM using native libmodplug.
    """

    def __init__(self, lib_path: str | None = None):
        self._dll_path = lib_path or self._discover_libmodplug()
        if not self._dll_path or not os.path.exists(self._dll_path):
            raise RuntimeError(
                f"libmodplug native library could not be located at '{self._dll_path}'. "
                "Ensure Pygame/SDL2_mixer or libmodplug is installed."
            )

        self._modplug = ctypes.CDLL(self._dll_path)
        self._bind_functions()

        self._handle = None
        self._sr: int = 44100
        self._duration: float = 0.0
        self._title: str = ""

    def _discover_libmodplug(self) -> str | None:
        """Finds libmodplug DLL/.so within Python packages or system library paths."""
        # 1. Check inside pygame site-packages (bundled in Windows wheels)
        try:
            import pygame
            pkg_dir = os.path.dirname(pygame.__file__)
            for candidate in ["libmodplug-1.dll", "libmodplug.dll", "libmodplug.so.1", "libmodplug.so"]:
                p = os.path.join(pkg_dir, candidate)
                if os.path.exists(p):
                    return p
        except ImportError:
            pass

        # 2. System discovery
        system_lib = ctypes.util.find_library("modplug")
        if system_lib:
            return system_lib

        # 3. Known fallback locations
        for candidate in ["libmodplug-1.dll", "libmodplug.dll", "/usr/lib/libmodplug.so.1", "/usr/local/lib/libmodplug.so"]:
            if os.path.exists(candidate):
                return candidate
        return None

    def _bind_functions(self) -> None:
        self._modplug.ModPlug_Load.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self._modplug.ModPlug_Load.restype = ctypes.c_void_p
        self._modplug.ModPlug_Unload.argtypes = [ctypes.c_void_p]
        self._modplug.ModPlug_Unload.restype = None
        self._modplug.ModPlug_Read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        self._modplug.ModPlug_Read.restype = ctypes.c_int
        self._modplug.ModPlug_GetName.argtypes = [ctypes.c_void_p]
        self._modplug.ModPlug_GetName.restype = ctypes.c_char_p
        self._modplug.ModPlug_GetLength.argtypes = [ctypes.c_void_p]
        self._modplug.ModPlug_GetLength.restype = ctypes.c_int
        self._modplug.ModPlug_Seek.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._modplug.ModPlug_Seek.restype = None

    def load(self, filepath: str) -> None:
        self.close()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Tracker file not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        self._handle = self._modplug.ModPlug_Load(data, len(data))
        if not self._handle:
            raise RuntimeError(f"libmodplug failed to parse tracker module: {filepath}")

        raw_title = self._modplug.ModPlug_GetName(self._handle)
        self._title = raw_title.decode("latin1", errors="ignore").strip() if raw_title else ""
        if not self._title:
            self._title = os.path.splitext(os.path.basename(filepath))[0]

        length_ms = self._modplug.ModPlug_GetLength(self._handle)
        self._duration = length_ms / 1000.0 if length_ms > 0 else 0.0

    def read_frames(self, num_frames: int) -> np.ndarray:
        if not self._handle:
            return np.zeros((0, 2), dtype=np.float32)

        # 16-bit interleaved stereo = 2 channels * 2 bytes/sample = 4 bytes per frame
        bytes_needed = num_frames * 4
        buf = ctypes.create_string_buffer(bytes_needed)
        bytes_read = self._modplug.ModPlug_Read(self._handle, buf, bytes_needed)

        if bytes_read <= 0:
            return np.zeros((0, 2), dtype=np.float32)

        int16_arr = np.frombuffer(buf[:bytes_read], dtype=np.int16)
        float32_pcm = (int16_arr.astype(np.float32) / 32768.0).reshape(-1, 2)
        return float32_pcm

    def seek(self, position_seconds: float) -> None:
        if self._handle:
            target_ms = max(0, int(position_seconds * 1000.0))
            self._modplug.ModPlug_Seek(self._handle, target_ms)

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return self._title

    def get_sample_rate(self) -> int:
        return self._sr

    def close(self) -> None:
        if self._handle:
            self._modplug.ModPlug_Unload(self._handle)
            self._handle = None
