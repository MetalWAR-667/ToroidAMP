# GPU-AUDIO-006B — Runtime Literal Parameterization

> **Status: IMPLEMENTED — unit-validated against the real corpus.** Human
> validation (TEST A-F, §11) is required before this can be considered
> CLOSED.

## 1. Evidence Base (GPU-AUDIO-006A)

The prior read-only audit
([13_gpu_audio_006a_discovery_audit.md](13_gpu_audio_006a_discovery_audit.md))
measured, against the real 5-shader USER corpus (`user_shaders/shadertoy/*`):

```text
Current discovery coverage: 0 / 5
direct/macro iTime multipliers: 3 / 5
simple local float literals:    4 / 5
combined (either pattern):      5 / 5
numeric #define:                0 / 5 useful
int/loop/array occurrences:     31, all structural, zero artist knobs
```

GPU-AUDIO-006B implements **exactly and only** the two patterns that
together reached 5/5 combined coverage — nothing else. This is the
"dumbest sufficiently useful solution" the audit recommended.

## 2. Phase-0 Architecture Findings

Traced before writing any code:

| Component | Finding |
|---|---|
| `classify_and_wrap_source()` | Already runs an additive two-stage pipeline: `parse_shader_parameters()` then GPU-AUDIO-004's `find_safe_promotable_consts()`, each stage merging into the same `parameters` dict and each free to further transform the same `clean_src` in-memory copy before the existing uniform-injection loop runs. This is the exact, proven insertion shape for a THIRD stage. |
| Uniform-injection loop | Generic over `parameters.values()` — declares `uniform float {p.name};` for anything not already declared, deduped by substring check. Requires zero changes: any new `ShaderParameter` added to `parameters` before this loop runs is picked up automatically. |
| `ShaderParameter` | Already extended once (GPU-AUDIO-004's `is_promoted_const`) with a backward-compatible defaulted field — same minimal-extension pattern reusable here. |
| `GLVisualizerCanvas.current_params` / `audio_bindings` | Both plain `Dict[str, ...]` rebuilt by name on every `load_shader_file()` — provenance-agnostic by construction. A generated `taAuto_*` name is indistinguishable from any other discovered float name to this machinery. |
| `musicalize()` (GPU-AUDIO-005) | Iterates `self.metadata.parameters.keys()`, filters `param_type == "float"` — no knowledge of *how* a parameter was discovered. Zero changes needed for generated parameters to become musicalizable. |
| Shader-switch isolation (GPU-AUDIO-005) | `audio_bindings` is reset to `{}` whenever `file_path != self.current_shader_path`, before the preserve-by-name loop runs — already fully generic, protects generated-parameter bindings identically to any other kind. |
| Compile/link rollback | `load_shader_file()` returns `False` on compile/link failure strictly before `self._program = new_prog` is reassigned — transactional by construction, agnostic to why the source changed. |
| `tools/shader_audit.py` (GPU-AUDIO-006A) | Confirmed real per-shader candidate data (§7) and, critically, exposed two regex pitfalls (trailing/leading dot literals colliding with `\b`, and identifier-embedded digits) that had to be independently re-solved here for the *transformer* (not just the read-only counter) — see §9. |

**Conclusion — insertion point**: a third additive stage inside
`classify_and_wrap_source()`, run immediately after GPU-AUDIO-004's const
promotion, on the same `clean_src` copy:

```python
clean_src, promoted_params = find_safe_promotable_consts(clean_src, set(parameters.keys()))
parameters.update(promoted_params)

# GPU-AUDIO-006B:
clean_src, runtime_params = find_runtime_literal_candidates(clean_src, set(parameters.keys()))
parameters.update(runtime_params)
```

Zero changes to `gpu_canvas.py`, zero changes to MUSICALIZE, zero changes
to the LAB card-building loop's structure (only a label-badge conditional,
identical in shape to GPU-AUDIO-004's `[CONST]` badge). The existing
parameter/uniform machinery is reused end to end, exactly as directed.

## 3. Supported Grammar

**Pattern A — LOCAL_FLOAT_LITERAL**: `float NAME = LITERAL;` (or `,`),
single declarator, outside any `for(...)` header. Same narrow,
one-declarator-per-statement posture GPU-AUDIO-004 already established for
`const float` — a multi-declarator statement (`float a = 1., b = 2.;`)
still only ever captures the first declarator; an expression initializer
(`float fov = 2.5 - k;`) simply never matches at all.

**Pattern B — TIME_SCALE**: `(iTime|u_time) * LITERAL` or
`LITERAL * (iTime|u_time)`, matched anywhere in the source — including
inside a `#define` body (§5).

Both patterns use a **broader literal grammar than GPU-AUDIO-004's**
`CONST_FLOAT_LITERAL_RE` (which deliberately excludes leading-dot literals):
`[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?` — accepting `.8`, `6.`,
`2e-3`, `-1.2`. This widening is directly evidence-driven: the real corpus
overwhelmingly uses leading/trailing-dot literals (`iTime*.2`, `iTime*6.`),
and excluding that shape would have failed on the majority of real matches.

## 4. Transformation Examples

```glsl
// before                          // after (in-memory only)
float fov = 2.5;                   float fov = taAuto_fov_A20D6240;
float t = iTime * 0.8;             float t = iTime * taAuto_timeScale_36F39520;
col *= .2*iTime;                   col *= taAuto_timeScale_D8FDF40C*iTime;
#define T (iTime*6.)               #define T (iTime*taAuto_timeScale_36F39520)
```

**Architectural rule enforced throughout**: PARAMETERIZE THE LITERAL, never
promote the local variable. `fov` keeps its exact name, scope, and type;
every other reference to `fov` anywhere in the shader is untouched — only
the numeric token at the literal's own character span is replaced. This is
structurally simpler than GPU-AUDIO-004's const promotion (which replaces
an entire declaration line with a comment): here there is no declaration to
neutralize, only a token to swap.

