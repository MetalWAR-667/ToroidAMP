"""
ToroidAMP - GPU-AUDIO-006A Read-Only Shader Parameter Discovery Auditor

Read-only developer instrumentation. Scans .frag files (a single file or a
directory tree) and reports, per shader and in aggregate, what kinds of
numeric "control points" the shader actually contains — explicit uniforms,
safe promotable consts (reusing the real GPU-AUDIO-004 production logic so
these numbers exactly match what the app would actually discover today),
and a taxonomy of NOT-currently-supported patterns (numeric #define, local
`float NAME = literal;`, direct iTime multipliers, literal vec2/3/4
constructors, structural ints, and generic inline scalar literals).

This tool NEVER modifies a shader file, NEVER promotes anything, and does
NOT require a GPU/OpenGL context or a running QApplication — it is pure
text analysis, safe to run against arbitrary downloaded Shadertoy sources.

Usage:
    python tools\\shader_audit.py <file_or_directory> [--json] [--tag TAG]

Examples:
    python tools\\shader_audit.py user_shaders
    python tools\\shader_audit.py user_shaders\\shadertoy\\rig_rekt\\Rig_Rekt.frag
    python tools\\shader_audit.py user_shaders --json > audit.json

See docs/design/13_gpu_audio_006a_discovery_audit.md for the methodology,
full corpus results, and the recommended next implementation cut.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Reuse the REAL production parser/promoter — this is not a reimplementation.
# "currently discoverable/promotable" in this audit's output is computed by
# calling the exact same functions gpu_canvas.py calls when a shader loads,
# so the audit's "0 eligible today" claims are never a separate opinion.
from toroidamp.visualizers.gpu_compiler import (  # noqa: E402
    parse_shader_parameters,
    find_safe_promotable_consts,
    SYSTEM_UNIFORMS,
)

# ---------------------------------------------------------------------------
# Comment stripping (audit-only). Block and line comments are replaced with
# an equal number of newlines (never fewer), so every surviving line number
# still matches the original file — this is how the mission's requirement
# "must not count commented-out code, but should preserve useful line-number
# reporting" is satisfied without a real GLSL lexer.
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def strip_comments(source: str) -> str:
    def _repl(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")
    return _COMMENT_RE.sub(_repl, source)


# ---------------------------------------------------------------------------
# Numeric literal grammar. Deliberately BROADER than GPU-AUDIO-004's
# CONST_FLOAT_LITERAL_RE (which excludes leading-dot literals like `.05` by
# design, for narrow promotion safety) — this audit needs to see every
# literal SHAPE real shaders actually use, including `.05`, `1e2`, `-9e9`.
# ---------------------------------------------------------------------------

NUM_RE = r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?"
_NUM_CORE = r"(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?"
_RAW_NUM_RE = re.compile(rf"[+-]?{_NUM_CORE}")


def _iter_num_tokens(text: str):
    """
    Yields (start, end, text) for numeric literal tokens, EXCLUDING digits
    embedded in a larger identifier — e.g. the '3' in 'vec3'/'mat3', the '4'
    in 'iChannel4', or a GLSL integer suffix like '16u'. Plain `\\d` regexes
    have no notion of "this digit belongs to an identifier, not a literal";
    this checks both neighboring characters explicitly.

    This is a boundary heuristic, not a lexer: an ambiguous leading sign
    directly adjacent to an identifier/closing-bracket (e.g. `d-16.`, which
    could be read as `d - 16.` or as `d` followed by literal `-16.`) is
    conservatively treated as unary and the whole signed token is checked
    against the SAME identifier-adjacency rule — so it is dropped only when
    it would otherwise land inside what reads as one longer identifier.
    """
    for m in _RAW_NUM_RE.finditer(text):
        start, end = m.start(), m.end()
        prev_ch = text[start - 1] if start > 0 else ""
        next_ch = text[end] if end < len(text) else ""
        if prev_ch.isalpha() or prev_ch == "_":
            continue
        if next_ch.isalpha() or next_ch == "_":
            continue
        yield (start, end, m.group(0))


_NUM_TOKEN_RE = re.compile(NUM_RE)  # still used where the match is already syntactically anchored (see below)
TIME_IDENTIFIERS = ("iTime", "u_time")
_TIME_ALT = "|".join(TIME_IDENTIFIERS)

CLASS_HIGH_VALUE = "HIGH_VALUE_SAFE_CANDIDATE"
CLASS_POSSIBLE = "POSSIBLE_CANDIDATE"
CLASS_STRUCTURAL = "STRUCTURAL_UNSAFE"
CLASS_UNKNOWN = "UNKNOWN"
CLASS_CURRENT = "CURRENT"  # already discoverable/promotable today, not a "candidate"


@dataclass
class Candidate:
    category: str
    classification: str
    line: int
    name: Optional[str]
    value_text: str
    snippet: str
    note: str = ""


@dataclass
class ShaderAuditResult:
    path: Path
    corpus_tag: str
    line_count: int
    candidates: List[Candidate] = field(default_factory=list)
    inline_literal_total: int = 0

    def by_category(self) -> Dict[str, List[Candidate]]:
        out: Dict[str, List[Candidate]] = {}
        for c in self.candidates:
            out.setdefault(c.category, []).append(c)
        return out

    def has_current_eligible_parameter(self) -> bool:
        return any(c.classification == CLASS_CURRENT for c in self.candidates)


def _line_of(source: str, pos: int) -> int:
    return source.count("\n", 0, pos) + 1


def _snippet(source: str, start: int, end: int, pad: int = 0) -> str:
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    if line_end == -1:
        line_end = len(source)
    return source[line_start:line_end].strip()


def _span_overlaps(span: Tuple[int, int], claimed: List[Tuple[int, int]]) -> bool:
    s, e = span
    for cs, ce in claimed:
        if s < ce and e > cs:
            return True
    return False


# ---------------------------------------------------------------------------
# Category A — explicit / already supported (reuses REAL production code)
# ---------------------------------------------------------------------------

def _scan_category_a(source: str, clean: str, claimed: List[Tuple[int, int]]) -> List[Candidate]:
    """
    `source` is the SAME text production actually parses (`raw_source.strip()`
    — comments intact), never the comment-stripped `clean` text: the
    `// [param:float] NAME: Label = ...` annotation syntax deliberately
    LIVES inside a `//` comment by design, so stripping comments first would
    make this the one category that can never detect an annotated
    parameter, breaking the "counts exactly match real production" guarantee
    this category exists for. (This does mean category A, like the real
    production parser, cannot distinguish a live annotation from one sitting
    inside dead/commented-out code — a narrow, pre-existing production
    characteristic this audit does not attempt to fix; see Limitations.)

    `clean` is still used afterward purely to re-locate a representative
    LIVE occurrence (a body usage or an un-commented declaration) for
    line-number/snippet reporting and for `claimed`-span bookkeeping shared
    with categories B-G, which DO operate on `clean`.
    """
    out: List[Candidate] = []
    params = parse_shader_parameters(source)
    _transformed, promoted = find_safe_promotable_consts(source, set(params.keys()))

    for name, p in params.items():
        if p.param_type != "float":
            continue
        # Locate a representative occurrence for line reporting.
        m = re.search(rf"\b{re.escape(name)}\b", clean)
        line = _line_of(clean, m.start()) if m else 0
        is_annotated = bool(re.search(rf"\[param:float\]\s*{re.escape(name)}\s*:", source))
        out.append(Candidate(
            category="uniform_float_annotated" if is_annotated else "uniform_float_bare",
            classification=CLASS_CURRENT,
            line=line,
            name=name,
            value_text=str(p.default_value),
            snippet=_snippet(clean, m.start(), m.end()) if m else "",
            note="explicit uniform, already discoverable (GPU-AUDIO-003)",
        ))
        if m:
            claimed.append((m.start(), m.end()))

    for name, p in promoted.items():
        m = re.search(rf"\bconst\s+float\s+{re.escape(name)}\s*=", clean)
        line = _line_of(clean, m.start()) if m else 0
        out.append(Candidate(
            category="const_float_safe_promotable",
            classification=CLASS_CURRENT,
            line=line,
            name=name,
            value_text=str(p.default_value),
            snippet=_snippet(clean, m.start(), m.end()) if m else "",
            note="already promotable, GPU-AUDIO-004",
        ))
        if m:
            claimed.append((m.start(), m.end()))

    return out


# ---------------------------------------------------------------------------
# Category B — numeric #define (plain, and the macro-wrapped time-multiplier
# sub-case observed in the real corpus, e.g. `#define T (iTime*6.)`)
# ---------------------------------------------------------------------------

_DEFINE_LINE_RE = re.compile(r"^[ \t]*#define\s+(?P<name>[A-Za-z_]\w*)\b(?P<rest>[^\n]*)$", re.MULTILINE)
_DEFINE_PLAIN_NUM_RE = re.compile(rf"^\s*({NUM_RE})\s*$")
_DEFINE_TIME_MULT_RE = re.compile(
    rf"^\s*\(?\s*(?:(?:{_TIME_ALT})\s*\*\s*{NUM_RE}|{NUM_RE}\s*\*\s*(?:{_TIME_ALT}))\s*\)?\s*$"
)


def _scan_category_b(clean: str, claimed: List[Tuple[int, int]]) -> List[Candidate]:
    out: List[Candidate] = []
    for m in _DEFINE_LINE_RE.finditer(clean):
        name = m.group("name")
        rest = m.group("rest").strip()
        line = _line_of(clean, m.start())
        if _DEFINE_TIME_MULT_RE.match(rest):
            out.append(Candidate(
                category="define_time_multiplier",
                classification=CLASS_HIGH_VALUE,
                line=line,
                name=name,
                value_text=rest,
                snippet=_snippet(clean, m.start(), m.end()),
                note="macro-wrapped direct time multiplier",
            ))
            claimed.append(m.span())
        elif _DEFINE_PLAIN_NUM_RE.match(rest):
            out.append(Candidate(
                category="define_numeric",
                classification=CLASS_POSSIBLE,
                line=line,
                name=name,
                value_text=rest,
                snippet=_snippet(clean, m.start(), m.end()),
                note="numeric #define",
            ))
            claimed.append(m.span())
        # Function-like macros (#define NAME(args) ...) and macros whose
        # body is a larger expression/vector are deliberately NOT classified
        # here — their bodies still contribute to category G's generic
        # inline-literal statistics, just without a dedicated named bucket.
    return out


# ---------------------------------------------------------------------------
# Category C — local float initialized from a literal:  float NAME = LIT;
# Excludes names already claimed by category A (const/uniform) and anything
# inside a for(...) header (that is loop-scoped, category F's territory).
# ---------------------------------------------------------------------------

_LOCAL_FLOAT_LIT_RE = re.compile(
    rf"(?<!const\s)(?<!uniform\s)\bfloat\s+(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>{NUM_RE})\s*[,;]"
)


def _for_header_spans(clean: str) -> List[Tuple[int, int]]:
    return [m.span(1) for m in re.finditer(r"for\s*\(([^)]*)\)", clean)]


def _scan_category_c(clean: str, for_spans: List[Tuple[int, int]], claimed: List[Tuple[int, int]]) -> List[Candidate]:
    out: List[Candidate] = []
    for m in _LOCAL_FLOAT_LIT_RE.finditer(clean):
        if _span_overlaps(m.span(), for_spans):
            continue  # loop-scoped declarator, e.g. for(float t = 0.0; ...) -> structural, category F
        if _span_overlaps(m.span(), claimed):
            continue
        name = m.group("name")
        if name in SYSTEM_UNIFORMS:
            continue
        out.append(Candidate(
            category="local_float_literal",
            classification=CLASS_HIGH_VALUE,
            line=_line_of(clean, m.start()),
            name=name,
            value_text=m.group("value"),
            snippet=_snippet(clean, m.start(), m.end()),
            note="local float initialized directly from a numeric literal",
        ))
        claimed.append(m.span())
    return out


# ---------------------------------------------------------------------------
# Category D — direct iTime/u_time scalar multipliers (both orders), plain
# expressions only (the macro-wrapped case is handled in category B).
# ---------------------------------------------------------------------------

_TIME_MULT_RE = re.compile(
    rf"\b(?:(?P<t1>{_TIME_ALT})\s*\*\s*(?P<m1>{NUM_RE})|(?P<m2>{NUM_RE})\s*\*\s*(?P<t2>{_TIME_ALT}))\b"
)


def _scan_category_d(clean: str, claimed: List[Tuple[int, int]]) -> List[Candidate]:
    out: List[Candidate] = []
    for m in _TIME_MULT_RE.finditer(clean):
        mult = m.group("m1") or m.group("m2")
        time_name = m.group("t1") or m.group("t2")
        out.append(Candidate(
            category="time_multiplier",
            classification=CLASS_HIGH_VALUE,
            line=_line_of(clean, m.start()),
            name=None,
            value_text=f"{time_name} * {mult}",
            snippet=_snippet(clean, m.start(), m.end()),
            note="direct scalar multiplier on the time uniform",
        ))
        claimed.append(m.span())
    return out


# ---------------------------------------------------------------------------
# Category E — vecN(...) constructors whose arguments are ALL bare numeric
# literals (not expressions/variables). Heuristic-only color/geometry guess.
# ---------------------------------------------------------------------------

_VEC_LIT_RE = re.compile(rf"\bvec(?P<n>[234])\s*\(\s*(?P<args>{NUM_RE}(?:\s*,\s*{NUM_RE}){{1,3}})\s*\)")


def _classify_vec(n: int, values: List[float]) -> str:
    if n == 3 and all(-0.05 <= v <= 1.05 for v in values):
        return "probable color (RGB, all components in ~0..1)"
    if n == 4 and all(-0.05 <= v <= 1.05 for v in values):
        return "probable color (RGBA, all components in ~0..1)"
    return "probable geometric/other (component(s) outside 0..1)"


def _scan_category_e(clean: str, claimed: List[Tuple[int, int]]) -> List[Candidate]:
    out: List[Candidate] = []
    for m in _VEC_LIT_RE.finditer(clean):
        n = int(m.group("n"))
        try:
            values = [float(x) for x in re.split(r"\s*,\s*", m.group("args"))]
        except ValueError:
            continue
        role = _classify_vec(n, values)
        out.append(Candidate(
            category="vec_literal",
            classification=CLASS_POSSIBLE if "color" in role else CLASS_UNKNOWN,
            line=_line_of(clean, m.start()),
            name=None,
            value_text=m.group(0),
            snippet=_snippet(clean, m.start(), m.end()),
            note=role,
        ))
        claimed.append(m.span())
    return out


# ---------------------------------------------------------------------------
# Category F — structural integer/numeric occurrences: array dimensions,
# indexing, loop bounds, switch/case labels. These quantify WHY arbitrary
# int promotion is dangerous; they are never candidates.
# ---------------------------------------------------------------------------

def _scan_category_f(clean: str, for_spans: List[Tuple[int, int]], claimed: List[Tuple[int, int]]) -> List[Candidate]:
    out: List[Candidate] = []

    # Array dimension / indexing: any literal directly inside [ ... ].
    # Uses _iter_num_tokens (not the raw regex) so e.g. `q[vec3(0).x]` can't
    # miscount the '3' in 'vec3' as an array-dimension literal.
    for bm in re.finditer(r"\[([^\[\]]*)\]", clean):
        for lit_start, lit_end, lit_text in _iter_num_tokens(bm.group(1)):
            abs_start = bm.start(1) + lit_start
            abs_end = bm.start(1) + lit_end
            span = (abs_start, abs_end)
            if _span_overlaps(span, claimed):
                continue
            out.append(Candidate(
                category="structural_int_array",
                classification=CLASS_STRUCTURAL,
                line=_line_of(clean, abs_start),
                name=None,
                value_text=lit_text,
                snippet=_snippet(clean, abs_start, abs_end),
                note="array dimension or index literal",
            ))
            claimed.append(span)

    # Loop bounds: every literal inside a for(...) header. Same identifier-
    # boundary guard — a `vec4(0)` inside a for-header (e.g.
    # `for(o=vec4(0); i++<5e1; ...)`, seen in the real corpus) must not
    # count the '4' in 'vec4' as a loop-bound literal.
    for fs, fe in for_spans:
        header = clean[fs:fe]
        for lit_start, lit_end, lit_text in _iter_num_tokens(header):
            abs_start = fs + lit_start
            abs_end = fs + lit_end
            span = (abs_start, abs_end)
            if _span_overlaps(span, claimed):
                continue
            out.append(Candidate(
                category="structural_int_loop_bound",
                classification=CLASS_STRUCTURAL,
                line=_line_of(clean, abs_start),
                name=None,
                value_text=lit_text,
                snippet=_snippet(clean, abs_start, abs_end),
                note="loop bound / iteration literal",
            ))
            claimed.append(span)

    # switch/case labels.
    for cm in re.finditer(r"\bcase\s+(" + NUM_RE + r")\s*:", clean):
        span = cm.span(1)
        if _span_overlaps(span, claimed):
            continue
        out.append(Candidate(
            category="structural_int_case",
            classification=CLASS_STRUCTURAL,
            line=_line_of(clean, span[0]),
            name=None,
            value_text=cm.group(1),
            snippet=_snippet(clean, cm.start(), cm.end()),
            note="switch/case label",
        ))
        claimed.append(span)

    return out


# ---------------------------------------------------------------------------
# Category G — everything else: generic inline scalar literals. Reported as
# aggregate statistics plus a bounded number of representative examples with
# a light keyword-window context guess, per the mission's explicit request
# NOT to dump every occurrence uncritically.
# ---------------------------------------------------------------------------

_CONTEXT_KEYWORDS = {
    "time-related": ("time", "speed", "rate", "bpm"),
    "glow/exposure-related": ("glow", "light", "bright", "exposure", "core", "flash"),
    "color-related": ("col", "color", "colour", "hue", "palette", "tint"),
    "coordinate/geometry-related": ("uv", "p.", "q.", "pos", "dist", "length", "fov", "zoom", "scale", "radius", "d ", "s ="),
}


def _guess_context(clean: str, pos: int, window: int = 40) -> str:
    start = max(0, pos - window)
    around = clean[start:pos].lower()
    for label, keywords in _CONTEXT_KEYWORDS.items():
        if any(k in around for k in keywords):
            return label
    return "unknown"


def _scan_category_g(clean: str, claimed: List[Tuple[int, int]], max_examples: int = 8) -> Tuple[int, List[Candidate]]:
    all_literals = [t for t in _iter_num_tokens(clean) if not _span_overlaps((t[0], t[1]), claimed)]
    total = len(all_literals)

    examples: List[Candidate] = []
    for start, end, text in all_literals:
        context = _guess_context(clean, start)
        classification = CLASS_POSSIBLE if context in ("glow/exposure-related", "coordinate/geometry-related") else CLASS_UNKNOWN
        if classification == CLASS_POSSIBLE and len(examples) < max_examples:
            examples.append(Candidate(
                category="inline_scalar_literal",
                classification=classification,
                line=_line_of(clean, start),
                name=None,
                value_text=text,
                snippet=_snippet(clean, start, end),
                note=f"heuristic context: {context}",
            ))
    if len(examples) < max_examples:
        for start, end, text in all_literals:
            if len(examples) >= max_examples:
                break
            context = _guess_context(clean, start)
            if context == "unknown":
                examples.append(Candidate(
                    category="inline_scalar_literal",
                    classification=CLASS_UNKNOWN,
                    line=_line_of(clean, start),
                    name=None,
                    value_text=text,
                    snippet=_snippet(clean, start, end),
                    note="heuristic context: unknown",
                ))
    return total, examples


# ---------------------------------------------------------------------------
# Corpus classification (auto-tag by path; overridable via --tag for a
# single-file invocation).
# ---------------------------------------------------------------------------

def classify_corpus_tag(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    if "official_shaders" in parts:
        return "OFFICIAL"
    if "experiments" in parts:
        return "EXPERIMENTAL"
    if "user_shaders" in parts:
        if "shadertoy" in parts:
            return "USER"
        if name.startswith("test_") or "_test" in name:
            return "TEST_FIXTURE"
        return "USER"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Top-level per-shader scan
# ---------------------------------------------------------------------------

def audit_shader(path: Path, corpus_tag: Optional[str] = None) -> ShaderAuditResult:
    raw = path.read_text(encoding="utf-8", errors="replace")
    clean = strip_comments(raw)
    tag = corpus_tag or classify_corpus_tag(path)

    claimed: List[Tuple[int, int]] = []
    candidates: List[Candidate] = []

    candidates += _scan_category_a(raw, clean, claimed)
    candidates += _scan_category_b(clean, claimed)

    for_spans = _for_header_spans(clean)
    candidates += _scan_category_c(clean, for_spans, claimed)
    candidates += _scan_category_d(clean, claimed)
    candidates += _scan_category_e(clean, claimed)
    candidates += _scan_category_f(clean, for_spans, claimed)

    inline_total, inline_examples = _scan_category_g(clean, claimed)
    candidates += inline_examples

    return ShaderAuditResult(
        path=path,
        corpus_tag=tag,
        line_count=raw.count("\n") + 1,
        candidates=candidates,
        inline_literal_total=inline_total,
    )


def iter_shader_files(target: Path) -> List[Path]:
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.frag"))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = [
    ("uniform_float_annotated", "annotated [param:float]"),
    ("uniform_float_bare", "uniform float (bare)"),
    ("const_float_safe_promotable", "const float (safe promotable)"),
    ("define_numeric", "numeric #define"),
    ("define_time_multiplier", "#define time multiplier"),
    ("local_float_literal", "local float = literal"),
    ("time_multiplier", "direct iTime multiplier"),
    ("vec_literal", "literal vecN(...)"),
    ("structural_int_array", "structural: array dim/index"),
    ("structural_int_loop_bound", "structural: loop bound"),
    ("structural_int_case", "structural: switch/case"),
]


def format_shader_report(result: ShaderAuditResult) -> str:
    lines = [f"Shader: {result.path.name}", f"Path: {result.path}", f"Category: {result.corpus_tag}", f"Lines: {result.line_count}", ""]
    lines.append(f"{'Pattern':<32}{'Found':>8}{'Safe/Possible':>16}")
    lines.append("-" * 56)
    by_cat = result.by_category()
    for key, label in _CATEGORY_LABELS:
        items = by_cat.get(key, [])
        found = len(items)
        safe = sum(1 for c in items if c.classification in (CLASS_CURRENT, CLASS_HIGH_VALUE, CLASS_POSSIBLE))
        lines.append(f"{label:<32}{found:>8}{safe:>16}")
    inline_total = result.inline_literal_total
    inline_possible = sum(1 for c in by_cat.get("inline_scalar_literal", []) if c.classification == CLASS_POSSIBLE)
    lines.append(f"{'inline scalar literals':<32}{inline_total:>8}{inline_possible:>16} (of examples shown)")
    lines.append("")

    representative = [c for c in result.candidates if c.classification in (CLASS_HIGH_VALUE, CLASS_POSSIBLE, CLASS_STRUCTURAL)]
    if representative:
        lines.append("Representative candidates:")
        for c in representative[:20]:
            lines.append(f"    line {c.line}:")
            lines.append(f"        {c.snippet}")
            lines.append(f"        {c.classification}")
            if c.note:
                lines.append(f"        note: {c.note}")
            lines.append("")
    return "\n".join(lines)


def format_corpus_summary(results: List[ShaderAuditResult]) -> str:
    user = [r for r in results if r.corpus_tag == "USER"]
    lines = []
    lines.append(f"REAL USER SHADERS AUDITED: {len(user)}")
    lines.append("")
    eligible_today = sum(1 for r in user if r.has_current_eligible_parameter())
    lines.append(f"Current discovery coverage: shaders with >=1 current eligible parameter: {eligible_today} / {len(user)}")
    lines.append("")

    def _coverage(*cats: str) -> int:
        """Shaders with >=1 candidate in ANY of the given categories (not a sum across categories, which would double-count a shader hitting more than one)."""
        return sum(1 for r in user if any(r.by_category().get(cat) for cat in cats))

    lines.append("Potential coverage if supporting:")
    lines.append(f"    direct iTime multipliers (incl. macro-wrapped): {_coverage('time_multiplier', 'define_time_multiplier')} / {len(user)}")
    lines.append(f"    simple local float literals:                    {_coverage('local_float_literal')} / {len(user)}")
    lines.append(f"    numeric #define:                                {_coverage('define_numeric')} / {len(user)}")
    lines.append(f"    probable color vecN literals:                   {sum(1 for r in user if any('color' in c.note for c in r.candidates if c.category == 'vec_literal'))} / {len(user)}")
    lines.append("")
    struct_total = sum(len(r.by_category().get('structural_int_array', [])) + len(r.by_category().get('structural_int_loop_bound', [])) + len(r.by_category().get('structural_int_case', [])) for r in user)
    lines.append(f"Structural/unsafe occurrences across USER corpus: {struct_total}")
    return "\n".join(lines)


def to_json(results: List[ShaderAuditResult]) -> str:
    def _enc(r: ShaderAuditResult):
        d = asdict(r)
        d["path"] = str(r.path)
        return d
    return json.dumps([_enc(r) for r in results], indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GPU-AUDIO-006A read-only shader parameter discovery auditor.")
    parser.add_argument("target", type=Path, help="A .frag file or a directory to scan recursively.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the text report.")
    parser.add_argument("--tag", default=None, help="Force a corpus tag (USER/OFFICIAL/TEST_FIXTURE/EXPERIMENTAL) instead of auto-classifying by path.")
    args = parser.parse_args(argv)

    files = iter_shader_files(args.target)
    if not files:
        print(f"No .frag files found under {args.target}", file=sys.stderr)
        return 1

    results = [audit_shader(f, corpus_tag=args.tag) for f in files]

    if args.json:
        print(to_json(results))
        return 0

    for r in results:
        print(format_shader_report(r))
        print("=" * 60)
        print()

    print(format_corpus_summary(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
