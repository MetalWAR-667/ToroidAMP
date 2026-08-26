"""
ToroidAMP - Normalized AudioFrame and Analysis Module
"""

from dataclasses import dataclass
import threading
import time
import numpy as np


@dataclass(slots=True, frozen=True)
class AudioFrame:
    """
    Normalized audio analysis frame delivered to visualizers and reactive UI elements.
    Derived purely from real-time decoded PCM. All amplitude metrics are [0.0, 1.0].
    """
    rms: float             # Root-mean-square amplitude [0.0, 1.0] (Overall energy)
    peak: float            # Peak sample magnitude [0.0, 1.0]
    bass: float            # Sub/Bass band energy (20 - 250 Hz) [0.0, 1.0]
    mids: float            # Midrange band energy (250 - 4000 Hz) [0.0, 1.0]
    treble: float          # High frequency band energy (4000 - 20000 Hz) [0.0, 1.0]
    spectrum: tuple[float, ...]  # 64-bin normalized log-spaced spectrum [0.0, 1.0]
    waveform: tuple[float, ...]  # 128 subsampled points [-1.0, 1.0]
    beat: bool             # Dynamic transient trigger
    strong_beat: bool      # Bass kick transient trigger


class AnalysisHandoff:
    """
    Thread-safe, non-blocking circular buffer handoff between high-priority
    audio output stream callbacks and visualizer/UI consumers.
    """
    def __init__(self, buffer_frames: int = 2048):
        self.buffer_frames = buffer_frames
        self._buffer = np.zeros((buffer_frames, 2), dtype=np.float32)
        self._lock = threading.Lock()
        
        # Beat tracking state
        self._energy_history: list[float] = []
        self._last_beat_time: float = 0.0

    def push_audio(self, pcm_chunk: np.ndarray) -> None:
        """
        Pushes a decoded PCM chunk from the audio callback thread.
        Ultra-fast (<20 microseconds), allocation-free.
        """
        n = len(pcm_chunk)
        if n == 0:
            return
        with self._lock:
            if n >= self.buffer_frames:
                self._buffer[:] = pcm_chunk[-self.buffer_frames:]
            else:
                self._buffer[:-n] = self._buffer[n:]
                self._buffer[-n:] = pcm_chunk

    def get_audio_frame(self, sr: int = 44100) -> AudioFrame:
        """
        Computes a normalized AudioFrame from the current PCM snapshot.
        Called on the UI/visualization timer (~60 Hz).
        """
        with self._lock:
            pcm = self._buffer.copy()

        mono = np.mean(pcm, axis=1) if pcm.ndim > 1 else pcm
        n = len(mono)
        if n == 0:
            return self._empty_frame()

        # 1. Amplitude metrics
        rms = float(np.sqrt(np.mean(mono**2)))
        peak = float(np.max(np.abs(mono)))

        # 2. Windowed FFT
        window = np.hanning(n)
        windowed = mono * window
        fft_complex = np.fft.rfft(windowed)
        fft_mag = (np.abs(fft_complex) / (n / 2.0)) * 4.0  # Scaled for visual responsiveness
        freqs = np.fft.rfftfreq(n, 1.0 / sr)

        # 3. Frequency bands
        bass_mask = (freqs >= 20) & (freqs <= 250)
        bass = min(1.0, float(np.mean(fft_mag[bass_mask]) * 3.0)) if np.any(bass_mask) else 0.0

        mids_mask = (freqs > 250) & (freqs <= 4000)
        mids = min(1.0, float(np.mean(fft_mag[mids_mask]) * 4.0)) if np.any(mids_mask) else 0.0

        treble_mask = (freqs > 4000) & (freqs <= 20000)
        treble = min(1.0, float(np.mean(fft_mag[treble_mask]) * 6.0)) if np.any(treble_mask) else 0.0

        # 4. Spectrum bins (64 log-spaced bins)
        bin_edges = np.geomspace(20, min(20000, sr / 2), 65)
        spectrum_bins = []
        for i in range(64):
            b_mask = (freqs >= bin_edges[i]) & (freqs < bin_edges[i + 1])
            val = float(np.mean(fft_mag[b_mask])) if np.any(b_mask) else 0.0
            spectrum_bins.append(min(1.0, val * 2.5))

        # 5. Subsampled waveform (128 points)
        step = max(1, n // 128)
        waveform = [float(x) for x in mono[::step][:128]]
        if len(waveform) < 128:
            waveform.extend([0.0] * (128 - len(waveform)))

        # 6. Dynamic Energy Variance Beat Detection
        now = time.time()
        instant_energy = rms ** 2
        self._energy_history.append(instant_energy)
        if len(self._energy_history) > 40:
            self._energy_history.pop(0)

        avg_energy = float(np.mean(self._energy_history)) if self._energy_history else 0.001
        variance = float(np.var(self._energy_history)) if self._energy_history else 0.0
        c = max(1.2, 1.5 - variance * 10)

        is_beat = False
        is_strong_beat = False
        if instant_energy > c * avg_energy and (now - self._last_beat_time) > 0.18:
            is_beat = True
            self._last_beat_time = now
            if bass > 0.35:
                is_strong_beat = True

        return AudioFrame(
            rms=min(1.0, rms * 1.5),
            peak=min(1.0, peak),
            bass=bass,
            mids=mids,
            treble=treble,
            spectrum=tuple(spectrum_bins),
            waveform=tuple(waveform),
            beat=is_beat,
            strong_beat=is_strong_beat
        )

    def _empty_frame(self) -> AudioFrame:
        return AudioFrame(
            rms=0.0,
            peak=0.0,
            bass=0.0,
            mids=0.0,
            treble=0.0,
            spectrum=tuple([0.0] * 64),
            waveform=tuple([0.0] * 128),
            beat=False,
            strong_beat=False
        )
