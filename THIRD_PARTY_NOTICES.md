# Third-Party Notices

ToroidAMP itself is released under the [MIT License](LICENSE). It is
built on, and its packaged Windows distribution redistributes, a number
of third-party open-source components. This file lists them.

Full license texts for each component are in [`licenses/`](licenses/).
This document is **not legal advice** — see
[`docs/release/RC_069_003B_license_and_docs.md`](docs/release/RC_069_003B_license_and_docs.md)
for the full audit trail, evidence sources, and a few items still marked
`NEEDS VERIFICATION`.

Only components genuinely **redistributed** with ToroidAMP (i.e. present
in the packaged Windows build) are listed — build-time-only tools
(PyInstaller itself) are noted separately and are not part of the
distributed product.

## Core Runtime

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| Python | 3.14 | Interpreter/runtime the frozen build embeds | PSF License (permissive) | [`licenses/Python.txt`](licenses/Python.txt) |
| PySide6 / Qt6 | 6.11.2 | GUI toolkit, OpenGL widget host | LGPL-3.0-only (dynamically linked; see the Qt/PySide6 review in the RC-069-003B design doc) | [`licenses/Qt-PySide6-LGPL-3.0.txt`](licenses/Qt-PySide6-LGPL-3.0.txt) *(reference only — see status note in that file)* |
| NumPy | 2.5.2 | Audio analysis, PCM/geometry math | BSD-3-Clause (+ a few permissive sub-component licenses within NumPy itself) | [`licenses/NumPy.txt`](licenses/NumPy.txt) |

## Visualizer / Media Engine

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| pygame-ce | 2.5.8 | CPU visualizer rendering, voice-line WAV playback, tracker DLL host directory | LGPL v2.1 (dynamically linked) | [`licenses/pygame-ce-LGPL-2.1.txt`](licenses/pygame-ce-LGPL-2.1.txt) |
| SDL2 (+ SDL2_image, SDL2_mixer, SDL2_ttf and their own codec helpers: libjpeg, libpng, libtiff, libwebp, libogg, libopus, libwavpack, FreeType) | bundled by pygame-ce | pygame-ce's underlying multimedia layer | zlib License (SDL2 core, verified); helper codec libraries are established permissively-licensed projects, exact texts `NEEDS VERIFICATION` — see matrix | [`licenses/SDL2.txt`](licenses/SDL2.txt) |

## Audio Playback — Conventional (MP3/WAV/OGG/FLAC)

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| soundfile | 0.14.0 | Python decoder wrapper | BSD 3-Clause | [`licenses/soundfile-python.txt`](licenses/soundfile-python.txt) |
| libsndfile | bundled by soundfile | The actual native decode engine | LGPL v2.1 (dynamically linked) | [`licenses/libsndfile-LGPL-2.1.txt`](licenses/libsndfile-LGPL-2.1.txt) |
| sounddevice | 0.5.6 | Python audio-output wrapper | MIT | [`licenses/sounddevice-python.txt`](licenses/sounddevice-python.txt) |
| PortAudio | bundled by sounddevice | The actual native audio output engine | MIT-style (permissive) | [`licenses/PortAudio.txt`](licenses/PortAudio.txt) |

## Audio Playback — Tracker (MOD/XM/IT/S3M)

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| libxmp | 4.6.3 | Native tracker module decode engine, dynamically loaded via ctypes (RC-069-002B) | Permissive (0BSD/BSD-3-Clause/ISC/MIT/Public-Domain family) — full library was LGPL-influenced before 4.6.1, confirmed clean of that as of the bundled 4.6.3 | [`licenses/libxmp.txt`](licenses/libxmp.txt) |

## Voice (Windows SAPI5)

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| pyttsx3 | 2.99 | Startup voice-identity line | MPL-2.0 | [`licenses/pyttsx3.txt`](licenses/pyttsx3.txt) |
| pywin32 | 312 | Windows COM/SAPI5 bindings pyttsx3 depends on | PSF-derived / permissive | [`licenses/pywin32.txt`](licenses/pywin32.txt) |
| comtypes | 1.4.16 | COM interop pyttsx3 depends on | MIT | [`licenses/comtypes.txt`](licenses/comtypes.txt) |

## Bundled Assets

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| Quantum (font) | — | CYBER YELLOW theme display typeface | SIL Open Font License 1.1 (Alexandros Tsitlakidis / Fontstruct) — explicitly permits bundling/redistribution with software | [`licenses/Quantum-font-OFL-1.1.txt`](licenses/Quantum-font-OFL-1.1.txt) |
| Branding icon, GPU texture, theme images, official `.frag` shaders | — | Application icon/tray, packaged GPU texture, DEFAULT/CYBER YELLOW theme chrome, the 4 official GPU visualizer shaders | **Original ToroidAMP work** — no third-party license applies; 3 of the 4 official shaders carry an explicit `License: MIT` header in their own source, consistent with ToroidAMP's own license | N/A |

## Build-Time-Only Tool (NOT part of the distributed product)

| Component | Version | Purpose | License |
|---|---|---|---|
| PyInstaller | 6.22.2 | Freezes the application into the ONEDIR distribution | GPL-2.0-or-later, **with an explicit bootloader/runtime exception** that means applications it builds are not themselves subject to the GPL — PyInstaller's own stated project policy. Never shipped inside `dist/ToroidAMP/`. Reference text: [`licenses/PyInstaller-BUILD-TOOL-ONLY.txt`](licenses/PyInstaller-BUILD-TOOL-ONLY.txt) |

## Additional Native Libraries Present in the Frozen Build (observed, not yet fully attributed)

| Component | Likely origin | Status |
|---|---|---|
| OpenSSL (`libcrypto-3*.dll`, `libssl-3*.dll`) | Not conclusively traced this cut — likely Python 3.14's own bundled TLS support or a transitive Qt/networking hook | License is well-established as Apache License 2.0 for OpenSSL 3.x; exact provenance/attribution `NEEDS VERIFICATION` |

---

**This is a good-faith, evidence-based inventory — not a legal
guarantee.** See the legal-readiness matrix in
`docs/release/RC_069_003B_license_and_docs.md` for exactly which items
are `READY` versus `ACTION REQUIRED` versus `NEEDS VERIFICATION` before
any public release.
