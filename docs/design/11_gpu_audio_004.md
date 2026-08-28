# GPU-AUDIO-004 — Safe Const-Float Promotion

> **Status: EXPERIMENTAL — safe const-float promotion implemented and unit-validated.**
>
> Precise language matters here: this document claims **"safe const-float promotion,"**
> never "automatic shader parameter extraction." The mechanism is deliberately narrow — see
> §2 for exactly what it does and does not cover, and §8 for what real evidence actually
> supports.

## 1. Relationship to GPU-AUDIO-003

GPU-AUDIO-003 (CLOSED — HUMAN VALIDATED, `docs/design/10_gpu_audio_003.md`) proved the full
production path — discovered `uniform float` → BASE → AUDIO source → AMOUNT → live musical
modulation — works in the real Integrated RETINA LAB. Human testing then exposed the actual
limitation the whole effort was investigating: **many arbitrary external/Shadertoy shaders
expose zero `uniform float` controls at all**, because authors commonly tune their shaders
with `const float NAME = <literal>;` declarations instead.

GPU-AUDIO-004 is a narrow, conservative extension: discover **safe** `const float` declarations
in an external shader, promote them to real uniforms in ToroidAMP's transient/internal
compilation copy, and route them through the **exact same** GPU-AUDIO-003 parameter/audio-binding
infrastructure. No second modulation system was created.

```text
PATH A — Native ToroidAMP authoring        shader declares taBass/taBeat/etc. → shader owns musical behavior.
PATH B — Discovered explicit parameters    shader declares uniform float → LAB exposes it → user assigns AUDIO.
PATH C — Safe promoted const  (THIS DOC)   shader declares eligible const float → ToroidAMP promotes a transient
                                             compilation copy → LAB exposes it → user assigns AUDIO manually.
PATH D — AUTO REACT                        arbitrary shader → generic presentation-space modulation only.
```

---

## 2. Phase 0 Audit — Insertion Point

Before writing any promotion code, the existing pipeline was traced end to end
(`src/toroidamp/visualizers/gpu_compiler.py`, `src/toroidamp/visualizers/gpu_canvas.py`):

| Stage | What already exists | Relevance to GPU-AUDIO-004 |
|---|---|---|
| Source loading | `GLVisualizerCanvas.load_shader_file()` reads the file into `raw_code` once, calls `classify_and_wrap_source(raw_code, ...)`, and **never writes `raw_code` back anywhere** — it only produces a new `full_source` string. | The absolute source-preservation rule is satisfied by construction as long as promotion stays inside this call chain, operating on in-memory copies only. |
| Shadertoy/native wrapper | `classify_and_wrap_source()` already has a generic "inject `uniform float NAME;` if not already declared" loop, driven purely by the `parameters: Dict[str, ShaderParameter]` produced by `parse_shader_parameters()`. | **This is the safest insertion point.** If promoted consts are added to the same `parameters` dict *before* this loop runs, the existing injection logic handles declaration generation for free — no duplicated wrapper logic needed. |
| Parameter/uniform parser | `parse_shader_parameters()` only recognizes `[param:...]` annotations and bare `uniform float` declarations. | Left completely unchanged — const promotion is a separate, additive pass. |
| Compile/link | `GLVisualizerCanvas.load_shader_file()`: vertex compile → fragment compile → link, each with an immediate `return False` on failure, **strictly before** `self._program = new_prog` is ever assigned. | Already-correct all-or-nothing rollback: if a promoted-const transformation happens to produce a shader that fails to compile, this existing check silently protects the user with zero new code — the whole shader load just fails cleanly, same as any other shader error, and the previous known-good program/state is untouched. |
| Active-uniform filtering | After link success, `active_parameters` is built by checking `new_prog.uniformLocation(p_name) != -1` for every discovered parameter, and only active-uniform names survive into `self.metadata`. | A second, independent safety net: even if a promoted uniform is somehow optimized away or not actually referenced, it silently disappears from the LAB instead of causing an error — exactly the same behavior as any other unused discovered uniform. |
| `current_params` / `audio_bindings` ownership | Both are plain `Dict[str, ...]` keyed by parameter **name**, rebuilt on every `load_shader_file()` call via "keep if name survives in `active_parameters`, else default" logic. | Because promoted consts keep their **original, unmodified name**, this preserve-by-name logic works for them automatically — no promotion-specific hot-reload code was needed at all. |
| Hot reload | `reload_current_shader()` calls `load_shader_file(self.current_shader_path)` — always re-reads the real file from disk. | "Hot reload always begins again from the real source file" was already guaranteed; nothing to add. |

