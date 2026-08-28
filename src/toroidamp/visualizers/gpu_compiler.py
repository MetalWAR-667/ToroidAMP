"""
ToroidAMP - GPU Shader Compiler & Metadata Parser (Production Foundation)

Handles:
- Parameter declaration parsing:
    // [param:float] u_speed: Speed = 1.0 (0.1 .. 5.0)
    or uniform float taParam... with automatic discovery
- Packaged 2D texture input for official shaders (taTexture0)
- Raw GLSL Fragment Shaders (#version 330 core / standard uniforms)
- Shadertoy-Style Level 1 Compatibility Wrapper (void mainImage(out vec4 fragColor, in vec2 fragCoord))
- ToroidAMP AudioFrame uniform injections
"""

import re
import zlib
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Optional, Set


@dataclass(slots=True)
class ShaderParameter:
    name: str          # Uniform name, e.g. "u_speed", "u_enableWarp", "u_primaryColor"
    display_name: str  # UI Label, e.g. "Speed", "Enable Warp", "Primary Color"
    param_type: str    # "float", "bool", "color"
    default_value: any # float for "float", bool for "bool", str ("#RRGGBB") for "color"
    min_value: float   # Relevant for float
    max_value: float   # Relevant for float
    current_value: any # Current runtime value
    is_promoted_const: bool = False  # GPU-AUDIO-004: True if this originated from a safely-promoted `const float`, not an authored uniform
    auto_param_kind: Optional[str] = None  # GPU-AUDIO-006B: "local_float" | "time_scale" | None (authored/annotated/promoted-const)


@dataclass(slots=True)
class ShaderMetadata:
    name: str
    is_shadertoy_style: bool
    description: str
    parameters: Dict[str, ShaderParameter] = field(default_factory=dict)
    uses_texture: bool = False
    adapted_source: Optional[str] = None  # GPU-AUDIO-006B: post-transformation, pre-wrap source, for diagnostics only


VERTEX_SHADER_SOURCE = """#version 330 core
layout (location = 0) in vec2 aPos;
out vec2 vUV;

void main() {
    vUV = (aPos + 1.0) * 0.5;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

TOROIDAMP_HEADER_NATIVE = """#version 330 core
out vec4 fragColor;
in vec2 vUV;

// Standard Viewport & Timing
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_timeDelta;
uniform int u_frame;

// ToroidAMP AudioFrame Analysis Contracts
uniform float taRms;
uniform float taPeak;
uniform float taBass;
uniform float taMids;
uniform float taTreble;
uniform int taBeat;
uniform int taStrongBeat;
uniform float taSpectrum[64];
uniform float taWaveform[128];

// Future Tempo/Phase Extension Points
uniform float taBpm;
uniform float taBeatPhase;
uniform float taBarPhase;

// Packaged Official Texture Sampler
uniform sampler2D taTexture0;
"""

SHADERTOY_WRAPPER_PREFIX = """#version 330 core
out vec4 _taFragColorOut;
in vec2 vUV;

// Shadertoy Standard Uniforms
uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;
uniform vec4 iMouse;
uniform vec4 iDate;
uniform float iSampleRate;

// ToroidAMP AudioFrame Analysis Extensions
uniform float taRms;
uniform float taPeak;
uniform float taBass;
uniform float taMids;
uniform float taTreble;
uniform int taBeat;
uniform int taStrongBeat;
uniform float taSpectrum[64];
uniform float taWaveform[128];
uniform float taBpm;
uniform float taBeatPhase;
uniform float taBarPhase;

// Packaged Official Texture Sampler
uniform sampler2D taTexture0;

// Generic Auto React Presentation Layer
uniform int taAutoReact;

