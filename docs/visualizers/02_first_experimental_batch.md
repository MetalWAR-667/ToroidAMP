# ToroidAMP — Visualizer Lab II: First Experimental Batch

> GOOD ENGINEERING. BAD TASTE PERMITTED.
> RANDOMNESS PROVIDES VARIATION. MUSIC PROVIDES CAUSALITY.
> SILENCE IS A MUSICAL STATE.

Three experimental visualizers, built entirely outside production, per Lab I's recommendation. **None are registered in the production visualizer selector.** Human evaluation decides what (if anything) gets promoted.

---

## 1. Executive Summary

Lab I established that MetalWar-Installer's visual effects contain valuable rendering DNA driven by fake reactivity (`sin(time.time())`, hardcoded `BPM=128`, `random.random()`). This lab gives three of those algorithms real musical input for the first time: `AudioFrame.rms/bass/mids/treble/spectrum/waveform/beat/strong_beat` from ToroidAMP's actual analysis pipeline.

All three experiments:
* have an explicit, one-sentence musical thesis;
* compose multiple `AudioFrame` fields rather than mapping RMS to everything;
* define deliberate silence behavior (none freeze or go dark);
* use smoothing/inertia for continuous signals and impulse+decay for beat events;
* survive all four required resize targets (420×240 through 1920×1080) without error;
* run comfortably under the 8ms/frame budget everywhere tested (worst case: Floor at 1920×1080, 3.4ms average);
* transform donor algorithms rather than porting them — every fake driver was discarded and rebuilt from real `AudioFrame` composition.

28 new automated tests pass; the full repository suite is unaffected (185 passed, 1 honestly skipped, 0 failed — up from the pre-existing 157 passed / 1 skipped baseline).

**Two real bugs were found and fixed during this lab** (§13, §18): a color-channel overflow in ToroidAMP Floor when strong-beat pulses pushed tile energy above 1.0, and (documented as evidence, not a bug) confirmation that the harness genuinely never calls `update()` — every experiment follows the same self-invoking convention as production, and nothing broke as a result.

---

## 2. Laboratory Architecture

```text
experiments/visualizers/
├── harness.py                  — tiny Pygame runner, one experiment at a time
├── profiles.py                 — deterministic synthetic AudioFrame generators
├── deep_field.py                — Experiment 1: STARFIELD: DEEP FIELD
├── toroidamp_floor.py           — Experiment 2: TOROIDAMP FLOOR
└── matrix_wing_commander.py     — Experiment 3: MATRIX WING COMMANDER
```

Every experiment visualizer subclasses `toroidamp.visualizers.base.Visualizer` (the real production contract — `resize()`/`update()`/`render()`/`get_name()`) for interface parity, but lives entirely in `experiments/`, is never imported by `src/toroidamp/ui/modules/visualizer_module.py` or `src/toroidamp/ui/fullscreen.py` (confirmed by `TestProductionIsolation`, §12), and never imports anything from `MetalWar-Installer` (confirmed by the same test suite — attribution comments naming the donor are expected and present; actual coupling is not).

`profiles.py` and the three experiment modules import `toroidamp.analysis.audio_frame.AudioFrame` and `toroidamp.visualizers.base.Visualizer` directly from the installed production package — this is the shared public contract, not donor coupling, and is exactly what would let a promoted experiment become a real `src/toroidamp/visualizers/*.py` file with minimal changes later.

---

## 3. Synthetic Musical Profiles

`profiles.py`'s `SyntheticProfile` base class is a small deterministic state machine: given a fixed seed and an identical sequence of `tick(dt)` calls, it reproduces comparable musical behavior (beat timing, envelope shape) — verified directly by `test_deterministic_profile_behavior`.

| Profile | Character | Beat interval | Notes |
|---|---|---|---|
| `silence` | Nothing playing | never | All fields `0.0`/`False` — the actual idle-state test case |
| `orchestral` | Sustained mids, broad slow dynamics | 3.0–5.5s, jittered | Slow ~52s dynamic swell (`sin(t*0.12)`), sparse strong beats (20% of beats) |
| `metal` | Dense mids, frequent transients, sustained energy | 0.5s ± jitter (~120bpm) | High sustained rms/mids/treble, strong_beat whenever bass > 0.55 |
| `electronic` | Dominant bass, mechanically regular beat | exactly 0.5s, **no jitter** | 16s build/drop energy cycle, deliberately robotic timing vs. metal's human jitter |
| `ambient` | Low RMS, slow spectral evolution | 10–20s, jittered | Near-silent, very slow sines, strong beats rare (10% of beats) |

`inject_beat(strong=False)` (harness SPACE/ENTER) merges a forced beat into the next `tick()` without disturbing the profile's own scheduled rhythm.

---

## 4. Deep Field