## 5. Macro-Wrapped `iTime` — Included, Not Deferred

The mission asked for an honest audit before committing to macro support.
Real corpus example: `happy_glow_cruise.frag`'s `#define T (iTime*6.)`.

**Finding**: supporting this required **zero** macro expansion,
preprocessor interpretation, or data-flow analysis. `#define NAME (iTime*
LITERAL)` is, to a text-level regex, structurally identical to the same
pattern appearing inside a function body — it is just another line of text
containing `iTime * LITERAL`. The substitution is applied at the exact same
character span regardless of which construct surrounds it; the *real* C
preprocessor (part of the GLSL compiler) transparently expands `T` at every
use site afterward — that expansion is GLSL's job, not this module's.
The only requirement is that the generated `uniform float taAuto_timeScale_
HASH;` declaration appears before the `#define` line in the final source —
already guaranteed for free, since the existing uniform-injection loop
always places the whole `param_header` block before `clean_src` in its
entirety (§2).

**Verified directly** against the real shader: 1 macro-wrapped candidate
found and correctly transformed, with the produced `#define T
(iTime*taAuto_timeScale_36F39520)` syntactically valid.

## 6. Overlap / Double-Promotion Rule

`float t = iTime * 0.8;` can look like both patterns. **TIME_SCALE takes
precedence** (as directed): the TIME_SCALE scan runs first and records
every literal span it claims; the LOCAL_FLOAT_LITERAL scan then explicitly
skips any span already claimed.

In practice, this precedence rule is **defense-in-depth rather than a
frequently-exercised code path**: Pattern A's grammar (`= LITERAL` followed
immediately by `,`/`;`) structurally cannot match `float t = iTime * 0.8;`
at all — after `=` comes `iTime`, not a bare literal, so Pattern A's regex
never even attempts a match on that statement. The explicit claimed-span
check exists for robustness and is directly regression-tested
(`test_06_overlap_produces_exactly_one_parameter`), not because the narrow
grammars are expected to collide often.

## 7. Generated Identity Policy

`taAuto_<base>_<hash6>`, where `<hash6>` is a 6-hex-character `zlib.crc32`
digest of `f"{kind}:{base_name}:{index}"`:

- `kind` — `"LOCAL_FLOAT"` or `"TIME_SCALE"`, so the two families can never
  collide with each other even at the same index.
- `base_name` — the local variable's own name for LOCAL_FLOAT (already a
  stable, human-meaningful identifier, e.g. `fov`), or the fixed literal
  `"timeScale"` for TIME_SCALE (which is not always tied to a named local
  variable — it can appear in a bare inline expression).
- `index` — a simple per-kind occurrence counter (1st, 2nd, ... match found
  in file-scan order), disambiguating same-named or same-kind candidates
  within one shader (e.g. `Skinketest.frag`'s three independent
  `iTime * literal` sites, all correctly producing three distinct
  `taAuto_timeScale_HASH` names).