// Shadertoy standard gl_FragCoord emulation
"""

SHADERTOY_WRAPPER_SUFFIX = """
void main() {
    if (taAutoReact == 0) {
        vec4 col = vec4(0.0);
        mainImage(col, gl_FragCoord.xy);
        _taFragColorOut = col;
        return;
    }

    // --- GENERIC AUTO REACT PRESENTATION LAYER ---
    // 1. Coordinate breathing/zoom (Bass + Strong Beat)
    vec2 center = 0.5 * iResolution.xy;
    vec2 p = gl_FragCoord.xy - center;
    float pulseZoom = 1.0 + (taBass * 0.08) + (float(taStrongBeat) * 0.05);

    // 2. Subtle rotational/drift perturbation (Mids)
    float rotAngle = (taMids > 0.0) ? (taMids - 0.5) * 0.035 : 0.0;
    float s = sin(rotAngle), c = cos(rotAngle);
    mat2 rot = mat2(c, -s, s, c);
    vec2 reactiveCoord = (rot * (p / pulseZoom)) + center;

    // 3. Render base shader pixels at reactive coordinate
    vec4 col = vec4(0.0);
    mainImage(col, reactiveCoord);

    // 4. Output post-modulation (Treble shimmer + Beat transient pulse + RMS exposure)
    float beatPulse = float(taBeat) * 0.08 + float(taStrongBeat) * 0.12;
    float trebleShimmer = taTreble * 0.06;
    float rmsLift = taRms * 0.05;

    vec3 boostedCol = col.rgb * (1.0 + beatPulse + trebleShimmer + rmsLift);
    _taFragColorOut = vec4(clamp(boostedCol, 0.0, 1.0), col.a);
}
"""

FALLBACK_FRAG_SOURCE = """#version 330 core
out vec4 fragColor;
in vec2 vUV;
uniform vec2 u_resolution;
uniform float u_time;

