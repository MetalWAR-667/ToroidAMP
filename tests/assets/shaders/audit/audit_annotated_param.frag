// ToroidAMP test fixture (MIT, project-owned). See ../README.md.
// [param:float] u_gain: Gain = 0.75 (0.0 .. 2.0)
uniform float u_gain;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = vec4(uv * u_gain, 0.25, 1.0);
}
