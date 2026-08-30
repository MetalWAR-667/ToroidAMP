"""
ToroidAMP - Reactive Spectral Neon Controller Subsystem
Provides continuous baseline breathing, restrained spectral color blending (Bass -> Violet/Magenta,
Mids -> Electric Cyan/Blue, Treble -> Ice Blue/White Cyan), dynamic luminosity scaling,
and unified Tier-1 / Tier-2 / Tier-3 color generation for the player chassis and modules.
"""

import math
from dataclasses import dataclass
from PySide6.QtGui import QColor

from ..analysis.audio_frame import AudioFrame


@dataclass
class NeonState:
    """Calculated spectral and intensity tiers for UI components."""
    tier1_chassis_color: QColor  # Outer chassis/module borders
    tier2_panel_color: QColor    # Internal framing, LCD border, module inner racks
    tier3_control_color: QColor  # Button and slider borders
    track_glow_color: QColor     # Expressive song title LCD glow/border
    track_bg_color: QColor       # LCD ambient tint
    intensity_factor: float      # Overall 0.0 -> 1.0
    spectral_shift: float        # -1.0 (Bass-heavy/Violet) to +1.0 (Treble-heavy/Ice)
    beat_impulse: float          # 0.0 -> 1.0


class ReactiveNeonController:
    """
    Central coordinator for chassis neon breathing and spectral musical reactivity.
    Target breathing cycle: ~3.2 seconds.
    Reactivity character: Visible spectral response and smooth, perceptible breathing
    without RGB cycling or visualizer-level chaos.
    """

    CYAN_H = 186.0 / 360.0       # Electric cyan (0.516) - Mids / Neutral baseline
    VIOLET_H = 285.0 / 360.0     # Deep violet / magenta (0.791) - Bass heavy
    ICE_H = 195.0 / 360.0        # Ice blue / white cyan (0.541) - Treble heavy
    
    YELLOW_H = 48.0 / 360.0      # Industrial amber / cyber yellow baseline
    YELLOW_BASS_H = 10.0 / 360.0 # Deep amber / orange on bass
    YELLOW_TREB_H = 60.0 / 360.0 # Bright electric lemon / white yellow on treble

    def __init__(self, theme_id: str = "default"):
        self._phase: float = 0.0
        self._beat_decay: float = 0.0
        self._theme_id = theme_id
        self._base_hue = self.YELLOW_H if theme_id == "cyber_yellow" else self.CYAN_H
        self._current_hue: float = self._base_hue
        self._current_state: NeonState = self._compute_state(0.5, self._current_hue, 0.0, 0.0, False)

    def set_theme_id(self, theme_id: str):
        self._theme_id = theme_id
        self._base_hue = self.YELLOW_H if theme_id == "cyber_yellow" else self.CYAN_H

    @property
    def theme_id(self) -> str:
        return self._theme_id

    @property
    def current_theme_id(self) -> str:
        return self._theme_id

    @property
    def current_state(self) -> NeonState:
        return self._current_state

    def update(self, dt: float, frame: AudioFrame | None = None, is_mini: bool = False) -> NeonState:
        """
        Advances the breathing cycle and mixes in real-time spectral audio metrics.
        dt: delta time in seconds (~0.016 for 60 Hz UI tick)
        """
        # 1. Advance continuous baseline breathing (~3.2s period: omega = 2*pi / 3.2 ~= 1.96)
        self._phase += dt * 1.96
        if self._phase > 2.0 * math.pi:
            self._phase -= 2.0 * math.pi

        # Smooth sine breathing: 0.0 to 1.0
        breath = (math.sin(self._phase) + 1.0) * 0.5

        # 2. Extract spectral and energy audio metrics
        rms = 0.0
        bass = 0.0
        mids = 0.0
        treble = 0.0
        target_hue = self._base_hue
        spectral_shift = 0.0

        if frame is not None:
            rms = min(1.0, frame.rms)
            bass = min(1.0, frame.bass)
            mids = min(1.0, frame.mids)
            treble = min(1.0, frame.treble)

            # Trigger beat impulse (strong beat gives bigger punch)
            if frame.strong_beat:
                self._beat_decay = 1.0
            elif frame.beat:
                self._beat_decay = max(self._beat_decay, 0.75)

            # Spectral Color Model:
            total_energy = bass + mids + treble + 1e-5
            b_norm = bass / total_energy
            t_norm = treble / total_energy
            m_norm = mids / total_energy

            # Spectral shift in range [-1.0 (Bass), +1.0 (Treble)]
            spectral_shift = (t_norm - b_norm)

            if self._theme_id == "cyber_yellow":
                if spectral_shift < -0.15:
                    ratio = min(1.0, (-spectral_shift - 0.15) * 2.0)
                    target_hue = self.YELLOW_H + ratio * (self.YELLOW_BASS_H - self.YELLOW_H)
                elif spectral_shift > 0.15:
                    ratio = min(1.0, (spectral_shift - 0.15) * 2.0)
                    target_hue = self.YELLOW_H + ratio * (self.YELLOW_TREB_H - self.YELLOW_H)
                else:
                    target_hue = self.YELLOW_H
            else:
                if spectral_shift < -0.15:
                    # Bass dominance -> Blend Cyan -> Violet
                    ratio = min(1.0, (-spectral_shift - 0.15) * 2.0)
                    target_hue = self.CYAN_H + ratio * (self.VIOLET_H - self.CYAN_H)
                elif spectral_shift > 0.15:
                    # Treble dominance -> Shift to Ice Blue
                    ratio = min(1.0, (spectral_shift - 0.15) * 2.0)
                    target_hue = self.CYAN_H + ratio * (self.ICE_H - self.CYAN_H)
                else:
                    target_hue = self.CYAN_H

        # Decay beat impulse (~140ms decay)
        if self._beat_decay > 0.0:
            self._beat_decay = max(0.0, self._beat_decay - (dt * 6.5))

        # Smooth hue transitions (~8.0 lerp factor)
        hue_diff = target_hue - self._current_hue
        self._current_hue += hue_diff * min(1.0, dt * 8.0)

        # 3. Scale reactivity by mode
        if is_mini:
            # MINI: quiet, ultra-low amplitude, barely noticeable atmosphere
            intensity = 0.40 + (breath * 0.14) + (rms * 0.10) + (self._beat_decay * 0.06)
        else:
            # NORMAL: clearly perceptible breathing and musical responsiveness.
            # Base breathing range ~0.40 -> 0.86 (widened from ~0.46 -> 0.78 --
            # v0.666 UX polish: the original swing was too subtle to register
            # in peripheral vision) + spectral RMS and beat kicks.
            intensity = 0.40 + (breath * 0.46) + (rms * 0.22) + (self._beat_decay * 0.12)

        intensity = max(0.25, min(1.0, intensity))
        self._current_state = self._compute_state(intensity, self._current_hue, spectral_shift, self._beat_decay, is_mini)
        return self._current_state

    def _compute_state(
        self,
        intensity: float,
        hue: float,
        spectral_shift: float,
        beat_impulse: float,
        is_mini: bool
    ) -> NeonState:
        # Tier 1 (Chassis Border): Crisp Electric Spectral Neon
        v1 = int(170 + (intensity * 85))
        a1 = int(190 + (intensity * 65))
        s1 = 0.95 if spectral_shift <= 0 else max(0.40, 0.95 - (spectral_shift * 0.50)) # Desaturate slightly on ice treble
        c1 = QColor.fromHsvF(hue % 1.0, s1, v1 / 255.0, a1 / 255.0)

        # Tier 2 (Panel Framing / LCD / Modules): Subdued structural framing
        v2 = int(100 + (intensity * 85))
        a2 = int(130 + (intensity * 85))
        c2 = QColor.fromHsvF(hue % 1.0, 0.85, v2 / 255.0, a2 / 255.0)

        # Tier 3 (Control Edges): Interactive buttons
        v3 = int(140 + (intensity * 95))
        a3 = int(160 + (intensity * 95))
        c3 = QColor.fromHsvF(hue % 1.0, 0.90, v3 / 255.0, a3 / 255.0)

        # Track LCD Border & Glow: Most expressive reactive element
        # Enhanced brightness + beat punch
        t_v = int(min(255, 180 + (intensity * 75) + (beat_impulse * 35)))
        t_a = int(min(255, 190 + (intensity * 65) + (beat_impulse * 35)))
        track_glow = QColor.fromHsvF(hue % 1.0, s1, t_v / 255.0, t_a / 255.0)

        # LCD Ambient Tint
        bg_a = int(15 + (intensity * 25) + (beat_impulse * 20))
        track_bg = QColor.fromHsvF(hue % 1.0, 0.80, 0.20, bg_a / 255.0)

        return NeonState(
            tier1_chassis_color=c1,
            tier2_panel_color=c2,
            tier3_control_color=c3,
            track_glow_color=track_glow,
            track_bg_color=track_bg,
            intensity_factor=intensity,
            spectral_shift=spectral_shift,
            beat_impulse=beat_impulse
        )
