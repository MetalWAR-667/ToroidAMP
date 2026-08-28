# GPU-AUDIO-006A — Real-World Shader Parameter Discovery Audit

> **Status: OBSERVATION CUT — COMPLETE.** This is read-only instrumentation
> and a data-gathering exercise, not a promotion/MUSICALIZE change. Nothing
> in `src/toroidamp/visualizers/gpu_compiler.py`, `gpu_canvas.py`, or the
> MUSICALIZE algorithm was touched. No shader source file was modified.

## 1. Motivation

GPU-AUDIO-005's human validation revealed that **0 of the 5 real user
shaders** currently loaded from `user_shaders/shadertoy/` benefit at all
from ToroidAMP's discovery/promotion system (GPU-AUDIO-003's `uniform float`
discovery, GPU-AUDIO-004's `const float` promotion). MUSICALIZE itself was
not suspected — there is simply nothing for it to bind to. Before designing
any expansion, we needed real evidence of *what* real Shadertoy-style
shaders actually use instead of `uniform float`/`const float`, so the next
cut's scope is driven by measured coverage, not speculation.

## 2. Architecture

**Chosen approach: a separate, standalone diagnostic tool** —
[`tools/shader_audit.py`](../../tools/shader_audit.py) — following this
repo's existing convention for developer-only scripts (`tools/bump_version.py`,
`tools/generate_ico.py`), rather than a new `toroidamp.tools` subpackage
inside `src/`. It is never imported by production code and is not exposed in
any UI.

It **reuses the real production parser** for everything already
discoverable/promotable today:

```python
from toroidamp.visualizers.gpu_compiler import (
    parse_shader_parameters,
    find_safe_promotable_consts,
    SYSTEM_UNIFORMS,
)
```

This is deliberate: the audit's "0/5 currently eligible" claim is not a
separate opinion re-implemented by a second parser that could drift from
production — it is the literal output of the same functions
`gpu_canvas.load_shader_file()` calls when a shader is actually loaded.

Everything **not** already supported (the new taxonomy in §3) is
purpose-built audit-only regex scanning, kept structurally identical in
spirit to GPU-AUDIO-004's own conservative posture (narrow grammar first,
explicit exclusion checks, "when uncertain, don't count it as safe") but
implemented independently — it does not touch `gpu_compiler.py` at all, so
there is zero risk of destabilizing production parsing.

Runs with **zero GPU/OpenGL/Qt dependency** — pure text analysis, usable
against arbitrary future downloaded `.frag` files with no application
launch required:

```bash
python tools\shader_audit.py user_shaders
python tools\shader_audit.py user_shaders\shadertoy\rig_rekt\Rig_Rekt.frag
python tools\shader_audit.py user_shaders --json > audit.json
```

## 3. Pattern Taxonomy

| Category | Pattern | Classification |
|---|---|---|
| A | `uniform float` / annotated `[param:float]` / safe `const float NAME = LITERAL;` | `CURRENT` (already discoverable/promotable today) |
| B | Numeric `#define NAME LITERAL` | `POSSIBLE_CANDIDATE` |
| B′ | Macro-wrapped time multiplier `#define NAME (iTime*LITERAL)` | `HIGH_VALUE_SAFE_CANDIDATE` (reported separately from B) |
| C | Local `float NAME = LITERAL;`, outside any `for(...)` header | `HIGH_VALUE_SAFE_CANDIDATE` |
| D | Direct `iTime * LITERAL` / `LITERAL * iTime` (or `u_time`) | `HIGH_VALUE_SAFE_CANDIDATE` |
| E | Literal `vecN(...)` constructors (all args bare numeric literals) | `POSSIBLE_CANDIDATE` if heuristically RGB-shaped (3-4 components, all in ~0..1), else `UNKNOWN` |
| F | Array dimensions/indices, loop bounds, `switch/case` labels | `STRUCTURAL_UNSAFE` (never a candidate) |
| G | Everything else — generic inline scalar literals | Aggregate count + a handful of representative examples, heuristically tagged (glow/exposure and coordinate/geometry context -> `POSSIBLE_CANDIDATE`; else `UNKNOWN`) |