void main() {
    vec2 p = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float d = length(p);
    float ring = sin(d * 20.0 - u_time * 4.0);
    vec3 col = mix(vec3(0.0, 0.94, 1.0), vec3(1.0, 0.0, 0.47), 0.5 + 0.5 * ring);
    fragColor = vec4(col * (1.0 - smoothstep(0.4, 0.6, d)), 1.0);
}
"""

# Regex for parameter annotations:
# // [param:float] u_speed: Speed = 1.0 (0.1 .. 5.0)
# // [param:bool] u_enableWarp: Enable Warp = true
# // [param:color] u_primaryColor: Primary Color = #00E5FF
PARAM_GENERIC_RE = re.compile(
    r"//\s*\[param:(?P<type>float|bool|color)\]\s*(?P<name>\w+)\s*:\s*(?P<label>[^=]+?)\s*=\s*(?P<rest>[^\r\n]+)",
    re.IGNORECASE
)

PARAM_FLOAT_REST_RE = re.compile(
    r"^(?P<default>[0-9.-]+)\s*\(\s*(?P<min>[0-9.-]+)\s*\.\.\s*(?P<max>[0-9.-]+)\s*\)",
    re.IGNORECASE
)

# Backward-compatibility alias
PARAM_ANNOTATION_RE = PARAM_GENERIC_RE

# Regex for unannotated taParam* uniform floats
UNIFORM_TAPARAM_RE = re.compile(
    r"uniform\s+float\s+(taParam\w+)\s*;",
    re.IGNORECASE
)

SYSTEM_UNIFORMS = {
    # Shadertoy
    "iResolution", "iTime", "iTimeDelta", "iFrame", "iMouse", "iDate", "iSampleRate", "iChannelTime", "iChannelResolution",
    # ToroidAMP Audio & Engine
    "u_resolution", "u_time", "u_timeDelta", "u_frame",
    "taRms", "taPeak", "taBass", "taMids", "taTreble", "taBeat", "taStrongBeat",
    "taSpectrum", "taWaveform", "taBpm", "taBeatPhase", "taBarPhase",
    "taTexture0", "taAutoReact",
}

UNIFORM_FLOAT_GENERIC_RE = re.compile(
    r"uniform\s+float\s+(?P<name>[a-zA-Z_]\w*)\s*;",
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# GPU-AUDIO-004 — Safe const-float promotion
#
# Deliberately narrow grammar: `const float NAME = <numeric literal>;`, one
# declarator per statement, nothing else on the line. Scientific notation
# (1e-3) is accepted since it's still a single numeric literal token.
# Anything more elaborate (multi-declarator lines, expression initializers,
# trailing comments on the same line) simply fails to match and is never
# considered a candidate — this is the primary defense, before the explicit
# exclusion checks below even run.
# ---------------------------------------------------------------------------

CONST_FLOAT_LITERAL_RE = re.compile(
    r"^[ \t]*const\s+float\s+(?P<name>[a-zA-Z_]\w*)\s*=\s*"
    r"(?P<value>[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*;[ \t]*$",
    re.MULTILINE
)

# Broader net used only for the "does another const's initializer depend on
# this name" exclusion — deliberately matches ANY type (not just float),
# since promoting NAME would break a dependent const regardless of that
# dependent const's own type.
CONST_ANY_RE = re.compile(
    r"const\s+\w+\s+(?P<name>[a-zA-Z_]\w*)\s*=\s*(?P<expr>[^;]+);"
)


def _const_is_unsafe_to_promote(name: str, source: str) -> bool:
    """
    Conservative exclusion checks for GPU-AUDIO-004. Returns True (unsafe —
    do not promote) if there is any evidence the name is required to remain
    a compile-time constant, or that its role is structural rather than
    presentational. When in doubt, this returns True: false negatives
    (a promotable const that stays const) are acceptable; false positives
    (breaking a shader) are not.
    """
    word = re.compile(rf"\b{re.escape(name)}\b")

    # 1. Array dimension: NAME referenced anywhere inside [ ... ], including
    #    wrapped in a cast/expression like `arr[int(STEPS)]` — not just a
    #    bare `[STEPS]`. Matches non-nested bracket groups, which covers
    #    ordinary GLSL array declarators/subscripts.
    for bracket_match in re.finditer(r"\[([^\[\]]*)\]", source):
        if word.search(bracket_match.group(1)):
            return True

    # 2. Loop bound / compile-time iteration structure: NAME appears
    #    anywhere inside a for(...) header.
    for for_match in re.finditer(r"for\s*\(([^)]*)\)", source):
        if word.search(for_match.group(1)):
            return True

    # 3. switch/case labels.
    if re.search(rf"case\s+{re.escape(name)}\s*:", source):
        return True

    # 4. Preprocessor expressions — NAME referenced on any '#' directive line.
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and word.search(stripped):
            return True

    # 5. Const-expression dependency: some OTHER const's initializer
    #    expression references NAME (e.g. `const float B = A * 2.0;` makes
    #    A unsafe to promote — promoting A would invalidate B's GLSL
    #    constant-expression requirement).
    for m in CONST_ANY_RE.finditer(source):
        other_name = m.group("name")
        if other_name == name:
            continue
        if word.search(m.group("expr")):
            return True

    return False


def find_safe_promotable_consts(
    source_code: str, existing_names: set
) -> Tuple[str, Dict[str, "ShaderParameter"]]:
    """
    Scans `source_code` for safely-promotable `const float NAME = literal;`
    declarations (per the exclusion rules above) that do not collide with
    an already-discovered parameter name or a SYSTEM_UNIFORMS name.

    Returns (transformed_source, promoted_params):
    - transformed_source: `source_code` with each promoted const's original
      declaration line replaced by a same-shape comment (so line numbers in
      any resulting compile error stay stable). This is an in-memory copy —
      the caller's original string, and the file it came from, are never
      touched.
    - promoted_params: name -> ShaderParameter (is_promoted_const=True),
      keyed by the const's own original name (never renamed), so the LAB
      displays e.g. "SPEED" rather than a generated identifier.
    """
    promoted: Dict[str, ShaderParameter] = {}
    transformed = source_code

    # Collect candidates first (against the untouched source), then apply
    # replacements — mutating `transformed` mid-scan would shift offsets
    # for subsequent regex matches against the original `source_code`.
    replacements = []  # list of (match_object, name, value)
    for match in CONST_FLOAT_LITERAL_RE.finditer(source_code):
        name = match.group("name")
        if name in existing_names or name in promoted or name in SYSTEM_UNIFORMS:
            continue
        if _const_is_unsafe_to_promote(name, source_code):
            continue
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        replacements.append((match, name, value))

    # Apply replacements back-to-front so earlier match spans stay valid.
    for match, name, value in sorted(replacements, key=lambda r: r[0].start(), reverse=True):
        # Deliberately does NOT quote "float <name>" verbatim — the caller's
        # generic uniform-injection dedup check (`"float {name}" not in
        # clean_src`) would otherwise see this comment and wrongly conclude
        # a real declaration already exists, skipping the actual `uniform
        # float <name>;` injection.
        comment = f"// [gpu-audio-004] promoted from const, default={value}: {name}"
        transformed = transformed[: match.start()] + comment + transformed[match.end():]

        span = _generate_promoted_range(value)
        promoted[name] = ShaderParameter(
            name=name,
            display_name=name,
            param_type="float",
            default_value=value,
            min_value=span[0],
            max_value=span[1],
            current_value=value,
            is_promoted_const=True,
        )

    return transformed, promoted


def _generate_promoted_range(value: float) -> Tuple[float, float]:
    """
    GPU-AUDIO-004 range-generation policy for promoted consts (no
    author-declared min/max exists). Deliberately simple and generic:

        span = max(abs(value) * 2.0, 1.0)
        min  = value - span
        max  = value + span

    - The original value always sits well inside the range (never at an edge).
    - A minimum absolute span of 1.0 on each side guarantees a useful
      non-zero editing range even for a zero-valued constant.
    - The span scales with the constant's own magnitude, so it stays
      proportionate rather than exploding for large constants, while never
      being so narrow that a small negative excursion is impossible.
    """
    span = max(abs(value) * 2.0, 1.0)
    return (value - span, value + span)


# ---------------------------------------------------------------------------
# GPU-AUDIO-006B — Runtime literal parameterization
#
# Architectural rule: PARAMETERIZE THE LITERAL, never "promote the local
# variable". A matched literal TOKEN is replaced in place by a generated
# uniform's identifier; the surrounding declaration/expression, the local
# variable's name, scope, and every existing reference to it are completely
# untouched. This is deliberately simpler than GPU-AUDIO-004's const
# promotion (which replaces a whole declaration line with a comment) — here
# there is no declaration to neutralize, only a numeric token to swap.
#
# Evidence base (docs/design/13_gpu_audio_006a_discovery_audit.md): across
# the real 5-shader USER corpus, exactly two patterns together reach 5/5
# coverage — TIME_SCALE (direct or macro-wrapped `iTime`/`u_time * LITERAL`)
# and LOCAL_FLOAT_LITERAL (`float NAME = LITERAL;`, outside any loop
# header). Nothing else is implemented here; see the design doc for why.
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _mask_comments_preserve_offsets(source: str) -> str:
    """
    Replaces every character of every comment with a space (newlines kept
    as newlines), so the result is EXACTLY the same length as `source` and
    every surviving character sits at the identical offset. Candidate
    regexes are matched against this masked copy — a commented-out literal
    becomes blank space and can never match — while the resulting spans are
    then valid offsets to slice/replace directly in the real, untouched
    `source` string. This also means production's `// [param:...]`
    annotation comments are inert here (they contain no matchable literal
    shape this module looks for), so annotation discovery is unaffected.
    """
    def _repl(m: re.Match) -> str:
        return "".join(ch if ch == "\n" else " " for ch in m.group(0))
    return _COMMENT_RE.sub(_repl, source)


_RUNTIME_LITERAL_CORE = r"(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?"
_RUNTIME_LITERAL_RE = rf"[+-]?{_RUNTIME_LITERAL_CORE}"
_TIME_IDENTIFIERS = ("iTime", "u_time")
_TIME_ALT = "|".join(_TIME_IDENTIFIERS)

# Pattern B — direct or macro-wrapped time scalar multiplier. Deliberately
# broader than GPU-AUDIO-004's CONST_FLOAT_LITERAL_RE (which excludes
# leading-dot literals like `.8` by design): the real corpus overwhelmingly
# uses leading/trailing-dot literals (`iTime*.2`, `iTime*6.`), so excluding
# that shape here would fail on the majority of real matches.
#
# Uses explicit lookaround guards per-branch instead of a single outer `\b`
# wrapping the whole alternation — a real, silent-corruption bug found
# during corpus validation: `\b` only means anything adjacent to a WORD
# character, and a literal can legitimately start OR end on a bare `.`
# (`.2`, `6.`). A trailing `\b` after `iTime*6.` cannot be satisfied (`.`
# followed by `)` is non-word -> non-word, no boundary), so the engine
# backtracked to the shorter, WRONG match `6` — silently dropping the `.`
# and leaving invalid GLSL (`taAuto_..._HASH.` — a dangling member-access
# dot) after substitution. Symmetrically, a leading `\b` before `.2*iTime`
# (preceded by whitespace) also fails, silently truncating `.2` to `2` —
# a 10x wrong value, not a compile error, which would have been far worse
# to ship undetected. Both are covered by regression tests.
#
# The leading guard `(?<![\w.])` rejects starting mid-identifier or
# mid-number; the trailing guard `(?![\w])` rejects ending mid-identifier
# (deliberately NOT excluding a trailing `.`, since the literal's own last
# character may legitimately BE a dot).
TIME_SCALE_RE = re.compile(
    rf"(?<![\w.])(?P<time1>{_TIME_ALT})\s*\*\s*(?P<lit1>{_RUNTIME_LITERAL_RE})(?![\w])"
    rf"|(?<![\w.])(?P<lit2>{_RUNTIME_LITERAL_RE})\s*\*\s*(?P<time2>{_TIME_ALT})(?![\w])"
)

# Pattern A — simple local float literal: float NAME = LITERAL; (or ,).
# Same narrow, single-declarator posture as GPU-AUDIO-004's const promoter:
# only a bare numeric literal immediately after `=` counts. An expression
# initializer (`float fov = 2.5 - k;`), a multi-declarator statement
# (`float a = 1., b = 2.;` — only `a` matches), or anything else more
# elaborate simply fails to match and is never a candidate.
LOCAL_FLOAT_LITERAL_RE = re.compile(
    rf"(?<!const\s)(?<!uniform\s)\bfloat\s+(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>{_RUNTIME_LITERAL_RE})\s*[,;]"
)


def _for_header_spans_006b(source: str) -> List[Tuple[int, int]]:
    return [m.span(1) for m in re.finditer(r"for\s*\(([^)]*)\)", source)]


def _span_in_any(span: Tuple[int, int], spans: List[Tuple[int, int]]) -> bool:
    s, e = span
    for cs, ce in spans:
        if s < ce and e > cs:
            return True
    return False


def _generate_runtime_uniform_name(
    kind: str, base_name: str, index: int, existing_names: Set[str]
) -> Optional[str]:
    """
    GPU-AUDIO-006B generated-identity policy: `taAuto_<base>_<hash6>`.

    Deliberately NOT line-number-based (a trivial edit above the candidate
    would shift every subsequent line number and destroy identity for no
    real reason) and NOT Python's salted `hash()` (not deterministic across
    process launches). Instead: a small CRC32 digest of
    `f"{kind}:{base_name}:{index}"` — `kind` separates the two candidate
    families so they can never collide with each other even at the same
    index; `base_name` is the local variable name for LOCAL_FLOAT (already
    a stable, human-meaningful identifier) or the fixed literal
    `"timeScale"` for TIME_SCALE; `index` is a simple deterministic
    per-kind occurrence counter (1st, 2nd, ... match found, in file scan
    order) that disambiguates same-named or same-kind candidates within one
    shader. This is deliberately NOT full AST identity — see the design doc
    for the resulting, documented hot-reload limitation.
    """
    digest = zlib.crc32(f"{kind}:{base_name}:{index}".encode("utf-8")) & 0xFFFFFFFF
    safe_base = re.sub(r"[^A-Za-z0-9_]", "_", base_name)
    uname = f"taAuto_{safe_base}_{digest:06X}"
    if uname in existing_names or uname in SYSTEM_UNIFORMS:
        return None
    return uname


# Sentinel/epsilon guard: raymarching-style GLSL idioms commonly use an
# extreme-magnitude literal as a "very far"/"very negative" accumulator seed
# (e.g. `float d = -9e9;`, observed directly in the real corpus —
# Rig_Rekt.frag) rather than as an artist-tunable value. Parameterizing one
# would be harmless to compile but produce a practically useless LAB
# slider (a multi-billion-unit range dwarfs any meaningful precision) and
# an equally useless MUSICALIZE candidate. Conservatively excluded — every
# genuine tunable value observed in the real corpus (speed/zoom/glow/fov-
# shaped constants) is well under this threshold.
_RUNTIME_LITERAL_MAGNITUDE_LIMIT = 1e4


def find_runtime_literal_candidates(
    source_code: str, existing_names: Set[str]
) -> Tuple[str, Dict[str, "ShaderParameter"]]:
    """
    Scans `source_code` for safely-parameterizable literal tokens (TIME_SCALE
    then LOCAL_FLOAT_LITERAL — TIME_SCALE takes precedence; a literal it
    claims can never also become a LOCAL_FLOAT_LITERAL candidate, so
    `float t = iTime * 0.8;` produces exactly ONE generated parameter, not
    two) and returns (transformed_source, generated_params).

    `transformed_source` has ONLY the matched literal TOKENS replaced by a
    generated uniform identifier — every declaration, expression, local
    variable name/scope, and macro body is otherwise byte-identical to
    `source_code`. This is an in-memory copy; `source_code` (and the file it
    came from) is never touched.
    """
    mask = _mask_comments_preserve_offsets(source_code)
    for_spans = _for_header_spans_006b(mask)

    generated: Dict[str, ShaderParameter] = {}
    replacements: List[Tuple[int, int, str]] = []
    claimed_spans: List[Tuple[int, int]] = []
    names_in_use = set(existing_names)

    time_scale_index = 0
    for m in TIME_SCALE_RE.finditer(mask):
        lit_group = "lit1" if m.group("lit1") is not None else "lit2"
        lit_start, lit_end = m.span(lit_group)
        try:
            value = float(m.group(lit_group))
        except ValueError:
            continue
        if abs(value) > _RUNTIME_LITERAL_MAGNITUDE_LIMIT:
            continue

        time_scale_index += 1
        uname = _generate_runtime_uniform_name("TIME_SCALE", "timeScale", time_scale_index, names_in_use)
        if uname is None:
            continue

        lo, hi = _generate_promoted_range(value)
        generated[uname] = ShaderParameter(
            name=uname,
            display_name=f"Time Scale {time_scale_index}",
            param_type="float",
            default_value=value,
            min_value=lo,
            max_value=hi,
            current_value=value,
            auto_param_kind="time_scale",
        )
        replacements.append((lit_start, lit_end, uname))
        claimed_spans.append((lit_start, lit_end))
        names_in_use.add(uname)

    local_float_index = 0
    for m in LOCAL_FLOAT_LITERAL_RE.finditer(mask):
        val_start, val_end = m.span("value")
        if _span_in_any((val_start, val_end), claimed_spans):
            continue  # already claimed by TIME_SCALE — overlap precedence rule
        if _span_in_any((val_start, val_end), for_spans):
            continue  # loop-scoped declarator, e.g. for(float t = 0.0; ...) — structural, never a candidate

        name = m.group("name")
        if name in SYSTEM_UNIFORMS:
            continue
        try:
            value = float(m.group("value"))
        except ValueError:
            continue
        if abs(value) > _RUNTIME_LITERAL_MAGNITUDE_LIMIT:
            continue

        local_float_index += 1
        uname = _generate_runtime_uniform_name("LOCAL_FLOAT", name, local_float_index, names_in_use)
        if uname is None:
            continue

        lo, hi = _generate_promoted_range(value)
        generated[uname] = ShaderParameter(
            name=uname,
            display_name=name,
            param_type="float",
            default_value=value,
            min_value=lo,
            max_value=hi,
            current_value=value,
            auto_param_kind="local_float",
        )
        replacements.append((val_start, val_end, uname))
        claimed_spans.append((val_start, val_end))
        names_in_use.add(uname)

    transformed = source_code
    for start, end, repl in sorted(replacements, key=lambda r: r[0], reverse=True):
        transformed = transformed[:start] + repl + transformed[end:]

    return transformed, generated


def hex_to_rgb_normalized(hex_str: str) -> Optional[Tuple[float, float, float]]:
    """Converts #RRGGBB or #RGB to normalized float tuple (0.0 .. 1.0)."""
    s = hex_str.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return None