**Conclusion**: the safest, smallest-footprint insertion point is a single call inside
`classify_and_wrap_source()`, right after `parameters = parse_shader_parameters(clean_src)`:
merge in a new dict of promoted `ShaderParameter` entries, and use a *transformed* copy of
`clean_src` (original const declarations neutralized into comments) for everything downstream.
No changes were needed in `gpu_canvas.py` at all.

---

## 3. Exact Supported Grammar

Deliberately narrow, exactly matching the mission's V1 contract:

```text
const float NAME = NUMERIC_LITERAL;
```

- One declarator per statement, nothing else on the line (`CONST_FLOAT_LITERAL_RE` requires the
  entire (stripped) line to be exactly this shape).
- `NUMERIC_LITERAL` = `[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?` — signed or unsigned, optional decimal,
  optional scientific-notation exponent (`1e-3`, `-2.5e2`). No leading-dot form (`.5`), no `f`
  suffix — not broadening the grammar merely for completeness.
- Only `const float`. `const int`, `const bool`, `const vec2/vec3/vec4`, `const mat*` are never
  even candidates — the regex requires the literal `float` keyword.
- Multi-declarator lines (`const float A = 1.0, B = 2.0;`), expression initializers
  (`const float B = A * 2.0;`), and anything with a trailing comment on the same line simply
  fail to match at all — the narrow grammar is the *first* line of defense, before any
  exclusion check even runs.

---

## 4. Exact Safety / Rejection Rules

A candidate that matches the grammar above is still rejected (never promoted) if
`_const_is_unsafe_to_promote()` finds any of:

1. **Array dimension** — the name appears anywhere inside `[ ... ]`, including wrapped in a
   cast/expression like `arr[int(STEPS)]`, not only a bare `[STEPS]`.
2. **Loop bound** — the name appears anywhere inside a `for ( ... )` header.
3. **switch/case label** — `case NAME:`.
4. **Preprocessor expression** — the name appears on any line starting with `#`
   (`#define`, `#if`, `#ifdef`, etc.).
5. **Const-expression dependency** — some *other* `const` declaration (of any type, not only
   `float`) has an initializer expression that references the name — e.g. `const float B = A *
   2.0;` makes `A` unsafe, because promoting `A` to a uniform would invalidate `B`'s GLSL
   constant-expression requirement.
6. **Non-float type** — enforced structurally by the grammar itself (§3), not a separate check.
7. **SYSTEM_UNIFORMS collision** — the name matches any entry in the existing
   `SYSTEM_UNIFORMS` set (`iTime`, `taBass`, `u_resolution`, etc.).
8. **Name already claimed** — the name is already a discovered annotated/explicit-uniform
   parameter (promoted consts are strictly additive; an authored uniform always wins).

**When any check is inconclusive or the construct isn't covered above: do not promote.**
False negatives (a promotable const that stays const) are accepted; false positives (breaking
an arbitrary shader) are not — this is enforced by design, not just documented as intent: every
check above defaults to "unsafe" on any match, and the grammar itself only ever considers the
narrowest possible shape as a candidate in the first place.

---

## 5. Internal Transformation Strategy

The transformation deliberately does **not** rename the constant. `SPEED` stays `SPEED`:

```glsl
// Before (in memory only — never written to the source file):
const float SPEED = 0.8;

// After (transient compilation copy):
// [gpu-audio-004] promoted from const, default=0.8: SPEED
uniform float SPEED;   // injected by the existing generic uniform-injection loop
```

This was chosen over generating a fresh identifier (e.g. `taPromotedConst_7_SPEED`) and
rewriting every reference to it, because:

- **Zero reference-rewriting risk** — every existing use of `SPEED` in the shader body is
  already correct; nothing downstream needs to change.
- **Names are already unique within the shader** — GLSL doesn't allow two declarations of the
  same identifier, so there's no collision to resolve by construction, other than checking
  against `SYSTEM_UNIFORMS` and already-discovered parameter names (§4, rules 7–8).
- **The LAB displays `SPEED`, not a mangled name** — for free, with no display-name mapping
  logic needed at all.