Category A reuses the exact production parser (§2). Categories B-G are
audit-only. **Nothing in categories B-G is promoted or written anywhere** —
they exist purely to be counted and reported.

## 4. Comment / Dead-Code Handling

A single stripping pass (`strip_comments()`) removes `//` line comments and
`/* ... */` block comments, replacing each match with an equal number of
newlines — so every surviving line number still matches the original file,
while none of the comment's content (including an entire dead
`mainImage()` implementation sitting inside a trailing block comment, which
the real `Skinketest.frag` shader in this corpus actually contains) is ever
counted.

**One deliberate exception**: category A (§3) is run against the
**uncomment-stripped** text — exactly the text real production parses
(`raw_source.strip()`, comments intact) — because the `// [param:float]
NAME: Label = ...` annotation syntax *itself lives inside a `//` comment by
design*. Stripping comments first would make this the one category that
could never detect an annotated parameter at all. This is not a
special-casing invented for convenience: it is required for category A's
counts to genuinely equal what production discovers. (This also means
category A, like real production, cannot distinguish a live annotation from
one sitting inside dead/commented-out code — a narrow, pre-existing
production characteristic this audit surfaces but does not attempt to fix;
see §9.)

## 5. Corpus Audited

| Tag | Meaning | Count | Files |
|---|---|---|---|
| **USER** | Real, unmodified Shadertoy imports under `user_shaders/shadertoy/` | **5** | `apollo_spiral.frag`, `happy_glow_cruise.frag`, `Rig_Rekt.frag`, `Skinketest.frag`, `Universe Ball 2.frag` |
| TEST_FIXTURE | Purpose-built ToroidAMP test/validation shaders (incl. `apollo_spiral_toroidamp_test.frag`, a ToroidAMP-adapted variant — its name and 4 real `uniform float` params mark it as an adapted fixture, not an unmodified pull) | 12 | `user_shaders/test_*.frag`, `apollo_spiral_toroidamp_test.frag` |
| OFFICIAL | Bundled production reference shaders | 4 | `src/toroidamp/assets/official_shaders/*.frag` |
| EXPERIMENTAL | Standalone GPU Lab experiment shaders | 3 | `experiments/gpu_visualizers/shaders/*.frag` |

Per the mission's explicit instruction, **fixtures do not inflate the USER
statistics** — `apollo_spiral_toroidamp_test.frag` already has 4 real
`uniform float` parameters (it would have made the corpus "1/6 benefiting"
instead of the honest "0/5"), so it is auto-classified `TEST_FIXTURE`, not
`USER`, and excluded from all USER-corpus aggregates.

## 6. Per-User-Shader Findings

| Shader | Lines | iTime× (direct+macro) | local float=lit | numeric #define | probable color vec | structural (array/loop/case) | inline literals (total) |
|---|---|---|---|---|---|---|---|
| `apollo_spiral.frag` | 53 | 0 | 1 (`w = 4.`) | 0 | 0 | 3 | 12 |
| `happy_glow_cruise.frag` | 63 | 2 (1 direct + 1 macro `T`) | 1 (`s = 4.` — from `s=4., d=9e9`) | 0 | 0 | 1 | 35 |
| `Rig_Rekt.frag` | 56 | 0 | 1 (`d = -9e9` — from `d=-9e9, i=1e1`) | 0 | 0 | 5 | 19 |
| `Skinketest.frag` | 169 | 3 (all direct) | 2 (`minDist`, `glowAcc`) | 0 | 3 (all in one `vec3(...)`-mix line + one background tint) | 16 | 58 |
| `Universe Ball 2.frag` | 33 | 1 (direct, `t=iTime*.2`) | 0† | 0 | 0 | 6 | 20 |

† `Universe Ball 2.frag`'s only local declaration with a literal initializer
is `t=iTime*.2` inside a multi-declarator statement — already counted under
the time-multiplier column; it has no *other* simple local float literal.

**Why `apollo_spiral.frag` and `Rig_Rekt.frag` show 0 direct iTime
multipliers**: both write `t = iTime;` completely unscaled (no literal
multiplier at all) — direct multiplier detection genuinely finds nothing to
report there, honestly.

