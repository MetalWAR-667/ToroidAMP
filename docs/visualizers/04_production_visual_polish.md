# ToroidAMP — VIS-002: Production Visual Polish & Retina Controls

> **If the effect exists in code but the human cannot perceive it, the effect does not exist.**
> **The human is seeking the cyberpunk visual splendour of the mid-90s demoscene.**

---

## 1. Initial Attempt & Human Perceptual Evaluation

VIS-002 initially implemented streak dynamics, multi-band color, floor redistribution, and basic fullscreen HUD controls. However, human validation of the initial implementation identified critical perceptual failures:

* **Deep Field Failures**:
  - Central circular bloom appeared as a mostly static on/off circle rather than a continuous amplitude vibration/breathing effect.
  - Overall star palette collapsed predominantly into one pink hue rather than presenting vivid multi-family spectral color gradation.
  - Streak response was delayed and infrequent during normal beats.
* **ToroidAMP Floor Failures**:
  - Illuminated tiles drifted out of alignment with the perspective wireframe grid because the grid scrolled while tiles remained static.
  - Tiles lacked visual power and hot glow cores.
  - A distracting blue horizontal stripe along the horizon degraded visual aesthetics.
* **3D Toroid Failure**:
  - FOV scaling did not communicate true 3D Z-depth camera travel ("moving toward / away from camera").
* **RETINA MELT Missing UX**:
  - Missing seek timeline and canonical scrolling marquee title.

---

## 2. Follow-Up: Perceptual Failures & The "Purple Disc" Trap

During human evaluation of the second iteration in RETINA MELT fullscreen:
1. **Deep Field**: The central purple alpha circle contributed nothing visually; it obstructed the vanishing point, flattened the depth of the 3D star tunnel, and felt like an artificial geometric sticker. Fullscreen density still felt sparse.
2. **ToroidAMP Floor**: Although geometry correctly followed the wireframe grid, illuminated cells looked like dark, translucent polygons rather than **EMISSIVE LIGHT**. Fullscreen density was weak, and too few cells had meaningful presence.

---

## 3. JACK PERCEPTUAL RESCUE

Jack (Demoscene Visual Engineer) was brought in with creative authority to eliminate decorative crutches, apply authentic demoscene software rasterization tricks, and enforce the primary rule: **LIGHT IS NOT OPACITY.**

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ DEEP FIELD: Zero Center Obstruction + Infinite Cosmic Vanishing Point   │
│             + Emissive Star Heads + Rhythmic Streak Flares              │
├─────────────────────────────────────────────────────────────────────────┤
│ TOROIDAMP FLOOR: Multi-Layer Emissive Cells (Saturated Body + Hot White │
│                  Core + White Outlines) + Broad Spectral Resonance      │
├─────────────────────────────────────────────────────────────────────────┤
│ 3D TOROID: Genuine 3D Z-Depth Perspective Camera Travel                 │
├─────────────────────────────────────────────────────────────────────────┤
│ RETINA MELT: 2-Row HUD + MarqueeLabel + SeekSlider Timeline             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. JACK FINAL PERCEPTUAL TUNING: Photon Trails & Dark Floor Baseline

Human validation confirmed that both visualizer compositions are conceptually right, but required precision perceptual tuning in RETINA MELT:

### 1. Deep Field: Multi-Pass Photon Trail Model
* **The Problem**: Star streaks looked like hard, crisp 1px/2px vector lines rather than luminous particles tearing through space.
* **Technique Rejected**: Expensive full-resolution Gaussian CPU blur (would cost 15–25ms per frame at 1080p).
* **Technique Selected (Multi-Pass Emissive Drawing)**:
  - **Outer Soft Halo Line**: A wider line (3–5px on near stars) drawn with reduced intensity in the star's spectral color family to fake optical blur.
  - **Inner Saturated Trail Line**: A 2–3px saturated line preserving the star's vivid spectral color.
  - **Hot Emissive Star Head**: A concentric 2-layer point with a saturated outer glow disc (`radius + 1`) and a hot white/near-white inner core disc (`radius`).
  - **Depth-Dependent Light**: Near-field stars ($z \to 0$) receive full photon halos and large emissive heads; distant stars ($z \to 1$) remain crisp pin-points to keep the vanishing point open and readable as deep space.