**Musical thesis**: the music changes SPACE, DEPTH, MOMENTUM, and ATMOSPHERE. This is an environment with inertia, not a screensaver with a speed knob.

**Donor DNA**: `effects.py:38` `Starfield`'s 3D projection (`factor = fov/z`), camera-plane rotation, exponential warp smoothing — the math is reused; every driver (`bpm_data`, fake `intensity`) is gone.

**AudioFrame mapping** (all via smoothed/inertial state, `deep_field.py`):

| Field | Behavior | Temporal model |
|---|---|---|
| `bass` | Depth pressure — forward-acceleration baseline | exponential smoothing toward target (`smooth_k = 1-e^(-dt*2.2)`) |
| `mids` | Lateral drift velocity (camera roll tendency) | smoothed velocity, integrated into a persistent camera angle |
| `treble` | Fine/sparkle star-layer density (`+0..220` extra far stars) | smoothed, independent of bass |
| `spectrum` | Warm/cool color bias between near and far star layers (low bins bias near-stars warm, high bins bias far-stars cool) | slow-evolving state (`τ ≈ 2.5s`) |
| `beat` | Short forward-acceleration impulse | fast decay impulse (`e^(-dt*5)`) |
| `strong_beat` | Rare hyperspace/compression event — bounded sine envelope, 0.45s duration | impulse + 1.4s cooldown, never re-triggers mid-event |
| `rms` | Restrained global brightness envelope only | smoothed, deliberately NOT the primary driver of anything structural |

**State/temporal model**: three star populations (near/mid/far, 500 base stars) recycled on reaching the camera plane; a fourth tagged "sparkle" population grows/shrinks toward a treble-driven target each frame.

**Silence behavior**: `depth_pressure` settles to `BASE_CRUISE = 0.35` (never zero) — verified by `test_silence_retains_slow_movement` (settles within 0.05 of `BASE_CRUISE`, always `> 0`). Stars keep drifting; nothing freezes.

**Character targets, empirically verified** (§9): electronic's dominant bass produces measurably higher `depth_pressure` than ambient's minimal bass (`test_bass_influences_depth_state`); metal's combined bass+treble produces a measurably different `star_count` than electronic's bass-only profile despite both having strong bass (`test_treble_influences_detail_independently_of_bass`) — this is the concrete proof that treble and bass drive genuinely independent visual dimensions, not one shared "intensity" knob.

**Beat/strong_beat behavior**: beat impulse verified to decay monotonically after injection (`test_beat_impulse_decays`); strong_beat verified to produce a bounded event that returns toward zero rather than staying pinned (`test_strong_beat_produces_bounded_event_not_spam`), even under repeated rapid injection — the cooldown does its job.

**Resize result**: PASS at 420×240, 800×450, 1280×720, 1920×1080 — no errors, `vis.w`/`vis.h` correctly updated each time.

**Performance** (metal profile, 200-frame sample, warmup dropped): 420×240 avg 0.97ms → 1920×1080 avg 1.50ms. Comfortably under the 8ms budget at every size; scales gently with resolution (mostly per-star draw calls, largely resolution-independent).

**GPU candidate note**: none observed — this experiment is cheap enough that GPU treatment would be solving a problem that doesn't exist yet, even at 1080p.

---

## 5. ToroidAMP Floor

**Musical thesis**: music has entered a physical grid. Frequency structure becomes spatial structure; rhythm propagates through it. Two tracks at a similar BPM but different spectral content must produce visibly different topology — that is the entire point.

**Donor DNA**: `effects.py:1905` `RetroGrid.lit_cells` — confirmed (Lab I) to be a **flat random-spawn-on-kick model with zero propagation and zero spatial meaning**. That flatness is exactly what's discarded; `toroidamp_floor.py` replaces it with spectrum-driven spatial placement and genuine ring-to-ring propagation the donor never had.

**Presentation**: a top-down radial field (10 rings × 28 sectors), not the donor's perspective floor — chosen deliberately for musical readability (explicit instruction: readability over gratuitous camera motion). Low spectrum bins → inner rings; high bins → outer rings.

**AudioFrame mapping**:

| Field | Behavior | Temporal model |
|---|---|---|
| `spectrum[64]` | Direct spatial placement: `ring = (i/63)*RINGS`, `sector = (i*5) % SECTORS` — the primary topology signal | continuous target, filtered through per-tile attack/decay |
| `bass` | Sustained structural illumination floor on the innermost 3 rings | continuous target |
| `mids` | Structural continuity across a mid-band ring region (rings 3–6) | continuous target |
| `treble` | Sharp peripheral accents — a handful of outer-ring tiles (not the whole ring), time-varying selection | continuous target, deterministic phase rotation (not free `random()` spam) |
| `beat` | Local propagation pulse launched from the current spectral-peak position, traveling outward at 4 rings/sec | event → traveling wave state (`_Pulse` list) |
| `strong_beat` | Larger geometric event — 4 simultaneous multi-origin pulses at 1.4× speed and 1.44× strength | event → multiple traveling waves |

