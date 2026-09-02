"""
ToroidAMP - Unified Audio Player Engine
Coordinates decoding, crossfade mixing, transport micro-fades, ReplayGain/normalization,
real-time stream output, and analysis handoff.
"""

from enum import Enum, auto
import math
import os
import threading
from typing import Optional
import numpy as np
import sounddevice as sd

from .decoders import AudioDecoder, ConventionalDecoder, TrackerDecoder
from .replaygain import estimate_track_gain, apply_safety_limiter
from ..analysis.audio_frame import AnalysisHandoff

import logging

logger = logging.getLogger("toroidamp.player")


def select_output_device(query_devices=sd.query_devices):
    """
    Capability-based output device policy (Linux audio reliability cut).
    Prefers a device named 'pipewire' if present, falls back to PortAudio default (None).
    """
    try:
        devices = query_devices()
    except Exception as e:
        logger.warning(f"Could not enumerate audio devices, using PortAudio default: {e}")
        return None

    for idx, dev in enumerate(devices):
        name = str(dev.get("name", "")).strip().lower()
        if name == "pipewire" and dev.get("max_output_channels", 0) > 0:
            return idx
    return None


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
    gapless & crossfade playback, transport micro-fades, loudness normalization,
    real-time output streaming, volume, seeking, and analysis handoff.
    """

    FADE_DURATION_SECONDS = 0.200       # 200 ms standard envelope fade
    MICRO_FADE_DURATION_SECONDS = 0.025 # 25 ms transport micro-fade (DSP-001A)

    def __init__(self, handoff: AnalysisHandoff, custom_tracker_lib_path: str | None = None):
        self.handoff = handoff
        self._custom_tracker_lib_path = custom_tracker_lib_path

        self._conventional_decoder = ConventionalDecoder()
        self._tracker_decoder: TrackerDecoder | None = None
        self._active_decoder: AudioDecoder | None = None

        # Crossfade outgoing decoder (DSP-001B)
        self._outgoing_decoder: AudioDecoder | None = None
        self._crossfade_total_frames: int = 0
        self._crossfade_remaining_frames: int = 0
        self._crossfade_duration: float = 0.0  # 0.0 = OFF, 0.5, 1.0, 1.5, 2.0 (DSP-001B)

        # Loudness normalization & track gain (DSP-001C)
        self._normalization_enabled: bool = False
        self._current_track_gain: float = 1.0
        self._outgoing_track_gain: float = 1.0

        self._state = PlaybackState.STOPPED
        self._fade_state = FadeState.IDLE
        self._fade_envelope: float = 0.0  # 0.0 to 1.0 multiplier
        self._fade_enabled: bool = True
        self._volume: float = 0.8
        self._current_filepath: str = ""
        self._sample_rate: int = 44100

        # Micro-fade transition flags (DSP-001A)
        self._pause_requested: bool = False
        self._seek_micro_fade_pending: bool = False

        # Robust decoder failure tracking
        self._generation: int = 0
        self._decoder_failed: bool = False
        self._last_error_generation: int = 0
        self._last_error_path: str = ""
        self._last_error_msg: str = ""

        self._stream: sd.OutputStream | None = None
        self._lock = threading.Lock()
        self._position_seconds: float = 0.0
        self._output_device: int | None = None
        self._output_device_resolved: bool = False

        self._eof_pending: bool = False
        self._pending_seek_seconds: float | None = None

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
    def crossfade_duration(self) -> float:
        return self._crossfade_duration

    @crossfade_duration.setter
    def crossfade_duration(self, duration_seconds: float) -> None:
        with self._lock:
            self._crossfade_duration = max(0.0, min(5.0, float(duration_seconds)))

    @property
    def normalization_enabled(self) -> bool:
        return self._normalization_enabled

    @normalization_enabled.setter
    def normalization_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._normalization_enabled = bool(enabled)
            if self._normalization_enabled and self._current_filepath:
                self._current_track_gain = estimate_track_gain(self._current_filepath)
            else:
                self._current_track_gain = 1.0

    @property
    def current_track_gain(self) -> float:
        return self._current_track_gain

    @property
    def fade_state(self) -> FadeState:
        return self._fade_state

    @property
    def decoder_failed(self) -> bool:
        with self._lock:
            return self._decoder_failed

    def check_and_clear_error(self) -> tuple[bool, str, str]:
        """Thread-safe check and consume of decoder error status."""
        with self._lock:
            if self._decoder_failed:
                failed_path = self._last_error_path
                msg = self._last_error_msg
                self._decoder_failed = False
                return True, failed_path, msg
            return False, "", ""

    def consume_natural_eof(self) -> bool:
        """Thread-safe check-and-clear of the natural-EOF flag."""
        with self._lock:
            if self._eof_pending:
                self._eof_pending = False
                return True
            return False

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
            return isinstance(self._active_decoder, TrackerDecoder)

    def _get_tracker_decoder(self) -> TrackerDecoder:
        return TrackerDecoder(self._custom_tracker_lib_path)

    def _create_decoder_for_file(self, filepath: str) -> AudioDecoder:
        ext = os.path.splitext(filepath)[1].lower()
        if ext in [".mod", ".xm", ".it", ".s3m"]:
            return self._get_tracker_decoder()
        return ConventionalDecoder()

    def load(self, filepath: str) -> None:
        """Loads a file and switches to the appropriate decoder."""
        self.stop_immediate()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with self._lock:
            self._generation += 1
            self._decoder_failed = False
            self._current_filepath = filepath
            self._close_outgoing_decoder()

            try:
                decoder = self._create_decoder_for_file(filepath)
                decoder.load(filepath)
                self._active_decoder = decoder
                self._sample_rate = decoder.get_sample_rate()
                self._position_seconds = 0.0
                if self._normalization_enabled:
                    self._current_track_gain = estimate_track_gain(filepath)
                else:
                    self._current_track_gain = 1.0
            except Exception as e:
                self._decoder_failed = True
                self._last_error_generation = self._generation
                self._last_error_path = filepath
                self._last_error_msg = str(e)
                self._active_decoder = None
                logger.error(f"Failed to load audio file '{filepath}': {e}")
                raise

    def load_and_crossfade(self, filepath: str, duration_seconds: Optional[float] = None) -> bool:
        """
        Loads the next track and initiates an equal-power crossfade transition (DSP-001B).
        If crossfade is disabled (duration=0.0 or not playing), falls back to normal load & play.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with self._lock:
            xf_dur = duration_seconds if duration_seconds is not None else self._crossfade_duration
            if self._state != PlaybackState.PLAYING or self._active_decoder is None or xf_dur <= 0.0:
                self.load(filepath)
                self.play()
                return True

            try:
                new_decoder = self._create_decoder_for_file(filepath)
                new_decoder.load(filepath)
                new_sr = new_decoder.get_sample_rate()

                # If sample rates differ, fallback to normal load to avoid pitch mismatch
                if new_sr != self._sample_rate:
                    self.load(filepath)
                    self.play()
                    return True

                # Clamp crossfade duration if next track is very short
                dur = new_decoder.get_duration()
                if dur > 0.0 and xf_dur > dur * 0.75:
                    xf_dur = max(0.2, dur * 0.5)

                self._close_outgoing_decoder()
                self._outgoing_decoder = self._active_decoder
                self._outgoing_track_gain = self._current_track_gain

                self._active_decoder = new_decoder
                self._current_filepath = filepath
                self._position_seconds = 0.0
                self._generation += 1

                if self._normalization_enabled:
                    self._current_track_gain = estimate_track_gain(filepath)
                else:
                    self._current_track_gain = 1.0

                self._crossfade_total_frames = max(1, int(xf_dur * self._sample_rate))
                self._crossfade_remaining_frames = self._crossfade_total_frames

                logger.info(f"Crossfade initiated ({xf_dur:.2f}s) to: {filepath}")
                return True
            except Exception as e:
                logger.warning(f"Crossfade load failed for '{filepath}': {e}. Falling back to standard load.")
                self.load(filepath)
                self.play()
                return False

    def play(self) -> None:
        with self._lock:
            if self._active_decoder is None or self._decoder_failed:
                return

            self._pause_requested = False

            if self._stream is None:
                if not self._output_device_resolved:
                    self._output_device = select_output_device()
                    self._output_device_resolved = True

                self._stream = sd.OutputStream(
                    samplerate=self._sample_rate,
                    channels=2,
                    dtype="float32",
                    callback=self._audio_callback,
                    blocksize=0,
                    device=self._output_device,
                )
                self._stream.start()

            was_paused = (self._state == PlaybackState.PAUSED)
            self._state = PlaybackState.PLAYING

            if was_paused:
                # Resume micro-fade in (DSP-001A)
                self._fade_state = FadeState.FADING_IN
                self._fade_envelope = 0.0
            elif self._fade_enabled:
                self._fade_state = FadeState.FADING_IN
            else:
                self._fade_state = FadeState.PLAYING
                self._fade_envelope = 1.0

    def pause(self) -> None:
        """Pauses playback with a 25 ms micro-fade-out (DSP-001A)."""
        with self._lock:
            if self._state == PlaybackState.PLAYING and self._fade_envelope > 0.05 and not self._decoder_failed and self._active_decoder is not None:
                self._pause_requested = True
                self._fade_state = FadeState.FADING_OUT
            else:
                self._state = PlaybackState.PAUSED
                self._fade_state = FadeState.IDLE
                self._fade_envelope = 0.0

    def stop(self) -> None:
        """Stops playback with a smooth fade-out (standard or 25ms micro-fade)."""
        with self._lock:
            self._eof_pending = False
            self._pause_requested = False
            if self._state == PlaybackState.PLAYING and self._fade_envelope > 0.05 and not self._decoder_failed and self._active_decoder is not None:
                self._fade_state = FadeState.FADING_OUT
            else:
                self._do_stop()


    def stop_immediate(self) -> None:
        """Immediately stops playback stream and resets state."""
        with self._lock:
            self._eof_pending = False
            self._pause_requested = False
            self._do_stop()

    def _close_outgoing_decoder(self) -> None:
        if self._outgoing_decoder:
            try:
                self._outgoing_decoder.close()
            except Exception:
                pass
            self._outgoing_decoder = None
        self._crossfade_total_frames = 0
        self._crossfade_remaining_frames = 0

    def _do_stop(self) -> None:
        self._state = PlaybackState.STOPPED
        self._fade_state = FadeState.IDLE
        self._fade_envelope = 0.0
        self._eof_pending = False
        self._pending_seek_seconds = None
        self._close_outgoing_decoder()
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
        Safely seeks the active decoder to target_seconds with micro-fade protection.
        """
        with self._lock:
            if self._decoder_failed or self._active_decoder is None:
                return False

            if self._state == PlaybackState.PLAYING:
                self._pending_seek_seconds = target_seconds
                self._position_seconds = target_seconds
                return True

            try:
                self._active_decoder.seek(target_seconds)
                self._position_seconds = target_seconds
                return True
            except Exception as e:
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
            self._close_outgoing_decoder()
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
        High-priority real-time audio callback.
        Handles crossfade mixing, sample-accurate micro-fades, ReplayGain/normalization,
        and analysis handoff.
        """
        if self._state != PlaybackState.PLAYING or self._active_decoder is None or self._decoder_failed:
            outdata.fill(0)
            return

        callback_gen = self._generation
        try:
            # 1. Apply pending seek with micro-fade protection (DSP-001A)
            pending_seek = self._pending_seek_seconds
            seek_just_performed = False
            if pending_seek is not None:
                self._pending_seek_seconds = None
                self._close_outgoing_decoder()
                self._active_decoder.seek(pending_seek)
                seek_just_performed = True

            # 2. Read frames from active decoder
            chunk_in = self._active_decoder.read_frames(frames)
            num_read = len(chunk_in)

            # Pad active chunk to frames if partial
            if num_read < frames:
                padded_in = np.zeros((frames, 2), dtype=np.float32)
                if num_read > 0:
                    padded_in[:num_read] = chunk_in
                chunk_in = padded_in

            # 3. Read and mix outgoing decoder during crossfade (DSP-001B)
            if self._outgoing_decoder is not None and self._crossfade_remaining_frames > 0:
                chunk_out = self._outgoing_decoder.read_frames(frames)
                if len(chunk_out) < frames:
                    padded_out = np.zeros((frames, 2), dtype=np.float32)
                    if len(chunk_out) > 0:
                        padded_out[:len(chunk_out)] = chunk_out
                    chunk_out = padded_out

                # Equal-power crossfade curve: cos(p * pi/2) and sin(p * pi/2)
                total_xf = float(self._crossfade_total_frames)
                p0 = 1.0 - (float(self._crossfade_remaining_frames) / total_xf)
                p1 = 1.0 - (float(max(0, self._crossfade_remaining_frames - frames)) / total_xf)
                progress = np.linspace(p0, p1, frames, dtype=np.float32)[:, None]
                progress = np.clip(progress, 0.0, 1.0)

                g_out = np.cos(progress * (math.pi / 2.0))
                g_in = np.sin(progress * (math.pi / 2.0))

                # Apply track gains and mix
                in_scaled = chunk_in * self._current_track_gain * g_in
                out_scaled = chunk_out * self._outgoing_track_gain * g_out
                playback_pcm = in_scaled + out_scaled

                self._crossfade_remaining_frames -= frames
                if self._crossfade_remaining_frames <= 0:
                    self._close_outgoing_decoder()
            else:
                playback_pcm = chunk_in * self._current_track_gain
                self._close_outgoing_decoder()

        except Exception as e:
            outdata.fill(0)
            with self._lock:
                if self._generation == callback_gen:
                    self._decoder_failed = True
                    self._last_error_generation = callback_gen
                    self._last_error_path = self._current_filepath
                    self._last_error_msg = f"Read error: {e}"
                    self._state = PlaybackState.STOPPED
                    self._fade_state = FadeState.IDLE
                    self._fade_envelope = 0.0
            return

        # 4. End-of-file check
        if num_read == 0 and self._outgoing_decoder is None:
            outdata.fill(0)
            self._state = PlaybackState.STOPPED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0
            self._eof_pending = True
            return

        # 5. Apply micro-fade in across seek boundary to eliminate click
        if seek_just_performed:
            seek_ramp_len = min(num_read, int(self.MICRO_FADE_DURATION_SECONDS * self._sample_rate))
            if seek_ramp_len > 0:
                seek_ramp = np.linspace(0.0, 1.0, seek_ramp_len, dtype=np.float32)[:, None]
                playback_pcm[:seek_ramp_len] *= seek_ramp

        # 6. Envelope calculation (Standard 200ms or Micro-Fade 25ms)
        envelope_curve = np.empty((frames, 1), dtype=np.float32)

        fade_dur = self.MICRO_FADE_DURATION_SECONDS if (self._pause_requested or not self._fade_enabled) else self.FADE_DURATION_SECONDS
        fade_step = 1.0 / max(0.001, (fade_dur * self._sample_rate))

        if self._fade_state == FadeState.PLAYING and not self._pause_requested:
            envelope_curve[:, 0] = 1.0
            self._fade_envelope = 1.0
        elif self._fade_state == FadeState.IDLE:
            envelope_curve[:, 0] = 0.0
            self._fade_envelope = 0.0
        elif self._fade_state == FadeState.FADING_IN:
            ramp = self._fade_envelope + fade_step * np.arange(1, frames + 1, dtype=np.float64)
            hits = np.flatnonzero(ramp >= 0.9999)
            if hits.size:
                k = int(hits[0])
                envelope_curve[:k, 0] = ramp[:k]
                envelope_curve[k:, 0] = 1.0
                self._fade_envelope = 1.0
                self._fade_state = FadeState.PLAYING
            else:
                envelope_curve[:, 0] = ramp
                self._fade_envelope = float(ramp[-1])
        else:  # FADING_OUT
            ramp = self._fade_envelope - fade_step * np.arange(1, frames + 1, dtype=np.float64)
            hits = np.flatnonzero(ramp <= 0.0001)
            if hits.size:
                k = int(hits[0])
                envelope_curve[:k, 0] = ramp[:k]
                envelope_curve[k:, 0] = 0.0
                self._fade_envelope = 0.0
                self._fade_state = FadeState.IDLE
                if self._pause_requested:
                    self._state = PlaybackState.PAUSED
                    self._pause_requested = False
                else:
                    self._state = PlaybackState.STOPPED
            else:
                envelope_curve[:, 0] = ramp
                self._fade_envelope = float(ramp[-1])

        # Apply envelope to playback PCM
        enveloped_pcm = playback_pcm * envelope_curve

        # 7. Analysis handoff: receives post-mix, post-envelope, leveled signal PRE-USER-VOLUME
        # Visualizers see actual musical playback dynamics independent of master volume knob
        analysis_pcm = np.zeros_like(outdata)
        if num_read > 0 or self._outgoing_decoder is not None:
            analysis_pcm[:] = enveloped_pcm[:frames]
        self.handoff.push_audio(analysis_pcm)

        # 8. Apply master user volume (self._volume is normalized [0.0, 1.0],
        # so it can only reduce magnitude, never introduce new overs -- the
        # limiter must run on this, the actual final output signal, not on
        # the pre-volume one. Limiting pre-volume was a real bug: source
        # material peaking at exactly 1.0 (common -- many masters hit 0
        # dBFS) triggered the limiter's soft knee unconditionally, shaving
        # ~1.3% off *every* sample regardless of how low the user's volume
        # was set -- work the limiter had no reason to do, since a signal
        # already being scaled down by volume was never going to clip.
        volume_pcm = enveloped_pcm * self._volume

        # 9. Soft safety limiter to prevent overs (> 1.0) in the actual
        # output -- still catches a genuine over from RMS/ReplayGain
        # leveling gain (applied earlier, in `playback_pcm`) combined with
        # a high volume setting; just no longer fires needlessly at low
        # volume or on unboosted full-scale source material.
        outdata[:] = apply_safety_limiter(volume_pcm)

        if num_read > 0:
            self._position_seconds += num_read / float(self._sample_rate)

        # If partial buffer at end of track without active crossfade, mark EOF
        if num_read < frames and self._outgoing_decoder is None:
            self._state = PlaybackState.STOPPED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0
            self._eof_pending = True