### 2. ToroidAMP Floor: Dark Silence Baseline & Explosive Dynamic Range
* **The Root Cause**: The previous rescue used an unconditional $+0.35$ base brightness floor and linear activation without a noise threshold, causing dozens of cells to remain lit even during idle/quiet passages.
* **Technique Selected (Shaped Non-Linear Activation & Wave Attenuation)**:
  - **Dead Zone & Power Curve**: Raw FFT bin values and audio band metrics below `0.10` are completely suppressed. Values above `0.10` follow a shaped power response ($E_{\text{shaped}} = ((E - 0.10) / 0.90)^{1.35}$).
  - **Silence is a State**: When playback stops or during quiet intros ($E \approx 0$), `tile_target` is strictly zero. Persistent energy rapidly decays ($k=2.8/\text{sec}$) to a clean, dark floor with a cyan perspective wireframe within 1.5 seconds.
  - **Dynamic Range**: Quiet audio produces sparse, isolated glowing cells; energetic tracks ignite dense multi-cluster neon fields with hot white cores; beats trigger traveling wave bursts with physical spatial attenuation.
  - **Retained Maximum Spectacle**: Maximum saturation, hot white cores ($35\%$ inset), and white outlines remain preserved when music is playing.

---

## 5. Performance & Frame Budgets

Benchmarked across 200 frames on Python 3.14 + Pygame-ce (metal profile, warmup dropped):

| Visualizer | Windowed (420×240) | Fullscreen (1920×1080) | 60 FPS Frame Budget Status |
|---|:---:|:---:|:---:|
| **Deep Field (Photon Trails)** | 2.48 ms avg / 2.62 ms p95 | 3.72 ms avg / 4.12 ms p95 | Well within 8.0 ms frame budget |
| **ToroidAMP Floor (Dark Baseline)** | 1.65 ms avg / 1.72 ms p95 | 3.05 ms avg / 3.22 ms p95 | Well within 8.0 ms frame budget |
| **3D Toroid** | 6.75 ms avg / 6.84 ms p95 | 8.08 ms avg / 8.76 ms p95 | Pure software 3D wireframe render |

---

## 6. Automated Test Results

* **`tests/test_vis_002.py`**: **24/24 passed** (100%).
* **`tests/test_vis_001.py`**: **22/22 passed** (100%).
* **Full Test Suite**: **231 passed, 0 failed, 1 skipped** in 9.65s.

---

## 7. Final Human Validation Procedure

### 1. Deep Field Validation (RETINA MELT Fullscreen)
1. Run `python -m toroidamp`, switch to `MODE: DEEP FIELD`, and enter fullscreen (`⛶ MELT`).
2. Play dynamic tracks (metal, orchestral, electronic):
   - Confirm star trails look like **luminous photon trails** with soft outer halos, bright saturated bodies, and hot white heads.
   - Confirm near-field stars visibly carry stronger photon glow than distant stars.
   - Confirm the cosmic vanishing point remains completely open and unobstructed.
   - Confirm beats trigger immediate responsive streak elongation and transient chromatic fringe.

### 2. ToroidAMP Floor Validation (RETINA MELT Fullscreen)
1. Switch to `MODE: TOROIDAMP FLOOR` in fullscreen:
   - **Check Silence**: Stop/pause audio; confirm the floor decays within ~1.5s to a **clean, mostly black floor with a restrained cyan wireframe** (zero active cells).
   - **Check Quiet Audio**: Play quiet/ambient audio; confirm sparse, isolated, gentle glowing cells emerge.
   - **Check Energetic Audio**: Play heavy metal/electronic tracks; confirm the floor progressively powers up into rich, densely illuminated neon bands with hot white cores.
   - **Check Beats**: Confirm beats and kicks trigger bright traveling wave bursts across the perspective grid.
