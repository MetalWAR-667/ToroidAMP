"""
ToroidAMP - Voice Synthesis Service
Provides asynchronous identity audio announcement and sound effect barks
isolated completely from music playback and visualizers.
Reuses the exact robotic dual-channel delay recipe from MetalWar-Installer.
"""

import logging
import os
import tempfile
import threading
import time
import pygame

logger = logging.getLogger("toroidamp.voice")

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class VoiceService:
    """
    Synthesizes and plays identity speech phrases asynchronously
    using native OS TTS engines via pyttsx3, temporary WAV generation,
    and the human-approved MetalWar-Installer robotic dual-channel stereo delay.
    """

    STARTUP_LINE = "ToroidAMP... It really warps the toroid's ass!"

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak_startup_phrase_async(self, phrase: str | None = None) -> None:
        """
        Synthesizes and plays the startup identity line asynchronously.
        Non-blocking: returns immediately so UI remains responsive.
        """
        text = phrase or self.STARTUP_LINE
        if not TTS_AVAILABLE:
            logger.info(f"TTS engine not available. Skipping voice line: '{text}'")
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
        try:
            # 1. Synthesize to temporary WAV file matching MetalWar-Installer parameters
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_wav_path = tmp.name

            engine = pyttsx3.init()
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
            del engine

            # 2. Reproduce exact MetalWar-Installer robotic playback:
            # Dual pygame mixer channels with 20ms inter-channel delay and 0.9 secondary volume
            if os.path.exists(temp_wav_path) and os.path.getsize(temp_wav_path) > 0:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(44100, -16, 2, 1024)

                sound = pygame.mixer.Sound(temp_wav_path)
                c1 = pygame.mixer.find_channel()
                c2 = pygame.mixer.find_channel()

                if c1:
                    c1.set_volume(1.0)
                    c1.play(sound)

                if c2:
                    time.sleep(0.02)  # Donor: 20ms stereo delay
                    c2.set_volume(0.9) # Donor: 0.9 secondary channel volume
                    c2.play(sound)

                # Wait for sound to complete on the primary channel
                if c1:
                    while c1.get_busy():
                        time.sleep(0.05)
                else:
                    time.sleep(sound.get_length())

                logger.info(f"Voice phrase announced with robotic parity: '{text}'")

        except Exception as e:
            logger.warning(f"Voice synthesis/playback failed gracefully: {e}")
        finally:
            self._is_speaking = False
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass
