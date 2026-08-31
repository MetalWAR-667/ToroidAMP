"""
ToroidAMP - Voice Synthesis Service
Provides asynchronous identity audio announcement and sound effect barks
isolated completely from music playback and visualizers.
Reuses the proven robotic dual-channel stereo delay recipe.
"""

import logging
import os
import sys
import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf

from .player import select_output_device

logger = logging.getLogger("toroidamp.voice")

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# RELEASE-BLOCKERS-001: voice playback previously went through
# pygame.mixer/SDL -- an entirely separate native audio stack from the one
# music playback uses (sounddevice/PortAudio). That second stack's Linux
# device lifecycle proved unreliable across repeated launches (synthesis
# always succeeded; audible playback did not) even after explicitly
# reconfiguring and quitting the mixer each time (UBUNTU-WAYLAND-002).
# Rather than continue chasing pygame.mixer/SDL's own PipeWire handshake,
# voice playback now decodes the synthesized WAV (via `soundfile`, the same
# library ConventionalDecoder already uses for music) and plays it through
# `sounddevice`, the exact backend + device-selection policy
# (`select_output_device()`) already validated for reliable Ubuntu/PipeWire
# music playback. `sd.play()` opens its own independent PortAudio stream,
# separate from PlayerEngine's -- PipeWire is a software mixing server, so
# a short concurrent voice line and ongoing music playback both reaching
# the same named "pipewire" device is expected to multiplex cleanly rather
# than fight over exclusive device ownership.
_playback_lock = threading.Lock()


class VoiceService:
    """
    Synthesizes and plays identity speech phrases asynchronously
    using native OS TTS engines via pyttsx3, temporary WAV generation,
    and robotic dual-channel stereo delay.
    """


    STARTUP_LINE = "ToroidAMP... It really warps the toroid's ass!"

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._is_speaking = False
        # Kept alive deliberately -- see the ownership note in
        # _synthesize_and_play() below (Linux eSpeak lifecycle fix).
        self._current_engine = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak_startup_phrase_async(self, phrase: str | None = None) -> None:
        """
        Synthesizes and plays the startup identity line asynchronously.
        Non-blocking: returns immediately so UI remains responsive.

        LINUX-TTS-001 (Deferred Platform Feature for v0.667):
        On Linux, native TTS synthesis via pyttsx3's eSpeak driver operates
        asynchronously in C/ctypes without synchronizing WAV file generation to
        the main thread before event pump termination, resulting in intermittent
        silence, /tmp pollution, and native ctypes callback lifecycle races.
        Automatic startup voice is cleanly deferred on Linux for v0.667 while
        remaining fully enabled and supported on Windows (SAPI5).
        """
        text = phrase or self.STARTUP_LINE
        if not TTS_AVAILABLE:
            logger.info(f"TTS engine not available. Skipping voice line: '{text}'")
            return

        if sys.platform.startswith("linux"):
            logger.info("Startup voice disabled on Linux (deferred platform support).")
            return

        self._thread = threading.Thread(
            target=self._synthesize_and_play,
            args=(text,),
            name="ToroidAMP-VoiceThread",
            daemon=True
        )
        self._thread.start()

    def _synthesize_and_play(self, text: str) -> None:
        self._is_speaking = True
        temp_wav_path = None
        playback_lock_held = False
        try:
            # 1. Synthesize to temporary WAV file matching MetalWar-Installer parameters
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_wav_path = tmp.name

            engine = pyttsx3.init()
            # Ownership note (Linux TTS lifecycle fix): pyttsx3's eSpeak
            # driver registers its synthesis-progress ctypes callback
            # (EspeakDriver._onSynth) against a weak reference to the
            # engine/driver. `runAndWait()` is not guaranteed to have that
            # callback fully quiesced by the time it returns on this
            # backend -- an explicit `del engine` immediately afterward
            # (as this code used to do) could drop the last strong
            # reference while eSpeak's C library still had that callback
            # in flight, so it fired against an already-collected weak
            # referent: `ReferenceError: weakly-referenced object no
            # longer exists`, raised from a ctypes callback trampoline
            # where Python can only log and ignore it -- the synthesis
            # itself had already produced a valid WAV file, but the
            # exception was noisy and the engine's teardown was unclean.
            # Keeping a strong reference on `self` for the engine's whole
            # natural lifetime (replaced only by the next synthesis call,
            # never explicitly deleted) gives any trailing native callback
            # a live object to find, instead of forcing early collection.
            # This is a Windows SAPI5 no-op: that driver's own COM
            # reference counting is unaffected by this change.
            self._current_engine = engine
            # Donor Voice Selection Logic: search for 'zira' (Windows female)
            for voice in engine.getProperty("voices"):
                if "zira" in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break

            # Donor Speech Parameters: rate=145, volume=1.0
            engine.setProperty("rate", 145)
            engine.setProperty("volume", 1.0)
            engine.save_to_file(text, temp_wav_path)
            engine.runAndWait()

            # 2. Reproduce the robotic dual-channel stereo delay (20ms
            # inter-channel delay, 0.9 secondary volume) by mixing it
            # directly into a single PCM buffer rather than relying on two
            # separate mixer channels -- this guarantees the exact timing/
            # gain relationship deterministically instead of depending on
            # the OS mixer to sum two independently-scheduled channels.
            if os.path.exists(temp_wav_path) and os.path.getsize(temp_wav_path) > 0:
                data, sr = sf.read(temp_wav_path, dtype="float32", always_2d=True)
                if data.shape[1] == 1:
                    data = np.column_stack((data[:, 0], data[:, 0]))
                elif data.shape[1] > 2:
                    data = data[:, :2]

                delay_frames = int(0.02 * sr)  # Donor: 20ms stereo delay
                secondary = np.zeros_like(data)
                if delay_frames < len(data):
                    secondary[delay_frames:] = data[: len(data) - delay_frames] * 0.9  # Donor: 0.9 secondary channel volume
                mixed = np.clip(data + secondary, -1.0, 1.0)

                if not _playback_lock.acquire(timeout=10.0):
                    # Another VoiceService call has been mixing/playing for
                    # an unreasonably long time -- fail loudly rather than
                    # hang this thread waiting on it forever.
                    logger.warning(f"Voice phrase synthesized but playback was skipped: a previous voice playback did not release its output device in time: '{text}'")
                else:
                    playback_lock_held = True
                    device = select_output_device()
                    sd.play(mixed, samplerate=sr, device=device)
                    sd.wait()
                    # sd.wait() blocks until this stream's playback has
                    # actually completed (or raises) -- unlike the old
                    # pygame-channel `get_busy()` polling, there is no
                    # "reported success but nothing audible" gap here:
                    # either this line is reached because the device
                    # genuinely played the buffer through, or an exception
                    # below was raised instead.
                    logger.info(f"Voice phrase playback completed on device={device if device is not None else 'default'}: '{text}'")

        except Exception as e:
            logger.warning(f"Voice synthesis/playback failed gracefully: {e}")
        finally:
            self._is_speaking = False
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass
            if playback_lock_held:
                _playback_lock.release()