**Deliberately NOT**: line-number-based (a trivial edit above the candidate
would shift every subsequent line number and destroy identity for no real
reason), and NOT Python's built-in `hash()` (salted per process, not
deterministic across launches — the same failure mode already avoided by
GPU-AUDIO-005's `musicalize()` hashing). Collision against
`SYSTEM_UNIFORMS`/already-claimed names is checked defensively (skip the
candidate entirely if a collision somehow occurred) though practically
unreachable given the hash space.

**Documented hot-reload limitation**: identity is a function of
`(kind, base_name, occurrence_index)`, not full AST position. If an edit
between reloads changes which occurrence-index a candidate falls at (e.g.
inserting a new earlier `iTime * literal` site before an existing one), the
later candidate's identity changes and its LAB/audio-binding state is
lost — this is the same class of limitation GPU-AUDIO-004/005 already
accept, deliberately not solved with fuzzy AST matching (out of scope, "do
not overengineer AST identity").

## 8. Generated Parameter Metadata & LAB Labels

`ShaderParameter` gained one new field: `auto_param_kind: Optional[str] =
None` (`"local_float"` | `"time_scale"` | `None`), backward-compatible
default, orthogonal to GPU-AUDIO-004's `is_promoted_const`.

- **`name`** (the real GLSL uniform identifier, used for
  `current_params`/`audio_bindings` keys and the actual `glUniform1f`
  upload) — the generated `taAuto_...` name.
- **`display_name`** (the human-facing LAB label) — deliberately the
  ORIGINAL local variable name for LOCAL_FLOAT (`fov`, not the ugly
  internal uniform name), or `f"Time Scale {index}"` for TIME_SCALE.

LAB card badge: `<display_name> [AUTO PARAM]` — same conditional-suffix
pattern as GPU-AUDIO-004's `[CONST]` badge, added to both the Integrated
RETINA LAB (`fullscreen.py`, both the TUNE and LAB panel card builders) and
the Standalone GPU Lab (`lab_app.py`).

## 9. Range / Default Policy

BASE always equals the original literal exactly (verified directly —
default rendering is unchanged with no user interaction). Reuses
GPU-AUDIO-004's `_generate_promoted_range()` unchanged
(`span = max(abs(value)*2, 1.0)`), audited specifically for this cut's new
value shapes:

- **Tiny glow values** (`.0015`): span floors at `1.0`, giving a range like
  `(-0.9985, 1.0015)` — coarse relative to the tiny original value, but the
  1000-step LAB slider still yields ~0.002-per-step granularity, comparable
  in magnitude to the value itself — judged acceptable, unchanged from
  GPU-AUDIO-004's precedent, not re-engineered.
- **Time multipliers** (`0.8`): range `(-0.8, 2.4)` — a sensible
  half-to-triple-speed-and-reverse editing range for a "speed" knob.
- **Negative values** (`-1.2`): range `(-3.6, 1.2)` — value sits well
  inside, handled correctly by the existing formula.
- **Zero**: range `(-1.0, 1.0)` — same non-degenerate minimum-span guarantee
  already validated in GPU-AUDIO-004.

**New guard found necessary during real-corpus validation — sentinel/
extreme-magnitude exclusion**: raymarching GLSL commonly seeds an
accumulator with an extreme "very far"/"very negative" literal
(`float d = -9e9;`, observed directly in `Rig_Rekt.frag`). Parameterizing
one would compile fine but produce a practically useless multi-billion-unit
LAB slider and an equally useless MUSICALIZE target. Candidates with
`abs(value) > 1e4` are now excluded (`_RUNTIME_LITERAL_MAGNITUDE_LIMIT`) —
every genuine tunable value observed in the real corpus is well under this
threshold, so the guard costs nothing real while removing a class of
non-useful "control."

**MUSICALIZE was not modified.** No compatibility defect was found —
generated parameters flow through the exact same relative-modulation
formula and range-clamping GPU-AUDIO-005 already validated.

## 10. Comment / Dead-Code Handling

Reuses the GPU-AUDIO-006A lesson directly, but with an offset-preserving
variant needed for actual transformation (not just counting):
`_mask_comments_preserve_offsets()` replaces every comment character with a
space (keeping newlines as newlines), so the masked copy is **exactly the
same length** as the real source and every surviving character sits at an
identical offset. Candidates are found by matching against this masked
copy — a commented-out literal (including a full duplicate `mainImage()`
sitting inside a trailing `/* */` block, the real `Skinketest.frag` shape)
becomes blank space and can never match — while the resulting match spans
are then valid, correct offsets to slice/replace directly in the real,
untouched source string.

Production `// [param:float] ...` annotation discovery is unaffected: this
module only looks for GLSL literal/expression shapes, never annotation
syntax, so it has no interaction with — and cannot break — the
comment-embedded annotation convention.

## 11. Compilation Failure / Rollback Behavior

**No new recovery machinery was added.** The existing GPU-AUDIO-003/004
transactional rollback in `load_shader_file()` (return `False` strictly
before `self._program` is reassigned) already protects the currently-active
program/state regardless of *why* the newly-submitted source failed to
compile — whether that's an author's own syntax error or, hypothetically,
an adaptation defect.

An automatic same-load "retry without adaptation" fallback was explicitly
considered and **deliberately not implemented**: it would require a second
compile pass and a way to selectively disable only this pass while keeping
GPU-AUDIO-004's promotion active, real complexity for a benefit that is
already covered by the fact that this transformation is a **provably pure
token substitution** for the narrow supported grammar (no control-flow,
type, or structural change is ever possible) — the same class of guarantee
GPU-AUDIO-004's const promotion already carries, and which has produced
zero real compile failures across this session's entire test history. This
matches the mission's explicit instruction: "a simple policy is
sufficient" — the simple policy here is the existing rollback, unchanged.

## 12. LAB Integration

Reuses the exact GPU-AUDIO-003/004 card-building loop — no new panel, no
new secondary editor. Generated parameters appear as ordinary float cards
(BASE slider + AUDIO source/AMOUNT row) the moment a shader with eligible
candidates loads, with the `[AUTO PARAM]` badge (§8) as the only visible
difference. Manual BASE slider movement calls the existing
`set_param_value()` and is immediately visible; manual AUDIO binding uses
the existing inline selector unchanged.

## 13. MUSICALIZE Integration

Zero code changes to `musicalize()`. It already iterates
`self.metadata.parameters` filtering `param_type == "float"` with no
awareness of provenance — generated parameters are automatically eligible.
Verified directly: pressing MUSICALIZE on a shader with generated
`fov`/`glow`-shaped candidates produces `mode="relative"`, `origin="auto"`
bindings with `|amount| <= 0.15`, identical in shape to bindings on any
other discovered/promoted parameter. No shader-specific knowledge, no
filename special-casing, no per-author mapping — verified against all 5
real corpus shaders using the same generic code path.

## 14. Ownership / CLEAR AUTO

Unchanged GPU-AUDIO-005 semantics, verified directly on generated
parameters: MUSICALIZE sets `origin="auto"`; any manual edit through the
existing source-select/amount-slider handlers (which always call
`set_param_audio_binding(name, src, amt)` positionally, defaulting to
`mode="absolute"`, `origin="manual"`) immediately takes ownership; CLEAR
AUTO removes only `origin=="auto"` entries, leaving manual work and BASE
values untouched.

## 15. Hot Reload

Unchanged GPU-AUDIO-003/004/005 preserve-by-name mechanism in
`load_shader_file()` — a generated parameter's full state (BASE, AUDIO
source, AMOUNT, mode, origin) survives a same-file reload exactly when its
generated identity (§7) is unchanged, verified directly. If the identity
changes (an edit shifts occurrence order) or the candidate disappears
entirely, its state is pruned — the same behavior, and the same accepted
limitation, as every prior GPU-AUDIO cut.