**Representative examples** (full listings for all 5 shaders were generated
via `python tools\shader_audit.py user_shaders\shadertoy`; excerpted here):

```text
Skinketest.frag, line 25:
    float t = iTime * 0.8;
    HIGH_VALUE_SAFE_CANDIDATE — direct scalar multiplier on the time uniform

happy_glow_cruise.frag, line 4:
    #define T (iTime*6.)
    HIGH_VALUE_SAFE_CANDIDATE — macro-wrapped direct time multiplier

apollo_spiral.frag, line 6:
    float w = 4.;
    HIGH_VALUE_SAFE_CANDIDATE — local float initialized directly from a literal

Skinketest.frag, line 66:
    vec3 glowColor = mix(vec3(1.0, 0.4, 0.1), vec3(0.2, 0.8, 1.0), snare);
    POSSIBLE_CANDIDATE — probable color (RGB, all components in ~0..1)

Skinketest.frag, line 52:
    int edges[16] = int[16](0,1, 1,2, 2,3, 3,0, 0,4, 1,4, 2,4, 3,4);
    STRUCTURAL_UNSAFE — array dimension or index literal
```

## 7. Corpus Summary (REAL USER SHADERS)

```text
REAL USER SHADERS AUDITED: 5

Current discovery coverage:
    shaders with >=1 current eligible parameter: 0 / 5

Potential coverage if supporting:
    direct iTime multipliers (incl. macro-wrapped):  3 / 5
    simple local float literals:                     4 / 5
    numeric #define (plain, non-time):                0 / 5
    probable color vecN literals:                     1 / 5

Combined coverage — (iTime multiplier) OR (local float literal):
    5 / 5   <-- full corpus coverage from just these two patterns

Structural/unsafe occurrences across USER corpus: 31
    (every single one inspected is an array dimension/index, a loop bound,
     or — never observed in this corpus — a switch/case label; zero were
     found to be an artist-controlled "knob" misclassified as structural)
```

## 8. Answers to Q1-Q10

**Q1 — Why did the 5 user shaders produce no useful MUSICALIZE behavior?**
None declares any `uniform float`, `[param:float]` annotation, or
safely-promotable `const float NAME = LITERAL;` — the only three shapes
GPU-AUDIO-003/004 currently discover. All 5 are dense, "golfed"
demoscene-style Shadertoy imports whose artist-controlled values are baked
directly into the code as inline literals, local-variable literals, or
(once) a macro-wrapped expression — never as an explicit named uniform.

**Q2 — Where are their artist-controlled numeric values actually encoded?**
Predominantly: (a) direct or macro-wrapped `iTime * literal` scalar
multipliers, driving animation rate — 3/5 shaders; (b) local `float NAME =
literal;` declarations, mostly geometry/lighting constants — 4/5 shaders;
(c) a large volume of genuinely anonymous inline literals scattered directly
in expressions (12-58 per file) with no name at all; (d) a handful of
pure-literal `vec3` color constructors — 1/5 shaders; (e) essentially never
through `#define` as a plain numeric knob.

**Q3 — How many would gain a candidate from direct iTime multipliers?**
3/5 (`happy_glow_cruise`, `Skinketest`, `Universe Ball 2`). The other two
(`apollo_spiral`, `Rig_Rekt`) write `t = iTime;` completely unscaled, so
there is genuinely nothing there to promote.

**Q4 — How many would gain candidates from `float NAME = LITERAL;`
promotion?** 4/5 (all except `Universe Ball 2`, whose only literal-driven
local declaration is the time multiplier already counted under Q3).

