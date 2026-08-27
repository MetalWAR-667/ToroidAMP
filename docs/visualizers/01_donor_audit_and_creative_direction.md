# ToroidAMP — Visualizer Lab I: Donor Audit & Creative Direction

> **What is this music doing?** — not merely **how loud is this music?**
> And some visualizers may answer: **X-WINGS.** That is also acceptable.

This is a research/creative-audit document. No production visualizer code was implemented in this cut.

---

## 1. Executive Summary

ToroidAMP's daily-use baseline (v0.2.1) is stable. This audit surveys the entire `MetalWar-Installer` donor codebase for reusable visual material, evaluates it against ToroidAMP's real `AudioFrame` pipeline, and proposes concrete creative directions for the next experimental cut (**Visualizer Lab II**).

**The single most important finding**: MetalWar-Installer has **zero real audio analysis anywhere in its codebase** (confirmed by exhaustive grep for `fft`, `sndarray`, `get_raw`, `pyaudio`, `librosa`, `aubio`, `rms` — zero hits outside an unrelated string). Every "music-reactive" donor effect — Starfield warp, the geometric transformer's pulse, spectrum bars, RetroGrid tile spawns, the rave post-FX chromatic aberration/bloom — is driven by `math.sin(time.time() * constant)` against a **hardcoded `BPM = 128`** wall-clock metronome, with `random.random()` for texture. ToroidAMP's `AudioFrame` (real RMS/bass/mids/treble/64-bin spectrum/beat detection from actual decoded PCM) is a genuinely different, better musical vocabulary than anything the donor code ever had. This means: **no donor effect is a drop-in port** — every driver call site needs rewiring — but the **rendering/visual logic itself is uniformly decoupled from its (fake) driver**, so it's trivially receptive to real signals. This is good news: the hard part (rendering) is reusable; the "AI-generated bones" of fake reactivity are exactly what should be discarded.

18 distinct donor visual/effect systems were inventoried (§4). Two are recommended as the strongest candidates for Visualizer Lab II: the RetroGrid-derived "illuminated tile" concept (§7, SIGNATURE candidate) and a Starfield evolution (§6, LOW-risk donor evolution) — alongside one deliberately absurd Because-We-Can candidate (Matrix + X-Wings, §9) that the mission explicitly protects from being cut for tastefulness.

The current `Visualizer` contract (§3) is sufficient for everything currently planned. Two non-blocking gaps were found and are reported, not fixed: `update()` is defined as a separate abstract lifecycle method but the runtime harness never calls it (each visualizer happens to call its own `self.update()` from inside `render()` by convention, not enforcement); and `reset()` is defined but has zero call sites anywhere in the codebase.

---

## 2. Current Visualizer Architecture

### The contract (`src/toroidamp/visualizers/base.py`)

```python
class Visualizer(ABC):
    @abstractmethod
    def resize(self, width: int, height: int) -> None: ...
    @abstractmethod
    def update(self, frame: AudioFrame, dt: float) -> None: ...
    @abstractmethod
    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None: ...
    @abstractmethod
    def get_name(self) -> str: ...
    def reset(self) -> None: ...  # optional hook
```

Four abstract methods, one optional hook. `resize()`/`update()`/`render()` all receive plain values (`int`, `AudioFrame`, `float`) — no Qt types anywhere, matching `visualizer-authoring`'s "no Qt in visualizer modules" rule.

### Production visualizers (`src/toroidamp/visualizers/`)

* **`ToroidVisualizer`** (`toroid.py`, 181 lines) — parametric 3D torus wireframe (rows=24, cols=36), full X/Y/Z rotation, `fckvar` (the one reserved archaeological demoscene variable — combined bass+rms+beat deformation factor), plasma-colored edges (heat from depth+bass+fckvar), waveform-driven vertex displacement, ghosting trail on strong beats. This *is* the direct architectural descendant of the donor `GeometricTransformer3D`'s `TORUS` shape (§4.2) — already ported, already real-audio-driven.
* **`WaveformRibbonVisualizer`** (`ribbon.py`, 72 lines) — a fluid neon oscilloscope ribbon built directly from `AudioFrame.waveform`, thickness from `rms`, sine wobble from `mids`, color from bass/mids/treble. Simple, clean, genuinely real-audio.

### Runtime harness