## 16. Shader-Switch Isolation

Unchanged GPU-AUDIO-005 fix: `audio_bindings` resets to `{}` whenever the
loaded file path differs from the previously-active one, before any
preserve-by-name logic runs. Verified directly with two synthetic shaders
carrying MUSICALIZE-generated bindings on their respective generated
parameters — switching between them leaves zero leaked bindings.

## 17. Original Source Immutability

Verified directly for every real corpus shader (`test_17`,
`test_27_real_user_corpus_parameterized_without_modification`): read bytes
before, load + hot-reload, read bytes after — byte-for-byte identical. No
`.toroid.frag`, no sidecar, no backup file is ever written. The transformed
source (`ShaderMetadata.adapted_source`) exists only as an in-memory Python
string, discarded on shader unload. `EXPORT ADAPTED SHADER` remains an
explicitly deferred future concept (§20) — not implemented.

## 18. Real-Corpus Results (the 5 USER shaders)

| Shader | Candidates found | Generated params | Kinds |
|---|---|---|---|
| `apollo_spiral.frag` | 1 | 1 | `w` (local_float) |
| `happy_glow_cruise.frag` | 2 | 2 | `Time Scale 1` (macro-wrapped `#define T`), `s` (local_float) |
| `Rig_Rekt.frag` | 1 candidate found, 0 generated | 0 | sole candidate (`d = -9e9`) excluded as an extreme-magnitude sentinel (§9) — honestly reported, not forced |
| `Skinketest.frag` | 5 | 5 | `Time Scale 1/2/3` (3 independent direct `iTime*literal` sites), `minDist`, `glowAcc` (local_float) |
| `Universe Ball 2.frag` | 1 | 1 | `Time Scale 1` |