**Q5 — How many rely heavily on numeric `#define`?** Effectively none.
0/5 have a *plain* numeric `#define`. The only numeric-ish `#define` in the
whole corpus (`happy_glow_cruise`'s `#define T (iTime*6.)`) is a time
multiplier, already counted under Q3 — not an independent pattern worth its
own promotion path.

**Q6 — How common are probable RGB `vec3` literals?** Rare and narrow: only
1/5 (`Skinketest`) has any (3 occurrences, all genuinely color-shaped and
used directly as color-mix targets). The other 4 shaders' literal
`vec3`/`vec4` constructors are all structural/geometric (e.g. the recurring
`vec4(0,33,11,0)` fake-rotation-matrix offset trick, or `vec3(6,4,2)` used
as a per-channel frequency multiplier, not a color).

**Q7 — Does the evidence justify touching `int` at all?** No. All 31
structural int/numeric occurrences found across the USER corpus are array
dimensions, indices, or loop bounds — zero were found to be an
artist-controlled "knob" misclassified as structural. The evidence actively
argues against touching `int`.

**Q8 — What minimal combination gives the best coverage?** Direct/macro
`iTime` multipliers **plus** simple local `float NAME = LITERAL;`
literals — together they cover **5/5 (100%)** of the real corpus. No other
pattern, and no larger combination, is needed to reach full coverage. This
is the "dumbest sufficiently useful solution" the mission asked for.

**Q9 — Can these two patterns be detected generically for a future
downloaded shader, with no shader-specific rules?** Yes. Both are pure
syntactic regex shapes with zero per-shader knowledge —
`(?:iTime|u_time)\s*\*\s*NUMBER` / `NUMBER\s*\*\s*(?:iTime|u_time)`, and
`\bfloat\s+NAME\s*=\s*NUMBER\s*[,;]` outside a `for(...)` header — exactly
the same posture as GPU-AUDIO-004's existing `const float` promoter, just
widened to two additional narrow, well-defined shapes. Nothing about them
depends on which shader is loaded.

**Q10 — Obvious false-positive risks?**
- **Multi-declarator statements** (`float a = 1., b = 2.;`) — the current
  regex reliably captures only the first `NAME = LITERAL` declarator per
  match position, same narrow-grammar precedent GPU-AUDIO-004 already
  accepted for `const float`.
- **Sign-adjacent-to-identifier ambiguity** in the generic literal scanner
  (e.g. `d-16.` could read as `d - 16.` or `d` then literal `-16.`) —
  documented directly in `tools/shader_audit.py`, resolved conservatively
  (excluded rather than misattributed).
- **Deeply nested multi-line `for(...)` headers containing their own
  function calls** (seen in the heavily golfed `Universe Ball 2.frag`) can
  defeat the simple `for\s*\(([^)]*)\)` span regex (it stops at the first
  `)`, which may belong to an inner call, not the loop header) — the exact
  same accepted limitation GPU-AUDIO-004's own loop-bound exclusion check
  already carries. Not attempted to fix generically here (§9).
- **Identifier-embedded digits** (`vec3`, `mat4`, a GLSL integer suffix like
  `16u`) look like bare numeric literals to a naive digit regex — found and
  fixed during this audit's own construction (§9) via an explicit
  boundary check (`_iter_num_tokens`), and regression-tested.

## 9. Validation Notes — Bugs Found and Fixed While Building the Auditor

Building this tool against real, messy, "golfed" Shadertoy code (rather than
only clean synthetic fixtures) surfaced two genuine bugs, both fixed before
this cut's results were trusted:

1. **Identifier-embedded digits miscounted as literals.** The naive
   `\d+\.\d*|\.\d+|\d+` token scanner matched the "3" in `vec3(...)`, the
   "4" in `mat4(...)`/`vec4(...)`, etc. First observed as a false
   `POSSIBLE_CANDIDATE` on the line `float orb(vec3 p) { ... }` (no literal
   is actually present there at all). Fixed with `_iter_num_tokens()`, which
   rejects any match with an alphabetic/underscore character immediately
   before or after it. This also silently corrected several structural/
   inline-literal counts upward-then-downward across the corpus (e.g.
   `happy_glow_cruise.frag`'s loop-bound count changed from a false 2 to the
   correct 1, and its inline-literal total from 52 to the correct 35) —
   every count quoted in §6-7 reflects the corrected scanner.
2. **Category A (production-reuse) silently returned nothing for annotated
   shaders.** Initially ran `parse_shader_parameters()` against the same
   comment-stripped text used for categories B-G — but the real
   `// [param:float] ...` annotation syntax lives inside a `//` comment by
   design, so this made category A structurally unable to ever detect an
   annotated parameter. Confirmed via all 4 `OFFICIAL` shaders (which use
   this exact annotation style) incorrectly reporting zero current-eligible
   parameters before the fix. Fixed by running category A against the
   uncomment-stripped text (§4) — exactly what production itself parses.

Both are covered by dedicated regression tests (`tests/test_gpu_audio_006a.py`,
tests 14 and 15).

## 10. Limitations

- This is a **heuristic reporting tool**, explicitly not a lexer/AST/GLSL
  compiler frontend. Every "probable color"/context-keyword classification
  is a guess for reporting purposes only, never authoritative.
- Multi-declarator local float statements are undercounted (only the first
  literal-initialized declarator per line is reliably captured).
- The `for(...)` header span regex can misalign on deeply nested,
  multi-line, heavily golfed headers (one real corpus example observed).
- Category G's "possible" vs. "unknown" split is a ~40-character
  keyword-window guess around each literal, not semantic understanding —
  useful only as an approximate signal of where interesting literals
  cluster, never as a promotion signal on its own.
- The corpus is small (5 real user shaders). The 100% combined-coverage
  finding (§8, Q8) is a strong, real signal for THIS corpus, but should be
  revisited if/when the real corpus grows meaningfully.

## 11. Recommended Next Implementation Cut (GPU-AUDIO-006B, NOT built here)

**Smallest expansion for largest real-world coverage**: implement discovery
+ promotion for exactly the two `HIGH_VALUE_SAFE_CANDIDATE` patterns that
alone reach 5/5 real-corpus coverage:

1. Direct/macro-wrapped `iTime`/`u_time` scalar multipliers.
2. Simple local `float NAME = LITERAL;` declarations (outside any loop
   header), using the exact same conservative exclusion posture
   GPU-AUDIO-004 already established for `const float` (reject on any
   structural ambiguity, never guess).

**Explicitly recommended AGAINST, based on measured evidence, not
speculation:**
- **`int` promotion of any kind** — 100% of the observed structural-int
  occurrences in the real corpus are loop bounds/array dimensions/indices;
  zero are artist knobs. §8 Q7.
- **Generic `#define` promotion** — 0/5 real shaders use a plain numeric
  `#define`; the one macro-numeric pattern that *is* common (a
  time-multiplier macro) is already covered by recommendation #1 above, so a
  separate `#define` promotion path would add real complexity for
  essentially no additional real-corpus coverage. §8 Q5.
- **`vec3`/`vec4` literal (color) musicalization** — only 1/5 real shaders
  has any probable-color literal at all; not enough signal in this corpus to
  justify the added risk of a vector-valued modulation model. §8 Q6.
- **Generic inline scalar-literal promotion** (category G at large) — the
  volume (12-58 literals per shader) and total absence of reliable naming
  makes this exactly the "arbitrary local-variable/magic-number extraction"
  territory both GPU-AUDIO-004 and GPU-AUDIO-005 explicitly, deliberately
  excluded as Level D+ scope. Nothing in this audit's evidence changes that
  conclusion.

## 12. Automated Tests

`tests/test_gpu_audio_006a.py` — 21/21 passed, runs with **zero Qt/OpenGL
dependency** (0.13-0.20s, no `QT_QPA_PLATFORM` needed): comment stripping
(line + block, incl. a Skinketest-shaped dead-code-doesn't-double-count
regression), direct/reversed/macro-wrapped time multipliers, local float
literals, numeric `#define`, vec-literal color heuristic, loop-bound and
array-dimension structural classification, source-file immutability,
deterministic output, the identifier-embedded-digit regression, the
category-A-through-comments regression, corpus auto-classification, and a
real-corpus smoke test asserting all 5 real shaders are read-only-scanned
and correctly report zero current-eligible parameters.

Full regression sweep: unaffected (same pre-existing, unrelated
`test_ux_004.py` marquee failures as every prior delivery this session;
everything else, including all 172+21+23+21 GPU/visualizer tests, passes).

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

Read-only observation/instrumentation cut. No production code, shader
source, or MUSICALIZE behavior changed; no phase or decision gate affected.
Consistent with every prior GPU-AUDIO cut this session.