**State/temporal model**: every tile (`tile_energy[ring][sector]`) has explicit attack (fast rise toward target, rate 14/s) and decay (`e^(-dt*0.6)`) — this is the floor's memory, giving residual glow rather than instant on/off, exactly per the mission's "explore attack/decay/residual glow" instruction.

**Silence behavior**: all spectral/bass/mids/treble targets go to zero; existing tile energy decays exponentially rather than snapping off — verified `total_energy` drops from ~203 (after 2s of metal) to ~11.6 after 5s of silence, and below 5.0 after 10s (`test_silence_approaches_dormant_state`) — a genuinely dim, dormant, but not instantly-dark grid.

**The signature claim, directly tested**: `test_same_bpm_different_spectrum_produces_different_topology` runs `metal` and `electronic` — both regular ~120bpm profiles — for 3 seconds each and compares the resulting `tile_energy` grids cell-by-cell. Measured total absolute difference: **106.3** (test threshold: >10.0). This is the concrete, numeric proof that similar rhythm does not produce similar shape — the explicit goal Lab I set for this candidate.

**Beat vs strong_beat, directly tested**: `test_strong_beat_differs_from_ordinary_beat` confirms a strong_beat always produces strictly more simultaneous active pulses than an ordinary beat from an identical silent baseline.

**Resize result**: PASS at all four required sizes.

**Performance** (metal profile, 200-frame sample): 420×240 avg 0.76ms → **1920×1080 avg 3.40ms** (p95 4.15ms, max 4.39ms). Still comfortably under the 8ms budget, but this is the steepest resolution-scaling curve of the three experiments — polygon fill cost scales with screen area at up to 280 tiles/frame.

**GPU candidate note**: **mild candidate**. If a future iteration wants substantially more tiles (finer rings/sectors) or a genuinely 3D/perspective presentation at 4K, the per-tile polygon-fill cost would start competing for the frame budget well before the other two experiments do. Not urgent — 3.4ms at 1080p leaves ample headroom — but worth flagging as the first place resolution scaling would actually bite.

---

## 6. Matrix Wing Commander

**Musical thesis**: Matrix rain. Spaceships. Music. No further conceptual justification required — but the implementation must be musically intelligent. Category: BECAUSE WE CAN, culturally protected.

```python
# Why?
# Because we could.
```
(present in `matrix_wing_commander.py`, both as a module-level statement and inline at the ship-spawn call site, per the mandatory-comment instruction.)

**Donor DNA**: `effects.py:2072` `PeaceCodeRain`'s pre-rendered per-glyph cache technique (16 hex chars × 2 colors, built once) — reused directly. `effects.py:2173` `PraxisEvent`'s `spawn_xwing`/`draw_xwing_3d` waypoint-flight concept — reused as a concept (fractional-coordinate routes + `1/z` perspective scale); the donor's specific hand-authored routes (tuned for one installer-climax timeline) were **not** reused verbatim — four new generic routes (`diagonal_pass`, `arc_barrel`, `formation_v`, `crossing`) were authored instead, parameterized in fractional screen-space so they survive arbitrary resize.

**Matrix rain mapping**:

| Field | Behavior | Temporal model |
|---|---|---|
| `mids` | Fall velocity | smoothed target |
| `treble` | Column density (18 base → up to 64) and per-glyph highlight | smoothed target |
| `bass` | Subtle per-column horizontal wobble/distortion | smoothed target |
| `beat` | Short global luminance flash + brief speed boost | fast-decay impulse |
| `spectrum` | **Regional column behavior** — each column samples one specific spectrum bin (`bin_i = i % 64`), so columns are provably not identical across a track | per-column, per-frame |

**Ship system** (event-driven, not timer-driven):

| Field | Behavior |
|---|---|
| `rms` | Baseline cruise energy — how briskly an *already-active* pass proceeds |
| `bass` | Apparent scale/perspective pressure (global scale multiplier on active ships) |
| `beat` | Maneuver impulse — speeds up existing passes; **never spawns a new one** |
| `strong_beat` | Formation-pass launch — the *only* way a `_ShipPass` is created, gated by a 1.2s cooldown |

Randomness (seeded, `random.Random(2049)`) selects **which** route (`diagonal_pass`/`arc_barrel`/`formation_v`/`crossing`), **which** ship silhouette (X-Wing/Y-Wing), and **how many** ships (2–4) — strictly variation, never causality. This is the mission's explicit GOOD/BAD example implemented literally: `test_ship_events_derive_from_beat_not_pure_random` proves it — a synthetic profile with `rms=0.8, bass=0.8` etc. but `beat=False, strong_beat=False` hardcoded for 10 full seconds produces **exactly zero** ship passes.

