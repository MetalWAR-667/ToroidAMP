"""
ToroidAMP - Unified Audio Player Engine
"""

from enum import Enum, auto
import os
import threading
import numpy as np
import sounddevice as sd

from .decoders import AudioDecoder, ConventionalDecoder, TrackerDecoder
from ..analysis.audio_frame import AnalysisHandoff


import logging

logger = logging.getLogger("toroidamp.player")


class PlaybackState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class FadeState(Enum):
    IDLE = auto()
    FADING_IN = auto()
    PLAYING = auto()
    FADING_OUT = auto()


class PlayerEngine:
    """
    Unified production playback engine coordinating audio decoding,
    real-time output streaming, volume, seeking, smooth gain envelope fading,
    robust decoder failure isolation, and analysis handoff.
    """

    FADE_DURATION_SECONDS = 0.200 # 200 ms smooth envelope

    def __init__(self, handoff: AnalysisHandoff, custom_modplug_path: str | None = None):
        self.handoff = handoff
        self._custom_modplug_path = custom_modplug_path

        self._conventional_decoder = ConventionalDecoder()
        self._tracker_decoder: TrackerDecoder | None = None
        self._active_decoder: AudioDecoder | None = None

        self._state = PlaybackState.STOPPED
        self._fade_state = FadeState.IDLE
        self._fade_envelope: float = 0.0 # 0.0 to 1.0 multiplier
        self._fade_enabled: bool = True
        self._volume: float = 0.8
        self._current_filepath: str = ""
        self._sample_rate: int = 44100

        # Robust decoder failure tracking
        self._generation: int = 0
        self._decoder_failed: bool = False
        self._last_error_generation: int = 0
        self._last_error_path: str = ""
        self._last_error_msg: str = ""

        self._stream: sd.OutputStream | None = None
        self._lock = threading.Lock()
        self._position_seconds: float = 0.0

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def fade_enabled(self) -> bool:
        return self._fade_enabled

    @fade_enabled.setter
    def fade_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._fade_enabled = bool(enabled)
            if not self._fade_enabled:
                if self._state == PlaybackState.PLAYING:
                    self._fade_state = FadeState.PLAYING
                    self._fade_envelope = 1.0
                else:
                    self._fade_state = FadeState.IDLE
                    self._fade_envelope = 0.0

    @property
    def fade_state(self) -> FadeState:
        return self._fade_state

    @property
    def decoder_failed(self) -> bool:
        with self._lock:
            return self._decoder_failed

    def check_and_clear_error(self) -> tuple[bool, str, str]:
        """
        Thread-safe check and consume of decoder error status.
        Returns (has_error, failed_filepath, error_message).
        """
        with self._lock:
            if self._decoder_failed:
                failed_path = self._last_error_path
                msg = self._last_error_msg
                self._decoder_failed = False
                return True, failed_path, msg
            return False, "", ""

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, val: float) -> None:
        self._volume = max(0.0, min(1.0, float(val)))

    @property
    def current_track_title(self) -> str:
        with self._lock:
            if self._active_decoder and not self._decoder_failed:
                try:
                    return self._active_decoder.get_title()
                except Exception:
                    return ""
            return ""

    @property
    def duration(self) -> float:
        with self._lock:
            if self._active_decoder and not self._decoder_failed:
                try:
                    return self._active_decoder.get_duration()
                except Exception:
                    return 0.0
            return 0.0

    @property
    def position(self) -> float:
        with self._lock:
            return self._position_seconds

    @property
    def is_tracker(self) -> bool:
        with self._lock:
            return self._active_decoder is self._tracker_decoder and self._tracker_decoder is not None

    def _get_tracker_decoder(self) -> TrackerDecoder:
        if self._tracker_decoder is None:
            self._tracker_decoder = TrackerDecoder(self._custom_modplug_path)
        return self._tracker_decoder

    def load(self, filepath: str) -> None:
        """Loads a file and switches to the appropriate decoder."""
        self.stop_immediate()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with self._lock:
            self._generation += 1
            self._decoder_failed = False
            self._current_filepath = filepath
            ext = os.path.splitext(filepath)[1].lower()

            if ext in [".mod", ".xm", ".it", ".s3m"]:
                decoder = self._get_tracker_decoder()
            else:
                decoder = self._conventional_decoder

            try:
                decoder.load(filepath)
                self._active_decoder = decoder
                self._sample_rate = decoder.get_sample_rate()
                self._position_seconds = 0.0
            except Exception as e:
                self._decoder_failed = True
                self._last_error_generation = self._generation
                self._last_error_path = filepath
                self._last_error_msg = str(e)
                self._active_decoder = None
                logger.error(f"Failed to load audio file '{filepath}': {e}")
                raise

    def play(self) -> None:
        with self._lock:
            if self._active_decoder is None or self._decoder_failed:
                return

            if self._stream is None:
                self._stream = sd.OutputStream(
                    samplerate=self._sample_rate,
                    channels=2,
                    dtype="float32",
                    callback=self._audio_callback,
                    blocksize=512
                )
                self._stream.start()
            self._state = PlaybackState.PLAYING
            if self._fade_enabled:
                self._fade_state = FadeState.FADING_IN
            else:
                self._fade_state = FadeState.PLAYING
                self._fade_envelope = 1.0

    def pause(self) -> None:
        with self._lock:
            self._state = PlaybackState.PAUSED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0

    def stop(self) -> None:
        """Stops playback with a smooth fade-out or immediate shutdown."""
        with self._lock:
            if self._fade_enabled and self._state == PlaybackState.PLAYING and self._stream is not None and self._fade_envelope > 0.05 and not self._decoder_failed:
                # Trigger fade-out in audio callback
                self._fade_state = FadeState.FADING_OUT
            else:
                self._do_stop()

    def stop_immediate(self) -> None:
        """Immediately stops playback stream and resets position."""
        with self._lock:
            self._do_stop()

    def _do_stop(self) -> None:
        self._state = PlaybackState.STOPPED
        self._fade_state = FadeState.IDLE
        self._fade_envelope = 0.0
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._active_decoder and not self._decoder_failed:
            try:
                self._active_decoder.seek(0.0)
            except Exception:
                pass
        self._position_seconds = 0.0

    def seek(self, target_seconds: float) -> bool:
        """
        Safely seeks the active decoder to target_seconds.
        Never throws exceptions into caller; returns True on success, False on error.
        """
        with self._lock:
            if self._decoder_failed or self._active_decoder is None:
                return False

            try:
                self._active_decoder.seek(target_seconds)
                self._position_seconds = target_seconds
                return True
            except Exception as e:
                # Isolate seek failure
                self._decoder_failed = True
                self._last_error_generation = self._generation
                self._last_error_path = self._current_filepath
                self._last_error_msg = f"Seek error: {e}"
                self._state = PlaybackState.STOPPED
                self._fade_state = FadeState.IDLE
                self._fade_envelope = 0.0
                logger.warning(f"Decoder seek failed on '{self._current_filepath}': {e}")
                return False

    def close(self) -> None:
        self.stop_immediate()
        with self._lock:
            if self._conventional_decoder:
                try:
                    self._conventional_decoder.close()
                except Exception:
                    pass
            if self._tracker_decoder:
                try:
                    self._tracker_decoder.close()
                except Exception:
                    pass
            self._active_decoder = None
            self._decoder_failed = False

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        """
        High-priority audio callback with sample-accurate gain envelope interpolation
        and hard boundary decoder exception isolation.
        Never blocks, never throws, never leaks exceptions to CFFI / sounddevice.
        """
        if self._state != PlaybackState.PLAYING or self._active_decoder is None or self._decoder_failed:
            outdata.fill(0)
            return

        callback_gen = self._generation
        try:
            chunk = self._active_decoder.read_frames(frames)
        except Exception as e:
            # HARD BOUNDARY: Silence output immediately and record failure state
            outdata.fill(0)
            with self._lock:
                # Verify generation matches so stale callbacks don't poison newly loaded tracks
                if self._generation == callback_gen:
                    self._decoder_failed = True
                    self._last_error_generation = callback_gen
                    self._last_error_path = self._current_filepath
                    self._last_error_msg = f"Read error: {e}"
                    self._state = PlaybackState.STOPPED
                    self._fade_state = FadeState.IDLE
                    self._fade_envelope = 0.0
            return

        num_read = len(chunk)

        if num_read == 0:
            # Normal End-Of-File (EOF)
            outdata.fill(0)
            self._state = PlaybackState.STOPPED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0
            return

        if not self._fade_enabled:
            # Bypass fade envelope completely
            self._fade_state = FadeState.PLAYING
            self._fade_envelope = 1.0
            gain = self._volume
            if num_read < frames:
                outdata[:num_read] = chunk * gain
                outdata[num_read:].fill(0)
                self._state = PlaybackState.STOPPED
                self._fade_state = FadeState.IDLE
                self._fade_envelope = 0.0
            else:
                outdata[:] = chunk * gain

            self._position_seconds += num_read / float(self._sample_rate)
            self.handoff.push_audio(outdata)
            return

        # Compute gain envelope interpolation across this chunk
        fade_step = 1.0 / (self.FADE_DURATION_SECONDS * self._sample_rate)
        envelope_curve = np.empty((num_read, 1), dtype=np.float32)

        for i in range(num_read):
            if self._fade_state == FadeState.FADING_IN:
                self._fade_envelope = min(1.0, self._fade_envelope + fade_step)
                if self._fade_envelope >= 0.9999:
                    self._fade_envelope = 1.0
                    self._fade_state = FadeState.PLAYING
            elif self._fade_state == FadeState.FADING_OUT:
                self._fade_envelope = max(0.0, self._fade_envelope - fade_step)
                if self._fade_envelope <= 0.0001:
                    self._fade_envelope = 0.0
                    self._fade_state = FadeState.IDLE
            elif self._fade_state == FadeState.PLAYING:
                self._fade_envelope = 1.0
            else: # IDLE
                self._fade_envelope = 0.0

            envelope_curve[i, 0] = self._fade_envelope

        # Apply gain envelope and master user volume
        gain = envelope_curve * self._volume
        if num_read < frames:
            outdata[:num_read] = chunk * gain
            outdata[num_read:].fill(0)
            self._state = PlaybackState.STOPPED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0
        else:
            outdata[:] = chunk * gain

        self._position_seconds += num_read / float(self._sample_rate)

        # If fade-out completed during this frame, complete stopping
        if self._fade_state == FadeState.IDLE and self._fade_envelope <= 0.0:
            self._state = PlaybackState.STOPPED

        # Push to analysis handoff
        self.handoff.push_audio(outdata)
