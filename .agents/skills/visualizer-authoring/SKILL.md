---
name: visualizer-authoring
description: >-
  Specialized guidance for creating, adapting, and rendering real-time audio visualizers
  in ToroidAMP using the AudioFrame contract, Pygame offscreen rendering, and PySide6 hosting.
---

# ToroidAMP — Visualizer Authoring Specialist Skill

This skill guides the creation and adaptation of visualizers for ToroidAMP.

---

## 1. When to Use
* Implementing a new internal visualizer subclassing `Visualizer`.
* Extracting/adapting legacy demoscene visualizers (starfields, spectrums, 3D wireframes).
* Binding visual parameters (rotation, color, deformation, particles) to `AudioFrame` metrics.
* Handling offscreen Pygame surface rendering, resizing, and fullscreen transitions.

## 2. When NOT to Use
* Writing audio decoders or manipulating audio output streams (use `audio-pipeline`).
* Designing player transport controls or main window layouts (use `reactive-player-ui`).

---

## 3. The Visualizer Contract

All visualizers must subclass `toroidamp.visualizers.base.Visualizer`:

```python
from toroidamp.visualizers.base import Visualizer
from toroidamp.analysis.audio_frame import AudioFrame
import pygame

class CustomVisualizer(Visualizer):
    def __init__(self, width: int = 640, height: int = 480):
        self.w, self.h = width, height

    def get_name(self) -> str:
        return "Custom Name"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def update(self, frame: AudioFrame, dt: float) -> None:
        # Update simulation physics / timers
        pass

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        # Draw directly to the provided offscreen Pygame surface
        pass
```

---

## 4. Musical Thesis (read before mapping signals)

**A visualizer should have a musical thesis.**

Before wiring `AudioFrame` fields to visual parameters, be able to state what the visualizer is actually *about* — what it means for the music to be "doing something" on screen. "Bass makes it bigger" is a parameter mapping, not a thesis. "The camera feels *pushed* by bass, drifts sideways with mids, and sparkles with treble" is a thesis, because it composes multiple fields into a coherent visual idea rather than one field per knob.

**Different music should change character, not only amplitude.** A visualizer whose only observable behavior is "louder music = more movement" has not earned its place — that mapping is explicitly rejected as creatively weak (`docs/visualizers/01_donor_audit_and_creative_direction.md`). Test a new visualizer against genuinely different material — sparse orchestral, classic heavy metal, dense modern metal, electronic, ambient — and ask whether it looks *different*, not just louder or quieter, across them. This echoes the shell's own established principle (POLISH-001): reactivity should be perceptible through contrast between different music, not exaggeration within one song.

**Define silence behavior explicitly.** What does the visualizer do when `rms` is near zero and no beats are firing — between tracks, during a quiet intro, after a song ends? "Freeze the last frame" and "keep animating on residual/decaying state" are both valid answers, but pick one on purpose. A visualizer with no silence behavior tends to either look broken (frozen) or keeps jittering on noise/random fallback, and this is easy to miss until someone actually leaves music paused.

---

## 5. Available Audio Signals (`AudioFrame`)

Visualizers receive normalized, thread-safe `AudioFrame` instances on every frame tick:

| Field | Range / Type | Primary Visual Use Case |
| :--- | :---: | :--- |
| `frame.rms` | $[0.0, 1.0]$ | Overall brightness, master scale, particle velocity. |
| `frame.peak` | $[0.0, 1.0]$ | Flash intensity, peak meter caps. |
| `frame.bass` | $[0.0, 1.0]$ ($20\text{--}250\text{ Hz}$) | Shape expansion, pulse, camera FOV dilation. |
| `frame.mids` | $[0.0, 1.0]$ ($250\text{--}4000\text{ Hz}$) | Rotation speed, plasma color cycles, mesh ripple. |
| `frame.treble` | $[0.0, 1.0]$ ($4000\text{--}20000\text{ Hz}$) | Sparkle, particle emission rate, edge jitter. |
| `frame.spectrum` | $64\text{ floats } [0.0, 1.0]$ | Equalizer bars, frequency ribbons, circular spectrum rings. |
| `frame.waveform` | $128\text{ floats } [-1.0, 1.0]$ | Oscilloscope lines, 3D vertex wave displacement. |
| `frame.beat` | `bool` | Rhythmic step, palette swap, camera snap. |
| `frame.strong_beat` | `bool` | Heavy kick, ghosting trail, screen shake. |

---

## 6. Performance & Rendering Rules
1. **Offscreen Rendering**: Visualizers render to an offscreen `pygame.Surface`. The UI transfers this surface to a Qt `QPixmap` via `pygame.image.tobytes(surface, 'RGBA')`.
2. **Frame Budget**: Keep total `render()` execution under **8 milliseconds** per frame to guarantee 60–120 FPS.
3. **No Qt Operations in Visualizer**: Visualizers must remain pure Python/Pygame/math. Do not import `PySide6` inside visualizer modules.
4. **Failure Isolation**: Visualizer errors should be trapped gracefully; a rendering bug must never crash playback.

---

## 7. Demoscene Historical Note: `fckvar`
ToroidAMP contains exactly **one** intentional archaeological demoscene variable:
* **Name**: `fckvar`
* **Location**: **STRICTLY RESERVED** for `ToroidVisualizer` (`toroid.py`).
* **Semantic Role**: Combined low-frequency deformation factor.
* **Rule**: Do **NOT** create `fckvar` in new visualizers. One archaeological artifact is enough.

---

## 8. Authoring Checklist
* [ ] Can state the visualizer's musical thesis in one sentence — not just a list of signal→parameter mappings.
* [ ] Inherits from `Visualizer` and implements `get_name()`, `resize()`, `update()`, `render()`.
* [ ] Uses real `AudioFrame` metrics rather than synthetic timers or fake sine clocks.
* [ ] Composes multiple `AudioFrame` fields so different genres produce different *character*, not just different amplitude.
* [ ] Defines explicit silence/near-zero-`rms` behavior.
* [ ] Handles `resize()` cleanly when switching between windowed and fullscreen.
* [ ] Runs within the 8ms frame budget.