**Silence behavior**: rain persists at the sparse baseline (18 columns, never fewer) — verified `test_rain_persists_at_silence_at_low_intensity`. Ships: zero passes ever, verified over 15 simulated seconds (`test_silence_does_not_spam_ships`) — "minimal matrix drift, no gratuitous attack-run spam," exactly as specified.

**Determinism**: `test_seeded_randomness_selects_deterministic_event_variant` drives two independent visualizer instances with an identical injected strong-beat sequence and confirms they select the identical sequence of ship silhouettes — the seeded RNG is genuinely deterministic, not merely "usually similar."

**Resize result**: PASS at all four required sizes — routes are fractional-coordinate, so this was expected to hold and did.

**Performance** (metal profile, 200-frame sample): 420×240 avg 0.86ms → 1920×1080 avg 1.37ms. Cheapest of the three experiments even with active ship passes running.

**GPU candidate note**: none observed at current scale. The per-glyph blit cache technique (donor DNA) is already doing the expensive part in advance; a much denser rain (hundreds of columns) or per-pixel chromatic distortion on the whole rain field would be the point where GPU treatment starts to matter.

---

## 7. Donor Algorithms Reused

| Donor source | What was reused | What was discarded |
|---|---|---|
| `effects.py:38` `Starfield` | 3D projection math (`factor = fov/z`), camera-plane rotation concept, exponential smoothing pattern | `bpm_data`, fake `intensity`, fixed 4-color palette cycling |
| `effects.py:1905` `RetroGrid` (`lit_cells`) | The *concept* of an illuminated cell field with color + fade — but not the random-spawn mechanism itself | Random per-cell spawn-on-kick (replaced with spectrum-driven placement); independent-decay-only model (replaced with propagation) |
| `effects.py:2072` `PeaceCodeRain` | Pre-rendered per-glyph cache technique (verbatim pattern: 16 hex chars × 2 colors, built once in `__init__`) | Nothing else — the donor's fall logic was pure-timer and not worth reusing |
| `effects.py:2173` `PraxisEvent` (`spawn_xwing`/`draw_xwing_3d`) | Waypoint-route + `1/z` perspective-scale concept; simple vector-line ship silhouettes | The donor's specific hand-authored routes (installer-climax-timed), all installer-narrative coupling (install state, bundled PNGs, specific SFX) |

Confirmed via `TestProductionIsolation.test_experiments_do_not_import_from_donor_repo`: no experiment file imports from or references a filesystem path inside `MetalWar-Installer` — every reuse is a *reimplementation informed by* the donor math, never a dependency on donor code.

---

## 8. AudioFrame Mapping Comparison

| Field | Deep Field | ToroidAMP Floor | Matrix Wing Commander |
|---|---|---|---|
| `rms` | Restrained global brightness only | — (not used directly) | Ship cruise energy baseline |
| `bass` | Depth pressure (forward accel) | Central/inner-ring sustained illumination | Rain distortion; ship scale/perspective pressure |
| `mids` | Lateral drift velocity | Structural mid-ring continuity | Rain fall velocity |
| `treble` | Fine star density/sparkle | Peripheral accent tiles | Rain column density/brightness |
| `spectrum[64]` | Near/far color bias (aggregate low/high split) | **Direct spatial placement** (per-bin ring+sector) | **Direct per-column assignment** (one bin per column) |
| `beat` | Short acceleration impulse | Local propagation pulse from spectral peak | Rain luminance/speed flash; ship maneuver impulse |
| `strong_beat` | Rare bounded compression event (cooldown-gated) | Larger multi-origin pulse burst | Formation-pass launch (cooldown-gated, the *only* spawn trigger) |
| `waveform[128]` | — (not used) | — (not used) | — (not used) |

No experiment uses every field — matching Lab I's explicit "prefer meaningful mappings over exhaustive mappings." `waveform` went unused across all three; this is not a gap, it simply wasn't the right signal for any of these three theses (a future oscilloscope-family experiment would be the natural place for it).

---

## 9. Musical Differentiation Findings

Directly measured, not just asserted:

* **Deep Field**: electronic (dominant bass) produces measurably higher smoothed `depth_pressure` than ambient (minimal bass) after 5 seconds. Metal (high bass+treble) produces a measurably different `star_count` than electronic (high bass, moderate treble) despite comparable bass — proof that bass and treble drive genuinely separable visual dimensions.
* **ToroidAMP Floor**: bass-dominant material (electronic) concentrates measurably more energy in the inner 3 rings than the outer 2 rings. **Metal vs. electronic at comparable ~120bpm beat rate produce a summed tile-energy difference of 106.3** — the core signature claim, numerically confirmed, not just visually plausible.
* **Matrix Wing Commander**: metal (high treble) sustains a measurably higher column count than ambient (low treble) after 5 seconds. Ship passes are proven to depend entirely on `strong_beat`, never on elapsed time or `random()` alone.