def parse_shader_parameters(source_code: str) -> Dict[str, ShaderParameter]:
    """
    Extracts author-declared parameters (float, bool, color) from comments or uniforms.
    Returns an ordered mapping of parameter name -> ShaderParameter metadata.
    """
    params: Dict[str, ShaderParameter] = {}

    # 1. Parse structured // [param:type] annotations
    for match in PARAM_GENERIC_RE.finditer(source_code):
        ptype = match.group("type").lower()
        pname = match.group("name").strip()
        plabel = match.group("label").strip()
        rest = match.group("rest").strip()

        if ptype == "float":
            f_match = PARAM_FLOAT_REST_RE.match(rest)
            if f_match:
                try:
                    pdef = float(f_match.group("default"))
                    pmin = float(f_match.group("min"))
                    pmax = float(f_match.group("max"))
                    params[pname] = ShaderParameter(
                        name=pname,
                        display_name=plabel,
                        param_type="float",
                        default_value=pdef,
                        min_value=pmin,
                        max_value=pmax,
                        current_value=pdef
                    )
                except ValueError:
                    continue
        elif ptype == "bool":
            b_val = rest.split()[0].lower() in ("true", "1", "yes", "on")
            params[pname] = ShaderParameter(
                name=pname,
                display_name=plabel,
                param_type="bool",
                default_value=b_val,
                min_value=0.0,
                max_value=1.0,
                current_value=b_val
            )
        elif ptype == "color":
            c_val = rest.split()[0].strip()
            if not c_val.startswith("#"):
                c_val = f"#{c_val}"
            rgb = hex_to_rgb_normalized(c_val)
            if rgb is not None:
                # Canonicalize uppercase 7-char hex
                canon_hex = f"#{int(round(rgb[0]*255)):02X}{int(round(rgb[1]*255)):02X}{int(round(rgb[2]*255)):02X}"
                params[pname] = ShaderParameter(
                    name=pname,
                    display_name=plabel,
                    param_type="color",
                    default_value=canon_hex,
                    min_value=0.0,
                    max_value=1.0,
                    current_value=canon_hex
                )

    # 2. Parse any unannotated custom float uniforms excluding known system uniforms
    for match in UNIFORM_FLOAT_GENERIC_RE.finditer(source_code):
        uname = match.group("name")
        if uname not in params and uname not in SYSTEM_UNIFORMS:
            disp = uname
            if disp.startswith("u_"):
                disp = disp[2:]
            elif disp.startswith("taParam"):
                disp = disp[7:]
            params[uname] = ShaderParameter(
                name=uname,
                display_name=disp,
                param_type="float",
                default_value=1.0,
                min_value=0.0,
                max_value=5.0,
                current_value=1.0
            )

    return params


