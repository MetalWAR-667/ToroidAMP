"""
ToroidAMP - POLISH-001 Reactive Spectral Neon Test Suite
Validates:
1. ReactiveNeonController breathing cycle (~3.2s period, smooth continuous modulation).
2. Spectral color modulation: Bass -> Violet/Magenta, Mids -> Electric Cyan, Treble -> Ice Blue.
3. Expressive track display and ambient background colors.
4. Scale-dependent scaling: MINI mode remains subtle (<15% breathing amplitude).
5. Contrast verification between radically different musical profiles (e.g. Orchestral/Acoustic vs Heavy Metal/Bass).
"""

import math
from PySide6.QtGui import QColor
from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.ui.neon import ReactiveNeonController, NeonState


def test_neon_controller_breathing_cycle():
    """Validates that baseline breathing modulates smoothly with clear, perceptible depth."""
    nc = ReactiveNeonController()
    
    # Sample breathing over one full 3.2s cycle at 30 Hz (dt = 0.033s)
    intensities = []
    for _ in range(100):
        state = nc.update(dt=0.033, frame=None, is_mini=False)
        intensities.append(state.intensity_factor)
        assert isinstance(state.tier1_chassis_color, QColor)
        assert isinstance(state.tier2_panel_color, QColor)
        assert isinstance(state.tier3_control_color, QColor)
        assert isinstance(state.track_glow_color, QColor)
        assert isinstance(state.track_bg_color, QColor)

    min_i = min(intensities)
    max_i = max(intensities)
    # NORMAL breathing range: ~0.40 to ~0.86 (v0.666: widened from ~0.46 ->
    # 0.78 for stronger peripheral-vision presence).
    assert min_i >= 0.38, f"Expected min intensity >= 0.38, got {min_i}"
    assert max_i <= 0.88, f"Expected max intensity <= 0.88, got {max_i}"
    # Verify perceptible breathing depth (> 0.40 swing, widened from the
    # previous >0.25 floor to match the stronger v0.666 amplitude).
    assert (max_i - min_i) >= 0.40, f"Breathing must be clearly perceptible, swing was {max_i - min_i}"


def test_mini_mode_subtle_restraint():
    """Validates that MINI mode maintains low-juice atmosphere and minimal amplitude."""
    nc = ReactiveNeonController()
    
    intensities = []
    for _ in range(100):
        state = nc.update(dt=0.033, frame=None, is_mini=True)
        intensities.append(state.intensity_factor)

    min_i = min(intensities)
    max_i = max(intensities)
    # MINI amplitude must be restrained (~0.14 total swing)
    assert (max_i - min_i) <= 0.16, f"MINI breathing too aggressive: swing={max_i - min_i}"
    assert max_i <= 0.56, f"MINI max intensity too bright: {max_i}"


def test_spectral_palette_discrimination():
    """
    Validates that two radically different musical tracks produce observably different
    spectral colors (Bass-heavy vs Treble-dominant).
    """
    # Track A: "Twilight of the Thunder Gods" / Heavy Metal (Massive Bass / Low Mids / Strong Beat)
    frame_heavy = AudioFrame(
        rms=0.75, peak=0.95, bass=0.85, mids=0.35, treble=0.15,
        spectrum=(0.0,)*64, waveform=(0.0,)*128, beat=True, strong_beat=True
    )

    # Track B: "Ecstasy of Gold" / Orchestral (Spacious Mids, Crisp Highs / Strings, Soft Bass)
    frame_orch = AudioFrame(
        rms=0.45, peak=0.60, bass=0.15, mids=0.55, treble=0.70,
        spectrum=(0.0,)*64, waveform=(0.0,)*128, beat=False, strong_beat=False
    )

    nc_heavy = ReactiveNeonController()
    nc_orch = ReactiveNeonController()

    # Step through multiple frames to allow lerping
    for _ in range(30):
        s_heavy = nc_heavy.update(dt=0.016, frame=frame_heavy, is_mini=False)
        s_orch = nc_orch.update(dt=0.016, frame=frame_orch, is_mini=False)

    # 1. Heavy Metal should have negative spectral shift (Bass-dominant) and shift towards Violet/Magenta hue
    assert s_heavy.spectral_shift < -0.30, f"Expected heavy bass spectral shift < -0.30, got {s_heavy.spectral_shift}"
    hue_heavy = s_heavy.tier1_chassis_color.hueF()
    # Cyan is ~0.516, Violet is ~0.791. Heavy bass hue should be shifted upwards towards violet
    assert hue_heavy > 0.55, f"Expected heavy track hue shifted towards violet (>0.55), got {hue_heavy}"

    # 2. Orchestral / Acoustic with high treble should have positive spectral shift (Ice-cyan / blue)
    assert s_orch.spectral_shift > 0.30, f"Expected orchestral treble spectral shift > 0.30, got {s_orch.spectral_shift}"
    hue_orch = s_orch.tier1_chassis_color.hueF()
    # Treble dominance stays near ice cyan (~0.516 - 0.545) with lower saturation / icy brightness
    assert abs(hue_heavy - hue_orch) > 0.05, f"Expected distinct spectral hues between tracks: heavy={hue_heavy}, orch={hue_orch}"


def test_track_display_responsiveness():
    """Validates that track LCD display glows brighter and responds to beat transients."""
    nc = ReactiveNeonController()
    s_idle = nc.update(dt=0.016, frame=None, is_mini=False)

    frame_kick = AudioFrame(
        rms=0.7, peak=0.9, bass=0.8, mids=0.4, treble=0.3,
        spectrum=(0.0,)*64, waveform=(0.0,)*128, beat=True, strong_beat=True
    )
    s_kick = nc.update(dt=0.016, frame=frame_kick, is_mini=False)

    # Track glow color on kick must be brighter than idle
    assert s_kick.track_glow_color.value() >= s_idle.track_glow_color.value()
    assert s_kick.beat_impulse > 0.5


if __name__ == "__main__":
    print("Running test_neon_controller_breathing_cycle...")
    test_neon_controller_breathing_cycle()
    print("PASS: test_neon_controller_breathing_cycle")

    print("Running test_mini_mode_subtle_restraint...")
    test_mini_mode_subtle_restraint()
    print("PASS: test_mini_mode_subtle_restraint")

    print("Running test_spectral_palette_discrimination...")
    test_spectral_palette_discrimination()
    print("PASS: test_spectral_palette_discrimination")

    print("Running test_track_display_responsiveness...")
    test_track_display_responsiveness()
    print("PASS: test_track_display_responsiveness")

    print("\n--> ALL POLISH-001 SPECTRAL NEON TESTS PASSED 100%! <--")