- **Deterministic and mappable back to the original name** — trivially, because it *is* the
  original name.

One implementation subtlety worth recording: the replacement comment text deliberately avoids
writing `"float SPEED"` as an adjacent phrase (it reads `"promoted from const, default=0.8:
SPEED"` instead of quoting the original declaration verbatim). The existing generic
uniform-injection loop dedups via a text search for `f"float {name}"` in the source — if the
comment had echoed the original `const float SPEED = 0.8;` line verbatim, that dedup check
would have wrongly concluded a real declaration already existed and skipped injecting the
actual `uniform float SPEED;` line. Caught and fixed during implementation via a real
end-to-end GL compile test.

---

## 6. Parameter Range-Generation Policy

Promoted consts have no author-declared `min`/`max`. The policy, applied uniformly:

```python
span = max(abs(value) * 2.0, 1.0)
min_value = value - span
max_value = value + span
```

- The original value always sits well inside the range, never at an edge.
- A minimum span of `1.0` on each side guarantees a useful non-zero editing range even for a
  **zero-valued** constant (`0.0` → range `(-1.0, 1.0)`).
- **Negative** constants remain fully representable — the formula is symmetric around `value`
  regardless of sign (`-0.4` → range `(-1.4, 0.6)`).
- The span scales proportionally with the constant's own magnitude, so it stays reasonable for
  larger constants (`2.0` → range `(-2.0, 6.0)`) without exploding.
- **Known limitation**: for very small-magnitude constants (e.g. `1e-3`), the generated range
  (`(-0.999, 1.001)`) is large *relative* to the constant's own scale — useful editing headroom
  exists, but fine-grained precision near the original value isn't specially preserved. This is
  an accepted tradeoff of a deliberately simple, generic policy rather than semantic inference
  (explicitly out of scope).

---

## 7. LAB Integration Behavior

Promoted consts appear through the exact same parameter-card system GPU-AUDIO-003 already
built — no separate "CONST PANEL" was created. The only visible addition is a provenance
suffix on the card's name label, applied identically in both the Integrated LAB
(`src/toroidamp/ui/fullscreen.py`) and the Standalone GPU Lab
(`experiments/gpu_visualizers/lab_app.py`):

```text
SPEED [CONST]
[--------- BASE ---------]
[ AUDIO: NONE ]   +0.00 [-------- AMOUNT --------]
```

This was cheap because the metadata model already supports it cleanly — `ShaderParameter`
gained one new field, `is_promoted_const: bool = False` (additive, backward-compatible; every
existing call site that constructs a `ShaderParameter` via keyword arguments is unaffected).
The card-building code checks `getattr(param, "is_promoted_const", False)` and appends
`" [CONST]"` to the display label when true. No architecture expansion beyond that one field
and one conditional string.

Audio modulation for a promoted const uses the identical formula and source set as any other
float parameter — `final_value = base_value + (audio_source_value * amount)`, sources
`NONE/BASS/MIDS/TREBLE/BEAT/STRONG BEAT/RMS/PEAK` — because it flows through the exact same
`GLVisualizerCanvas.set_param_audio_binding()`/`get_param_audio_binding()`/`paintGL()`
modulation code GPU-AUDIO-003 already validated. Silence resolves exactly to BASE, verified
directly against a promoted const (not only the original discovered-uniform fixture).

---

## 8. Hot-Reload / State Behavior

Governed entirely by the existing preserve-by-name logic in `load_shader_file()` — no
promotion-specific reload code was written:

- **Survives by original name**: BASE, AUDIO source, and AMOUNT all survive a hot reload for a
  promoted const whose name is still present (and still safely promotable) in the reloaded
  source — verified directly.
- **Disappears or becomes unsafe**: its `current_params`/`audio_bindings` entries are pruned,
  because the rebuild loop only keeps entries for names present in the newly filtered
  `active_parameters` set — traced manually in the Phase 0 audit; not independently exercised
  by an automated test in this environment (see the environment caveat below).
- **Compile/link failure**: the previous known-good `self._program`, `self.metadata`,
  `self.current_params`, and `self.audio_bindings` are never reassigned — this is the existing
  GPU-AUDIO-003 rollback behavior, unmodified, and applies uniformly whether the failure came
  from a genuinely broken external shader or (hypothetically) from a promotion mistake.
