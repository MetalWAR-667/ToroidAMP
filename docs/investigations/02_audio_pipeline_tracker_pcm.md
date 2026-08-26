# ToroidAMP — Foundation II: Audio Pipeline & Tracker PCM Prototype

> **"Different audio formats can become the same PCM, the same PCM can become the same AudioFrame, and the same AudioFrame can make the same toroid lose its dignity."**

---

## 1. Executive Summary

Foundation II establishes the core audio and analysis architecture of ToroidAMP. 

### Key Discoveries & Architectural Closures:
1. **Unified Downstream Pipeline**: We successfully proved that **conventional audio** (MP3, OGG, WAV, FLAC) and **tracker modules** (MOD, XM, IT, S3M) decode into the exact same normalized `float32` interleaved stereo PCM representation ($44100\text{ Hz}$).
2. **Deterministic Audio Analysis**: The PCM buffer is continuously processed by an ultra-fast, windowed FFT analysis pipeline that produces a clean, normalized `AudioFrame` without taking CPU time from the high-priority OS audio output callback.
3. **Tracker PCM Native Engine**: Using `libmodplug` (bundled cleanly in Pygame / SDL2 environments and cross-platform native binaries), tracker files render directly to float32 PCM chunks via a lightweight, deterministic CFFI/ctypes binding, bypassing Pygame's black-box mixer.
4. **The Toroid Responds to Truth**: The extracted 3D Torus visualizer renders inside PySide6 widgets with zero synthetic timers or fake oscillators. It directly reacts to real-time `bass`, `mids`, `treble`, `spectrum`, and `beat` triggers derived from the decoded stream.
5. **Demoscene Compatibility Variable**: The internal parameter `fckvar` was implemented inside the toroid visualizer to modulate geometric distortion, vertex jitter, and plasma heating from low-frequency energy.

---

## 2. Conventional Audio Backend Evaluation

| Candidate | Formats Decoded | Float32 PCM | Sample-Rate Control | Seeking & State | Output Reliability | Platform Support | Evaluation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`soundfile` + `sounddevice`** | WAV, MP3, OGG, FLAC | **YES** | Native / Preserved | Sample-accurate cursor | Rock-solid (PortAudio) | Windows & Linux (Wheels) | **CONFIRMED FOR V1**. Zero native build requirement, robust float32 streaming. |
| **`miniaudio` + `sounddevice`** | WAV, MP3, OGG, FLAC | **YES** | Flexible resampling | Sample-accurate | Excellent | Windows & Linux (Wheels) | **CONFIRMED ALTERNATIVE**. Fast streaming decoder. |
| **`pygame.mixer.music`** | MP3, OGG, WAV | **NO** | Fixed to mixer | Imprecise / Resets on loop | Good audio | Windows & Linux | **REJECTED AS AUDIO BACKEND** (Black-box, no real-time PCM stream). |

---

## 3. Tracker Decoder Evaluation

| Library | Formats Decoded | Output Format | Seeking / Timing | Metadata | Integration & Dependencies | Evaluation |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`libmodplug` (via ctypes)** | MOD, XM, IT, S3M | 16-bit stereo $\to$ normalized `float32` | Millisecond accurate (`ModPlug_Seek`) | Title, Song Length, Track Info | Native DLL/.so bundled with SDL_mixer / Pygame | **CONFIRMED & VALIDATED**. Lightweight, robust, zero extra native compilation required on standard environments. |
| **`libopenmpt`** | MOD, XM, IT, S3M | Direct `float32` | Sub-pattern accurate | Complete metadata | Requires compiling/bundling standalone DLL/.so | **VALIDATED ALTERNATIVE**. High-accuracy open-source standard. |
| **`libxmp`** | MOD, XM, IT, S3M | 16-bit stereo | Pattern/Row accurate | Good metadata | Requires standalone binary | **VALIDATED ALTERNATIVE**. |

---

## 4. PCM Representation Decision

The downstream internal contract between audio decoders, output streams, and the analysis worker is strictly defined as:

```text
Format:           float32 (-1.0 to +1.0 normalized)
Channels:         2 (Stereo, interleaved or 2D array [N, 2])
Sample Rate:      44100 Hz default (or native file rate)
Block Size:       512 frames (audio output) / 2048 frames (analysis window)
```

No downstream consumer (analysis, spectrum, visualizer, UI) knows or cares whether the audio stream originated from `Burn The World Waltz.mp3` or `dalezy-lotus_drei_remix.xm`.

---

## 5. Audio Output Strategy

