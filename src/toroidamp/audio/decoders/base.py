"""
ToroidAMP - Abstract Decoder Base Interface
"""

from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class AudioDecoder(ABC):
    """
    Interface for audio format decoders.
    Decoders must yield normalized float32 stereo PCM arrays with shape (N, 2).
    """

    @abstractmethod
    def load(self, filepath: str) -> None:
        """Loads and prepares the specified audio file for decoding."""
        pass

    @abstractmethod
    def read_frames(self, num_frames: int) -> np.ndarray:
        """
        Reads up to num_frames of audio as normalized float32 PCM [-1.0, 1.0].
        Returns array of shape (K, 2) where K <= num_frames. Returns empty array on EOF.
        """
        pass

    @abstractmethod
    def seek(self, position_seconds: float) -> None:
        """Seeks to the given position in seconds."""
        pass

    @abstractmethod
    def get_duration(self) -> float:
        """Returns track duration in seconds, or 0.0 if unknown/streaming."""
        pass

    @abstractmethod
    def get_title(self) -> str:
        """Returns track title metadata or empty string."""
        pass

    @abstractmethod
    def get_sample_rate(self) -> int:
        """Returns the native sample rate (e.g. 44100)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Releases underlying file handles and native resources."""
        pass