def classify_and_wrap_source(raw_source: str, title: str = "Shader") -> Tuple[str, ShaderMetadata]:
    """
    Analyzes raw GLSL code. If it detects `mainImage`, wraps it with
    the Shadertoy single-pass compatibility header and driver main().
    Otherwise, if it contains standard main(), injects the ToroidAMP native header
    if #version is missing. Extracts any authoring parameter declarations and texture usage.
    """
    clean_src = raw_source.strip()
    is_shadertoy = "mainImage" in clean_src
    parameters = parse_shader_parameters(clean_src)
    uses_texture = "taTexture0" in clean_src

    # GPU-AUDIO-004: safe const-float promotion. Operates only on this
    # in-memory `clean_src` copy — `raw_source` (and the file it was read
    # from) is never touched. Promoted names are additive: any name already
    # claimed by an authored uniform/annotation is left alone.
    clean_src, promoted_params = find_safe_promotable_consts(clean_src, set(parameters.keys()))
    parameters.update(promoted_params)

    # GPU-AUDIO-006B: safe runtime literal parameterization (TIME_SCALE +
    # LOCAL_FLOAT_LITERAL). Same additive/in-memory-only posture as
    # GPU-AUDIO-004 above — operates on this same `clean_src` copy (now
    # already reflecting const promotion too), never on `raw_source`.
    clean_src, runtime_params = find_runtime_literal_candidates(clean_src, set(parameters.keys()))
    parameters.update(runtime_params)

    adapted_source = clean_src  # GPU-AUDIO-006B: diagnostics snapshot, post-transform/pre-wrap

    param_uniform_lines = []
    for p in parameters.values():
        if p.param_type == "float":
            decl = f"uniform float {p.name};"
            if decl not in clean_src and f"float {p.name}" not in clean_src:
                param_uniform_lines.append(decl)
        elif p.param_type == "bool":
            decl = f"uniform bool {p.name};"
            if decl not in clean_src and f"bool {p.name}" not in clean_src:
                param_uniform_lines.append(decl)
        elif p.param_type == "color":
            decl = f"uniform vec3 {p.name};"
            if decl not in clean_src and f"vec3 {p.name}" not in clean_src:
                param_uniform_lines.append(decl)
    
    param_header = "\n// Exposed Authoring Parameters\n" + "\n".join(param_uniform_lines) + "\n" if param_uniform_lines else ""

    if is_shadertoy:
        full_source = SHADERTOY_WRAPPER_PREFIX + param_header + clean_src + SHADERTOY_WRAPPER_SUFFIX
        meta = ShaderMetadata(
            name=title,
            is_shadertoy_style=True,
            description="Shadertoy Single-Pass (Level 1 + Level 2 Extensions)",
            parameters=parameters,
            uses_texture=uses_texture,
            adapted_source=adapted_source,
        )
    else:
        if not clean_src.startswith("#version"):
            full_source = TOROIDAMP_HEADER_NATIVE + param_header + "\n" + clean_src
        else:
            if param_header:
                parts = clean_src.split("\n", 1)
                full_source = parts[0] + "\n" + param_header + (parts[1] if len(parts) > 1 else "")
            else:
                full_source = clean_src
        meta = ShaderMetadata(
            name=title,
            is_shadertoy_style=False,
            description="Native ToroidAMP GLSL Fragment Shader",
            parameters=parameters,
            uses_texture=uses_texture,
            adapted_source=adapted_source,
        )

    return full_source, meta


