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


class PlaybackState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class PlayerEngine:
    """
    Unified production playback engine coordinating audio decoding,
    real-time output streaming, volume, seeking, and analysis handoff.
    """

    def __init__(self, handoff: AnalysisHandoff, custom_modplug_path: str | None = None):
        self.handoff = handoff
        self._custom_modplug_path = custom_modplug_path

        self._conventional_decoder = ConventionalDecoder()
        self._tracker_decoder: TrackerDecoder | None = None
        self._active_decoder: AudioDecoder | None = None

        self._state = PlaybackState.STOPPED
        self._volume: float = 0.8
        self._current_filepath: str = ""
        self._sample_rate: int = 44100

        self._stream: sd.OutputStream | None = None
        self._lock = threading.Lock()
        self._position_seconds: float = 0.0

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, val: float) -> None:
        self._volume = max(0.0, min(1.0, float(val)))

    @property
    def current_track_title(self) -> str:
        if self._active_decoder:
            return self._active_decoder.get_title()
        return ""

    @property
    def duration(self) -> float:
        if self._active_decoder:
            return self._active_decoder.get_duration()
        return 0.0

    @property
    def position(self) -> float:
        return self._position_seconds

    @property
    def is_tracker(self) -> bool:
        return self._active_decoder is self._tracker_decoder and self._tracker_decoder is not None

    def _get_tracker_decoder(self) -> TrackerDecoder:
        if self._tracker_decoder is None:
            self._tracker_decoder = TrackerDecoder(self._custom_modplug_path)
        return self._tracker_decoder

    def load(self, filepath: str) -> None:
        """Loads a file and switches to the appropriate decoder."""
        self.stop()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        self._current_filepath = filepath
        ext = os.path.splitext(filepath)[1].lower()

        if ext in [".mod", ".xm", ".it", ".s3m"]:
            decoder = self._get_tracker_decoder()
        else:
            decoder = self._conventional_decoder

        decoder.load(filepath)
        self._active_decoder = decoder
        self._sample_rate = decoder.get_sample_rate()
        self._position_seconds = 0.0

    def play(self) -> None:
        if self._active_decoder is None:
            return

        with self._lock:
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

    def pause(self) -> None:
        with self._lock:
            self._state = PlaybackState.PAUSED

    def stop(self) -> None:
        with self._lock:
            self._state = PlaybackState.STOPPED
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            if self._active_decoder:
                self._active_decoder.seek(0.0)
            self._position_seconds = 0.0

    def seek(self, target_seconds: float) -> None:
        with self._lock:
            if self._active_decoder:
                self._active_decoder.seek(target_seconds)
                self._position_seconds = target_seconds

    def close(self) -> None:
        self.stop()
        if self._conventional_decoder:
            self._conventional_decoder.close()
        if self._tracker_decoder:
            self._tracker_decoder.close()
        self._active_decoder = None

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        """
        High-priority audio callback.
        Never blocks, never allocates heavily, never invokes GUI/Pygame.
        """
        if self._state != PlaybackState.PLAYING or self._active_decoder is None:
            outdata.fill(0)
            return

        chunk = self._active_decoder.read_frames(frames)
        num_read = len(chunk)

        if num_read == 0:
            outdata.fill(0)
            self._state = PlaybackState.STOPPED
            return

        if num_read < frames:
            outdata[:num_read] = chunk * self._volume
            outdata[num_read:].fill(0)
            self._state = PlaybackState.STOPPED
        else:
            outdata[:] = chunk * self._volume

        self._position_seconds += num_read / float(self._sample_rate)
        # Push to analysis handoff
        self.handoff.push_audio(outdata)