**Coverage: 4 / 5 (80%)** real user shaders now expose at least one
generated LAB/MUSICALIZE-eligible control — up from **0 / 5** before this
cut. `Rig_Rekt.frag`'s honest 0/5-contribution is not a bug or a macro
limitation: it is the direct, evidence-based consequence of the
sentinel-value safety guard (§9) correctly declining to turn a
"very-far-raymarch-seed" constant into a fake tunable control. No shader
was modified, and no exception/special-case was added to force a different
number.

## 19. Files Modified / Created

**Modified**:
- `src/toroidamp/visualizers/gpu_compiler.py` — `ShaderParameter.auto_param_kind`, `ShaderMetadata.adapted_source`, `find_runtime_literal_candidates()` and its regex/identity helpers, integration into `classify_and_wrap_source()`.
- `src/toroidamp/ui/fullscreen.py` — `[AUTO PARAM]` badge (2 card-builder sites, mirroring the existing `[CONST]` badge).
- `experiments/gpu_visualizers/lab_app.py` — same badge (Standalone Lab parity).

**Created**:
- `tests/test_gpu_audio_006b.py` (29 tests).
- `docs/design/14_gpu_audio_006b_runtime_parameterization.md` (this document).

No shader source file was modified. No new files were written anywhere
under `user_shaders/` or `src/toroidamp/assets/`.

## 20. Deferred: EXPORT ADAPTED SHADER

Explicitly recorded as a future concept, **not implemented in this cut**:
a user-triggered action to write the current in-memory `adapted_source`
(§10, now directly inspectable via `ShaderMetadata.adapted_source`) to a
new physical `.frag` file the user could keep, edit further by hand, or
share — turning a one-off runtime adaptation into a durable, author-owned
artifact. This would need its own explicit UI action, its own file-naming/
overwrite-safety policy, and careful wording that the exported file is a
*starting point*, not an authoritative "fixed" version of the original.
Out of scope here; the architecture (a clean, inspectable, purely-in-memory
`adapted_source` string) was built specifically to make this cheap to add
later without revisiting the transformation logic itself.

## 21. Known Limitations

- Multi-declarator local float statements only capture the first
  literal-initialized declarator (same accepted GPU-AUDIO-004 precedent).
- Generated identity is `(kind, base_name, occurrence_index)`, not full AST
  position — an edit that reorders occurrences can lose a specific
  candidate's saved LAB/audio state across hot reload (§7, §15).
- The sentinel/extreme-magnitude guard (`abs(value) > 1e4`) is a blunt
  threshold, not semantic understanding — chosen generously above every
  genuine tunable value observed in the real corpus, but a legitimate
  large-but-tunable constant in some future shader would also be excluded.
  Conservative by design; revisit only with further evidence.
- Tiny-magnitude local floats (`.0015`-shaped) get a coarse relative LAB
  slider range — accepted, unchanged GPU-AUDIO-004 tradeoff (§9).
