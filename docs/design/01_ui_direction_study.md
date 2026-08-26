# ToroidAMP — UI Direction Study

> **"ToroidAMP should feel like somebody accidentally gave a demoscene coder access to a modern UX toolkit."**

This document investigates and defines **three distinct reactive UI directions** for ToroidAMP. Each direction explores a unique interaction philosophy, visual language, and reactive feel, maintaining strict usability while bringing character to desktop playback.

---

## Comparative Overview

| Dimension | Direction A: Retro Instrument | Direction B: Reactive Minimal | Direction C: Demoscene Console |
| :--- | :--- | :--- | :--- |
| **Design Thesis** | Compact high-density cyber-audio appliance with tactile hardware controls and tracker-inspired typography. | Sleek, modern distraction-free canvas where subtle typography and generous visualizer breathing take center stage. | Expressive demoscene workstation featuring vector HUDs, technical audio telemetry, and cyber-terminal aesthetics. |
| **Primary Footprint** | $400 \times 240\text{ px}$ (Compact) / $720 \times 540\text{ px}$ (Expanded) | $320 \times 110\text{ px}$ (Compact) / $680 \times 480\text{ px}$ (Expanded) | $460 \times 280\text{ px}$ (Compact) / $820 \times 600\text{ px}$ (Expanded) |
| **Transport Aesthetic** | Segmented bevel buttons with mechanical click response and LED status jewels. | Flat borderless glyphs with smooth color transitions and contextual hover reveals. | Neon vector brackets, high-contrast toggle chips, and cyber-grid borders. |
| **Visualizer Role** | Integrated instrument display window with bezel framing. | Dominant borderless background or floating reactive hero element. | Framed multi-mode radar viewport with technical grid telemetry overlays. |
| **Musical Reactivity** | Mechanical VU needles / LED bar cascades reacting to RMS & Peak. | Subtle background glow pulse and fluid typographic breathing. | Dynamic HUD vector twitching, real-time FFT telemetry panels, and beat strobe borders. |
| **Implementation Complexity** | Medium | Low | Medium-High |
| **Juice / Gamefeel** | Tactile mechanical snap, springy toggle feedback, LED phosphor glow. | Fluid cubic-bezier morphing, smooth alpha fades, minimalist ripple. | Vector scanlines, phosphor persistence, electronic CRT-flicker transitions. |

---

## Direction A — Retro Instrument

### 1. Design Thesis
Inspired by classic standalone audio players and pro-audio rack gear. It treats the player as a precision physical instrument: information-dense, high tactile affordance, mechanical feedback, and unmistakable playback state.

### 2. Layout & ASCII Wireframe

```text
┌────────────────────────────────────────────────────────┐
│ [ TOROIDAMP v0.1 ]                           [ _ ][ X ] │
├────────────────────────────┬───────────────────────────┤
│  TITLE: Burn The World     │  ┌─────────────────────┐  │
│  ARTIST: Mihwe / Master    │  │                     │  │
│  TIME:  02:45 / 03:20      │  │     3D TOROID       │  │
│  FMT:   MP3 [44.1kHz]      │  │     VIEWPORT        │  │
│  ┌──────────────────────┐  │  │                     │  │
│  │ L: [||||||||||....]  │  │  └─────────────────────┘  │
│  │ R: [||||||||||||..]  │  │   VIS: [ 3D TORUS    v ]  │
│  └──────────────────────┘  │   [FS] [CFG]              │
├────────────────────────────┴───────────────────────────┤
│ [◄◄ PREV]  [► PLAY]  [❚❚ PAUSE]  [■ STOP]  [►► NEXT]   │
│ VOL: [========|===] 80%    SEEK: [====|==============]  │
├────────────────────────────────────────────────────────┤
│ ▼ PLAYLIST (3 TRACKS)                                  │
│  1. Burn The World Waltz.mp3                  03:20    │
│ >2. dalezy-lotus_drei_remix.xm                00:40    │
│  3. 08_sad_song.it                            03:19    │
└────────────────────────────────────────────────────────┘
```

### 3. Interaction & Musical Reactivity
* **Tactile Response**: Buttons depress with a 2-pixel offset and crisp highlight bevel on mouse-down; settled state indicated by green/cyan LED indicators.
* **Music Reactivity**: Dual-channel LED bar meters on the left panel reflect instantaneous `peak` and `rms`. Track title subtly glows on `strong_beat`.
* **Compact Mode**: Collapses the playlist and visualizer into a sleek $400 \times 130\text{ px}$ mini-rack.