All three experiments therefore satisfy the audit's authoritative test — **different music produces different character**, not merely different volume of the same behavior.

---

## 10. Temporal/Smoothing Findings

Every continuous `AudioFrame` field (bass, mids, treble, rms) is consumed through exponential smoothing (`1 - e^(-dt*k)`) with a per-signal time constant chosen for what it represents — fast for things that should feel responsive (treble density, ~0.3s), slower for things that should feel like atmosphere (spectral color bias in Deep Field, ~2.5s). Every discrete event (`beat`, `strong_beat`) is consumed as an impulse-plus-decay or a cooldown-gated state machine, never as a raw boolean directly driving a visual parameter for exactly one frame. No experiment exhibited visible jitter from raw per-frame noise during manual smoke-testing — the smoothing layers did their job. This validates the mission's explicit guidance (bass=smooth, beat=impulse+decay, spectral identity=slow state) as sound default practice, not merely a suggestion.

---

## 11. Resize Results

All three experiments tested at all four required targets — **420×240, 800×450, 1280×720, 1920×1080** — via `test_resize_safe` in each test class: `resize(w, h)` followed by several render ticks, confirming no exception and correct `vis.w`/`vis.h` state afterward. **PASS for all three at all four sizes.** No hardcoded pixel assumptions were found or introduced — every spatial calculation in all three experiments derives from `self.w`/`self.h` (Deep Field: `cx=self.w/2`; Floor: `max_radius = min(self.w,self.h)*0.46`; Matrix: fractional route coordinates × `self.w`/`self.h`).

---

## 12. Performance Results

200-frame samples (first 20 dropped as warmup), `metal` profile, measured with `time.perf_counter()` around `render()` only:

| Experiment | 420×240 | 800×450 | 1280×720 | 1920×1080 |
|---|---|---|---|---|
| Deep Field | 0.97ms | 1.05ms | 1.23ms | 1.50ms |
| ToroidAMP Floor | 0.76ms | 1.28ms | 2.23ms | **3.40ms** |
| Matrix Wing Commander | 0.86ms | 0.96ms | 1.09ms | 1.37ms |

All three stay well under the 8ms/frame budget (`visualizer-authoring` §6) at every tested resolution — full 60fps headroom even at 1080p. **ToroidAMP Floor is the one to watch**: its cost scales most steeply with resolution (polygon-fill area), and is the only one flagged as even a mild future GPU candidate (§5).

No allocation hotspots were identified as blocking — Deep Field's star list mutation (`list.remove()` in a loop when shrinking the sparkle layer) is the least elegant piece of the three and would be the first thing to optimize (swap to a preallocated pool) if this experiment were promoted and pushed to much higher star counts.

---

## 13. Contract Evidence

Lab I flagged two contract quirks and asked this lab to gather real evidence rather than assume they matter.

1. **`update()` is never called by any harness — confirmed, and it didn't matter.** `harness.py` (like production's `VisualizerModule`/`RetinaMeltWindow`) calls only `render(surface, frame, dt)`. All three experiments follow the exact same convention as `ToroidVisualizer`/`WaveformRibbonVisualizer`: `render()` calls `self.update(frame, dt)` internally as its first line. Building three more visualizers this way surfaced zero friction and zero bugs traceable to this pattern — the convention is load-bearing but stable. **Evidence-based recommendation: leave it as-is.** It is a discoverability wart for a future author who doesn't read an existing visualizer first, not a functional problem.
2. **`reset()` remains dead code.** None of the three experiments needed it — visualizer switching wasn't exercised by this lab (each harness invocation runs exactly one experiment), so this lab's evidence is silent on whether `reset()` would matter for switching. Recommendation: still no action; this lab simply didn't generate evidence either way.
3. **A genuine new finding, not predicted by Lab I**: ToroidAMP Floor's color computation revealed that `AudioFrame`-driven internal state can legitimately exceed the `[0.0, 1.0]` range that `AudioFrame` itself enforces — `tile_energy` intentionally overshoots past 1.0 during a strong-beat pulse (by design: a visible "hot" moment as the wave passes). This is not an `AudioFrame` contract problem (its own fields stayed correctly normalized throughout — verified by `test_all_profiles_construct_valid_audioframes`), but it is a reminder that visualizer-*internal* derived state does not inherit `AudioFrame`'s `[0,1]` discipline automatically, and pixel-color code must clamp explicitly at the point of conversion to RGB. This was caught immediately by manual smoke-testing (a `pygame.draw.polygon` call raising `ValueError: invalid color`) and fixed in the same session (§18) — worth stating as authoring guidance rather than an `AudioFrame` change.

---

## 14. PostFX Evidence

