"""
ToroidAMP - GPU Shader Compiler & Metadata Parser (Authoring Lab Wrapper)

Re-exports core compiler interfaces from production package to avoid duplication.
"""

from toroidamp.visualizers.gpu_compiler import (
    ShaderParameter,
    ShaderMetadata,
    VERTEX_SHADER_SOURCE,
    TOROIDAMP_HEADER_NATIVE,
    SHADERTOY_WRAPPER_PREFIX,
    SHADERTOY_WRAPPER_SUFFIX,
    FALLBACK_FRAG_SOURCE,
    PARAM_ANNOTATION_RE,
    UNIFORM_TAPARAM_RE,
    parse_shader_parameters,
    classify_and_wrap_source,
)

__all__ = [
    "ShaderParameter",
    "ShaderMetadata",
    "VERTEX_SHADER_SOURCE",
    "TOROIDAMP_HEADER_NATIVE",
    "SHADERTOY_WRAPPER_PREFIX",
    "SHADERTOY_WRAPPER_SUFFIX",
    "FALLBACK_FRAG_SOURCE",
    "PARAM_ANNOTATION_RE",
    "UNIFORM_TAPARAM_RE",
    "parse_shader_parameters",
    "classify_and_wrap_source",
]
