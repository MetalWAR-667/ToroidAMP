"""
ToroidAMP - ReplayGain, Level Normalization & Safety Limiter Subsystem
Provides lightweight metadata extraction, conservative fallback leveling,
and transparent soft-knee limiting without dynamic pumping or heavy dependencies.
"""

import math
import os
import re
from typing import Optional
import numpy as np
import soundfile as sf

# Regex pattern matching standard ReplayGain track gain strings, e.g. "-6.5 dB", "+2.1 dB", "-4.2"
_REPLAYGAIN_PATTERN = re.compile(r"replaygain_track_gain\s*[:=]\s*([+-]?\d+(?:\.\d+)?)\s*(?:db)?", re.IGNORECASE)


def parse_replaygain_tags(filepath: str) -> Optional[float]:
    """
    Parses ReplayGain track gain tags from audio metadata (FLAC, OGG, WAV, MP3).
    Returns linear gain multiplier if tag exists, or None.
    """
    if not os.path.exists(filepath):
        return None

    try:
        # 1. Try reading extra_info and comment metadata from SoundFile
        with sf.SoundFile(filepath, mode="r") as sfile:
            extra_info = getattr(sfile, "extra_info", "") or ""
            comment = getattr(sfile, "comment", "") or ""
            combined_meta = f"{extra_info}\n{comment}"

            match = _REPLAYGAIN_PATTERN.search(combined_meta)
            if match:
                gain_db = float(match.group(1))
                # Clamp ReplayGain to conservative range [-9.0 dB, +6.0 dB]
                gain_db = max(-9.0, min(6.0, gain_db))
                return math.pow(10.0, gain_db / 20.0)
    except Exception:
        pass

    # 2. Fast scan of initial header bytes for ID3 / Vorbis comment text (up to 32KB)
    try:
        with open(filepath, "rb") as f:
            header_chunk = f.read(32768)
        text_chunk = header_chunk.decode("latin-1", errors="ignore")
        match = _REPLAYGAIN_PATTERN.search(text_chunk)
        if match:
            gain_db = float(match.group(1))
            gain_db = max(-9.0, min(6.0, gain_db))
            return math.pow(10.0, gain_db / 20.0)
    except Exception:
        pass

    return None


def calculate_fallback_leveling(pcm_sample: np.ndarray, target_db: float = -16.0) -> float:
    """
    Calculates conservative track leveling gain from a representative PCM sample.
    Clamps gain adjustment strictly to [-6.0 dB, +6.0 dB] to preserve dynamics.
    Returns linear gain multiplier.
    """
    if pcm_sample is None or len(pcm_sample) == 0:
        return 1.0

    rms = float(np.sqrt(np.mean(pcm_sample ** 2)))
    if rms < 0.001 or not np.isfinite(rms):
        return 1.0

    rms_db = 20.0 * math.log10(rms)
    gain_db = target_db - rms_db
    # Conservative clamp [-6.0 dB, +6.0 dB] (linear range [0.50, 2.0])
    gain_db = max(-6.0, min(6.0, gain_db))
    return math.pow(10.0, gain_db / 20.0)


def estimate_track_gain(filepath: str, sample_frames: Optional[np.ndarray] = None) -> float:
    """
    Estimates track gain for normalization:
    1. Prefers ReplayGain metadata if present.
    2. Falls back to conservative RMS leveling if audio samples are provided or readable.
    3. Defaults to 1.0 (unity gain) on error or silence.
    """
    # 1. Check ReplayGain metadata
    rg_gain = parse_replaygain_tags(filepath)
    if rg_gain is not None:
        return rg_gain

    # 2. If PCM sample is provided directly (e.g. from tracker decoder excerpt)
    if sample_frames is not None and len(sample_frames) > 0:
        return calculate_fallback_leveling(sample_frames)

    # 3. Otherwise read initial 2 seconds for conventional files
    try:
        with sf.SoundFile(filepath, mode="r") as sfile:
            sr = sfile.samplerate
            frames_to_read = min(len(sfile), int(sr * 2.0))
            if frames_to_read > 0:
                data = sfile.read(frames=frames_to_read, dtype="float32", always_2d=True)
                return calculate_fallback_leveling(data)
    except Exception:
        pass

    return 1.0


def apply_safety_limiter(pcm: np.ndarray) -> np.ndarray:
    """
    Fast, transparent soft-knee safety limiter.
    Signals with |x| <= 0.95 pass through 100% linearly with 0 distortion.
    Signals with |x| > 0.95 are smoothly compressed using a hyperbolic tangent knee asymptotic to 1.0.
    Guarantees output is strictly bounded to (-1.0, 1.0) without hard clipping clicks.
    """
    if pcm is None or len(pcm) == 0:
        return pcm

    abs_pcm = np.abs(pcm)
    over_mask = abs_pcm > 0.95
    if not np.any(over_mask):
        return pcm

    limited = np.copy(pcm)
    excess = abs_pcm[over_mask] - 0.95
    scale = (0.95 + 0.049 * np.tanh(excess * 20.0)) / abs_pcm[over_mask]
    limited[over_mask] *= scale
    return limited
