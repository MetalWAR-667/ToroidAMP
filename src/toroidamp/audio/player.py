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


def select_output_device(query_devices=sd.query_devices):
    """
    Capability-based output device policy (Linux audio reliability cut).

    Prefers a device literally named "pipewire" if PortAudio's ALSA host
    API exposes one -- modern Mint/Ubuntu desktops route audio through
    PipeWire, and PortAudio's ALSA "default" device typically reaches it
    through an extra ALSA userspace plugin chain (dmix/rate/plug) sitting
    *underneath* PipeWire's own graph. That chain negotiates its own
    buffering independently of what PortAudio requests, invisible to
    `pw-top`'s XRUN accounting (which only sees PipeWire's own nodes) --
    a plausible source of audible dropouts that don't show up as PipeWire
    underruns. Talking to the "pipewire" ALSA PCM directly removes that
    extra indirection layer.

    Returns None (PortAudio's own default device) on any system without a
    device named exactly "pipewire" -- Windows, macOS, and Linux systems
    not running PipeWire all fall through unchanged. This is a name-based
    capability check via `query_devices()`, not a platform/distro branch:
    it makes the same decision it always would if some future Windows
    audio backend happened to expose a device with that exact name.
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
    real-time output streaming, volume, seeking, smooth gain envelope fading,
    robust decoder failure isolation, and analysis handoff.
    """

    FADE_DURATION_SECONDS = 0.200 # 200 ms smooth envelope

    def __init__(self, handoff: AnalysisHandoff, custom_tracker_lib_path: str | None = None):
        self.handoff = handoff
        # RC-069-002B: renamed from custom_modplug_path — tracker playback
        # now uses libxmp, not libmodplug (which was never actually
        # available in this project's toolchain; see
        # docs/release/RC_069_002B_tracker_libxmp.md).
        self._custom_tracker_lib_path = custom_tracker_lib_path

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
        # Resolved once per process (device.py's query_devices() involves a
        # real host-API scan) rather than on every play(); None is a valid,
        # meaningful result (PortAudio default), so a separate flag tracks
        # whether resolution has actually happened yet.
        self._output_device: int | None = None
        self._output_device_resolved: bool = False

        # Playback-state semantics (STOP/EOF/seek stabilization cut).
        # Natural end-of-track (decoder genuinely ran out of frames) is a
        # distinct event from PlaybackState.STOPPED, which is *also* the
        # state a user-initiated stop lands in -- including the delayed
        # transition to STOPPED that a fade-out completes asynchronously
        # in the audio callback, well after PlayerEngine.stop() already
        # returned. Downstream playlist auto-advance must react to real
        # EOF only, never to "we're currently in the STOPPED state" alone.
        self._eof_pending: bool = False
        # Seek target awaiting application by the audio callback thread,
        # which owns exclusive decoder access while PLAYING (see seek()).
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

    def consume_natural_eof(self) -> bool:
        """
        Thread-safe check-and-clear of the natural-EOF flag. Returns True
        exactly once per genuine end-of-track completion (the decoder
        returned zero frames) -- never for a user-initiated stop, even one
        that finishes an in-progress fade-out asynchronously in the audio
        callback well after stop()/stop_immediate() already returned.
        This is the only signal playlist auto-advance should react to.
        """
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
            return self._active_decoder is self._tracker_decoder and self._tracker_decoder is not None

    def _get_tracker_decoder(self) -> TrackerDecoder:
        if self._tracker_decoder is None:
            self._tracker_decoder = TrackerDecoder(self._custom_tracker_lib_path)
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

            try:
                # RC-069-002: tracker-decoder CONSTRUCTION (which raises
                # RuntimeError when the native tracker library is
                # unavailable — no longer true in this dev environment as
                # of RC-069-002B's migration to libxmp, but this failure
                # path still matters on any machine where it genuinely is
                # missing) now shares the exact same try/except as
                # decoder.load() below, instead of being constructed
                # before this block. Previously, a missing
                # native tracker backend bypassed `_decoder_failed`/
                # `_last_error_msg` entirely — invisible to `_tick()`'s
                # normal decoder-failure poll (window_manager.py), which is
                # what drives the existing clean "log + auto-advance/stop"
                # behavior every other decode failure already gets. This
                # was a real, silent product gap: playlist selection would
                # visibly move to the failed track with no playback, no
                # error surfaced, and no auto-advance — exactly the
                # "mysterious failure with no clear diagnostic" this cut's
                # tracker-failure-semantics requirement exists to close.
                if ext in [".mod", ".xm", ".it", ".s3m"]:
                    decoder = self._get_tracker_decoder()
                else:
                    decoder = self._conventional_decoder
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
                if not self._output_device_resolved:
                    self._output_device = select_output_device()
                    self._output_device_resolved = True

                self._stream = sd.OutputStream(
                    samplerate=self._sample_rate,
                    channels=2,
                    dtype="float32",
                    callback=self._audio_callback,
                    # blocksize=0: let PortAudio/the host API negotiate its
                    # own natural chunk size instead of forcing a fixed 512
                    # frames. Linux dropout investigation: a fixed block
                    # size not evenly served by the underlying ALSA/
                    # PipeWire buffering chain is a well-documented source
                    # of exactly the intermittent stutter reported here,
                    # with no XRUN showing in pw-top (that chain sits below
                    # PipeWire's own graph). _audio_callback already reads
                    # `frames` dynamically, never assumes 512, so this is
                    # a config-only change.
                    blocksize=0,
                    device=self._output_device,
                )
                self._stream.start()
                # Diagnostics only -- must never take playback down with it.
                try:
                    logger.info(
                        "Audio stream started: device=%s samplerate=%s negotiated_blocksize=%s "
                        "negotiated_latency=%.4fs",
                        self._describe_output_device(self._output_device),
                        self._sample_rate,
                        self._stream.blocksize,
                        self._stream.latency,
                    )
                except Exception:
                    pass
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
            # USER_STOP is never natural EOF, even though the fade-out
            # path below completes asynchronously in the audio callback
            # (which sets state to STOPPED on its own once the envelope
            # reaches 0) well after this call already returned.
            self._eof_pending = False
            if self._fade_enabled and self._state == PlaybackState.PLAYING and self._stream is not None and self._fade_envelope > 0.05 and not self._decoder_failed:
                # Trigger fade-out in audio callback
                self._fade_state = FadeState.FADING_OUT
            else:
                self._do_stop()

    def stop_immediate(self) -> None:
        """Immediately stops playback stream and resets position."""
        with self._lock:
            self._eof_pending = False
            self._do_stop()

    def _do_stop(self) -> None:
        self._state = PlaybackState.STOPPED
        self._fade_state = FadeState.IDLE
        self._fade_envelope = 0.0
        self._eof_pending = False
        self._pending_seek_seconds = None
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

        While PLAYING, the actual decoder seek is deferred to the audio
        callback thread instead of applied here directly (see
        _audio_callback). The callback owns exclusive read/seek access to
        the decoder while it's actively pulling frames without holding
        self._lock (a deliberate real-time-safety choice -- the callback
        must never block on a lock the UI thread might hold); calling
        decoder.seek() from this thread at the same time raced that
        unlocked read against soundfile/libsndfile, which is not safe for
        concurrent access from two threads on the same handle. That race
        was the root cause of both an occasional spurious end-of-track
        (a corrupted read returning zero frames, misread as natural EOF)
        and audible playback interruption while dragging the timeline.
        Deferring to the callback also naturally coalesces rapid
        successive calls (e.g. a slider drag) to whichever target was set
        most recently before the callback next runs.

        While paused/stopped, no audio thread is reading concurrently, so
        the seek is applied immediately and synchronously as before.
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

    @staticmethod
    def _describe_output_device(device_index: int | None) -> str:
        """Best-effort human-readable device name for the one-line startup
        diagnostic -- never raises, always returns something loggable."""
        if device_index is None:
            return "PortAudio default"
        try:
            return f"{device_index}: {sd.query_devices(device_index)['name']}"
        except Exception:
            return f"index {device_index}"

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
            # Apply a pending seek before reading -- see seek()'s comment.
            # This thread is the only one that ever calls seek()/
            # read_frames() on the decoder while PLAYING, by design.
            pending_seek = self._pending_seek_seconds
            if pending_seek is not None:
                self._pending_seek_seconds = None
                self._active_decoder.seek(pending_seek)
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
            self._eof_pending = True
            return

        if not self._fade_enabled:
            # Bypass fade envelope completely
            self._fade_state = FadeState.PLAYING
            self._fade_envelope = 1.0
            gain = self._volume
            if num_read < frames:
                outdata[:num_read] = chunk * gain
                outdata[num_read:].fill(0)
                # Analysis handoff must stay independent of the user's
                # listening volume (self._volume) -- reactivity should
                # reflect musical content, not how loudly the user chose
                # to hear it. Push the decoded chunk unscaled by gain,
                # shaped like outdata (zero-padded past num_read, which
                # correctly reads as silence for a partial/EOF chunk).
                analysis_pcm = np.zeros_like(outdata)
                analysis_pcm[:num_read] = chunk
                self._state = PlaybackState.STOPPED
                self._fade_state = FadeState.IDLE
                self._fade_envelope = 0.0
                self._eof_pending = True
            else:
                outdata[:] = chunk * gain
                analysis_pcm = chunk

            self._position_seconds += num_read / float(self._sample_rate)
            self.handoff.push_audio(analysis_pcm)
            return

        # Compute gain envelope interpolation across this chunk. Vectorized
        # (Linux dropout investigation): a per-sample Python loop here ran
        # unconditionally on every real-time callback -- including the
        # steady-state PLAYING/IDLE cases where the envelope is simply
        # constant -- spending real-time callback budget on Python-level
        # iteration for no audible benefit. Produces bit-for-bit equivalent
        # output to the old loop (same linear ramp, same 0.9999/0.0001
        # snap-to-target thresholds, same mid-chunk state transition).
        fade_step = 1.0 / (self.FADE_DURATION_SECONDS * self._sample_rate)
        envelope_curve = np.empty((num_read, 1), dtype=np.float32)

        if self._fade_state == FadeState.PLAYING:
            envelope_curve[:, 0] = 1.0
            self._fade_envelope = 1.0
        elif self._fade_state == FadeState.IDLE:
            envelope_curve[:, 0] = 0.0
            self._fade_envelope = 0.0
        elif self._fade_state == FadeState.FADING_IN:
            ramp = self._fade_envelope + fade_step * np.arange(1, num_read + 1, dtype=np.float64)
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
            ramp = self._fade_envelope - fade_step * np.arange(1, num_read + 1, dtype=np.float64)
            hits = np.flatnonzero(ramp <= 0.0001)
            if hits.size:
                k = int(hits[0])
                envelope_curve[:k, 0] = ramp[:k]
                envelope_curve[k:, 0] = 0.0
                self._fade_envelope = 0.0
                self._fade_state = FadeState.IDLE
            else:
                envelope_curve[:, 0] = ramp
                self._fade_envelope = float(ramp[-1])

        # Apply gain envelope and master user volume
        gain = envelope_curve * self._volume
        if num_read < frames:
            outdata[:num_read] = chunk * gain
            outdata[num_read:].fill(0)
            # Analysis handoff tracks the fade envelope (real audio
            # presence -- silent during an actual fade-out/fade-in edge)
            # but never the user's listening volume (self._volume), so
            # reactivity reflects musical content rather than how loudly
            # the user chose to hear it.
            analysis_pcm = np.zeros_like(outdata)
            analysis_pcm[:num_read] = chunk * envelope_curve
            self._state = PlaybackState.STOPPED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0
            # The decoder itself ran out of frames -- genuine EOF -- even
            # if a user-initiated fade-out also happened to be in
            # progress this same callback; the track really did end.
            self._eof_pending = True
        else:
            outdata[:] = chunk * gain
            analysis_pcm = chunk * envelope_curve

        self._position_seconds += num_read / float(self._sample_rate)

        # If fade-out completed during this frame, complete stopping
        if self._fade_state == FadeState.IDLE and self._fade_envelope <= 0.0:
            self._state = PlaybackState.STOPPED

        # Push to analysis handoff
        self.handoff.push_audio(analysis_pcm)
