"""
ToroidAMP - Conventional Audio Decoder (soundfile)
Supports WAV, MP3, OGG/Vorbis, FLAC
"""

import os
import soundfile as sf
import numpy as np
from .base import AudioDecoder


class ConventionalDecoder(AudioDecoder):
    """
    Decodes conventional compressed and uncompressed audio formats
    (WAV, MP3, OGG, FLAC) into normalized float32 stereo PCM.
    """

    def __init__(self):
        self._sf_file: sf.SoundFile | None = None
        self._sr: int = 44100
        self._channels: int = 2
        self._duration: float = 0.0
        self._title: str = ""
        self._filepath: str = ""

    def load(self, filepath: str) -> None:
        self.close()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Audio file not found: {filepath}")

        self._filepath = filepath
        self._sf_file = sf.SoundFile(filepath, mode="r")
        self._sr = self._sf_file.samplerate
        self._channels = self._sf_file.channels
        self._duration = len(self._sf_file) / float(self._sr) if self._sr > 0 else 0.0
        self._title = os.path.splitext(os.path.basename(filepath))[0]

    def read_frames(self, num_frames: int) -> np.ndarray:
        if self._sf_file is None or self._sf_file.closed:
            return np.zeros((0, 2), dtype=np.float32)

        data = self._sf_file.read(frames=num_frames, dtype="float32", always_2d=True)
        if len(data) == 0:
            return np.zeros((0, 2), dtype=np.float32)

        # Convert mono to stereo if necessary
        if data.shape[1] == 1:
            data = np.column_stack((data[:, 0], data[:, 0]))
        elif data.shape[1] > 2:
            data = data[:, :2]

        return data

    def seek(self, position_seconds: float) -> None:
        if self._sf_file and not self._sf_file.closed:
            target_frame = max(0, min(len(self._sf_file), int(position_seconds * self._sr)))
            self._sf_file.seek(target_frame)

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return self._title

    def get_sample_rate(self) -> int:
        return self._sr

    def close(self) -> None:
        if self._sf_file and not self._sf_file.closed:
            self._sf_file.close()
        self._sf_file = None