No global PostFX system was built, per explicit instruction. Local, small-scale post-like techniques were used within single experiments where they materially served the thesis:

* **Deep Field**: near-field streak lines (a trail effect drawn as a short line from a star's previous position rather than a single point) — this is a local, cheap post-like technique, not the full donor bloom/chromatic-aberration pipeline.
* **Matrix Wing Commander**: a full-surface `BLEND_ADD` fill on `beat` for the luminance-flash effect — directly analogous to the donor's chromatic/bloom pipeline's additive-blend technique (§Lab I `apply_glitch`), scaled down to a single cheap full-surface tint rather than a multi-pass bloom/chromatic/vignette stack.

Neither experiment needed the donor's full chromatic-aberration/bloom/vignette pipeline (`main.py:1310-1495`, Lab I §4.17) to satisfy its thesis. **Recommendation, not action**: if a future experiment (or a promoted visualizer) wants a shared "beat flash" or "chromatic pulse" primitive, that repeated pattern (both experiments independently reached for an additive full-surface tint on beat) is worth factoring into a genuinely small, local helper function — not the full PostFX architecture Lab I described, and still not built here, per instruction to only recommend, not architect.

---

## 15. GPU Candidates

Recorded as evidence for a future `EXP-GL-001`, per instruction — nothing installed or implemented:

* **ToroidAMP Floor** (§5, §12): the only experiment where resolution scaling meaningfully ate into the frame budget (3.4ms at 1080p vs. ~1.3-1.5ms for the other two). A denser tile field or a true 3D/perspective presentation at 4K would be the first place in this batch where software rendering genuinely fights back.
* **Deep Field's near-field streaks**: currently drawn as individual `pygame.draw.line` calls per streaking star; a GPU point-sprite/line-instancing approach would scale to far higher star counts than the current ~500-720 star budget without a linear per-star cost increase — not needed at current scale, but the ceiling is closer here than in Matrix Wing Commander.
* **No experiment in this batch actually needed GPU treatment** — this is itself useful evidence: three donor-DNA-derived visualizers, built with real musical mapping and reasonable star/tile/column counts, all comfortably fit the software budget. GPU work remains correctly deferred to `EXP-GL-001` and should be motivated by a *new* visual idea (per Lab I's Aurora Field proposal) rather than by these three needing rescue.

---

## 16. Human Evaluation Instructions

```bash
python experiments\visualizers\harness.py deep-field
python experiments\visualizers\harness.py floor
python experiments\visualizers\harness.py matrix-wing
```

Controls (also drawn live in the window's top-left overlay):

```text
1-5     switch profile: SILENCE / ORCHESTRAL / METAL / ELECTRONIC / AMBIENT
SPACE   inject a beat
ENTER   inject a strong_beat
F       toggle the FPS/debug overlay
ESC     quit
```

The window is resizable — drag any edge to confirm the resize behavior live, matching the automated `test_resize_safe` coverage.

---

## 17. Promotion Recommendations

### Deep Field
* **NAME**: Starfield: Deep Field
* **MUSICAL THESIS**: The music changes space, depth, momentum, and atmosphere — not just speed.
* **DONOR DNA USED**: `Starfield` 3D projection + camera-rotation + smoothing pattern.
* **AUDIOFRAME MAPPING**: bass→depth pressure, mids→lateral drift, treble→sparkle density, spectrum→color bias, beat→impulse, strong_beat→bounded compression event, rms→restrained brightness.
* **STATE/TEMPORAL MODEL**: exponential smoothing on continuous signals, impulse+decay on beat, cooldown-gated bounded event on strong_beat.
* **SILENCE BEHAVIOR**: settles to a slow inertial cruise (`BASE_CRUISE=0.35`), never stops.
* **ORCHESTRAL CHARACTER**: gentle, warm-leaning, sparse lurches.
* **METAL CHARACTER**: dense near field, frequent controlled impulses, high star_count.
* **ELECTRONIC CHARACTER**: strong sustained depth pressure from dominant bass, punchy on the regular beat grid.
* **AMBIENT CHARACTER**: near-cruise baseline, minimal color drift.
* **BEAT BEHAVIOR**: short forward-acceleration impulse, fast decay.
* **STRONG_BEAT BEHAVIOR**: rare, cooldown-gated, bounded 0.45s compression event.
* **RESIZE RESULT**: PASS, all four sizes.
* **PERFORMANCE RESULT**: 0.97–1.50ms across all sizes — cheapest-to-mid of the three.
* **CREATIVE STRENGTH**: genuinely feels like an environment, not a speed-o-meter; the near/far color-bias split is subtle and effective.
* **TECHNICAL WEAKNESSES**: sparkle-layer add/remove uses `list.remove()` in a loop (fine at current scale, would need a pool at much higher star counts).
* **PRODUCTION PROMOTION RECOMMENDATION: YES** — lowest risk, cleanest donor evolution, ready for real-music validation with only cosmetic polish remaining.

### ToroidAMP Floor
* **NAME**: ToroidAMP Floor
* **MUSICAL THESIS**: Music has entered a physical grid — frequency structure becomes spatial structure, rhythm propagates through it.
* **DONOR DNA USED**: `RetroGrid.lit_cells` concept (illuminated cell + fade), deliberately NOT its random-spawn mechanism.
* **AUDIOFRAME MAPPING**: spectrum→direct spatial placement (the core mechanism), bass→inner-ring floor, mids→mid-ring body, treble→outer accents, beat→propagation pulse, strong_beat→multi-origin burst.
* **STATE/TEMPORAL MODEL**: per-tile attack (fast)/decay (slow) memory; traveling `_Pulse` objects for propagation.
* **SILENCE BEHAVIOR**: dim dormant grid, energy exponentially fades, never instant-off.
* **ORCHESTRAL CHARACTER**: broad, slowly evolving regions (not directly re-tested this lab, inferred from mapping — see Known Limitations).
* **METAL CHARACTER**: dense, high total energy, frequent propagating pulses.
* **ELECTRONIC CHARACTER**: strongly bass-concentrated (inner rings), mechanically regular pulses.
* **AMBIENT CHARACTER**: sparse, low energy (inferred, not directly re-tested — see Known Limitations).
* **BEAT BEHAVIOR**: single propagation pulse from the current spectral peak.
* **STRONG_BEAT BEHAVIOR**: four simultaneous origin pulses, faster and stronger than a normal beat — numerically confirmed distinct.
* **RESIZE RESULT**: PASS, all four sizes.
* **PERFORMANCE RESULT**: 0.76–3.40ms — steepest resolution scaling of the three, still within budget.
* **CREATIVE STRENGTH**: the strongest, most literal fulfillment of "different music, different shape" in the whole batch — numerically proven (106.3 topology difference, same BPM).
* **TECHNICAL WEAKNESSES**: highest performance cost at 1080p (still fine, but the one to watch); top-down radial presentation is a deliberate readability choice that trades away the donor's perspective-floor spectacle — worth a second presentation experiment if human evaluation wants more camera drama.
* **PRODUCTION PROMOTION RECOMMENDATION: YES** — this is the SIGNATURE candidate Lab I predicted, and the numbers back it up. Recommend prioritizing this for real-music validation first.

### Matrix Wing Commander
* **NAME**: Matrix Wing Commander
* **MUSICAL THESIS**: Matrix rain, spaceships, music. (No further justification required.)
* **DONOR DNA USED**: `PeaceCodeRain`'s glyph-cache technique; `PraxisEvent`'s waypoint-route + perspective-scale concept (new routes authored, not the donor's specific ones).
* **AUDIOFRAME MAPPING**: mids→fall speed, treble→density, bass→wobble+ship scale pressure, spectrum→per-column regional variation, beat→flash+maneuver impulse, strong_beat→**the only ship-pass spawn trigger**.
* **STATE/TEMPORAL MODEL**: smoothed rain parameters; event-driven, cooldown-gated `_ShipPass` list.
* **SILENCE BEHAVIOR**: sparse rain baseline (never fewer than 18 columns), zero ship passes.
* **ORCHESTRAL CHARACTER**: sparse rain (inferred from mids/treble mapping, not directly re-tested — see Known Limitations), rare elegant flybys since strong beats are rare in this profile.
* **METAL CHARACTER**: dense bright rain (directly measured — higher column count than ambient), frequent formation passes (strong_beat fires often).
* **ELECTRONIC CHARACTER**: mechanically regular rain rhythm and pass timing (inferred from the profile's own regularity — not separately re-tested here).
* **AMBIENT CHARACTER**: minimal rain, essentially no ship activity (strong_beat is rare in this profile).
* **BEAT BEHAVIOR**: luminance flash + existing-pass speed boost — never spawns anything new.
* **STRONG_BEAT BEHAVIOR**: launches a new formation pass (2-4 ships, seeded-random route/kind selection), cooldown-gated — proven causally tied to strong_beat, not to elapsed time or free randomness.
* **RESIZE RESULT**: PASS, all four sizes.
* **PERFORMANCE RESULT**: 0.86–1.37ms — cheapest of the three even with active ships.
* **CREATIVE STRENGTH**: the ship-causality design (music decides WHEN, randomness decides WHICH) is exactly the mission's stated ideal, cleanly and verifiably implemented.
* **TECHNICAL WEAKNESSES**: ship silhouettes are intentionally minimal (crossed lines / triangle) — fine per "abstraction is sufficient, this is not a flight simulator," but the visual punch of a "formation pass" is the weakest-rendered of the three experiments' signature moments and would benefit from more deliberate on-screen readability (bigger, more numerous ships, clearer approach/depart framing) if promoted.
* **PRODUCTION PROMOTION RECOMMENDATION: MAYBE** — the engineering and causality model are solid and correctly protected per the mission's cultural mandate, but the actual ship-pass spectacle needs a visual-polish pass (this lab prioritized correct musical causality over visual punch) before it's genuinely promotion-ready. Recommend a short follow-up focused purely on ship/formation visual readability, not re-architecture.

---

## 18. Skill Changes

**No changes were made to `visualizer-authoring` in this lab.** Per the explicit instruction ("update only with evidence... demonstrated by THREE experiments or a particularly strong failure"), the evidence gathered was evaluated against the four candidate questions:

* **Is silence behavior guidance sufficient?** Yes — the skill's existing silence-behavior guidance (added in Lab I's own update) was directly followed by all three experiments without friction or ambiguity. No gap found.
* **Does randomness policy belong in the skill?** Considered, not added. All three experiments independently converged on "music decides WHEN, randomness decides WHICH" without needing it stated as a skill rule — it emerged naturally from having a real musical thesis, suggesting the existing "musical thesis" guidance (also from Lab I) already does the necessary work. Adding a separate randomness rule now would be pre-emptive rather than evidence-driven; if a fourth experiment gets this wrong, that's the trigger to add it.
* **Should temporal smoothing/inertia become explicit?** Considered, not added. All three experiments used smoothing/impulse-decay/cooldown patterns successfully and without incident (§10). This is a real, demonstrated pattern — but three *successful* uses of a technique is not the same evidentiary bar as "a particularly strong failure," and the technique itself (exponential smoothing, impulse+decay) is standard enough that documenting it risks becoming implementation trivia the skill explicitly warns against. Deferred, not rejected — if Lab III's experiments also reach for the identical pattern, that repetition would tip this into "durable enough."
* **Do strong beats need event semantics rather than scalar semantics?** This is the closest candidate to a real finding. All three experiments treat `strong_beat` as a discrete, cooldown-gated *event* (spawns something, launches something, triggers a bounded state machine) rather than a scalar intensity multiplier — and this pattern was load-bearing in avoiding "spam" in all three (Deep Field's compression-event cooldown, Floor's multi-origin burst, Matrix's pass-launch gate). This is a genuine, repeated, three-for-three pattern. **However**, it was not added to the skill in this pass, because the existing "musical thesis" + "silence behavior" language already implicitly covers it (a thesis-driven author naturally arrives at event semantics once they've internalized "different character, not just amplitude"), and the mission's own instruction for this lab explicitly says not to update the skill "just because new visualizers exist." This is flagged here as the strongest candidate for a **Lab III** skill update if a fourth experiment independently confirms the same pattern.

---

## 19. Known Limitations

* **Character-target claims for ORCHESTRAL and AMBIENT are partially inferred, not all independently re-tested in this lab.** The automated test suite directly measures metal-vs-ambient and metal-vs-electronic differentiation (the highest-contrast, most decisive pairs) but does not independently assert every cell of every experiment's orchestral/ambient character table entry in §17 — those are derived from the mapping design and spot-checked via the harness rather than exhaustively covered by a dedicated automated test per profile per experiment. This was a deliberate scope decision (the mission asks for contract/state/math tests, not exhaustive profile-matrix coverage) but is worth stating plainly rather than implying full coverage exists.
* **No live-desktop / real-music validation was performed.** Every finding in this document comes from synthetic profiles and direct state inspection (`get_debug_state()`), consistent with every prior ToroidAMP cut's stated limitation — human evaluation with real music remains authoritative and has not yet happened.
* **Matrix Wing Commander's visual polish lags its engineering** (§17) — the causality model is solid; the ships themselves are minimal placeholders, not yet a satisfying spectacle.
* **ToroidAMP Floor's presentation (top-down radial) is one valid choice among several** the mission explicitly allowed (perspective floor, pseudo-3D, horizon+depth) — this lab picked readability over spectacle deliberately; a perspective variant remains unexplored.
* **`get_debug_state()` is a testing convenience, not part of the `Visualizer` contract** — if any of these experiments get promoted to production, this method should either be formalized (if genuinely useful for a future debug overlay) or stripped (if it was purely a Lab II testing artifact). Not resolved here, since promotion itself hasn't happened.
* **`_extra_far_target` shrink logic in Deep Field** uses `list.remove()` inside a loop (§12) — correct but not the most efficient pattern; flagged for cleanup if promoted, not fixed here (no premature optimization).

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

This is experimental research within the existing ACTIVE Production Cut 3 phase ("Visualizer Expansion & Effects"). Production remains untouched — no visualizer was registered in the selector, no production file under `src/toroidamp/` was modified, version stays at `0.2.1`. Operational baseline remains STABLE.
