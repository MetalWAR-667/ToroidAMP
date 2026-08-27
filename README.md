# ToroidAMP

> **"Make the music play reliably. Make the code understandable. Make the screen do something unreasonable. Make Future Crew cry."**

ToroidAMP is a compact, modular, musically reactive audio player and real-time audiovisual playground built with Python, PySide6, Pygame-CE, and OpenGL/GLSL.

It combines a deliberately small desktop music player with a demoscene-inspired visualization engine, real-time audio analysis, GPU shaders, and live visual authoring tools.

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
* OpenGL-capable GPU for hardware GLSL visualizers

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

### MINI — 380 × 36 px

> *"I am here if you need me."*

* Ultra-compact, always-on-top control strip.
* Snaps magnetically to screen edges.
* Zero visual distraction while working.

### NORMAL — 420 × 135 px + Modules

> *"Let's listen to music."*

* Compact player core with tactile transport controls, seek scrubber, and volume.
* Dockable **Visualizer** and **Playlist** modules.
* CPU visualizers render directly inside the modular desktop interface.
* GPU visualizers expose direct entry into RETINA MELT.

### RETINA MELT — Fullscreen

> *"TE VOY A DERRETIR LA RETINA."*

* Fullscreen visualizer takeover at native display resolution.
* CPU and hardware-accelerated GPU visualizers.
* Real-time music-driven rendering.
* Auto-hiding playback HUD.
* Explicit HUD pin/dismiss interaction.
* Live visualizer tuning.
* Integrated GLSL Shader Lab.
* Clean return to the previous desktop experience.

RETINA MELT is not just a fullscreen mode: it is ToroidAMP's primary audiovisual environment.

---

## 3. Audio & Tracker Format Support

ToroidAMP uses a unified decoding architecture where supported formats are converted into normalized `float32` stereo PCM at 44100 Hz, feeding both audio playback and real-time visual analysis.

### Conventional Audio

* MP3
* OGG/Vorbis
* WAV
* FLAC

Decoding is provided through `soundfile` / `miniaudio`.

### Tracker Modules

* MOD
* XM
* IT
* S3M

Tracker playback uses native `libmodplug` integration through `ctypes`.

### Real-Time Audio Analysis

The visualizer engine receives a canonical `AudioFrame` containing musical analysis data such as:

* RMS energy
* Peak energy
* Bass
* Midrange
* Treble
* Beat events
* Strong beat events
* Spectrum data
* Waveform data

This provides a common reactive contract for both CPU and GPU visualizers.

---

## 4. Visualizer Engine

ToroidAMP supports two complementary rendering paths.

### CPU Visualizers

CPU visualizers use the existing Pygame-CE/software rendering pipeline.

Included visualizers currently include:

**3D Toroid**

A parametric 3D wireframe torus reacting to waveform data, bass expansion, plasma heat shading, and the infamous `fckvar` deformation variables.

**Waveform Ribbon**

A multilayer glowing neon oscilloscope ribbon driven by waveform displacement and midrange harmonic energy.

**Deep Field**

A perspective star field with depth-dependent photon trails, luminous heads, chromatic energy, and beat-driven acceleration.

**ToroidAMP Floor**

A perspective reactive floor with a dark silence baseline, nonlinear audio activation, illuminated cell clusters, and traveling beat waves.

### GPU Visualizers

ToroidAMP also includes a hardware-accelerated OpenGL/GLSL rendering path hosted directly by Qt.

GPU visualizers run primarily inside **RETINA MELT** and receive the same real-time `AudioFrame` information as CPU visualizers.

Official GPU visualizers include:

**Toroid Identity**

ToroidAMP's audiovisual identity shader, combining branded artwork with toroidal distortion, chromatic separation, emissive glow, rotation, and beat-driven shockwaves.

**Cyber Bloom**

A procedural audio-reactive GLSL composition demonstrating harmonic geometry, distortion, configurable neon palettes, typed authoring parameters, and transient beat responses.

---

## 5. RETINA MELT — Live Visual Authoring

RETINA MELT provides three deliberately separated interaction layers:

```text
HUD   → LISTEN

TUNE  → ADJUST

LAB   → EXPERIMENT
```

### HUD

The lightweight fullscreen HUD provides normal playback interaction without permanently covering the visualization.

### TUNE

Official GPU visualizers can expose live authoring parameters directly from shader metadata.

Supported parameter types:

* `float` → sliders
* `bool` → toggles
* `color` → color pickers

Changes are uploaded directly to GPU uniforms and affect the running shader immediately.

### Shader Lab

RETINA MELT also contains an integrated Shader Authoring Lab for deeper experimentation.

It supports:

* Official GPU shaders
* Local GLSL shader loading
* Live typed parameters
* Hot reload
* JSON presets
* Shader reset
* Compiler diagnostics
* Safe compilation rollback
* Real music / real `AudioFrame` reactivity