- **Source file**: never written to, at any point in this pipeline — verified directly by
  hashing/reading the fixture file's bytes before and after a full load→reload cycle.

**Environment caveat, stated honestly**: this development/test environment's
`GLVisualizerCanvas.isValid()` never becomes `True` (no software OpenGL backend is configured
for the offscreen Qt platform here), so `load_shader_file()` always takes its
headless/metadata-only fallback branch — the branch that never performs real GLSL compilation,
active-uniform filtering, or the pruning-on-vanish behavior. Two automated tests that
specifically require that live-context branch (pruning of a vanished promoted param; rollback
on a genuine compile/link failure) are **honestly skipped** with a clear reason, rather than
asserted against the headless fallback (which would either trivially pass for the wrong reason
or require faking GL state). This mirrors the project's established `libmodplug`-unavailable
skip precedent. Everything else — including real end-to-end compilation, verified manually
during implementation (§9) — was validated against an actual live GL context obtained outside
the pytest harness.

---

## 9. Real External Shader Audit

Per the mission's explicit instruction not to validate this only with synthetic shaders, every
external/user `.frag` already present in this repository was inspected for `const float`
usage:

| Shader | Custom `uniform float` discovered | Safe `const float` discovered | Safe `const float` promoted | Consts rejected | Notes |
|---|---|---|---|---|---|
| `user_shaders/shadertoy/apollo_spiral/apollo_spiral.frag` | 0 | 0 | 0 | — | Heavily golfed demoscene Shadertoy shader — every numeric tunable is an inline literal, no named `const` at all. |
| `user_shaders/shadertoy/happy_glow_cruise/happy_glow_cruise.frag` | 0 | 0 | 0 | — | Same style — `#define` macros for repeated expressions, but zero `const float` declarations. |
| `user_shaders/shadertoy/rig_rekt/Rig_Rekt.frag` | 0 | 0 | 0 | — | Same style. |
| `user_shaders/apollo_spiral_toroidamp_test.frag` | 4 (`[param:float]`-annotated) | 0 | 0 | — | Already a natively-authored ToroidAMP shader (Path A) — fully parameterized by hand, no bare consts. |
| `user_shaders/test_user_spiral.frag`, other `user_shaders/test_*.frag` fixtures | varies (existing GPU-AUDIO-001/003 fixtures) | 0 | 0 | — | Purpose-built test fixtures for other GPU-AUDIO cuts; none use `const float`. |
| `src/toroidamp/assets/official_shaders/*.frag` (existing) | 3–7 each (`[param:float]`-annotated) | 0 | 0 | — | All official reference shaders already use the annotation system, by design. |

**Honest empirical finding: none of this repository's currently-bundled or user-provided
external shaders contain a `const float` declaration at all.** This is genuinely useful
evidence, not a failure to report quietly — the sampled Shadertoy imports are dense,
competition-golfed demoscene shaders (`fractal(vec3 p)` one-liners, comma-operator loop bodies)
where every tunable is an inline literal; ToroidAMP's own native-authoring shaders already use
the `[param:...]` annotation system instead of bare consts, since that's the more expressive
Path A/B mechanism. The corpus available in this repository simply doesn't exercise the shape
GPU-AUDIO-004 targets.

To still provide concrete, honest human validation material (TEST A, §11), a **new** fixture —
clearly labeled as such, not represented as a pre-existing shader retroactively benefiting —
was added: `user_shaders/test_const_promotion_demo.frag`. It represents the realistic shape of
an external shader with zero authored controls but named `const float` tunables an author might
plausibly have used (`SPEED`, `ZOOM`, `GLOW`), plus a deliberately-included `const int STEPS`
loop bound to demonstrate the exclusion rules working on a realistic structure rather than only
a synthetic unit-test string. Verified end-to-end: `SPEED`/`ZOOM`/`GLOW` promote correctly;
`STEPS` is correctly rejected (wrong type **and** unsafe loop-bound usage, independently).

---

## 10. Audio Reactive Reference — Official Visualizer Registration

