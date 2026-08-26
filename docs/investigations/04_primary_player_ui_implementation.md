# ToroidAMP — Production Cut 1B: Primary Player UI Implementation Report

> **"ToroidAMP has three personalities: MINI ('I am here if you need me.'), NORMAL ('Let's listen to music.'), and RETINA MELT ('TE VOY A DERRETIR LA RETINA.')."**

---

## 1. Executive Summary

Production Cut 1B has converted ToroidAMP from a series of design probes into a **fully functional production desktop music player**.

### Key Milestones Completed:
1. **Packaging & Clean Installation**: Configured standard `pyproject.toml` supporting editable installation (`pip install -e .`) and established production entry points (`python -m toroidamp` and `toroidamp`).
2. **Unified Chassis Implementation**: Built `UnifiedChassis` in `src/toroidamp/ui/chassis.py` seamlessly switching between **MINI** ($380 \times 36\text{ px}$ always-on-top control strip with screen-edge snapping) and **NORMAL** ($420 \times 135\text{ px}$ modular core).
3. **Dockable Modules**: Implemented `VisualizerModule` ($420 \times 240\text{ px}$, bottom dock) and `PlaylistModule` ($270 \times 240\text{ px}$, right dock) with magnetic proximity snapping (~30px threshold) and floating window support.
4. **Interactive Playlist System**: Full queue management including drag-and-drop file ingestion, track reordering, double-click playback, shuffle, repeat, and standard extended M3U/M3U8 load/save.
5. **Real DSP & Visualizer Wiring**: Connected real-time `PlayerEngine` output and `AnalysisHandoff` to live visualizers (`ToroidVisualizer` with `fckvar` and `WaveformRibbonVisualizer`).
6. **RETINA MELT Fullscreen**: Native resolution fullscreen visualizer takeover with prior-scale return memory and an auto-hiding floating HUD.
7. **Production Verification**: 100% test pass rate across unit and full end-to-end integration workflows.

---

## 2. Packaging & Python Configuration Result

* **File**: [`pyproject.toml`](file:///C:/ToroidAMP/ToroidAMP/pyproject.toml)
* **Build System**: `setuptools` with `src` layout.
* **Dependencies**: `PySide6>=6.6.0`, `pygame-ce>=2.5.0`, `numpy>=1.24.0`, `sounddevice>=0.4.6`, `soundfile>=0.12.0`, `miniaudio>=1.59`.
* **Entry Point**: `toroidamp = "toroidamp.__main__:main"`.
* **Install Command**: `python -m pip install -e .`
* **Run Command**: `python -m toroidamp` or `toroidamp [files...]`.

---

## 3. Production UI Components Implemented

```text
src/toroidamp/ui/
├── __init__.py
├── chassis.py            # UnifiedChassis (MINI and NORMAL views via QStackedWidget)
├── fullscreen.py         # RetinaMeltWindow (Fullscreen takeover + auto-hide HUD)
├── window_manager.py     # WindowManager (Central orchestrator & docking choreography)
└── modules/
    ├── __init__.py
    ├── base.py           # ModuleShell (Frameless, draggable, dockable base)
    ├── visualizer_module.py  # VisualizerModule (Offscreen Pygame surface hosting)
    └── playlist_module.py    # PlaylistModule (Track list, drag-and-drop, M3U I/O)
```

---

## 4. Subsystem Verification Matrix

### A. Audio & Tracker Formats
* **MP3**: **CONFIRMED** (`Burn The World Waltz.mp3`).
* **WAV**: **CONFIRMED** (`temp_intro.wav`).
* **OGG/Vorbis**: **CONFIRMED** (`typewriter.ogg`).
* **FLAC**: **PARTIALLY VALIDATED** (Decoded via `soundfile`).
* **XM**: **CONFIRMED** (`dalezy-lotus_drei_remix.xm`).
* **IT**: **CONFIRMED** (`08_sad_song.it`).
* **MOD**: **CONFIRMED** (`tubularbells-metal hr.mod`, `alleviation-metal hr.mod`).
* **S3M**: **PARTIALLY VALIDATED** (Supported by native `libmodplug` pipeline).

### B. Experience Scales & Transitions
* **MINI Mode**: $380 \times 36\text{ px}$, Always-On-Top, 25px screen-edge magnetic snapping, zero visualizer overhead when hidden.
* **NORMAL Mode**: $420 \times 135\text{ px}$, tactile transport controls, seek scrubber, volume, module chips (`VIS`, `PL`).
* **Module Docking**: Visualizer docks to bottom ($420 \times 240\text{ px}$); Playlist docks to right ($270 \times 375\text{ px}$ matched height). Moving core moves docked modules simultaneously.
* **Module State Preservation**: Switching NORMAL $\to$ MINI hides modules; switching MINI $\to$ NORMAL automatically restores active modules.
* **RETINA MELT**: Fullscreen visualizer with auto-hiding HUD; preserves prior scale on exit (`MINI` $\to$ `MELT` $\to$ `MINI`, and `NORMAL` $\to$ `MELT` $\to$ `NORMAL`).

---

## 5. Visualizer Subsystem

* **`ToroidVisualizer`**: 3D parametric torus wireframe with real-time waveform ripples, plasma heat-shading, beat jitter, and preserved internal demoscene variable `fckvar`.
* **`WaveformRibbonVisualizer`**: Layered glowing neon oscilloscope ribbon reacting to audio waveform displacement and midrange harmonic frequencies.
* **Live Switching**: Visualizers switch instantly during continuous audio playback with zero audio glitching or buffer dropouts.

---

## 6. Testing & Manual Validation

* **Unit & Integration Suite**: [`tests/test_production_cut1b.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut1b.py)
  * `test_playlist_manager`: **PASS** (Add, remove, reorder, shuffle, repeat, M3U I/O)
  * `test_audio_and_decoders`: **PASS** (Conventional & Tracker decoding, `AudioFrame` DSP)
  * `test_visualizers_contract`: **PASS** (Toroid & Ribbon rendering contracts)
  * `test_ui_experience_scales`: **PASS** (MINI/NORMAL/RETINA MELT scale transitions and module state restoration)
* **Full End-to-End Workflow**: 11-step automated verification passing 100%.

---

## 7. Skill Evaluation
* `audio-pipeline`: **SUFFICIENT** (Accurately guided decoder abstraction, float32 PCM normalization, and audio callback isolation).
* `visualizer-authoring`: **SUFFICIENT** (Directly enabled clean visualizer lifecycle and offscreen rendering).
* `reactive-player-ui`: **SUFFICIENT** (Encoded the 3 Experience Scales, small-scale juice budgets, and docking constraints).

---

## 8. Known Limitations (Current Cut)
* Direct folder/directory drop into playlist is deferred (single and multi-file drag-and-drop is fully operational).
* Neon RMS border breathing polish is deferred to the visual polish phase.

---

## 9. Recommended Next Cut

### **Production Cut 2 — Visualizer Engine Expansion & Demoscene Effects**
* Port and adapt additional donor visualizers from `MetalWAR-Installer` (`Starfield`, `RetroGrid`, `SpectrumAnalyzer`) into the `toroidamp.visualizers` package.
* Implement visualizer configuration options and intensity throttling for motion safety.
* Implement subtle audio-reactive UI chassis breathing (Juice budget: LOW).
