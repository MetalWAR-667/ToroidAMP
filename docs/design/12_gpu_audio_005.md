# GPU-AUDIO-005 — Bounded Auto Musicalization

> **Status: EXPERIMENTAL — implemented and unit-validated.** Human validation
> (TEST A–E, §10) is required before this can be considered CLOSED.
>
> Precise language: this is **bounded auto musicalization** — a conservative,
> deterministic, reversible first-pass audio binding generator built on top
> of the existing GPU-AUDIO-003/004 parameter/binding architecture. It is
> **not** semantic shader understanding, and makes no claim to "know" what a
> parameter does.

## 1. Motivation

GPU-AUDIO-003 gave discovered shader parameters manual audio bindings.
GPU-AUDIO-004 extended discovery to safe promoted `const float` values. Both
require a human to open the LAB and configure every binding by hand — correct
for native ToroidAMP authoring (where `taBass -> scale` etc. is a deliberate
artistic decision worth preserving exactly as authored), but for an arbitrary
*external* shader with no musical intent baked in, requiring a human to
manually wire five sliders before hearing anything react is friction with no
upside: ToroidAMP does not need to understand what an external shader's
parameters *mean* to give it *some* restrained, reversible motion as a
starting point.

## 2. Phase 0 Audit

Traced the real code paths before writing anything:

| Path | Finding |
|---|---|
| `ShaderParameter` metadata | Already carries `min_value`/`max_value` for every float parameter, whether annotated (`[param:float]`), unannotated (`uniform float NAME;`, default range `0.0..5.0`), or GPU-AUDIO-004 promoted const (generated span). Every eligible parameter therefore always has a usable clamp range — no special-casing needed for "parameters without a declared range." |
| `current_params` / `audio_bindings` | Both plain `Dict[str, ...]` on `GLVisualizerCanvas`, rebuilt by name on every `load_shader_file()`. Confirmed (Phase 0, this cut) that `audio_bindings` was being preserved-by-name across a load of a genuinely *different* file, not just a same-file hot reload — a real leak risk this cut needed to close (§7). |
| `set_param_audio_binding()` / `get_param_audio_binding()` | The only two entry points anything (LAB UI, tests) ever used to read/write a binding. Both call sites in `fullscreen.py`'s LAB card handlers call `set_param_audio_binding(name, src, amt)` positionally — no keyword usage anywhere in the codebase. This meant new optional trailing parameters with safe defaults are the minimal, fully backward-compatible extension point (§6). |
| Integrated RETINA LAB cards (`fullscreen.py`) | Card construction and the AUDIO source/amount row are generic over `metadata.parameters` — adding a new action button and a provenance badge required no structural changes, only two small, additive edits. |
| Standalone GPU Lab (`lab_app.py`) | Structurally identical card-building code (same comments even reference the Integrated LAB) — confirmed true parity is achievable with the same two edits mirrored. |
| Hot reload / shader switching | `reload_current_shader()` always re-reads from `current_shader_path` — unchanged, still guarantees no synthetic drift on reload. `load_shader_file()` did **not** previously distinguish "reload of the same file" from "load of a different file" for binding preservation — fixed in this cut (§7). |
| AUTO REACT | Fully independent code path (`self.auto_react` bool, generic Shadertoy-wrapper post-modulation) with zero interaction with `audio_bindings` — confirmed no merge risk. |

**Conclusion**: reuse the exact same `audio_bindings` dict and
`set_param_audio_binding`/`get_param_audio_binding` entry points from
GPU-AUDIO-003/004. No second modulation system. The two things that had to be
added were (a) a `mode`/`origin` tag on each binding, carried as extra
elements of the same tuple with backward-compatible defaults, and (b) a
`musicalize()` method that is just a deterministic loop calling the existing
`set_param_audio_binding()`.

## 3. Relative vs. Absolute Modulation

Manual bindings (GPU-AUDIO-003/004, unchanged) stay **absolute**:

```text
final = base + audio * amount
```

Auto-generated (MUSICALIZE) bindings use a new **relative** mode:

