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
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Optional


@dataclass(slots=True)
class ShaderParameter:
    name: str          # Uniform name, e.g. "u_speed", "u_enableWarp", "u_primaryColor"
    display_name: str  # UI Label, e.g. "Speed", "Enable Warp", "Primary Color"
    param_type: str    # "float", "bool", "color"
    default_value: any # float for "float", bool for "bool", str ("#RRGGBB") for "color"
    min_value: float   # Relevant for float
    max_value: float   # Relevant for float
    current_value: any # Current runtime value


@dataclass(slots=True)
class ShaderMetadata:
    name: str
    is_shadertoy_style: bool
    description: str
    parameters: Dict[str, ShaderParameter] = field(default_factory=dict)
    uses_texture: bool = False


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

// Shadertoy standard gl_FragCoord emulation
"""

SHADERTOY_WRAPPER_SUFFIX = """
void main() {
    vec4 col = vec4(0.0);
    mainImage(col, gl_FragCoord.xy);
    _taFragColorOut = col;
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

    # 2. Parse any unannotated taParam* uniforms with sensible defaults
    for match in UNIFORM_TAPARAM_RE.finditer(source_code):
        uname = match.group(1)
        if uname not in params:
            disp = uname
            if disp.startswith("taParam"):
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
            uses_texture=uses_texture
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
            uses_texture=uses_texture
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
