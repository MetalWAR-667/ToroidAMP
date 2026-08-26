---
name: audio-pipeline
description: >-
  Specialized guidance for working with ToroidAMP's audio subsystem, decoders,
  normalized float32 PCM architecture, output stream safety, and real-time analysis handoff.
---

# ToroidAMP — Audio Pipeline Specialist Skill

This skill encodes the architectural invariants, performance constraints, and implementation guidelines for ToroidAMP's playback, decoding, and analysis subsystems.

---

## 1. When to Use
* Implementing or modifying audio decoders (`AudioDecoder`, `ConventionalDecoder`, `TrackerDecoder`).
* Working with audio streaming output (`PlayerEngine`, `sounddevice.OutputStream`).
* Modifying PCM buffer normalization, sampling, or channel layout.
* Working with `AnalysisHandoff` and `AudioFrame` generation.
* Debugging audio glitches, buffer underruns, or decoder seek/position logic.

## 2. When NOT to Use
* Authoring visualizer graphics (use `visualizer-authoring`).
* Designing UI layouts or widgets (use `reactive-player-ui`).
* General git workflow or documentation lifecycle management.

---

## 3. Core Architectural Invariants

### Invariant 1: Format Disappearance
The moment an audio file is decoded, its source format (`.mp3`, `.flac`, `.xm`, `.it`) **must completely disappear**. Downstream systems (audio output, analysis, visualizers, UI) must receive the exact same normalized PCM representation:
* **Data type**: `numpy.float32`
* **Range**: Normalized $[-1.0, 1.0]$
* **Layout**: 2-channel stereo (shape `(N, 2)`)
* **Sample Rate**: Native or standard $44100\text{ Hz}$

### Invariant 2: Audio Output Callback Is Sacrosanct
The audio output callback runs on a high-priority OS real-time thread.
* **NEVER** perform Qt / PySide6 operations inside the audio callback.
* **NEVER** execute Pygame rendering or surface manipulation inside the audio callback.
* **NEVER** compute heavy FFTs, memory allocations, or file I/O inside the audio callback.
* **RULE**: The callback must only pull decoded PCM, apply volume, copy to output, and push to `AnalysisHandoff` (<20 $\mu\text{s}$ total).

### Invariant 3: Playback Isolation from Visualizers
Audio playback must **never wait for visualizer rendering**. Visualizers may drop frames or crash; audio playback must continue smoothly.

---

## 4. Subsystem Components

```text
Audio File (MP3 / OGG / MOD / XM)
               │
               ▼
   AudioDecoder (Base Interface)
   ├── ConventionalDecoder (soundfile)
   └── TrackerDecoder (libmodplug ctypes)
               │
               ▼ [float32 (N, 2) PCM]
          PlayerEngine
         ┌─────┴────────────────────────┐
         ▼                              ▼
sounddevice.OutputStream         AnalysisHandoff (Circular Buffer)
   (Audio Hardware)                     │
                                        ▼
                                 AudioFrame Generator
                                        │
                                        ▼
                                   Visualizers
```

---

## 5. Validation Expectations & Testing

When adding or modifying decoders or playback components:
1. **Verify PCM dtype and shape**: Must be `np.float32` and `ndim == 2` (`shape[1] == 2`).
2. **Verify amplitude bounds**: Ensure values are clamped/normalized to $[-1.0, 1.0]$.
3. **Verify EOF behavior**: Decoder must return empty array `shape (0, 2)` on EOF, triggering clean state transitions.
4. **Verify seeking**: Ensure seeking resets internal buffers without audio pops or clicks.

---

## 6. Common Failure Modes & Solutions
* **Audio pops/clicks on loop**: Ensure smooth buffer zero-fill when chunks are shorter than requested block size.
* **Thread deadlocks**: `PlayerEngine._lock` must never be held while calling blocking external libraries.
* **Tracker crash on large files**: Never load tracker files into Pygame's `Sound` object; always stream through `TrackerDecoder` (`libmodplug`).