```text
final = base * (1 + audio * amount)
```

Worked examples (verified in `tests/test_gpu_audio_005.py::test_02_*`):

```text
base=24.0, audio=0.8, amount=+0.10  ->  25.92
base=0.2,  audio=0.8, amount=+0.10  ->  0.216
```

This scales naturally with the author's own value instead of applying the
same absolute nudge to every parameter regardless of its magnitude — the
thing that would otherwise turn `0.2 -> 2.2` from the same absolute delta
that reasonably moves `24.0 -> 26.0`.

**Edge cases and policy** (`GLVisualizerCanvas._apply_audio_modulation`,
`src/toroidamp/visualizers/gpu_canvas.py`):

- **Zero / near-zero base** (`abs(base) < 1e-6`): pure multiplication of 0 is
  always 0 regardless of `audio`/`amount` — degenerate. Falls back to the
  same small bounded *absolute* nudge (`base + audio*amount`) so a
  musicalized parameter that happens to sit at exactly 0 still gets some
  restrained motion, rather than silently never moving.
- **Negative base**: handled naturally by the formula — sign is preserved,
  deviation stays proportional (`-2.0` at `audio=0.8, amount=0.10` ->
  `-2.16`).
- **Range clamping**: whenever the parameter has a declared
  `min_value <= max_value` (always true — see §2), the relative-mode result
  is clamped into that range. Manual/absolute bindings are deliberately left
  unclamped, matching the pre-existing, already human-validated GPU-AUDIO-003
  behavior exactly — this cut does not retroactively change manual semantics.
- **Silence** (`audio == 0`): `final == base` exactly, for every base
  including 0, in relative mode — no synthetic drift from this layer.

This math is implemented as a small pure static method
(`GLVisualizerCanvas._apply_audio_modulation`), refactored out of `paintGL`
specifically so it is unit-testable without a live GL context — the same
formula the renderer actually calls, not a parallel implementation asserted
against in tests.

## 4. Automatic Modulation Bounds

Deliberately restrained, per the mission's guidance:

```text
Continuous sources (BASS, MIDS, TREBLE, RMS, PEAK):  magnitude in {5%, 8%, 10%, 12%, 15%}
Transient sources   (BEAT, STRONG BEAT):              magnitude in {3%, 5%}, selected 1-in-6
```

Sign (`+`/`-`) is chosen per-parameter, also deterministically. No generated
`amount` ever exceeds `±15%` (verified,
`test_02b_amounts_stay_within_conservative_bounds`). BEAT/STRONG BEAT are
used "only conservatively" exactly as the mission specifies: a 1-in-6
selection weight and a smaller magnitude pool than the five continuous
signals, reflecting that they are discontinuous transient triggers (0/1) that
would otherwise produce a visible snap rather than a smooth deviation.

## 5. Automatic Audio-Source Assignment & Determinism

For each eligible float parameter (sorted by name for stable iteration
order), `GLVisualizerCanvas.musicalize()` derives four independent decisions
from one stable hash:

```python
h = zlib.crc32(param_name.encode("utf-8"))
use_transient = (h % 6) == 0                      # 1-in-6 chance
source        = pool[(h // 6) % len(pool)]         # pool = transient or continuous
magnitude     = magnitudes[(h // 37) % len(magnitudes)]
sign          = +1 if (h % 2 == 0) else -1
amount        = sign * magnitude
```

`zlib.crc32` was chosen deliberately over Python's built-in `hash()`:
`hash()` on strings is salted per-process (`PYTHONHASHSEED`) specifically to
resist certain attacks, which means it produces a **different** mapping on
every single launch — exactly the opposite of what was needed. `crc32` is a
plain deterministic function of the bytes, so the same shader with the same
parameter names produces the identical mapping every time, verified directly
(`test_01_deterministic_automatic_mapping`, three fresh canvases, three loads,
byte-identical results).

No semantic understanding is involved or claimed — the mapping is a
structural function of the parameter's own name, nothing more.

## 6. Manual vs. Auto Ownership

