# ToroidAMP

> **"Make the music play reliably. Make the code understandable. Make the screen do something unreasonable. Make Future Crew cry."**

ToroidAMP is a compact, modular, musically reactive audio player with a demoscene visualizer engine built with Python, PySide6, and Pygame-CE.

```text
WINAMP FOOTPRINT.
MODULAR CONSTRUCTION.
MODERN GAMEFEEL.
DEMOSCENE SOUL.
```

---

## 1. Quick Start / Installation

### Prerequisites
* Python 3.11, 3.12, 3.13, or 3.14
* PortAudio / Audio output device
* Windows, Linux, or macOS

### Installation
From the repository root:

```powershell
python -m pip install -e .
```

### Launch Application
You can launch ToroidAMP using either command:

```powershell
python -m toroidamp
```

or via the installed console script:

```powershell
toroidamp
```

You can also pass audio files directly via command line:

```powershell
toroidamp "path/to/song.mp3" "path/to/module.xm"
```

---

## 2. The Three Experience Scales

ToroidAMP operates across three distinct user experience scales:

1. **MINI ($380 \times 36\text{ px}$)**:
   * *"I am here if you need me."*
   * Ultra-compact, always-on-top control strip.
   * Snaps magnetically to screen edges (Top/Bottom/Left/Right).
   * Zero visual distraction while working.
2. **NORMAL ($420 \times 135\text{ px} + \text{Modules}$)**:
   * *"Let's listen to music."*
   * Standalone player core with tactile transport controls, seek scrubber, volume, and module toggles (`VIS`, `PL`).
   * Attaches dockable modules: **Visualizer** (Bottom) and **Playlist** (Right).
3. **RETINA MELT (Fullscreen)**:
   * *"TE VOY A DERRETIR LA RETINA."*
   * Fullscreen procedural visualizer takeover at native display resolution.
   * Auto-hiding floating playback HUD (appears on mouse move, fades after 2.5s).
   * Remembers and returns cleanly to the prior experience scale (MINI or NORMAL) on `Esc`.

---

## 3. Audio & Tracker Format Support

ToroidAMP uses a unified decoding architecture where every format decodes into normalized `float32` stereo PCM ($44100\text{ Hz}$) feeding both the audio hardware and real-time FFT/waveform analysis.

* **Conventional Audio**: MP3, OGG/Vorbis, WAV, FLAC (via `soundfile` / `miniaudio`).
* **Tracker Modules**: MOD, XM, IT, S3M (via native `libmodplug` ctypes).

---

## 4. Included Visualizers

* **`3D Toroid`**: 3D parametric wireframe torus ($24 \times 36$ vertices) reacting to real-time audio waveforms, bass expansion, plasma heat-shading, and demoscene `fckvar` deformation.
* **`Waveform Ribbon`**: Multi-layered glowing neon oscilloscope ribbon driven by real-time waveform displacement and midrange harmonic frequencies.

---

## 5. Development & Testing

Run the production test suite:

```powershell
py -3.13 tests/test_production_cut1b.py
```