A broken shader does not stop playback or destroy the current visualization. If recompilation fails, ToroidAMP keeps the previous valid GPU program running and reports the GLSL diagnostic.

---

## 6. Local GLSL / Shadertoy-Style Shaders

ToroidAMP supports local experimentation with compatible single-pass GLSL shaders.

Local shaders can be placed under:

```text
user_shaders/
```

This directory is intentionally ignored by Git.

From the integrated RETINA Shader Lab or standalone GPU Lab, users can load:

```text
.frag
.glsl
.txt
```

### Level-1 Shadertoy-Style Compatibility

Single-pass shaders using the familiar:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord)
```

model can run through ToroidAMP's compatibility wrapper with standard inputs such as:

```text
iResolution
iTime
iTimeDelta
iFrame
```

Shaders do not need to be audio-reactive to run.

ToroidAMP-aware shaders may additionally consume its real-time audio uniforms.

Local shaders remain **LOCAL** content. ToroidAMP does not copy them into official assets, silently modify their source, or treat them as first-party visualizers.

---

## 7. Shader Authoring Parameters & Presets

Shaders can optionally declare authoring controls through lightweight metadata.

Example:

```glsl
// [param:float] u_glow: Glow Intensity = 1.2 (0.2 .. 3.5)
// [param:bool] u_distortion: Enable Distortion = true
// [param:color] u_primaryColor: Primary Neon = #00E5FF
```

ToroidAMP automatically creates the corresponding controls and binds them to GLSL uniforms.

Visualizer states can also be stored as JSON presets.

Presets support:

* Float clamping
* Boolean parameters
* `#RRGGBB` colors
* Missing-key tolerance
* Unknown-key forward compatibility
* Immediate restoration of the rendered composition

---

## 8. Standalone GPU Visualizer Lab

ToroidAMP also retains a dedicated standalone GPU development environment:

```powershell
py -3.13 experiments\gpu_visualizers\lab_app.py
```

The standalone Lab is intended for shader development and isolated experimentation rather than normal listening.

It provides:

* Synthetic audio profiles
* Official and local shaders
* Parameter authoring
* Presets
* Hot reload
* Compiler diagnostics
* Deliberate shader failure testing
* Fullscreen inspection

The two environments therefore have different jobs:

```text
STANDALONE LAB
→ build and break things safely

RETINA MELT LAB
→ experience and tune them against real music
```

---

## 9. Shader Territories

ToroidAMP keeps first-party, experimental, and user-provided shader content explicitly separated:

```text
src/toroidamp/assets/official_shaders/
    Official ToroidAMP shaders

experiments/gpu_visualizers/shaders/
    Internal R&D shaders

user_shaders/
    Local/user/third-party exploration
    Git ignored
```

This separation is intentional.

Third-party shaders are never automatically promoted into ToroidAMP's distributed assets.

---

## 10. Current GPU Compatibility

ToroidAMP 0.3.1 establishes the production baseline for single-pass GPU visualizers.

### Available

* OpenGL/GLSL GPU host
* Single-pass fragment shaders
* Level-1 Shadertoy-style compatibility
* Real `AudioFrame` uniforms
* Spectrum and waveform uniform arrays
* Static packaged texture support for official visualizers
* Float / bool / color parameters
* JSON presets
* Local shader loading
* Hot reload
* Compilation failure isolation
* RETINA MELT integration
* Standalone Shader Lab

### Future / Experimental Roadmap

Not yet part of the production baseline:

* `iChannel0..3` generalized texture channels
* Audio spectrum/waveform textures
* Multipass rendering
* Buffer A/B/C/D style pipelines
* FBO feedback
* Temporal accumulation
* Composition/chaining systems
* Additional DSP and rhythm-analysis capabilities

These are deliberately deferred until their architecture has been validated experimentally.

---

## 11. Development & Testing

ToroidAMP uses automated regression tests alongside human perceptual validation for audiovisual features.

Run the complete test suite with:

```powershell
py -3.13 -m unittest discover -s tests
```

GPU and visualizer features are additionally validated through dedicated experimental and production integration suites.

For visual work, automated tests verify contracts and lifecycle safety; final appearance and musical causality are validated manually.

---

## 12. Current Version

```text
ToroidAMP 0.3.1
```

The 0.3.1 baseline establishes ToroidAMP's first complete GPU visualizer and authoring stack:

```text
AUDIO
  ↓
AudioFrame
  ↓
CPU / GPU VISUALIZERS
  ↓
RETINA MELT
  ├── HUD
  ├── TUNE
  └── LAB
        ├── LOCAL GLSL
        ├── PARAMETERS
        ├── PRESETS
        └── HOT RELOAD
```

The player is still compact.

The visualizer is becoming increasingly unreasonable.