// ToroidAMP test fixture (MIT, project-owned). See ../README.md.
// Supported bool parameter, but deliberately not float-promotable.
// [param:bool] u_invert: Invert = false
uniform bool u_invert;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = vec4(u_invert ? 1.0 - uv : uv, 0.5, 1.0);
}