def create_shader_preset(shader_id: str, current_params: Dict[str, any]) -> dict:
    """Serializes current typed parameters into a canonical ToroidAMP preset dictionary."""
    return {
        "format": "toroidamp_shader_preset",
        "version": 1,
        "shader": shader_id,
        "parameters": dict(current_params)
    }


def parse_and_apply_preset(
    preset_data: dict,
    active_shader_name: str,
    metadata: Optional[ShaderMetadata],
    current_params: Dict[str, any]
) -> Tuple[bool, str, int]:
    """
    Validates and applies a preset dictionary to the target metadata and parameter dict.
    Returns (success: bool, status_message: str, applied_count: int).
    """
    if not isinstance(preset_data, dict) or preset_data.get("format") != "toroidamp_shader_preset":
        return False, "Invalid preset format (expected 'toroidamp_shader_preset')", 0

    preset_shader = preset_data.get("shader", "")
    warning_prefix = ""
    if preset_shader and active_shader_name and preset_shader.lower() != active_shader_name.lower():
        warning_prefix = f"Preset was authored for '{preset_shader}', applying to '{active_shader_name}'. "

    raw_params = preset_data.get("parameters", {})
    if not isinstance(raw_params, dict):
        return False, "Missing or invalid 'parameters' dictionary in preset", 0

    if not metadata:
        return False, "No active shader parameter metadata available", 0

    param_dict = metadata.parameters if hasattr(metadata, "parameters") else metadata
    if not isinstance(param_dict, dict) or not param_dict:
        return False, "No active shader parameter metadata available", 0

    applied_count = 0
    for p_name, param in param_dict.items():
        if p_name in raw_params:
            val = raw_params[p_name]
            if param.param_type == "float":
                try:
                    f_val = float(val)
                    f_val = max(param.min_value, min(param.max_value, f_val))
                    current_params[p_name] = f_val
                    applied_count += 1
                except (ValueError, TypeError):
                    pass
            elif param.param_type == "bool":
                b_val = val is True or val == 1 or str(val).lower() in ("true", "1")
                current_params[p_name] = b_val
                applied_count += 1
            elif param.param_type == "color":
                c_str = str(val).strip()
                if hex_to_rgb_normalized(c_str) is not None:
                    current_params[p_name] = c_str.upper()
                    applied_count += 1

    msg = f"{warning_prefix}Applied {applied_count} parameter(s) from preset."
    return True, msg, applied_count