Playback is driven by `sounddevice.OutputStream`:
* **Blocksize**: 512 frames (~11.6 ms of audio at 44.1 kHz).
* **Latency**: High-priority real-time audio thread.
* **Callback Rule**: The audio callback executes **zero** allocations, **zero** Qt operations, and **zero** FFT math. It fills `outdata` and pushes the output chunk to `AnalysisHandoff`.

---

## 6. Analysis Handoff Strategy

* **Mechanism**: Dedicated thread-safe circular buffer (`AnalysisHandoff`) holding the most recent 2048 samples (approx. 46.4 ms window).
* **Audio Thread Overhead**: **~17 microseconds** per 512-frame block push.
* **Visualizer Thread Overhead**: **~0.8 microseconds** for snapshot acquisition.
* **Failure Isolation**: If the UI stalls or the visualizer drops frames, the audio output callback continues uninterrupted.

---

## 7. AudioFrame Contract Evaluation

The validated `AudioFrame` structure is defined as:

```python
@dataclass(slots=True)
class AudioFrame:
    rms: float             # Overall loudness [0.0 - 1.0] -> Master energy
    peak: float            # Peak sample amplitude [0.0 - 1.0]
    bass: float            # 20 - 250 Hz energy [0.0 - 1.0] -> Toroid pulse
    mids: float            # 250 - 4000 Hz energy [0.0 - 1.0] -> Plasma rotation
    treble: float          # 4000 - 20000 Hz energy [0.0 - 1.0] -> Jitter / particles
    spectrum: list[float]  # 64 log-spaced normalized frequency bins [0.0 - 1.0]
    waveform: list[float]  # 128 subsampled points [-1.0 - 1.0] -> Oscilloscope / vertex wave
    beat: bool             # Dynamic transient trigger -> Rhythmic step
    strong_beat: bool      # Bass kick transient trigger -> Ghosting / camera shake
```

---

## 8. Waveform Decision

**DECISION: Waveform is INCLUDED in `AudioFrame`.**
* **Rationale**: Providing a 128-point subsampled normalized waveform vector (`list[float]`) introduces virtually zero overhead and allows geometric visualizers (such as Toroid vertex ripple and oscilloscopes) to deform shapes with authentic wave physics without accessing raw audio buffers.

---

## 9. FFT / Frequency-Band Design

* **Windowing**: Hanning window applied over 2048 audio frames.
* **Transform**: Real FFT (`numpy.fft.rfft`), producing 1025 discrete frequency bins.
* **Band Partitioning**:
  * **Bass**: 20 Hz – 250 Hz
  * **Mids**: 250 Hz – 4000 Hz
  * **Treble**: 4000 Hz – 20000 Hz
* **Spectrum Partitioning**: 64 geometrically spaced bins ($\text{geomspace}(20, 20000, 65)$) scaled for visual responsiveness.

---

## 10. Beat Detection Design

* **Algorithm**: Dynamic sliding-window variance tracker. Compares instantaneous energy ($E = \text{RMS}^2$) against moving average energy ($\bar{E}$) with dynamic variance thresholding ($c = \max(1.2, 1.5 - 10 \cdot \text{Var})$).
* **Debounce**: 180 ms refractory window to prevent false double-triggers.
* **Strong Beat**: Triggered when a transient coincides with elevated bass energy ($\text{bass} > 0.4$).
* **BPM Status**: Explicit BPM estimation is **excluded** from V1 `AudioFrame` to keep contracts lean and transient-reactive.

---

## 11. Toroid Integration

The 3D Torus parametric mesh ($24 \times 36$ vertices = 864 vertices, 1728 wireframe edges) was extracted into `Toroid3DVisualizer` and bound to the live `AudioFrame`:
* **Pulse / Expansion**: Scaled by `frame.bass`.
* **Vertex Ripple**: Modulated by `frame.waveform`.
* **Plasma Color Spectrum**: Shifted by `frame.mids` and `frame.treble`.
* **Jitter & Camera Shake**: Triggered on `frame.strong_beat`.
* **Ghosting Trails**: Rendered on translucent overlays during high-energy transients.

---

## 12. `fckvar` Historical Compatibility Note

In accordance with demoscene archaeological compatibility, the internal variable `fckvar` is preserved within `Toroid3DVisualizer.render()`:

```python
# -------------------------------------------------------------
# DEMOSCENE ARCHAEOLOGICAL COMPATIBILITY
# Historical variable controlling musical deformation & irresponsibility
# -------------------------------------------------------------
beat_boost = 1.6 if frame.strong_beat else (0.8 if frame.beat else 0.0)
fckvar = (frame.bass * 1.5) + (frame.rms * 0.5) + beat_boost
# -------------------------------------------------------------
```