* **`VisualizerModule`** (`ui/modules/visualizer_module.py`) hosts a `list[Visualizer]`, cycles the active index via `btn_switch`, and renders only the active one (`vis.render(surface, frame, dt)`) every UI tick (~60 FPS, gated on `isVisible()`). Since UX-003, the offscreen Pygame surface is resized dynamically to match the actual widget viewport (`_sync_surface_size`), calling `.resize(w, h)` on **every** visualizer instance (not just the active one) so switching after a resize stays correct.
* **`RetinaMeltWindow`** (`ui/fullscreen.py`) holds its own **separate** `list[Visualizer]` instances (not shared with `VisualizerModule`), sized to the actual screen resolution at fullscreen entry. This is deliberate isolation, not an oversight — confirmed in UX-003's audit that VIS-module size and fullscreen size never interfere with each other.
* Both harnesses transfer the finished frame the same way: `pygame.image.tobytes(surface, "RGBA")` → `QImage(..., Format_RGBA8888)` → `QPixmap` on a `QLabel`. This is the exact pipeline validated in Foundation I (~1.27ms at 800×600, ~5.59ms at 1080p — see `docs/investigations/01_technical_reconnaissance.md`).
* Rendering is wrapped in a bare `try/except: pass` in both harnesses — a visualizer render exception never crashes playback (matches AGENTS.md's failure-isolation policy), but it also means a crashing visualizer silently produces a frozen last frame with no logged diagnostic. Worth knowing, not blocking.

### Two non-blocking contract observations (reported, not fixed — per this audit's charter)

1. **`update()` is never called by the harness.** Grepping the entire `src/toroidamp/ui/` tree for `.update(` and `.reset()` calls turns up zero call sites against any `Visualizer` instance. Both `VisualizerModule.render_frame` and `RetinaMeltWindow.render_frame` call only `vis.render(surface, frame, dt)`. The two production visualizers both call `self.update(frame, dt)` themselves at the top of their own `render()` — by convention, not by contract enforcement. A visualizer author who skips that internal call would silently never update. Not blocking (nothing has hit this yet; the skill's authoring checklist implicitly covers it by showing `update()`+`render()` together), but worth knowing before adding more visualizer authors.
2. **`reset()` is dead code.** Defined as an optional hook, zero call sites anywhere. No lifecycle event (switching visualizers, entering/leaving fullscreen, track change) currently calls it. This matters for §14 (contract sufficiency) — see NICE TO HAVE there.

---

## 3. AudioFrame Vocabulary

The current, closed contract (`ANALYSIS-001`, `docs/ARCHITECTURE.md` / `docs/investigations/02_audio_pipeline_tracker_pcm.md`):

| Field | Type/Range | What it actually measures |
|---|---|---|
| `rms` | `[0.0, 1.0]` | Overall loudness envelope |
| `peak` | `[0.0, 1.0]` | Instantaneous peak level |
| `bass` | `[0.0, 1.0]` | ~20–250 Hz band energy |
| `mids` | `[0.0, 1.0]` | ~250–4000 Hz band energy |
| `treble` | `[0.0, 1.0]` | ~4000–20000 Hz band energy |
| `spectrum` | `64` floats, `[0.0, 1.0]` | Log-spaced FFT bins |
| `waveform` | `128` floats, `[-1.0, 1.0]` | Raw sample window |
| `beat` | `bool` | Transient energy crossing threshold |
| `strong_beat` | `bool` | Heavy bass transient |

This is the primary musical vocabulary every proposal in this document is built from. **RMS-only mapping is explicitly rejected as creatively weak** per the mission brief — every candidate below is evaluated on whether it uses at least 3–4 distinct fields in ways that produce genuinely different *character* (not just different *intensity*) across musical styles, per ToroidAMP's own established principle:

> **"Reactivity should be perceptible through contrast between different music, not through exaggeration within a single song."** (`docs/polish/001_reactive_neon_chassis.md`)

---

## 4. Donor Inventory

All 18 systems found in `MetalWar-Installer` (10 `.py` files, ~16K lines; effects concentrated in `effects.py` [3280 lines, 7 classes] and `ui.py` [2300 lines, 9 classes]). **The fake-reactivity core driving nearly everything**: `main.py:204` `MusicClock` (wall-clock phase from a fixed `BPM=128` in `config.py:75`), `main.py:333` `BPMSynchronizer` (turns that into `beat_pulse`/`strong_beat` flags on fixed beat-count modulo), and the literal driver expressions at `main.py:874-884`: `kick = max(0, sin(t*7))**10` (normal) or `0.6 + sin(t*50)*0.3` (rave mode); `intensity = 0.5 + 0.3*sin(beat_phase*pi)` or `random.random()`-based.

| # | Name / Location | Visual | Original Driver | Rendering Tech | Key Math | Deps | Installer Coupling | Extraction | Reuse Value |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Starfield** — `effects.py:38` | 3D perspective star warp, 4 neon palettes, light-trail streaks, brightens on beat | Fake (`bpm_data`) | Raw `pygame.draw.line`/`set_at` | 3D star projection (`factor=fov/z`), camera-plane rotation, exp-smoothed warp factor | pygame, random, math | LOW — only needs `(w,h)` + `(surface, intensity, bpm_data)` | LOW | HIGH |
| 2 | **GeometricTransformer3D** — `effects.py:222` | Wireframe mesh morphing SPHERE↔TORUS↔KNOT↔CYLINDER, plasma/heatmap edges, particle sparks, ghosting | Fake (`intensity`, `bpm_state`) | `pygame.draw.line/polygon`, custom alpha-blit, persistent `SRCALPHA` ghost surface | Exact parametric torus (`R=1.0,r=0.4`) — direct ancestor of `ToroidVisualizer` — plus sphere/knot(p=2,q=3)/cylinder; full XYZ rotation; 4-sine plasma color | pygame, math, random, colorsys | LOW-MEDIUM — reads `current_fmt` string, trivially stripped | LOW-MEDIUM | **SIGNATURE** |
| 3 | **SpectrumAnalyzer** — `effects.py:636` (~1100 lines) | Multi-mode "simulator": MAGMA liquid waveform (MP3), particle bursts (OGG), 3D particles (IT/XM), 64-bar gravity physics | Fake (`intensity, kick, fmt, bpm_data`); own internal fake-BPM estimator too | numpy-vectorized bar/peak arrays (optional), procedural magma texture (scroll-blitted) | Asymmetric gravity bar/peak decay, 3-octave sine "terrain" magma, freq-position color gradient | pygame, numpy (optional), colorsys | MEDIUM — heavy `fmt`-string branching (tracker vs mp3 vs ogg) | MEDIUM (large, format-branchy) | HIGH (sub-effects, not the whole class) |
| 4 | **CRTBoot** — `effects.py:1723` | Typewriter boot-text, scanline overlay + moving scan bar, cursor blink | Manual/event (preload callback) | Cached text surface, precomputed scanlines | Timers only | pygame, time, os | MEDIUM — tied to app preload sequencing | LOW | MEDIUM |
| 5 | **RetroGrid** — `effects.py:1905` | Tron/synthwave perspective floor grid (24 rows), individual quad cells flash-illuminate in 4 neon colors and fade | Fake `kick` only — **not RetroGrid's own BPM logic** | `pygame.draw.polygon/line` on persistent `SRCALPHA` surface | Hand-tuned trapezoid perspective (nonlinear row-Y cache `(row*20)**1.1`) | pygame, random | LOW — fully self-contained `(w,h)` init, `(surface, time_val, kick)` per frame | LOW | HIGH |
| 6 | **PeaceCodeRain** (Matrix rain) — `effects.py:2072` | Falling hex-digit columns, bright head + dim trail | **Pure timer** — zero audio/beat coupling | Pre-rendered per-glyph cache (16 hex chars × 2 colors, built once) | Linear motion + list bookkeeping | pygame, random | LOW | LOW (near-trivial) | MEDIUM |
| 7 | **PraxisEvent** — `effects.py:2173` (~1100 lines, incl. X-Wings) | Installer-finale set-piece: shake→blast→peace sequence; includes 8 X-Wings + Y-Wing squadrons flying scripted 3D waypoint routes (`CURVE_RIGHT`, `DIVE`, `BARREL_ROLL`, `ZIGZAG`, `LOOP`) | **Entirely manual/timer/event** (`.trigger()`, elapsed-time phase thresholds) | Raw draws, `pygame.mask` for peace-symbol collision, PNG w/ text fallback | Waypoint lerp with `z` as depth/scale (`size=80/z`), 2D bank/roll rotation | pygame, math, random, `audio.AudioManager` (optional) | **HIGH** for the whole class (installer-narrative-specific); the ship sub-system alone is decoupled | MEDIUM-HIGH (whole class); LOW (ship sub-system alone) | MEDIUM (class); **HIGH** (X-Wing/Y-Wing waypoint flight isolated) |
| 8 | **KeyboardFX** — `installer.py:27` | Physical keyboard LED control (Caps/Num/Scroll Lock), disco + Knight Rider patterns | Manual triggers | `ctypes.windll.user32` (Windows-only, no screen surface) | — | ctypes | N/A — no on-screen component | N/A | LOW/N-A for ToroidAMP |
| 9 | **LogoMetalWAR** — `ui.py:20` | Logo entrance: center-appear → hover-float → travel to corner, 4-direction glow blit, diagonal shine sweep, small beat pulse at rest | Mixed — fixed voiceover-timed timeline + small fake-`intensity` pulse | `BLEND_RGBA_MULT/ADD` compositing, `smoothscale` | Smoothstep interpolation | pygame | MEDIUM — timed to specific voiceover script | LOW-MEDIUM | MEDIUM |
| 10 | **C64Scroller** — `ui.py:916` | Amiga/C64 demoscene scrolltext: per-char sine bounce, per-char rainbow (3 sines, 120° phase-shift), drop shadow, flipped/scaled reflection, scanline mask | Pure `time.time()` sine — not audio-reactive | Per-frame font render (no cache), `transform.flip/scale` | Sine oscillation | pygame, math, time | LOW | LOW | MEDIUM-HIGH |
| 11 | **SpainText** — `ui.py:1060` | Flag-textured "sticker" text, drop-shadow, horizontal-flip pulse scale, rising fire/gold particle system | `kick`/`intensity` (fake) drive particle spawn rate | `BLEND_RGBA_MULT`, alpha-circle particles | — | pygame | MEDIUM — hardcoded app-specific text/colors | LOW-MEDIUM | LOW (branding-specific); MEDIUM (technique) |
| 12 | **CyberCursor** — `ui.py:1421` | Custom cursor: fading trail, state-dependent shape, counter-rotating arcs, pulsing dot | Manual (mouse pos + hover bool) | Small per-frame `SRCALPHA` surface | — | pygame | LOW | LOW | LOW-MEDIUM |
| 13 | **TacticalHUD** — `ui.py:1608` | "Targeting" HUD: button contracts, scanning reticle on randomized waypoints, lock-on crosshair + blinking text | Manual (`time_factor` progress) | Raw draws | — | pygame | HIGH — bound to install-button UX flow | — | LOW |
| 14 | **HexDumpLoader** — `ui.py:1827` | Fake scrolling hex-dump terminal + progress bar | Manual (progress float), fixed-timer random hex | Text render | — | pygame | HIGH — installer chrome | — | LOW |
| 15 | **SystemMonitor** — `ui.py:1950` | FPS line-graph, fake VRAM number, real thread count (F1 toggle) | **Real** FPS (only genuinely-real-data UI in the codebase — not audio) | Line graph | — | pygame | LOW | LOW | LOW (debug overlay) |
| 16 | **CyberControlsUI** — `ui.py:2029` | Parallax mountain silhouettes + hand-drawn Death Star (concentric circles, superlaser dish) | Manual scroll offset | Layered blits | — | pygame | MEDIUM | LOW | LOW-MEDIUM |
| 17 | **CRT/rave post-FX pipeline** — `main.py:1310-1495` (inline, not a class) | Screen shake, **chromatic aberration** (RGB-split + beat offset + hue cycle), **bloom** (downsample/upsample additive), scanlines + glitch-strip displacement, orbiting/beat lens flare, breathing vignette | Fake `beat_val`/`kick` | `BLEND_RGBA_ADD/MULT`, `smoothscale` bloom | — | pygame | **HIGH as written** — inline in `main()`, entangled with module globals | MEDIUM (needs lifting into a class) | **HIGH** |
| 18 | **`apply_glitch`** — `utils.py:167` (standalone fn) | Chromatic-split glitch + one random horizontal strip displacement per call | `intensity` param (caller-supplied) | Pure blend ops | — | pygame | **NONE** — pure function of `(surface, intensity, w, h)` | TRIVIAL | HIGH |

**Shared-code note**: there is no central plasma/palette utility — `GeometricTransformer3D`'s plasma/heatmap color math, `SpectrumAnalyzer`'s independent frequency-color gradient, and its separate magma-texture sine formula are all reimplemented independently. The neon 4-color palette (`[(255,0,110),(0,240,255),(180,0,255),(220,255,0)]`) is duplicated verbatim between `RetroGrid` and `PraxisEvent`. The "lit cell that fades" pattern is implemented twice independently. None of this blocks reuse — it just means ToroidAMP gets to build the shared palette/color-engine utility the donor never had, if that proves worth doing.

---

## 5. Visualizer Families

```text
MUSICAL                              DEMOSCENE                          BECAUSE WE CAN
(represents musical structure)       (music drives spectacle)           (unnecessary → mandatory)
──────────────────────────────       ──────────────────────────────      ──────────────────────────
SPECTRAL                             GEOMETRIC                          SCENE-BASED
  spectrum bars/ribbons/rings          ToroidVisualizer (existing)        X-Wing/Y-Wing waypoint flights
  spectrum heightfield                 RetroGrid perspective grid
  circular spectrum                    Starfield 3D warp
                                        GeometricTransformer3D shapes    TYPOGRAPHIC (absurd variant)
TYPOGRAPHIC (informative variant)                                         Matrix rain as pure texture,
  future LRC/lyric display           PARTICLE                             decoupled from any info role
                                        Starfield streaks
FEEDBACK (analytical variant)          SpectrumAnalyzer particle bursts  PSYCHEDELIC (extreme variant)
  RMS/peak meters                      SpainText embers                   rave post-FX pushed past
                                                                            "tasteful" into deliberate excess
                                      RETRO
                                        C64Scroller
                                        CRT scanline/glitch pipeline
                                        PeaceCodeRain (Matrix rain)

                                      PSYCHEDELIC
                                        magma texture
                                        chromatic aberration / bloom
                                        plasma color cycling
```

Several donor effects are legitimately hybrid — e.g. the proposed **BPM Tiles** (§7) is simultaneously MUSICAL (spectral distribution encodes real structure) and DEMOSCENE (illuminated grid spectacle); **Matrix + X-Wings** (§9) is BECAUSE WE CAN by mission decree but the Matrix-rain half is also RETRO/TYPOGRAPHIC. Forcing single-family classification would lose information — hybrid tags are used throughout §10 (creative proposals).

---

## 6. Starfield Audit & Reinterpretation

**Donor**: `effects.py:38-215`, `Starfield`. 3D perspective star-tunnel, camera roll, 4 selectable neon palettes, light-trail streaks on fast stars, warp brightens/speeds on beat. Driven entirely by fake `bpm_data`. Extraction: LOW. Reuse: HIGH.

**Rejected naive mapping**: `rms → star speed` (explicitly called out as creatively weak in the mission brief, and it's exactly what the donor already does with fake intensity).

**ToroidAMP reinterpretation** — multi-field mapping:

| AudioFrame field | Starfield behavior |
|---|---|
| `bass` | Depth acceleration / "camera pressure" — the tunnel's forward-thrust rate, not the stars' raw speed. Heavy bass makes the *whole scene lean forward*, like the camera itself is being pushed. |
| `mids` | Lateral drift / slow camera roll — mid-heavy material (vocals, guitar leads, synth pads) makes the starfield gently curve/bank rather than fly dead straight. |
| `treble` | Star density and sparkle-detail — treble-rich material spawns more, smaller, twinklier stars; treble-poor material has fewer, bigger, calmer points. |
| `spectrum[64]` | Depth-band color distribution — map low bins to near/warm stars, high bins to far/cool stars, so the *current spectral balance*, not a fixed palette choice, determines the tunnel's color gradient live. |
| `beat` | Short warp impulse — a brief forward lurch, not a full burst. |
| `strong_beat` | Hyperspace burst / streak event — the donor's existing beat-driven brighten/speed-up, now gated to genuine strong transients only. |
| silence (`rms≈0`, no beats) | Slow inertial drift — stars keep gently moving from residual "velocity" that decays over ~2-3s rather than snapping to a dead stop, so silence between tracks doesn't feel broken. |

**Character differentiation** (the actual test this audit applies):
* **Morricone-style orchestral**: low `bass`/`treble`, moderate `mids` swells, sparse/irregular `beat`. Result: a slow, curving, warm-toned drift — the camera gently banking through a sparse field, occasional soft lurches on orchestral hits, never a hard strobe.
* **Classic heavy metal**: strong periodic `bass`+`beat` (kick drum), bright `treble` (cymbals/distortion harmonics), dense `mids` (rhythm guitar wall). Result: a driving, forward-leaning tunnel with regular short lurches on the beat, dense sparkling stars, warm-to-cool gradient oscillating with the riff.
* **Dense modern metal** (djent/deathcore): very high sustained `bass`+`mids` energy with less periodic beat clarity (blast beats, syncopation), high `treble` from cymbal wash. Result: near-constant forward pressure (less punchy, more sustained), very high star density, aggressive but less rhythmically "on-the-one" than classic metal — visibly different character from classic metal despite similar loudness.
* **Electronic/EDM**: extremely regular `beat`/`strong_beat` on a four-on-the-floor pattern, strong `bass` drops, `spectrum` shifting dramatically between build-ups (treble-heavy, sparse) and drops (full-spectrum, bass-heavy). Result: sharp, clock-precise lurches exactly on the beat grid, dramatic density/color swings between build and drop sections — visibly punchier and more binary than metal's continuous intensity.
* **Sparse ambient**: near-silent `rms`, almost no `beat`, slow `mids` swells. Result: mostly the silence-drift behavior — a calm, slowly rotating field that almost never lurches, distinguishing itself from *every* other genre above purely through stillness.

---

## 7. BPM Tiles Audit — SIGNATURE Candidate

**Donor**: this is `RetroGrid.draw()` (`effects.py:1905-2064`), *not* a separate "tile/floor" class — the codebase names it as a grid, the effect the human remembered as "illuminated tiles" is `RetroGrid`'s cell-flash mechanic. Confirmed: no code anywhere uses the words "tile," "floor," or "dance" — this concept exists only under the `RetroGrid`/`lit_cells` name.

**Exact donor mechanism** (important — it's simpler than it might sound):
* Tile topology: a 24-row perspective floor grid, each cell addressed by `(row, col)`.
* Illumination is **not propagation-based**. There is no wave spreading from a source cell, no neighbor-lighting logic, no lattice state machine. It's a flat spawn model: `if kick > 0.5: num_spawns = int(kick*16)+2`, then that many `[row, col, color, life=1.0]` cells are appended at **uniformly random** `(row, col)` positions, `color` chosen randomly from the 4-color neon palette.
* Fade: `life -= 0.05` per frame; alpha ∝ `life`; a white outline while `life > 0.7`. Purely independent per-cell decay, no interaction between cells.
* Timing driver: whatever `kick` scalar it's handed (fake `sin(t*7)**10` in the donor) — `RetroGrid` itself has zero BPM logic; it's a pure function of a per-frame kick value.

**Why this is a strong SIGNATURE candidate for ToroidAMP, and what must change**: the donor's random-cell-spawn model produces *statistically* similar-looking output for any two songs with a similar beat rate, because `kick` is the only input — there's no way for the donor version to distinguish "which part of the spectrum is loud" from "how often the beat lands." The explicit design goal stated in the mission — *two songs with similar BPM should still produce different tile patterns* — requires the ToroidAMP version to break that flatness. Proposed mapping:

| AudioFrame field | Tile behavior |
|---|---|
| `bass` | Central / low zone — illuminates tiles nearest a central "sub" region of the field, sustained/glowing rather than flash-decay, forming a slow-breathing core. |
| `mids` | Structural mid-band — a ring/region of tiles between center and edge that responds to sustained mids energy (vocal/guitar presence), giving the field a persistent "body" independent of transients. |
| `treble` | Peripheral/highlight tiles — brief, sharp, edge-biased flashes; treble-heavy material makes the *rim* of the field sparkle while bass-heavy material barely touches it. |
| `beat` | **Propagation pulse** — this is the genuine upgrade over the donor: instead of random spawn, a beat triggers a pulse that visibly *travels outward* from the currently-loudest spectral zone (computed from which of the 64 `spectrum` bins currently has the most energy, mapped to a tile-field position) across neighboring tiles with a short propagation delay per ring — an actual lattice wave, not independent random cells. |
| `strong_beat` | Larger geometric event — a full-field flash-ring or a simultaneous multi-zone pulse (e.g. all four palette-color zones pulse together), reserved for genuine transient peaks so it reads as an *event*, not routine. |
| `spectrum[64]` | **Spatial distribution across the tile field** — this is the field that actually makes two same-BPM songs look different: map the 64 bins to tile-field position (e.g. low bins → center, high bins → edge, or a radial/angular layout), so a bass-heavy song and a treble-heavy song at the identical BPM light up *structurally different regions* of the field, not just "the same random cells at the same rate." |

This candidate is recommended to become ToroidAMP's flagship signature visualizer (see §16 scorecard, §17 first-three-experiments) precisely because it's the one donor concept where "port it as-is" would actively fail the project's stated creative principle, and "reinterpret it properly" produces something the donor genuinely never had: a visualizer where the *shape* of the illumination, not just its rate, is musically meaningful.

---

## 8. Spectrum Family Audit

**Donor**: `SpectrumAnalyzer` (`effects.py:636-1723`, ~1100 lines) — the biggest single class in the codebase. Its own docstring literally says *"Simulador de analizador de espectro visual"* (visual spectrum analyzer **simulator**) — an honest admission it was never real.

**Visual grammar breakdown**:
1. **64-bar gravity physics** — bars have asymmetric rise/fall (`BAR_GRAVITY`/`PEAK_GRAVITY` differential decay), giving a "snappy attack, slow settle" feel that reads as more musical than a raw bar chart even with fake input. **Distinct and worth keeping** — but the fake *targets* it animates toward (sine waves + kick pulses + `np.random.rand()` noise) are worthless; only the physics envelope is reusable.
2. **MAGMA liquid waveform** (MP3-format variant) — a scrolling procedural heat-texture (3-octave sine "terrain") blended with a particle bubble layer. **Distinct** — visually unlike a bar chart, genuinely interesting as its own thing.
3. **Format-branched particle variants** (OGG bursts, IT/XM 3D particles) — mostly cosmetic variation keyed to `fmt` string, not fundamentally different visual grammar from each other. **Redundant** relative to each other; not worth porting all three separately.
4. Internal fake-BPM estimator (`_apply_bpm_sync`) — irrelevant to ToroidAMP, which already has real beat detection (`ANALYSIS-002`, closed).

**Is `AudioFrame.spectrum[64]` sufficient?** Yes for raw data — 64 log-spaced bins is plenty of resolution for any bar/ribbon/ring visual grammar. **What's missing is not in the contract, it's in visualizer-local state**: the donor's gravity-physics feel requires **smoothing + peak-hold + short history**, none of which needs to be a new `AudioFrame` field — this is exactly the kind of thing a visualizer's own `update()` should own (maintain a `self._smoothed_bars`/`self._peak_hold` array across frames), matching the existing contract's per-visualizer persistent-state model. **No contract change needed.**

**Classification**: bar-physics envelope = **expressive** (worth keeping, needs a rewire not a rewrite); magma texture = **expressive** (distinct, worth a dedicated visualizer); format-branched particle variants = **redundant** relative to each other (pick one particle grammar, not three); the fake-BPM estimator = **redundant** (ToroidAMP already has this, done properly).

**Proposed direction that isn't "64 vertical bars"**: a **radial/circular spectrum ring** wrapped around (or replacing) the toroid's silhouette — low bins at the inner edge, high bins radiating outward, using the donor's gravity-physics envelope for per-bin motion and the magma texture's heat-gradient coloring instead of a flat per-bar color. This keeps both of the donor's genuinely distinct visual grammars (physics feel + heat coloring) while producing something that reads as "a ToroidAMP thing" rather than a generic winamp-style bar EQ.

---

## 9. Matrix + X-Wings Audit — BECAUSE WE CAN (culturally protected)

**Donor**: two separate systems, confirmed distinct.

* **Matrix rain** = `PeaceCodeRain` (`effects.py:2072-2166`). Falling hex-digit columns, bright head + dim trailing body, per-column independent speed/length. **Purely timer-driven** — no audio/beat coupling exists in the donor at all. Rendering technique worth stealing regardless of the visual: a **pre-rendered per-glyph cache** (16 hex chars × 2 colors, built once in `__init__`), avoiding per-frame font rendering. Extraction: LOW (near-trivial). Reuse: MEDIUM.
* **X-Wings/Y-Wings** = inside `PraxisEvent` (`effects.py:2173-3280`), specifically `spawn_xwing`/`draw_xwing_3d` (8-ship squadron on 4 hand-authored 3D waypoint routes with named maneuvers: `CURVE_RIGHT`, `DIVE`, `BARREL_ROLL`, `ZIGZAG`, `LOOP_START/MID`, `EXIT`) and `spawn_ywing_squad`/`draw_ywing_3d` (background V-formation squadrons on separate routes). Ships are simple 3D vector sketches (crossed-line wings + engine dots for X-Wings; triangle cockpit + arm geometry for Y-Wings), perspective-scaled by `1/z`, banked/rolled from velocity. **Entirely manual/scripted** — waypoint interpolation on wall-clock time, zero audio coupling in the flight itself. The class as a whole (`PraxisEvent`) is HIGH-coupling installer-narrative machinery (triggered by install-complete state, loads specific PNGs, plays specific SFX) — but the ship-drawing + waypoint-route sub-system is cleanly separable and **decoupled from that narrative already**, since the ships fly scripted routes regardless of what triggered them.

**Reinterpretation** (per the mission's explicit mapping, confirmed technically feasible against the donor's actual code):

| AudioFrame field | Matrix Rain | X-Wings |
|---|---|---|
| `treble` | Character density / brightness — treble-heavy material spawns denser, brighter columns | — |
| `mids` | Fall speed | — |
| `bass` | Depth/distortion (chromatic-style offset per column, borrowing `apply_glitch`'s technique) | Scale/perspective pressure — bass makes the formation feel "closer," synced with the depth-scale math already in `draw_xwing_3d` (`size=80/z`) |
| `rms` | — | Cruise speed along the scripted waypoint routes |
| `beat` | Short global luminance impulse across all columns | Maneuver impulse — trigger the next scripted maneuver segment (`BARREL_ROLL`, `ZIGZAG`) on a beat instead of a fixed wall-clock schedule |
| `strong_beat` | — | Formation pass / attack run / close flyby — a full squadron pass timed to a strong transient, the closest thing to the donor's original "climax" framing but audio-triggered instead of install-event-triggered |
| `spectrum` | — | Optional formation/color behavior (e.g. squadron color shifts with spectral balance) |

**Explicit note per mission instruction**: this must not be quietly sanded down into something "tasteful." If eventually implemented, the required comment survives verbatim:

```python
# Why?
# Because we could.
```

Not implemented in this cut — audit only.

---

## 10. Scroll/Text Audit

**Donor**, two distinct systems:

* **`C64Scroller`** (`ui.py:916-1052`) — genuine Amiga/C64 demoscene scrolltext: per-character sine-wave vertical bounce, per-character rainbow color cycling (3 sines, 120° phase-shifted), drop shadow, a vertically-flipped/scaled **reflection** underneath, scanline mask, slide-in entrance. Purely `time.time()`-sine driven, not audio-reactive. LOW coupling, LOW extraction difficulty, MEDIUM-HIGH reuse (iconic, cheap to add polish).
* **`SpainText`** (`ui.py:1060-1413`) — flag-textured "sticker" text with rising-particle emission (`kick`/`intensity`-driven spawn rate, currently fake). LOW value for ToroidAMP specifically (it's a joke/branding effect tied to the donor's Spanish flag gag), but the underlying **"particle-emitting text"** pattern is a MEDIUM-value reusable technique independent of that specific content.

**What the donor offers for each requested capability**:
* Horizontal crawl — **present** (`C64Scroller`'s core motion), directly reusable.
* Vertical scroll — **absent** in the donor; would need new work (the mechanics are simple — same per-character technique, transposed axis — but nothing to extract).
* Perspective text — **absent**; nothing in the donor projects text into pseudo-3D depth.
* Wave deformation — **present** (`C64Scroller`'s per-character sine bounce is exactly this).
* Depth movement — **absent** as a dedicated technique, though `PraxisEvent`'s `1/z` scale-by-depth math is directly transferable if text needed to recede/approach.
* Raster-style effects — **present**, `C64Scroller`'s scanline mask + reflection qualify; the CRT/rave post-FX pipeline (§4.17) also has directly relevant scanline/glitch machinery.

**Classification** — this matters for future LRC/lyrics, credits, and ToroBot barks, none of which are being implemented now:

* `C64Scroller`'s sine-bounce + rainbow-cycle + reflection technique → **FUTURE SHARED TYPOGRAPHY EFFECT**. This should not be embedded inside one specific visualizer — it's exactly the kind of reusable "make text feel alive" primitive that LRC display, credits, and ToroBot barks will all eventually want, and building it once as a shared component (independent of any single visualizer's lifecycle) avoids three separate reimplementations later.
* `SpainText`'s "particle-emitting text" pattern (the technique, not its Spanish-flag content) → **FUTURE SHARED TYPOGRAPHY EFFECT** as well, for the same reason, but lower priority.
* Any donor CRT-scanline/raster treatment applied to text specifically → **VISUALIZER-LOCAL** for now — it only becomes shared if/when a specific fullscreen typography use case actually needs it; premature to generalize a rendering filter before there's a second consumer.

---

## 11. RetroGrid Audit (as a grid, distinct from the BPM Tiles reinterpretation in §7)

**Donor**: `effects.py:1905-2064`, same class analyzed in §7, but here evaluated for its *grid* character specifically, kept deliberately distinct from the BPM Tiles proposal above (they should not become the same visualizer — one is a spatially-encoded illumination field, the other is a classic perspective-horizon grid with wave/heightfield behavior).

**Avoiding "just a generic synthwave grid"** — proposed musically-driven distinctions:

| AudioFrame field | RetroGrid behavior |
|---|---|
| `bass` | Horizon depth / grid extrusion — bass energy pushes the horizon line and extrudes the grid's apparent depth, making low-end-heavy material feel like it's opening up the floor. |
| `mids` | Camera motion — sustained mids drive a slow forward-glide rate along the grid, distinct from any beat-triggered event. |
| `treble` | Line sharpness / sparkle — treble crispens grid line rendering (thinner, brighter lines with sparkle highlights at intersections) vs. a softer, thicker-line look on bass-heavy/treble-poor material. |
| `spectrum[64]` | **Grid heightfield** — map the 64 bins across the grid's row axis so each row's "height"/brightness reflects a specific frequency band, turning the flat floor into a live spectral heightfield (this is the piece that gives RetroGrid genuine musical information content, not just decoration). |
| `beat` | Horizon pulse — a brief brightness/scale pulse at the horizon line. |
| `strong_beat` | **Wave traveling across the grid** — an actual traveling deformation (a visible ripple moving from horizon to camera) on strong transients, distinct from the Tiles' propagation pulse (§7) in that it's a continuous surface wave, not discrete cell illumination. |

---

## 12. Other Discovered Donor Effects

| Effect | Classification | AudioFrame mapping (if applicable) | Decision |
|---|---|---|---|
| **CRTBoot** (`effects.py:1723`) | RETRO/typographic | None — boot-sequence intro, not a visualizer | **REJECT** for visualizer work (out of scope: "do not add splash screens" was explicit in BRAND-001 and remains a reasonable default here); technique (cached text + scanlines) noted for future reference only |
| **LogoMetalWAR** (`ui.py:20`) | TYPOGRAPHIC | `beat_impact = intensity**2 * 0.08` scale pulse | **REJECT** — branding-specific choreography tied to a voiceover script that doesn't exist in ToroidAMP; the glow/shine compositing technique is generic but not worth extracting for a specific reveal animation ToroidAMP doesn't need |
| **CyberCursor** (`ui.py:1421`) | FEEDBACK/UI-chrome | Manual (mouse) | **REJECT** — not a visualizer, not currently a UI priority |
| **TacticalHUD** (`ui.py:1608`) | UI-chrome | Manual | **REJECT** — installer-button-specific |
| **HexDumpLoader** (`ui.py:1827`) | UI-chrome | Manual | **REJECT** — installer-specific busy indicator |
| **SystemMonitor** (`ui.py:1950`) | FEEDBACK | Real FPS (not audio) | **COMPONENT ONLY** — a debug FPS overlay could be genuinely useful for visualizer development/tuning, but it's tooling, not a visualizer |
| **CyberControlsUI** parallax mountains + Death Star (`ui.py:2029`) | RETRO/SCENE-BASED | None currently | **EXPERIMENT CANDIDATE** — parallax silhouette layers are a decent generic ambient-background primitive (`bass` → foreground layer scroll speed, `mids` → background layer, ala classic 2D parallax) if ToroidAMP ever wants a calmer, non-3D ambient visualizer; the Death Star itself is a novelty easter egg, **REJECT** unless a future cut specifically wants an easter egg |
| **CRT/rave post-FX pipeline** (`main.py:1310-1495`) | PSYCHEDELIC/FEEDBACK | `beat`→chromatic-aberration offset, `strong_beat`→bloom/flare/vignette pulse, `bass`→shake amplitude | **PORT CANDIDATE** (as a component, not a standalone visualizer) — this is the single highest-value non-signature find in the whole audit: a genuinely cinematic post-processing layer (chromatic aberration, bloom, scanlines, vignette, lens flare) that could be applied as a **post-pass over any visualizer's finished frame**, not just one effect. Needs to be lifted out of `main()`'s procedural globals into a standalone `PostFXPipeline`-style component first. |
| **`apply_glitch`** (`utils.py:167`) | FEEDBACK/PSYCHEDELIC | `intensity` param (would become e.g. `strong_beat`-gated) | **PORT CANDIDATE** — already a pure, standalone function of `(surface, intensity, w, h)`, zero coupling, trivial to adopt as-is with a real trigger signal |
| **KeyboardFX** (`installer.py:27`) | N/A | N/A | **REJECT** — no on-screen surface, Windows-only ctypes hack, out of scope entirely |

---

## 13. Current Contract Sufficiency

| Capability | Assessment |
|---|---|
| Dynamic resizing | **NOT NEEDED** (change) — already solved. `resize(w, h)` is called on every visualizer whenever the viewport changes (UX-003); both production visualizers already handle it correctly by recomputing center/geometry from `self.w`/`self.h` on every frame rather than caching stale dimensions. |
| Fullscreen | **NOT NEEDED** — `RetinaMeltWindow` already maintains fully independent visualizer instances sized to actual screen resolution; verified in UX-003 that fullscreen and windowed sizes never leak into each other. |
| Spectrum access | **NOT NEEDED** — `AudioFrame.spectrum[64]` already present and sufficient per §8. |
| Waveform access | **NOT NEEDED** — `AudioFrame.waveform[128]` already present, already consumed by `WaveformRibbonVisualizer`. |
| Timing | **NOT NEEDED** — `dt` passed to every lifecycle method already. |
| Persistent per-visualizer state | **NOT NEEDED** — visualizers are plain Python objects that persist across frames (`self.rot_x`, `self._smoothed_bars`, etc. all work today); this is exactly the pattern §8's spectrum-physics proposal and §7's tile-decay state would use. |
| Visualizer switching | **NICE TO HAVE** — works today (`VisualizerModule` cycles a list), but switching doesn't call any activate/deactivate hook. A newly-activated visualizer currently just resumes rendering with whatever internal state it was last in (which for most effects is fine — particles/rotation continuing silently offscreen is harmless), but the dead `reset()` hook (§2) suggests this was anticipated and never wired up. Not blocking anything currently planned; worth wiring if a future visualizer specifically needs a clean-slate entry (e.g. the BPM Tiles field shouldn't show stale illumination from before it was last active). |
| Future GPU visualizers | **BLOCKING for GPU specifically, not for the current roadmap.** The contract's `render(surface: pygame.Surface, ...)` signature is inherently CPU/Pygame-shaped — a GPU/shader visualizer wouldn't want to draw into a CPU-side `pygame.Surface` at all; it would want a GL context and its own present path. This isn't a defect in the current contract (nothing GPU-based is being built yet, per explicit instruction), but a real future visualizer using OpenGL/GLSL would need either a parallel contract (e.g. an alternate `render_gl(context, ...)` path) or a wrapper that treats the whole GL-rendered frame as an opaque texture blitted into the existing pygame pipeline. See §14 (EXP-GL-001) — this is exactly the kind of investigation that future probe should resolve, not this document. |
| Future text/LRC input | **NICE TO HAVE** — the contract has no first-class concept of "text content" alongside `AudioFrame`. This doesn't block anything: a lyrics-aware visualizer could simply accept extra data via its own constructor/setter (e.g. `set_lyrics_source(...)`) without touching the shared `Visualizer` ABC or `AudioFrame`, exactly the same way `ToroidVisualizer` already takes `width`/`height` in its constructor beyond the shared contract. Only becomes a real design question once LRC work actually starts — not now. |

**No blocking change exists in the current Visualizer contract for anything planned in this document.** Both flagged items (`update()` never called by the harness; `reset()` dead code) are pre-existing, harmless-so-far inconsistencies worth a maintainer's attention someday, not blockers for Visualizer Lab II.

---

## 14. Software vs. GPU Direction

Staying entirely CPU/Pygame for this generation, per instruction — no OpenGL/GLSL implemented here. Classification of what's a natural software fit vs. a future shader candidate:

**Stay PYGAME/SOFTWARE** (all current proposals in §15 qualify): Starfield evolution, BPM Tiles, spectrum ring, RetroGrid evolution, Matrix+X-Wings, C64 typography component. All of these are well within Pygame's per-frame draw-call budget at the resolutions ToroidAMP actually renders at (windowed module ≈ 300-700px, fullscreen ≈ 1080p-1440p), consistent with the 8ms render budget in `visualizer-authoring`.

**Natural future OPENGL/GLSL fits** (none implemented, all deferred):
* **Plasma** (§4.2, §8 magma texture) — per-pixel sine-field color is exactly what a fragment shader does trivially at any resolution with zero CPU cost, vs. the donor's CPU-bound procedural texture generation.
* **Pixel warping / feedback** (§4.17 chromatic aberration, bloom) — GPU-native operations (texture sampling offset, downsample/blur/composite) that Pygame currently does via slow `smoothscale`+blend-mode chains.
* **Kaleidoscope** — trivial in a fragment shader via coordinate-space folding; painful in Pygame per-pixel.
* **Raymarching / shader tunnels** — a GPU-native genre with no meaningful Pygame equivalent; would be a genuinely new visual space for ToroidAMP, not a donor port at all.
* **Procedural fields** (Starfield's warp field, RetroGrid's heightfield) — both would benefit from GPU parallelism at scale, though the current Pygame versions are already performant enough not to need it yet.
* **Per-pixel spectral color** — mapping all 64 spectrum bins to a full-frame gradient per-pixel (not just per-bar) is GPU-natural, CPU-expensive.
* **Post-processing** (§4.17's whole pipeline) — this is the single strongest GPU case in the whole audit: applying chromatic aberration/bloom/vignette as a *shader pass over whatever the active visualizer just rendered* would let every visualizer — donor-derived or new — gain a cinematic finishing layer for free, something no individual Pygame visualizer should have to reimplement itself.

**Proposed future investigation** (not executed):

> **EXP-GL-001 — GPU Visualizer Probe**
> A small executable probe (per AGENTS.md §18's "technical investigation policy") answering: can a PySide6-hosted OpenGL context coexist cleanly with the existing Pygame-offscreen pipeline (same transfer-to-QPixmap model, or a parallel `QOpenGLWidget` path)? Can `AudioFrame` be handed to a GLSL fragment shader as uniforms (spectrum as a 64-texel 1D texture, bass/mids/treble/beat as scalar uniforms) without breaking the existing zero-Qt-in-visualizers rule? What's the actual frame-transfer cost vs. the already-measured 1.27ms/5.59ms Pygame path? This probe should produce evidence, not a production visualizer — matching how Foundation I's Pygame↔PySide6 bridge was validated before any real visualizer was built on top of it.

---

## 15. Creative Proposals

Six directions, deliberately mixing donor evolutions, recombination, new AudioFrame-native ideas, and one GPU-future idea.

### 1. STARFIELD: DEEP FIELD
**Category**: MUSICAL/DEMOSCENE, GEOMETRIC+PARTICLE (donor evolution, §6)
**Visual thesis**: A 3D star tunnel where camera *pressure* (not speed) and spectral color distribution carry the musical information; motion reads as "being pushed through space by the music" rather than "space is scrolling faster."
**AudioFrame mapping**: `bass`→depth acceleration, `mids`→lateral drift/roll, `treble`→density/sparkle, `spectrum`→depth-color gradient, `beat`→short lurch, `strong_beat`→hyperspace burst.
**Silence behavior**: slow inertial drift, no hard stop.
**Slow music character**: gentle curving drift, warm sparse palette, rare soft lurches.
**Fast music character**: dense, forward-leaning, frequent sharp lurches, saturated shifting palette.
**Beat behavior**: brief forward lurch.
**Strong_beat behavior**: hyperspace streak burst.
**Technology**: Pygame/software.
**Estimated complexity**: LOW (donor math ports almost directly; only driver rewiring + the new spectrum-color-gradient piece is new work).
**Why it belongs**: proven, portable, immediately differentiates genres per §6's analysis, low technical risk — the safe anchor of the batch.

### 2. TOROIDAMP FLOOR (BPM Tiles reinterpretation)
**Category**: MUSICAL/DEMOSCENE hybrid, SPECTRAL+SCENE-BASED (donor evolution, §7)
**Visual thesis**: An illuminated field where the *shape* of illumination — not just its rate — encodes real spectral structure, so a bass-heavy and treble-heavy song at identical BPM look structurally different.
**AudioFrame mapping**: `bass`→central sustained zone, `mids`→structural mid-ring, `treble`→peripheral flashes, `spectrum[64]`→spatial distribution across the field, `beat`→propagation pulse from the loudest spectral zone, `strong_beat`→full-field/multi-zone event.
**Silence behavior**: field dims to a faint, slow-breathing residual glow at the center; no full blackout, no flashing.
**Slow music character**: a calm, mostly-central glow with occasional gentle rings.
**Fast music character**: constant propagating pulses, full field regularly lit, sharp edge activity.
**Beat behavior**: propagation wave outward from the current spectral peak position.
**Strong_beat behavior**: full-field or multi-zone simultaneous flash.
**Technology**: Pygame/software.
**Estimated complexity**: MEDIUM (the propagation-lattice logic is genuinely new work beyond the donor's flat random-spawn model; spectrum-to-spatial-position mapping needs design/tuning).
**Why it belongs**: this is the SIGNATURE candidate — it's the one place where "port as-is" would actively fail ToroidAMP's stated creative principle, so getting the reinterpretation right produces something the donor never had at all.

### 3. SPECTRAL RING
**Category**: MUSICAL, SPECTRAL (donor recombination — physics+color from `SpectrumAnalyzer`, geometry inspired by `ToroidVisualizer`)
**Visual thesis**: The frequency spectrum wraps radially around a toroid-like silhouette instead of sitting as flat bars — low frequencies inner, high frequencies outer — so the spectrum visualizer feels native to ToroidAMP's identity rather than generic.
**AudioFrame mapping**: `spectrum[64]`→radial bar length (with gravity-physics envelope kept in visualizer-local state), `bass`/`mids`/`treble`→heat-gradient color zones (borrowing the magma texture's warmth logic), `beat`→ring pulse, `strong_beat`→full-ring flash.
**Silence behavior**: ring collapses to a thin, dim, slowly-rotating outline.
**Slow music character**: smooth, low-amplitude ring with warm inner glow.
**Fast music character**: spiky, high-contrast ring reaching far outward, hot outer edge.
**Beat behavior**: brief radial pulse.
**Strong_beat behavior**: full-ring flash + brief scale-up.
**Technology**: Pygame/software (numpy optional for bar-array physics, matching donor's optional-numpy pattern).
**Estimated complexity**: MEDIUM (bar-physics port is straightforward; radial layout + heat coloring is new composition work, not new math).
**Why it belongs**: gives ToroidAMP a genuinely distinct spectrum visualizer instead of a generic EQ bar chart, while reusing two of the donor's most technically interesting sub-systems (§8).

### 4. MATRIX WING COMMANDER
**Category**: BECAUSE WE CAN, TYPOGRAPHIC+SCENE-BASED (donor evolution, §9)
**Visual thesis**: Matrix rain as an audio-reactive backdrop, with a squadron of X-Wings/Y-Wings flying scripted formation routes that launch their next maneuver on the beat instead of a fixed clock. Absurd on purpose.
**AudioFrame mapping**: rain — `treble`→density/brightness, `mids`→fall speed, `bass`→depth/distortion; ships — `rms`→cruise speed, `bass`→formation scale pressure, `beat`→maneuver trigger, `strong_beat`→formation attack-run pass, `spectrum`→optional formation color.
**Silence behavior**: rain slows to a bare trickle, ships hold cruise/idle waypoints, no maneuvers trigger.
**Slow music character**: sparse dim rain, ships gliding calmly through wide, slow routes.
**Fast music character**: dense bright rain, ships snapping through maneuvers rapidly, frequent formation passes.
**Beat behavior**: next scripted maneuver segment triggers.
**Strong_beat behavior**: full formation attack-run/close-flyby pass.
**Technology**: Pygame/software.
**Estimated complexity**: MEDIUM (rain is near-trivial; ship waypoint system needs beat-gating logic added on top of the donor's already-built route/draw code).
**Why it belongs**: explicitly protected by mission decree as the deliberately-absurd Because-We-Can candidate; the donor material is unusually reusable (ships are audio-decoupled already, just need beat-gating instead of clock-gating) which makes this cheaper than it looks despite the joke premise.

### 5. HORIZON WAVE (RetroGrid evolution)
**Category**: MUSICAL/DEMOSCENE, GEOMETRIC (donor evolution, §11)
**Visual thesis**: A synthwave perspective grid whose surface is a live spectral heightfield, distinct from a decorative static grid by actually encoding frequency-band structure per row.
**AudioFrame mapping**: `bass`→horizon depth/extrusion, `mids`→camera glide speed, `treble`→line sharpness/sparkle, `spectrum[64]`→per-row heightfield, `beat`→horizon pulse, `strong_beat`→traveling surface wave.
**Silence behavior**: flat, dim, static grid — no glide, no pulses.
**Slow music character**: gentle glide, soft heightfield undulation, thick soft lines.
**Fast music character**: fast glide, sharply carved heightfield, thin bright sparkling lines, frequent traveling waves.
**Beat behavior**: horizon brightness/scale pulse.
**Strong_beat behavior**: visible surface ripple traveling from horizon to camera.
**Technology**: Pygame/software.
**Estimated complexity**: LOW-MEDIUM (perspective projection ports almost directly; heightfield-from-spectrum and traveling-wave are new but contained additions).
**Why it belongs**: rounds out the genre coverage with a distinct geometric family (surface/heightfield) not otherwise represented among the other five proposals, at low risk.

### 6. AURORA FIELD (GPU-future idea)
**Category**: MUSICAL/DEMOSCENE, PSYCHEDELIC (new idea, GPU-native, no direct donor equivalent)
**Visual thesis**: A full-frame procedural plasma/aurora field driven per-pixel by the actual spectrum, not a handful of sampled scalars — something only sane at shader scale, giving ToroidAMP a genuinely new visual space rather than a donor descendant.
**AudioFrame mapping**: `spectrum[64]`→ a 1D texture driving per-pixel color-field phase (each screen column samples a different bin), `bass`→global field distortion/turbulence amplitude, `mids`→flow speed, `treble`→fine-detail noise octave weight, `beat`→brightness pulse, `strong_beat`→turbulence burst.
**Silence behavior**: field settles to a slow, dim, barely-moving ambient wash.
**Slow music character**: smooth, low-turbulence, slowly shifting color field.
**Fast music character**: high-turbulence, fast-flowing, high-contrast field with fine per-pixel detail responding to treble.
**Beat behavior**: global brightness pulse.
**Strong_beat behavior**: turbulence burst rippling across the whole field.
**Technology**: **OpenGL/GLSL** — explicitly the EXP-GL-001 (§14) test case; not buildable at acceptable quality/cost in Pygame per-pixel.
**Estimated complexity**: HIGH (blocked on EXP-GL-001 resolving the GPU-hosting question first; the shader math itself is well-trodden plasma/noise-field territory once a GL path exists).
**Why it belongs**: gives the audit an honest answer to "what should be GPU, not just what could be" — a genuinely spectrum-native full-frame visual that no amount of Pygame optimization would make cheap, and that motivates actually running EXP-GL-001 rather than deferring GPU work indefinitely.

---

## 16. Candidate Scorecard

Scale 1–5. Technical risk: **5 = low risk**. Implementation effort: **5 = cheap/easy**.

| Candidate | Visual Identity | Musical Differentiation | Donor Reuse Value | Technical Risk (5=low) | Resize Compat. | Fullscreen Potential | Performance | Impl. Effort (5=cheap) | ToroidAMP Personality |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 1. Starfield: Deep Field | 4 | 4 | 5 | 5 | 5 | 5 | 5 | 4 | 4 |
| 2. ToroidAMP Floor (BPM Tiles) | 5 | 5 | 3 | 3 | 4 | 5 | 4 | 2 | 5 |
| 3. Spectral Ring | 4 | 3 | 4 | 4 | 4 | 5 | 4 | 3 | 4 |
| 4. Matrix Wing Commander | 5 | 3 | 4 | 3 | 4 | 5 | 3 | 3 | 5 |
| 5. Horizon Wave | 3 | 4 | 5 | 4 | 4 | 5 | 4 | 4 | 3 |
| 6. Aurora Field (GPU) | 5 | 4 | 1 | 1 | 3 | 5 | 3 (once built) | 1 | 4 |

**Tradeoffs, not hidden**: BPM Tiles scores highest on identity/differentiation/personality but lowest technical-risk-and-effort among the software candidates — it is genuinely the most work because the propagation model is new engineering, not a port. Matrix Wing Commander is cheap on the ship-flight side but the rain+ship+beat-gating integration and tuning (making it feel synchronized rather than merely decorated) will take real iteration. Aurora Field is honestly scored low on risk/effort/reuse *on purpose* — it's gated entirely behind EXP-GL-001 and shouldn't be attempted before that probe exists; its high identity/differentiation scores are aspirational, contingent on the GPU path actually working.

**Overall recommendation**: Starfield: Deep Field is the safest immediate win. BPM Tiles is the right investment for ToroidAMP's long-term identity despite the higher effort. Aurora Field should stay parked until EXP-GL-001 runs — including it in the *first* batch would be premature.

---

## 17. Recommended First Three Experiments (Visualizer Lab II)

1. **Starfield: Deep Field** — LOW/MEDIUM-risk donor evolution. Chosen because it validates the "real `AudioFrame` field → genuinely different character" methodology (§6's genre-differentiation analysis) on the cheapest, lowest-risk donor port in the whole audit, establishing a template other visualizers can follow. If this doesn't feel meaningfully different across genres once built, that's an early, cheap signal to recalibrate the whole mapping approach before investing in the harder candidates.

2. **ToroidAMP Floor (BPM Tiles)** — the SIGNATURE candidate. Chosen because it's explicitly the concept the mission treats as flagship-worthy, and because it's the one candidate where the reinterpretation work (spectrum→spatial distribution, real propagation) is itself the interesting engineering problem — worth tackling early while the creative direction is fresh, rather than deferring the hardest/most identity-defining candidate to a later batch.

3. **Matrix Wing Commander** — the deliberately absurd Because-We-Can candidate, per the mission's preferred first-batch structure (one donor evolution, one signature, one absurd). Chosen specifically because it's culturally protected by explicit instruction ("do not remove the X-Wings... that would miss the point") and because the underlying donor material is unusually cheap to adapt (ships already fly audio-decoupled scripted routes; only needs beat-gating swapped in for clock-gating) — low actual engineering cost for a high personality payoff, and it exercises a completely different code path (scripted waypoint animation) than the other two, giving Lab II real creative-space coverage rather than three variations on "particles react to bass."

Spectral Ring and Horizon Wave are strong second-batch candidates (both scored well, §16) but were not selected for the first three specifically to keep the first batch's creative-space spread wide (starfield/geometric vs. tile/spatial vs. scripted-scene) rather than clustering two spectrum/grid-family effects together in the same batch.

---

## 18. Skill Evaluation — `visualizer-authoring`

Read in full (`.agents/skills/visualizer-authoring/SKILL.md`). Evaluated against this audit's findings:

* **Does it encourage real musical differentiation?** Partially. It lists all `AudioFrame` fields with example use-cases (§4 of the skill), which is good, but every example is single-field ("`rms` → brightness," "`bass` → pulse") — it never states that a visualizer should combine multiple fields to produce *different character*, not just different *magnitude*, across genres. This audit's whole methodology (§6's Morricone/metal/electronic differentiation test) is missing from the skill as a principle.
* **Does it over-focus on simple signal-to-parameter mapping?** Yes, structurally — the "Available Audio Signals" table (§4) is literally a signal→parameter mapping table, which is useful reference material but reads as an implicit invitation to "pick one field per visual parameter" rather than "compose fields to express a musical thesis."
* **Does it define silence behavior?** No. Not mentioned anywhere. Every creative proposal in §15 of this document had to specify silence behavior explicitly because the skill gives no guidance on it — a visualizer author following the skill as-is could easily ship something that looks broken (frozen, or worse, jittering on `random()` fallback) during quiet passages or between tracks.
* **Does it define resize behavior?** Yes — §5's "Handles `resize()` cleanly when switching between windowed and fullscreen" is in the authoring checklist, and both production visualizers already comply (§2). Adequate as-is.
* **Does it support stateful effects?** Implicitly yes (the contract's `__init__`/`update()`/`render()` structure naturally supports persistent instance state, and both production visualizers already use it — `ToroidVisualizer`'s rotation angles, `WaveformRibbonVisualizer`'s phase) but the skill never says this explicitly, which matters given `reset()` exists but is dead code (§2) — a reader could reasonably wonder whether visualizers are expected to be stateless and just doesn't know state is fine.
* **Does it distinguish shell UI from visual spectacle?** No — and it shouldn't have to; that distinction is already owned by `reactive-player-ui` (POLISH-001's "the shell owns atmosphere, the visualizer owns spectacle" principle). Fine as-is; not a gap in this skill specifically.
* **Does it need guidance for future shader visualizers?** Not yet — per this audit's own recommendation (§14), GPU visualizers are correctly deferred behind EXP-GL-001, which hasn't run. Adding shader guidance now would be speculative; better to update the skill once that probe produces real answers about the actual GL/Pygame coexistence contract.

**Update applied**: two durable additions to the skill (not donor-specific, not implementation trivia):

> **A VISUALIZER SHOULD HAVE A MUSICAL THESIS.**
> **DIFFERENT MUSIC SHOULD CHANGE CHARACTER, NOT ONLY AMPLITUDE.**

plus a short explicit note on silence behavior, since its complete absence was a real, concrete gap this audit had to work around six separate times in §15. See the skill file diff — the update is a short, principle-level addition, not a rewrite of the existing signal-mapping reference material (which remains accurate and useful).

---

## 19. Risks

1. **BPM Tiles complexity risk**: the propagation-lattice logic (§7) is genuinely new engineering, not a donor port — if Visualizer Lab II's timeline is tight, this candidate could balloon. Mitigate by building the flat spectrum-spatial-distribution mapping first (cheap, already differentiates songs) and treating true propagation as a stretch goal within the same experiment rather than a hard requirement.
2. **SpectrumAnalyzer extraction cost**: at ~1100 lines with heavy format-branching, pulling out just the two genuinely valuable sub-systems (bar physics, magma texture) without dragging in the format-specific cruft will take real editorial discipline during implementation — this is a MEDIUM extraction difficulty for a reason.
3. **Post-FX pipeline entanglement**: the CRT/rave pipeline (§4.17, §12) is the highest general-purpose value non-signature find in the audit, but it's currently inline procedural code tangled with `main()`'s module-level globals in the donor — lifting it into a reusable `PostFXPipeline` component is real refactoring work, not a copy-paste, and should be scoped as its own small task rather than folded silently into whichever visualizer wants it first.
4. **X-Wing tone risk**: "beat-gated maneuvers" needs actual tuning to feel synchronized rather than randomly-timed-but-occasionally-coincidental — beat detection firing during a maneuver mid-flight vs. between maneuvers will need explicit state-machine handling (queue the next maneuver on beat rather than interrupt mid-flight), a design detail not fully resolved in this creative-direction pass.
5. **GPU path is a real unknown**: Aurora Field's viability depends entirely on EXP-GL-001 answering questions this audit deliberately did not investigate (per explicit instruction not to implement OpenGL yet) — treat its scorecard numbers as provisional until that probe exists.

---

## 20. Recommended Visualizer Lab II

Implement the three candidates selected in §17 (Starfield: Deep Field, ToroidAMP Floor, Matrix Wing Commander) as real `Visualizer` subclasses following the existing contract unchanged (§13 — no blocking gaps found), each validated against the multi-genre differentiation test established in §6, each specifying explicit silence behavior (closing the gap identified in §18), and each kept within the existing 8ms render budget. Spectral Ring and Horizon Wave are recommended as the natural second batch. Aurora Field and the broader post-FX pipeline extraction remain explicitly deferred — the former behind `EXP-GL-001`, the latter as its own scoped task rather than bundled into Lab II.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

This is a research/creative-direction audit within the existing ACTIVE Production Cut 3 phase ("Visualizer Expansion & Effects"). No new production visualizers were implemented, no architecture changed, no phase or decision gate closed. Operational baseline remains STABLE.