The `audio_bindings` dict value was extended from a 2-tuple to a 4-tuple:

```python
# was:  Dict[str, Tuple[str, float]]                    (source, amount)
# now:  Dict[str, Tuple[str, float, str, str]]           (source, amount, mode, origin)
```

`set_param_audio_binding(name, source, amount, mode="absolute", origin="manual")`
gained two new **optional, defaulted** parameters. Every pre-existing call
site in `fullscreen.py`/`lab_app.py` (the LAB's source-select and
amount-slider handlers) calls this positionally with exactly 3 arguments —
unchanged, and because the defaults are `"absolute"`/`"manual"`, those calls
keep producing exactly the same binding shape GPU-AUDIO-003 always produced.

This is also the entire mechanism for "human edit takes ownership": since the
LAB's manual controls always call `set_param_audio_binding(name, src, amt)`
with no mode/origin override, *any* interaction with a card's AUDIO source or
AMOUNT control — even on a parameter MUSICALIZE just touched — immediately
re-writes its binding as `("...", ..., "absolute", "manual")`, taking it out
of MUSICALIZE's reach with no extra code (verified,
`test_07c_manual_edit_of_auto_binding_takes_ownership`).

`get_param_audio_binding(name)` keeps its original 2-tuple return shape
(back-compat for every existing caller); `get_param_audio_binding_full(name)`
is new, returning the full 4-tuple; `is_param_binding_auto(name)` is a small
convenience predicate.

`musicalize()` itself respects ownership on the way in: it skips any
parameter whose current binding has `origin == "manual"`, so re-running
MUSICALIZE never clobbers something the human already configured — only
unbound or still-"auto" parameters are (re)computed.

## 7. MUSICALIZE / CLEAR AUTO UI

Added to both the Integrated RETINA LAB (`fullscreen.py`) and the Standalone
GPU Authoring Lab (`lab_app.py`), styled consistently with each surface's
existing action-bar buttons:

```text
[ ⚡ MUSICALIZE ]   [ CLEAR AUTO ]
```

- **MUSICALIZE**: calls `canvas.musicalize()`, then rebuilds the parameter
  cards (`_rebuild_lab_panel()` / `_rebuild_parameter_ui()`) so every
  generated mapping is immediately visible and immediately editable through
  the exact same AUDIO source / AMOUNT controls GPU-AUDIO-003 built — no
  separate "generated parameters" view, no black-box mode.
- **CLEAR AUTO**: calls `canvas.clear_auto_bindings()`, which removes only
  `origin == "auto"` entries, then rebuilds the cards. Manually-configured
  bindings are untouched (chosen semantic — Option A from the mission's
  reversibility section: an explicit, separate CLEAR action, since the
  Integrated LAB's other action buttons — LOAD, RELOAD, RESET — are already
  plain non-toggleable buttons and MUSICALIZE fits that same idiom better
  than a checkable toggle would).
- **Inspectability**: every card whose current binding has `origin == "auto"`
  shows `AUDIO: <SOURCE> [AUTO]` (accent-colored) instead of the ordinary
  `AUDIO: <SOURCE>`, mirroring the `[CONST]` provenance badge pattern already
  established by GPU-AUDIO-004 for promoted parameters. This is the whole
  "inspectable in the existing LAB controls" requirement — no new panel, one
  conditional string.

## 8. Hot Reload / Shader-Switch Behavior

- **Hot reload of the same file** (`R` / RELOAD): unchanged preserve-by-name
  behavior, now naturally carrying the full 4-tuple (BASE, source, amount,
  mode, origin all survive together) since the preservation loop in
  `load_shader_file()` copies whatever tuple shape `audio_bindings` holds —
  it required no changes for GPU-AUDIO-005's tuple extension.
