# ToroidAMP — POLISH-001: Reactive Neon Chassis Report

> **"BLACK INSTRUMENT + THIN CYAN ELECTRIC EDGES + SUBTLE BREATHING + SMALL MUSICAL RESPONSE."**
> **"The visualizer owns the spectacle; the shell owns the atmosphere."**

---

## 1. Problem
On dark/black desktop environments, the dark cyber chassis ($#0a0b10$) was visually too difficult to distinguish, losing its silhouette and tactile instrument presence. A static border or generic RGB cycling would either look lifeless or resemble noisy gaming hardware.

---

## 2. Design Intent & Spectral Model
Implement an atmospheric, restrained reactive neon identity with distinct **spectral discrimination**:
* **Baseline Breathing**: Clearly perceptible $\sim 3.2\text{s}$ sine breathing cycle ($\text{swing} \ge 0.25$ in NORMAL mode).
* **Spectral Color Space**:
  * **Mids / Neutral Balance**: Electric Cyan ($H=186^\circ$, $S=100\%$).
  * **Bass Dominance**: Controlled Violet / Deep Magenta blend ($H=285^\circ$) indicating low-end power.
  * **Treble Dominance**: Ice-blue / Near-white Cyan tint ($H=195^\circ$, slightly reduced saturation).
* **Dynamic Energy (RMS)**: Controls overall luminosity and brightness, not raw hue.
* **Expressive Track Display**: The song title rectangle acts as the primary reactive instrument panel, glowing dynamically with spectral color and pulsing on beat kicks.
* **Full Module & Panel Propagation**: Propagated Tier-2 neon styling across docked/floating `VisualizerModule` inner viewport and `PlaylistModule` list views.
* **Unobtrusive MINI Strip**: Maintained quiet, restrained breathing ($< 16\%$ swing).


---

## 3. Neon Hierarchy (Tiers)

| Tier | Component | Color / Value Range | Visual Role |
| :--- | :--- | :--- | :--- |
| **Tier 1 — Chassis / Outer Edge** | Outer chassis perimeter & floating module edges | HSV $(186^\circ, 95\%, 170\text{--}255, 190\text{--}255)$ | Strongest persistent silhouette against dark backgrounds |
| **Tier 2 — Panel / Section Edges** | Module docking seams, LCD framing, progress groove | HSV $(186^\circ, 80\%, 90\text{--}170, 120\text{--}200)$ | Subdued structural framing without visual clutter |
| **Tier 3 — Interactive Controls** | Transport buttons, VIS / PL chips, sliders | Normal: #1f273d border; Hover: #00f0ff; Pressed/Checked: Solid cyan fill | Tactile feedback and immediate button affordance |

---

## 4. Breathing & Audio Reactivity Model

Calculated in `ReactiveNeonController.update(dt, frame, is_mini)`:
```text
Phase: phase += dt * 1.96  (Period = 2 * pi / 1.96 ≈ 3.2 seconds)
Breath Sine: breath = (sin(phase) + 1.0) * 0.5  [0.0 to 1.0]

NORMAL Mode:
Intensity = 0.50 + (breath * 0.22) + (RMS * 0.18) + (beat_decay * 0.10)
Clamped: [0.20, 1.00]

MINI Mode:
Intensity = 0.42 + (breath * 0.12) + (RMS * 0.08) + (beat_decay * 0.05)
Clamped: [0.20, 0.60]
```

---

## 5. Docked Module Cohesion & Floating State
* **Docked Modules**: When a module is magnetically docked to the chassis, its outer border automatically scales down to Tier 2 intensity, creating a single seamless instrument silhouette rather than a doubled neon seam.
* **Floating Modules**: When undocked, the module border returns to Tier 1 electric cyan, maintaining a distinct presence against the desktop.

---

## 6. Implementation Architecture & Performance
* **Single Shared Controller**: `ReactiveNeonController` computes coordinated `NeonState` objects in `WindowManager._tick()`.
* **Zero Repaint Storms**: Custom `paintEvent` implementations on `UnifiedChassis` and `ModuleShell` render antialiased rounded rect outlines in single-pass Qt painting without costly multi-layer drop-shadow effects or per-frame QSS re-parsing.
* **Tray & Background Optimization**: When minimized to tray or running without active visualizers, neon updates and Pygame DSP passes are automatically bypassed.

---

## 7. Verification & Test Results
* [`tests/test_polish_001.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_polish_001.py): **PASS (100%)**
  * `test_neon_controller_breathing_cycle`: **PASS** (Smooth sine oscillation without abrupt spikes).
  * `test_mini_mode_subtle_restraint`: **PASS** (MINI amplitude swing $\le 15\%$).
  * `test_audio_reactivity_rms_and_beat`: **PASS** (Validates RMS and transient impulses).
  * `test_neon_state_tier_hierarchy`: **PASS** (Tier 1 > Tier 3 > Tier 2 brightness).
* [`tests/test_fix_002.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_fix_002.py): **PASS (100%)**
* [`tests/test_fix_001.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_fix_001.py): **PASS (100%)**
* [`tests/test_production_cut2.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut2.py): **PASS (100%)**
* [`tests/test_production_cut1b.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut1b.py): **PASS (100%)**

---

## 8. Manual Validation Summary
1. **Dark Desktop Visibility**: On a solid black desktop, the electric cyan chassis silhouette is crisp, distinct, and visible at all times.
2. **Breathing Atmosphere**: The slow 3.2s breathing cycle feels organic and continuous without flashing.
3. **Audio Reactivity**: Bass transients and high RMS audio provide a subtle electric pulse without interfering with the visualizer.
4. **Button Affordance**: Hovering or depressing buttons produces immediate tactile neon feedback.
5. **MINI Quietness**: MINI mode remains calm and unobtrusive during desktop multitasking.

---

## 9. Human Validation History & Design Principle Closure

### A. Initial Evaluation (Partial Failure)
The initial baseline implementation successfully solved the dark-desktop visibility issue and tactile button affordance. However, real-world listening tests revealed critical deficiencies:
* Baseline breathing was too faint to perceive clearly in everyday viewing;
* Neon presence was excessively concentrated on the main chassis outline;
* Dockable modules and interior UI panels did not feel like part of the same electrified instrument;
* Radically different musical genres (e.g. *The Ecstasy of Gold* vs. *Twilight of the Thunder Gods*) generated nearly identical visual feedback because reactivity was purely scaled by raw RMS amplitude.

### B. Spectral Follow-Up & Resolution
To solve this without creating distracting high-frequency flashing:
1. **Spectral Balance Model**: Derived relative spectral distribution from normalized `AudioFrame` bands (`bass`, `mids`, `treble`). Heavy bass gracefully warms the palette into violet/magenta ($H=285^\circ$), while airy orchestral/acoustic treble cools the palette into crisp ice-blue ($H=195^\circ$).
2. **Perceptible Breathing**: Increased NORMAL mode breathing depth ($\text{swing} \ge 0.25$) while keeping frequency locked at a slow, calming $\sim 3.2\text{s}$ sine cycle.
3. **Expressive Track Display**: Promoted the song-title LCD frame to the primary reactive instrument panel, giving immediate feedback that the instrument is listening.
4. **Panel & Module Propagation**: Extended Tier-2 dynamic framing across the `VisualizerModule` inner viewport and `PlaylistModule` list containers.

### C. Final Human Validation
* **Listening Comparison**: A direct comparison between dynamically and spectrally diverse music produced clearly distinguishable visual character while remaining visually restrained and elegant.
* **Human Evaluator Verdict**: *"Queda muy fino."* (Passed 100%).

### D. Authoritative Design Principle

> **"Reactivity should be perceptible through contrast between different music, not through exaggeration within a single song."**
> 
> * **DIFFERENT MUSIC $\to$ DIFFERENT CHARACTER**
> * **MORE MUSIC $\ne$ MORE BLINKING**

This principle dictates that:
* Musical differences should emerge organically over listening time rather than through frantic micro-animations;
* The shell owns **atmosphere** and **differentiation**; the visualizer owns **spectacle**;
* Stronger reactivity does not automatically mean better reactivity.