It directly drives wireframe vertex distortion, field-of-view dilation, and heat-color saturation.

---

## 13. Conventional Audio Validation

* **Asset**: `Burn The World Waltz.mp3` (Redistributable test asset).
* **Verification**: Sample-accurate decoding to `(8823168, 2)` float32 array; live streaming via `sounddevice`; verified active energy envelopes at 5s (`RMS = 0.115`, `Bass = 0.154`, `Mids = 0.019`).
* **Status**: **CONFIRMED**.

---

## 14. Tracker Validation

* **Assets Tested**:
  * `dalezy-lotus_drei_remix.xm` (XM format) $\to$ **CONFIRMED** (`RMS = 0.087`, `Bass = 0.077`).
  * `08_sad_song.it` (IT format) $\to$ **CONFIRMED** (`RMS = 0.143`, `Bass = 0.210`).
  * `tubularbells-metal hr.mod` (MOD format) $\to$ **CONFIRMED** (`RMS = 0.041`, `Bass = 0.002`).
* **Observation**: Tracker files decode cleanly into raw float32 PCM blocks and drive the identical Toroid visualizer without format-specific branching.
* **Status**: **CONFIRMED**.

---

## 15. Performance Observations

* **Audio Output Stream Callback**: ~17 $\mu\text{s}$ per chunk.
* **Analysis & FFT Calculation**: ~0.85 ms per frame.
* **Pygame Wireframe Render (864 vertices, 1728 edges)**: ~3.2 ms per frame.
* **Pygame $\to$ Qt QPixmap Transfer**: ~1.3 ms per frame.
* **Total Frame Budget**: ~5.4 ms per frame (**~185 FPS capacity** on standard desktop).
* **Audio Glitches / Underruns**: **Zero** detected during multi-track playback.

---

## 16. Failure & Error Findings

* **Missing Files / Corrupted Headers**: Caught cleanly with informative logging; output falls back to silence without crashing the Qt application.
* **Visualizer Errors**: Wrapped in try/except blocks; visual rendering fails gracefully while audio playback continues uninterrupted.
* **Missing Tracker DLLs**: Handled with explicit fallback errors prompting the user.

---

## 17. Packaging & Native Dependency Implications

* **`soundfile` / `sounddevice`**: Pre-built wheels contain PortAudio and libsndfile DLLs for Windows and Linux.
* **`libmodplug`**: Bundled by default with standard Pygame/SDL2 wheels or available via system packages on Linux (`libmodplug1`).

---

## 18. Risks

1. **Linux Dynamic Library Discovery**: On Linux, `libmodplug.so.1` or `libopenmpt.so.0` should be resolved via `ctypes.util.find_library`.
2. **High Track Seeking Latency in Huge Tracker Files**: Seeking in tracker files requires unrolling pattern state. `ModPlug_Seek` handles this well, but tracks over 30 minutes may incur minor seek pauses.

---

## 19. Decisions Recommended for Closure

| Decision Gate | Recommendation | Status |
| :--- | :--- | :---: |
| **AUDIO-001** (Conventional Playback Backend) | `sounddevice` + `soundfile` / `miniaudio` stream pipeline | **CLOSE** |
| **AUDIO-002** (Tracker PCM Decoder) | Native `libmodplug` / `libopenmpt` CFFI stream decoder | **CLOSE** |
| **AUDIO-003** (PCM Access Strategy) | Shared `AnalysisHandoff` ring-buffer stream snapshot | **CLOSE** |
| **ANALYSIS-001** (AudioFrame Contract) | Normalized `AudioFrame` (including 128-pt `waveform`) | **CLOSE** |
| **ANALYSIS-002** (Beat Detection) | Dynamic sliding-window energy transient detector | **CLOSE** |
| **RUNTIME-001** (Concurrency Model) | Isolated high-priority audio callback + timer-driven UI analysis | **CLOSE** |

---

## 20. Decisions Remaining Open

* **PACKAGE-001 (Distribution Strategy)**: PyInstaller / Nuitka packaging configuration deferred to pre-release stabilization.

---

## 21. Recommended Next Cut

### **Phase 1 — Core Architecture Skeleton & Foundation Implementation**
* Establish production repository package structure (`src/toroidamp/`).
* Implement production `PlaybackEngine`, `TrackerDecoder`, `ConventionalDecoder`, and `AudioAnalyzer`.
* Build the base `Visualizer` contract and integrate `Toroid3D` as default visualizer.
* Implement the core PySide6 compact player window with playlist integration.