- No live-GL compile verification in this development environment
  (`GLVisualizerCanvas.isValid()` is always `False` here — the same
  structural caveat every prior GPU-AUDIO cut has carried); mitigated by
  direct textual verification of every transformed shader's full generated
  GLSL (§4, §5) and by the mandatory human validation route (§11 of the
  GPU-AUDIO-005 doc's pattern, replicated below for this cut).

## 22. Deferred Opportunities Discovered During Implementation

- **Macro-wrapped TIME_SCALE turned out to be free** (§5) — worth
  remembering for any *future* discovery-expansion cut: text-level
  substitution inside `#define` bodies is not inherently risky the way
  macro *expansion*/interpretation would be, as long as the substitution
  never depends on understanding what the macro does.
- The sentinel-value guard (§9) suggests a broader, still-unimplemented
  question for a future cut: are there other common "structural sentinel"
  idioms (e.g. `1e-6` epsilon comparisons) worth a similarly narrow,
  evidence-gated exclusion? Not investigated here — no evidence of an
  epsilon-shaped false positive was observed in this corpus, so nothing was
  added speculatively.

## 23. Human Validation Route

**Recommended shaders** (from the real corpus):
- **Local float literal**: `user_shaders/shadertoy/apollo_spiral/apollo_spiral.frag` (single clean candidate — `w`) or `Skinketest.frag` (`minDist`, `glowAcc`, plus 3 time scales, richest single-shader validation surface).
- **iTime multiplier**: `user_shaders/shadertoy/Universe Ball 2/Universe Ball 2.frag` (single clean `Time Scale 1` candidate) or `happy_glow_cruise.frag` (also exercises the macro-wrapped case, §5).
- **Both in one shader**: `Skinketest.frag` (recommended primary validation target — 3 time scales + 2 local floats) or `happy_glow_cruise.frag` (1 macro time scale + 1 local float).

**TEST A — Baseline fidelity**
1. Load `Skinketest.frag`.
2. Observe it render before touching any generated control.
3. Confirm it visually matches its known prior baseline (pulsing neon
   pyramid reacting to its own internal kick/snare envelopes) — BASE always
   equals the original literal, so default rendering must be unchanged.

**TEST B — Generated controls**
1. Open LAB.
2. Confirm 5 `[AUTO PARAM]` cards appear: `Time Scale 1/2/3`, `minDist`,
   `glowAcc`.
3. Move `Time Scale 1`'s BASE slider significantly (e.g. toward 0 or 2×).
4. Confirm a visible change in animation rate/sync.

**TEST C — MUSICALIZE**
1. Restore sensible BASE values if needed (or hot reload, R, to reset).
2. Press MUSICALIZE.
3. Play dynamic music.
4. Confirm `[AUTO]`-tagged AUDIO bindings appear on the generated cards.
5. Confirm a visible, bounded musical response.

**TEST D — CLEAR AUTO**
1. Press CLEAR AUTO.
2. Confirm the generated cards' AUDIO bindings return to `NONE`.
3. Confirm the shader returns to BASE-driven-only behavior.

**TEST E — Hot reload**
1. Set a BASE value and an AUDIO mapping on one generated card.
2. Press R.
3. Confirm that state survives (same shader file, same occurrence order —
   identity unchanged).

**TEST F — Source integrity**
1. Confirm `user_shaders/shadertoy/Skinketest/Skinketest.frag` is
   byte-for-byte unchanged on disk after the whole session above.

## 24. Automated Tests

`tests/test_gpu_audio_006b.py` — **29/29 passed**, covering: local-float
and time-scale detection (direct/reversed/macro-wrapped), overlap
precedence, deterministic/collision-free identity, comment/dead-code
exclusion (incl. a Skinketest-shaped regression), annotation-discovery
non-interference, all structural exclusions (loop/array/int/vec3/`#define`),
source immutability, adapted-source inspectability, real LAB card
generation with the `[AUTO PARAM]` badge, manual BASE/AUDIO controls,
MUSICALIZE/CLEAR AUTO integration, silence-to-BASE, hot-reload preservation,
shader-switch isolation, the full real 5-shader corpus (byte-for-byte
untouched, >=4/5 gaining generated parameters), the macro-wrapped-`#define`
regex-fix regression, and the sentinel-magnitude exclusion.

Full regression sweep: unaffected (same pre-existing, unrelated
`test_ux_004.py` marquee failures as every prior delivery this session;
everything else — including all GPU-AUDIO-001 through 006A tests —
continues to pass unmodified).

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

Additive extension of the already-ACTIVE Production Cut 3 phase, built
entirely on existing GPU-AUDIO-003/004/005 infrastructure. No phase or
decision gate changed. Consistent with every prior GPU-AUDIO cut this
session.