- **Loading a genuinely different shader file**: previously, `load_shader_file()`
  preserved `audio_bindings` by parameter *name* across any load, including a
  load of an unrelated shader that happened to reuse a name like `u_speed` —
  a real leak this cut closes. `load_shader_file()` now detects
  `file_path != self.current_shader_path` (only true for a real switch, never
  for `reload_current_shader()`, which always re-passes the same path) and
  resets `audio_bindings = {}` before applying the new shader's parameters —
  verified directly, no binding survives a switch to a different file
  (`test_09_shader_switch_does_not_leak_bindings`). `current_params` (BASE
  values) intentionally keep their pre-existing preserve-by-name behavior,
  unchanged — that's validated GPU-AUDIO-003 territory outside this cut's
  scope, and the mission's explicit ask was about binding leakage.
- **Compile failure**: unchanged, pre-existing GPU-AUDIO-003/004 transactional
  rollback (`self._program`/state only reassigned on link success).

## 9. Real Shader Audit

Ran `musicalize()` against every shader currently in the repository:

| Shader | Eligible float params | Musicalize result |
|---|---|---|
| `user_shaders/shadertoy/apollo_spiral/apollo_spiral.frag` | 0 | `{}` — golfed inline-literal Shadertoy import, no discoverable/promotable params at all (same finding as GPU-AUDIO-004's audit). |
| `user_shaders/shadertoy/happy_glow_cruise/happy_glow_cruise.frag` | 0 | `{}` — same. |
| `user_shaders/shadertoy/rig_rekt/Rig_Rekt.frag` | 0 | `{}` — same. |
| `user_shaders/apollo_spiral_toroidamp_test.frag` | 4 (`u_iterCount`, `u_speed`, `u_bassScale`, `u_glow`) | `{'u_bassScale': ('BASS', -0.1), 'u_glow': ('PEAK', 0.05), 'u_iterCount': ('TREBLE', 0.1), 'u_speed': ('BASS', -0.1)}` — a genuinely real, pre-existing repo shader with useful auto-generated bindings (category D — see below). |
| `user_shaders/test_discovered_params.frag` | 3 (`u_zoom`, `u_speed`, `u_glow`) | `{'u_glow': ('PEAK', 0.05), 'u_speed': ('BASS', -0.1), 'u_zoom': ('TREBLE', -0.1)}` — category C. |
| `user_shaders/test_const_promotion_demo.frag` | 3 (`SPEED`, `ZOOM`, `GLOW` — `STEPS` correctly excluded, wrong type) | `{'GLOW': ('BASS', -0.05), 'SPEED': ('STRONG BEAT', 0.05), 'ZOOM': ('TREBLE', 0.1)}` — category B. |
| `src/toroidamp/assets/official_shaders/audio_reactive_reference.frag` | 5 | `{'u_detail': ('MIDS', -0.08), 'u_glow': ('PEAK', 0.05), 'u_speed': ('BASS', -0.1), 'u_twist': ('PEAK', -0.12), 'u_zoom': ('TREBLE', -0.1)}` — category A. |
| `src/toroidamp/assets/official_shaders/cyber_bloom.frag` | 3 of 7 (bool/color params correctly skipped: `u_enableDistortion`, `u_invertColors`, `u_primaryColor`, `u_accentColor`) | `{'u_glowIntensity': ('BEAT', 0.05), 'u_speed': ('BASS', -0.1), 'u_warpDepth': ('TREBLE', 0.15)}` |
| `src/toroidamp/assets/official_shaders/toroid_identity.frag` | 5 | `{'u_bgIntensity': ('RMS', -0.15), 'u_chroma': ('BASS', -0.08), 'u_glow': ('PEAK', 0.05), 'u_rotation': ('RMS', -0.15), 'u_warp': ('PEAK', -0.05)}` |

**Honest reporting on category D** (real external shader with suitable
discoverable/promotable candidates): the three pure Shadertoy imports
(apollo_spiral, happy_glow_cruise, Rig_Rekt) still have zero eligible params
— confirmed unchanged from the GPU-AUDIO-004 finding, still golfed
inline-literal demoscene code. `apollo_spiral_toroidamp_test.frag`, however,
**is** a real, pre-existing repo shader (a ToroidAMP-adapted variant with
authored `uniform float` parameters, not a synthetic fixture created for this
cut) that MUSICALIZE handles correctly and usefully — this genuinely
satisfies category D without needing to write a new fixture. Safety rules
were not weakened anywhere to manufacture this result.

## 10. Human Validation Protocol

**TEST A — Reference shader**
1. RETINA MELT -> LAB. Load/select `audio_reactive_reference.frag`.
2. Confirm AUTO REACT is OFF.
3. Press `⚡ MUSICALIZE`.
4. Play music.
5. Confirm multiple parameter cards show `AUDIO: <SOURCE> [AUTO]`.
6. Confirm visible, restrained musical response (not destructive to the
   shader's baseline identity).
7. Press `CLEAR AUTO` — confirm all cards return to `AUDIO: NONE` and the
   shader visibly returns to its unmodulated baseline.

**TEST B — Const promotion fixture** (retest after the Human Gate Defect A fix, §13)
1. Load `user_shaders/test_const_promotion_demo.frag`.
2. Confirm AUTO REACT is OFF (this shader is Shadertoy-style and does
   support the AUTO REACT branch, unlike `audio_reactive_reference.frag` —
   leaving it ON would visually mask which effect is MUSICALIZE's).
3. Confirm `SPEED [CONST]`, `ZOOM [CONST]`, `GLOW [CONST]` cards appear
   (`STEPS` does not — GPU-AUDIO-004 exclusion, unaffected by this cut).
4. Press `⚡ MUSICALIZE` — confirm all three cards show `AUDIO: <SOURCE> [AUTO]`.
5. Play music — confirm `ZOOM` (bound to TREBLE) produces a visible
   frame-wide scale pulse and `GLOW` (bound to BASS, now driving overall
   exposure post-fix) produces a visible frame-wide brightness pulse.
   `SPEED` is bound to STRONG BEAT at a small magnitude and drives only the
   animation *rate* — expect at most a subtle drift, not a dramatic effect;
   this is an inherent characteristic of rate parameters, not a defect.
6. Press `CLEAR AUTO` — confirm all three cards return to `AUDIO: NONE` and
   the shader visibly returns to its static-BASE appearance (aside from its
   own native time-driven animation).

**TEST C — Edit generated result**
1. On a card MUSICALIZE just generated, manually change its AUDIO source.
2. Manually change its AMOUNT.
3. Confirm the `[AUTO]` badge disappears immediately (ownership transferred).
4. Press `⟳ RELOAD (R)`.
5. Confirm the manually-edited BASE/source/amount survive the reload.

**TEST D — Clear/revert**
1. With a mix of manual and MUSICALIZE-generated bindings present, press
   `CLEAR AUTO`.
2. Confirm only the still-`[AUTO]`-tagged cards return to `AUDIO: NONE` /
   BASE.
3. Confirm the manually-owned binding from TEST C is untouched.

**TEST E — Silence**
1. Press `⚡ MUSICALIZE`. Play music, observe modulation.
2. Pause/stop playback.
3. Confirm every auto-modulated parameter's rendered value settles back to
   exactly its BASE slider value while the shader's own native `u_time`
   animation continues normally (no post-musicalization freeze, no residual
   offset).

## 11. Relationship to AUTO REACT / Native `ta*` Authoring

```text
NATIVE ta* AUTHORING           Highest artistic control — the shader author deliberately
                                wires taBass/taMids/etc. into its own logic.
DISCOVERED/PROMOTED BINDING    Human chooses shader parameter <-> musical signal
(GPU-AUDIO-003/004)            manually, absolute modulation, unclamped.
MUSICALIZE (GPU-AUDIO-005)     ToroidAMP generates conservative, deterministic,
                                relative/clamped bindings as an editable starting point,
                                through the SAME discovered-parameter binding system.
AUTO REACT                     Generic presentation-level post-modulation, entirely
                                independent of shader-internal parameters or bindings.
```

MUSICALIZE operates exclusively through `audio_bindings` — the same
mechanism TUNE/LAB manual controls use — and never touches `auto_react` or
the Shadertoy-wrapper post-modulation layer. Verified directly
(`test_14_auto_react_independent_of_musicalize`): enabling AUTO REACT,
running MUSICALIZE, and clearing MUSICALIZE's bindings each leave the other
system's state completely unaffected.

## 12. Limitations / Out of Scope (Level D+, explicitly deferred)

Per the mission, none of the following were implemented in this cut:
persistent shader/audio association profiles; semantic interpretation of
parameter names; arbitrary local-variable promotion; int/vec2/vec3/vec4/
matrix musicalization; `#define` promotion; spectrum/waveform texture
binding; iChannel textures; BPM/downbeat analysis; multipass Buffer A/B/C/D;
FBO feedback. `taBpm`/`taBeatPhase`/`taBarPhase` are never used as
musicalize sources, matching the mission's explicit exclusion (they remain
experimental placeholders).

Additional honest limitations:
- The deterministic hash-based assignment is a structural function of the
  parameter's *name string only* — it has no notion of what a parameter
  visually does, by design. Two differently-behaving parameters that happen
  to share a name across two different shaders will musicalize identically;
  this is expected and acceptable given the "no semantic understanding"
  boundary.
- No live-GL-context validation of the actual `glUniform1f` upload path in
  this offscreen development environment (same structural caveat as
  GPU-AUDIO-004) — mitigated by refactoring the modulation formula into a
  standalone pure function (`_apply_audio_modulation`) that is unit-tested
  directly, and by real Human Gate validation (§10) before closing.
- Whether the generated mappings are *good* rather than merely *safe* is
  precisely what TEST A/B human validation is for — bounded and reversible
  does not automatically mean aesthetically pleasing, and this doc does not
  claim otherwise pending that validation.

---

## 13. Human Gate Defect A — Promoted Const Parameters "Not Musicalized"

**Reported**: `audio_reactive_reference.frag` PASSED human validation (MUSICALIZE
visibly reactive, CLEAR AUTO correct). `test_const_promotion_demo.frag`
FAILED: "MUSICALIZE produces no observable parameter/audio modulation."
Metal's hypothesis: promoted const parameters were not reaching the
GPU-AUDIO-005 eligible-parameter/binding path correctly.

**Trace performed** (via the real `RetinaMeltWindow`, real
`QTest.mouseClick` on `btn_lab_musicalize`, real `render_frame()` calls —
not a parser/model-only shortcut) against every layer of the pipeline:

| Layer | Traced result |
|---|---|
| GPU-AUDIO-004 detection -> promotion -> `ShaderParameter` | `SPEED`/`ZOOM`/`GLOW` correctly discovered as `is_promoted_const=True`, `STEPS` correctly excluded (wrong type + unsafe loop-bound usage). |
| Generated uniform declaration / linked active uniform | Full wrapped GLSL inspected directly — `uniform float GLOW/ZOOM/SPEED;` declared once each, all three referenced in `mainImage()`'s body (cannot be dead-code-eliminated), syntactically valid `#version 330 core`. |
| `metadata.parameters` -> `current_params` -> LAB card | Cards confirmed present via the real LAB rebuild: `GLOW [CONST]`, `ZOOM [CONST]`, `SPEED [CONST]`, BASE values `1.80`/`1.40`/`0.60` matching the declared consts exactly. |
| `musicalize()` eligibility | All three float promoted params pass eligibility (no pre-existing manual bindings) and receive generated bindings. |
| Generated `audio_bindings` 4-tuple | `GLOW: ('BASS', -0.05, 'relative', 'auto')`, `SPEED: ('STRONG BEAT', 0.05, 'relative', 'auto')`, `ZOOM: ('TREBLE', 0.1, 'relative', 'auto')` — `mode`/`origin` exactly as expected. |
| `_apply_audio_modulation()` with the real generated range | Evaluated with a deliberately strong `AudioFrame` (bass/mids/treble/rms/peak=0.9-0.95, beat/strong_beat=True): `GLOW: 1.80 -> 1.719`, `ZOOM: 1.40 -> 1.526`, `SPEED: 0.60 -> 0.63` — all three **materially differ from BASE**, none clamped to BASE. |
| Range clamping (prime suspect per the mission) | Generated ranges are `GLOW (-1.8, 5.4)`, `ZOOM (-1.4, 4.2)`, `SPEED (-0.6, 1.8)` — all well-formed, non-degenerate, non-inverted, and nowhere near clamping the strong-frame results above. **Clamping was directly ruled out** — a synthetic degenerate-range unit test (`test_05_final_value_clamped_to_declared_range`) confirms clamping activates only when actually out of range. |
| Silence | All three resolve exactly to BASE (`final == base`, verified via direct equality, not `assertAlmostEqual`). |
| CLEAR AUTO | `audio_bindings` empties correctly via the real button click. |

**Root cause**: no divergence was found in the binding/promotion/modulation
pipeline itself — it is structurally identical in behavior to the passing
`audio_reactive_reference.frag` path (same code, same formula, real
verified value differences). Metal's hypothesis (promoted consts not
reaching the eligible/binding path) is **refuted** by this trace: they do
reach it, correctly, every layer.

The actual cause of "no observable modulation" was a **shader-fixture
visibility gap**, not a pipeline defect: `test_const_promotion_demo.frag`'s
own GLSL body fed `GLOW` into a *tightly localized* term
(`GLOW * 0.05 / (r + 0.05)`) that only meaningfully affects a small
near-center hotspot — a ~5% deviation there reads as an almost imperceptible
flicker in a small region of the frame, unlike `audio_reactive_reference.frag`
(intentionally authored as a dramatic LAB showcase, where every parameter —
`u_zoom`, `u_glow`, `u_twist`, `u_detail` — directly and visibly transforms
the *entire* frame). `test_const_promotion_demo.frag` was originally built
only to validate that promotion/detection *worked at all* (GPU-AUDIO-004),
not as a visually dramatic showcase — a gap that only became apparent once
GPU-AUDIO-005 needed a human to actually *watch* it react.

**Fix applied** (fixture only — GPU-AUDIO-004/005 pipeline code and
MUSICALIZE's algorithm/percentages were **not** touched):
`user_shaders/test_const_promotion_demo.frag`'s `mainImage()` body was
changed so `GLOW` scales overall frame exposure (`col *= GLOW * 0.55`)
instead of only a small hotspot, and the previous hotspot term is kept but
weakened so it can no longer dominate. The three `const float` declarations
(`SPEED = 0.6`, `ZOOM = 1.4`, `GLOW = 1.8`) and `STEPS`'s promotion-exclusion
role are unchanged — every existing GPU-AUDIO-004 test that depends on the
declared names/defaults still passes unmodified.

**Production-path regression test added**:
`tests/test_gpu_audio_005.py::TestGPUAudio005HumanGateDefectA` reproduces
Metal's exact 14-step failed path against the real production window (steps
1-14 from the mission, including real `QTest.mouseClick` on both
`btn_lab_musicalize` and `btn_lab_clear_auto`, and the same
`_apply_audio_modulation` production formula evaluated against the real
generated range). One boundary genuinely cannot be crossed by this offscreen
test environment: whether the evaluated final float value is actually
uploaded via `glUniform1f` to the linked uniform location and produces the
expected pixels — that remains the human-gate's job (§10, TEST B), not this
automated test's. `test_defect_a_reference_shader_regression` confirms
`audio_reactive_reference.frag` is unaffected and still passes the same
production path.

**Result**: 23/23 tests pass in `test_gpu_audio_005.py` (2 new tests added).
Full regression sweep unaffected (same pre-existing, unrelated
`test_ux_004.py` marquee failures as every prior delivery this session;
nothing else changed).

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

Additive extension of the already-ACTIVE Production Cut 3 phase, built
entirely on existing GPU-AUDIO-003/004 infrastructure. No phase or decision
gate changed. Consistent with GPU-AUDIO-001 through 004, none of which were
itemized in `docs/CURRENT_STATE.md` either.
