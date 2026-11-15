# Shader Test Fixtures

Project-owned GLSL fixtures used by automated tests. Every file here is an
original ToroidAMP test resource, licensed under the repository's MIT license
(see the root `LICENSE`), and is **not** copied from `user_shaders/` or any
third-party Shadertoy corpus.

## Layout

- `supported/` — valid Shadertoy-subset shaders (`mainImage` plus ToroidAMP
  system uniforms such as `iResolution` / `iTime`). Used for real
  compile/link/render smoke coverage.
- `unsupported/` — deliberately invalid GLSL used to prove compile failures
  are detected, not mistaken for success.
- `audit/` — small sources for `tools/shader_audit.py` parameter-discovery
  regression tests:
  - `audit_annotated_param.frag` — explicit `[param:float]` annotation
    (current-eligible).
  - `audit_promotable_const.frag` — safe promotable `const float`
    (current-eligible).
  - `audit_non_promotable_bool.frag` — a supported bool parameter that is
    not float-promotable (not current-eligible).
  - `audit_structural_only.frag` — loop bounds and array dimensions only;
    no current-eligible parameter.

## Compatibility Scope

Fixtures intentionally stay inside the currently supported Shadertoy subset.
`iChannel0..3` texture/sampler emulation is **DEFERRED / NOT AUTHORIZED**
(BASELINE-REPAIR-005); no fixture declares or uses those uniforms.

## Provenance

Self-authored for ToroidAMP by the project maintainers, 2026-11-15. No
third-party shader code. Covered by the root `LICENSE`.