---

## Direction B — Reactive Minimal

### 1. Design Thesis
A contemporary, distraction-free aesthetic where visual noise is removed in favor of generous visualizer real estate, clean typography, and fluid kinetic transitions.

### 2. Layout & ASCII Wireframe

```text
┌────────────────────────────────────────────────────────┐
│ ♫ Burn The World Waltz — Mihwe               [ ⛶ ][ ✕ ] │
├────────────────────────────────────────────────────────┤
│                                                        │
│                                                        │
│                     3D TOROID                          │
│                (BORDERLESS HERO VIEW)                  │
│                                                        │
│                                                        │
├────────────────────────────────────────────────────────┤
│ 02:45 ━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━ 03:20  │
│                                                        │
│            [⏮]      [ ▶ / ⏸ ]      [⏭]      [ 🔊 80% ]│
│                                                        │
│  [≡ Playlist (3)]                       [ ✦ Visualizer]│
└────────────────────────────────────────────────────────┘
```

### 3. Interaction & Musical Reactivity
* **Minimal Friction**: Controls softly reveal high-contrast highlights on hover; the progress bar thickens dynamically when seeking.
* **Music Reactivity**: The outer window border softly pulses with ambient color derived from `AudioFrame.mids` and `AudioFrame.bass`. The track title smoothly tracks volume intensity.
* **Compact Mode**: Morphs into a floating pill ($320 \times 70\text{ px}$) displaying track name, mini play/pause, and a subtle single-line waveform ribbon.

---

## Direction C — Demoscene Console

### 1. Design Thesis
An expressive tribute to demoscene tracker culture, second-reality vector graphics, and cyber-terminal telemetry. Highly technical, full of character, and unapologetically stylized while maintaining strict ergonomics.

### 2. Layout & ASCII Wireframe

```text
┌────────────────────────────────────────────────────────┐
│ // TOROIDAMP_CORE :: [ONLINE]            SYS_FREQ: 44.1│
├───────────────────────────────┬────────────────────────┤
│ > TRACK: dalezy-lotus.xm      │ ┌────────────────────┐ │
│ > TYPE : AMIGA_TRACKER [4CH]  │ │▓▓▓ 3D TORUS ▓▓▓▓▓▓▓│ │
│ > BASS : [████████░░] 0.82    │ │    (FCKVAR=1.45)   │ │
│ > MIDS : [█████░░░░░] 0.45    │ │                    │ │
│ > BEAT : [*KICK*]             │ └────────────────────┘ │
│ > FFT  : ▃▄▅█▇▆▅▄▃▂▂          │ [RENDER: OFFSCREEN]    │
├───────────────────────────────┴────────────────────────┤
│ [◄◄ REV] [► EXEC] [❚❚ HOLD] [■ HALT] [►► FWD] [⛶ FULL] │
│ TRACK_POS [ 00:24 // 00:40 ]  ||||||||||||||||........ │
├────────────────────────────────────────────────────────┤
│ == QUEUE BUFFER ====================================== │
│ [01] Burn The World Waltz.mp3               [PCM_OK]   │
│ [02]>dalezy-lotus_drei_remix.xm             [MOD_ACTIVE│
│ [03] 08_sad_song.it                         [PCM_OK]   │
└────────────────────────────────────────────────────────┘
```

### 3. Interaction & Musical Reactivity
* **Vector Aesthetic**: Glowing cyan/magenta HUD brackets, monospace technical readout, real-time FFT sparkline bar graphs, and telemetry labels.
* **Music Reactivity**: Real-time `fckvar` indicator displayed on HUD; UI chassis brackets pulse subtly on `strong_beat`; status lights flash in real time with audio frequency bands.
* **Compact Mode**: Collapses into a high-density cyber-deck ($460 \times 150\text{ px}$) with mini oscilloscope and tactical transport chips.

---

## Recommendations & Next Steps
* Each direction was prototyped in small interactive executable mockups in `experiments/ui_directions/`.
* The directions are submitted for user evaluation to decide the visual and interaction foundation for **Production Cut 1B**.