`audio_reactive_reference.frag` (GPU-AUDIO-003's bundled reference shader) is now reachable
through ToroidAMP's normal visualizer cycle, using the **exact same** registration mechanism as
`toroid_identity.frag` and `cyber_bloom.frag` — no new selector, no new registry architecture.

- New descriptor class: `src/toroidamp/visualizers/audio_reactive_reference.py` →
  `AudioReactiveReferenceVisualizer(Visualizer)`, structurally identical to
  `CyberBloomVisualizer`/`ToroidIdentityVisualizer` (`get_id()`, `get_name()`, `is_gpu()==True`,
  `is_retina_only()==True`, `get_shader_path()` resolving to the bundled `.frag`,
  `get_metadata()` via the existing `parse_shader_parameters()`, and a simple CPU-fallback
  `render()` for the windowed VIS module's RETINA-only placeholder view).
- Registered in both places the two existing official GPU visualizers already are:
  `RetinaMeltWindow.visualizers` (`src/toroidamp/ui/fullscreen.py`) and
  `VisualizerModule.visualizers` (`src/toroidamp/ui/modules/visualizer_module.py`), appended at
  the end of each list — every existing index (0–5) is unchanged; only a new index 6 was added.
- **Zero other code needed changing.** Visualizer switching (`_switch_vis_mode`,
  `_cycle_visualizer_mode`), the RETINA-only CPU placeholder (`sync_visualizer_presentation`),
  GPU shader dispatch (`_apply_visualizer_selection`), and per-visualizer session-parameter
  persistence (`visualizer_parameters.get(vis_id, {})`, keyed by `get_id()`) are all already
  fully generic/duck-typed over the visualizer list — confirmed by reading each call site before
  touching anything, not merely assumed.
- **No automatic audio binding.** Because session persistence only ever stores `current_params`
  (BASE values) per visualizer id, never `audio_bindings`, and nothing populates
  `visualizer_parameters["audio_reactive_reference"]` by default, the shader loads with all five
  parameters at their authored defaults and `AUDIO: NONE` — verified directly
  (`test_19b_no_automatic_audio_binding_on_default_load`). At default state it only animates via
  its own native `u_time`-driven motion, exactly as GPU-AUDIO-003 intended.

---

## 11. Human Validation

### TEST A — Real (fixture) shader const promotion

Since no pre-existing repository shader qualifies (§9), use the new demonstration fixture:

```text
Shader path:        user_shaders\test_const_promotion_demo.frag
Promoted consts:    SPEED (default 0.60), ZOOM (default 1.40), GLOW (default 1.80)
Expected LAB cards: 3 float cards, each labeled "<NAME> [CONST]"
                     (STEPS must NOT appear — it's an int loop-bound const)
```

1. Enter RETINA MELT → LAB.
2. LOAD → `user_shaders/test_const_promotion_demo.frag`.
3. Confirm three cards appear: `SPEED [CONST]`, `ZOOM [CONST]`, `GLOW [CONST]` — a shader that
   previously exposed **zero** controls (no `[param:...]`, no `uniform float`) now has three
   meaningful editable parameters.
4. Useful BASE manipulation: drag `ZOOM`'s BASE slider — the coordinate space should visibly
   scale. Drag `SPEED` to `0.0` — the whole field should visibly freeze (only `SPEED` drives
   time in this fixture).
5. Recommended AUDIO source: `GLOW` ← `BASS`, amount **+1.20** — the center glow should pulse
   with the kick.
6. Press `R` (hot reload) — confirm BASE/AUDIO/AMOUNT all survive for `GLOW`.

### TEST B — Official reference cycle

```text
1. Launch ToroidAMP.
2. Enter RETINA MELT (or open the windowed VIS module) and cycle visualizers normally
   (the mode-cycle control / hotkey) until reaching "Audio Reactive Reference (GPU)".
3. Verify it renders correctly — an abstract cyan/pink petal-ring pattern, natively animated.
4. Enter LAB.
5. Verify its five authored parameters appear with their authored defaults and no [CONST]
   badge: u_zoom (1.0), u_speed (1.0), u_glow (1.5), u_twist (1.0), u_detail (6.0).
6. Manually bind one parameter — e.g. u_zoom -> BASS, amount +0.60 — and play music.
7. Verify the bound parameter visibly responds to the music, and the other four remain
   governed purely by their BASE sliders (no automatic binding).
```

---

## 12. Automated Tests

`tests/test_gpu_audio_004.py` — 21 passed, 2 honestly skipped (environment-gated, §8):

| # | Test | Covers |
|---|---|---|
| 1–2 | `test_01_*`, `test_02_*`, `test_02b_*` | Simple safe const discovered; original value → BASE; range always includes the original value, handles zero/negative, never absurdly large |
| 3–5 | `test_03_*`–`test_05_*` | Promoted param drives `current_params`; existing AUDIO binding infrastructure works unmodified on a promoted const; silence resolves exactly to BASE |
| 6 | `test_06_*` | Real fixture file's bytes unchanged after load+reload |
| 7–10 | `test_07_*`–`test_10_*` | Array-dimension rejection (incl. wrapped in a cast); loop-bound rejection; switch/case + preprocessor rejection; dependent-const-expression rejection; non-float consts ignored |
| 11 | `test_11_*`, `test_11b_*` | No `SYSTEM_UNIFORMS` collision; an existing authored uniform always wins over a same-named const elsewhere |
| 12–13 | `test_12_*` (runs), `test_13_*` (skipped) | Hot-reload preservation for a surviving param; pruning for a vanished param (environment-gated) |
| 14 | `test_14_*` (skipped) | Compile-failure rollback (environment-gated) |
| 15–17 | `test_15_*`–`test_17_*` | Explicit `uniform float` discovery unchanged; native `ta*`-authored official shader (`cyber_bloom.frag`) carries zero promoted-const params; AUTO REACT toggle behavior unchanged |
| 18–19 | `test_18_*`, `test_19_*`, `test_19b_*` | Official visualizer registration correct; appears in the cycle exactly once; no automatic audio binding at default load |

Broader regression (GPU-AUDIO-001/002/003/004, GPU-OFFICIAL-001, GPU-PROD-001/001-stabilization/002, VIS-001/002, EXP-GL-001, EXP-VISLAB-001/002/003, run together in one process): **172 passed, 2 skipped, 0 failed.** `tests/test_vis_001.py` and `tests/test_vis_002.py` visualizer-count/ordering/cycling assertions were updated from a stale 5 to the current, intentional 7 (they were already stale at 5 vs. the actual pre-existing 6 before this cut even started — `CyberBloomVisualizer` had been added without updating them; this cut both accounts for that pre-existing gap and adds `AudioReactiveReferenceVisualizer` as index 6, fixing both in the same pass rather than hiding either behind a skip).

---

## 13. Known Limitations / Deferred Level D+ Work

Explicitly out of scope for this cut, per the mission's Level D+ boundary — none of the
following were implemented:

- Arbitrary local-variable promotion.
- Magic-number extraction.
- A general AST/GLSL parser (this remains regex-based, by design — narrow and auditable).
- Semantic inference from variable names (e.g. guessing that `SPEED` should default to a
  time-multiplier range different from the generic policy).
- Automatic audio-source assignment.
- AI-assisted parameter selection.
- Shader/audio association presets.
- Source rewriting on disk (the absolute preservation rule holds throughout).
- `vec2`/`vec3`/`vec4`/`int`/`bool`/matrix/macro/function-argument promotion.
- Loop restructuring.

Additional limitations specific to this implementation:

- **No live-GL-context validation in this development environment** — two automated tests
  (pruning-on-vanish, compile-failure rollback) are honestly skipped rather than faked; both
  behaviors were traced manually against the actual `gpu_canvas.py` source during the Phase 0
  audit and are structurally unchanged, pre-existing GPU-AUDIO-003 logic. Confirming them with
  a live GPU-backed session remains a human validation item, not an automated one.
- **Real-world corpus evidence is currently zero-positive** — every external shader already in
  this repository happens to avoid the target grammar entirely (§9). The mechanism is
  demonstrably correct against both synthetic unit tests and a realistic new fixture, but no
  pre-existing "real" shader in this repo was actually improved by it. Whether this feature
  earns its keep against genuine, unmodified third-party Shadertoy content in the wild remains
  unproven — worth revisiting once a broader shader corpus is available.
- **Tiny-magnitude constants get a coarse relative range** (§6) — accepted tradeoff of a simple,
  generic policy.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

This is an experimental extension of an already-CLOSED cut (GPU-AUDIO-003), within the existing
ACTIVE Production Cut 3 phase. No phase changed, no decision gate closed or reopened, no
architectural boundary moved — the new mechanism is additive and self-contained inside the
existing shader-compilation pipeline. Operational baseline remains STABLE.
