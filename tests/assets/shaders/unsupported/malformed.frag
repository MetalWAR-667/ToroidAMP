// ToroidAMP test fixture (MIT, project-owned). See ../README.md.
// Deliberately invalid: an undefined identifier must fail compilation.
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(totallyUndefinedIdentifier);
}
