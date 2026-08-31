# Third-Party Notices

ToroidAMP itself is released under the [MIT License](LICENSE). It is
built on, and its packaged Windows distribution redistributes, a number
of third-party open-source components. This file lists them.

Full license texts for each component are in [`licenses/`](licenses/).
This document is **not legal advice** — see
[`docs/release/RC_069_003C_final_license_closure.md`](docs/release/RC_069_003C_final_license_closure.md)
(and the earlier [`docs/release/RC_069_003B_license_and_docs.md`](docs/release/RC_069_003B_license_and_docs.md))
for the full audit trail and evidence sources.

Only components genuinely **redistributed** with ToroidAMP (i.e. present
in the packaged Windows build) are listed — build-time-only tools
(PyInstaller itself) are noted separately and are not part of the
distributed product.

## Core Runtime

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| Python | 3.14 | Interpreter/runtime the frozen build embeds | PSF License (permissive) | [`licenses/Python.txt`](licenses/Python.txt) |
| PySide6 / Qt6 | 6.11.2 | GUI toolkit, OpenGL widget host | LGPL-3.0-only (dynamically linked; see the Qt/PySide6 review in the RC-069-003C design doc) | [`licenses/Qt-PySide6-LGPL-3.0.txt`](licenses/Qt-PySide6-LGPL-3.0.txt) *(full LGPLv3+GPLv3 text embedded as of RC-069-003C)* |
| NumPy | 2.5.2 | Audio analysis, PCM/geometry math | BSD-3-Clause (+ a few permissive sub-component licenses within NumPy itself) | [`licenses/NumPy.txt`](licenses/NumPy.txt) |

## Visualizer / Media Engine

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| pygame-ce | 2.5.8 | CPU visualizer rendering, tracker DLL host directory | LGPL v2.1 (dynamically linked) | [`licenses/pygame-ce-LGPL-2.1.txt`](licenses/pygame-ce-LGPL-2.1.txt) |
| SDL2 (core) | bundled by pygame-ce | pygame-ce's underlying multimedia layer | zlib License | [`licenses/SDL2.txt`](licenses/SDL2.txt) |
| FreeType | bundled by pygame-ce (SDL2_ttf) | Font rendering used by SDL2_ttf | FreeType License (FTL) | [`licenses/FreeType-FTL.txt`](licenses/FreeType-FTL.txt) |
| libpng | bundled by pygame-ce (SDL2_image) | PNG decode | libpng License | [`licenses/libpng.txt`](licenses/libpng.txt) |
| libjpeg (IJG-API-compatible) | bundled by pygame-ce (SDL2_image) | JPEG decode | IJG License + Modified BSD License | [`licenses/libjpeg-IJG-and-BSD.txt`](licenses/libjpeg-IJG-and-BSD.txt) |
| libtiff | bundled by pygame-ce (SDL2_image) | TIFF decode | libtiff License (permissive) | [`licenses/libtiff.txt`](licenses/libtiff.txt) |
| libwebp / libwebpdemux | bundled by pygame-ce (SDL2_image) | WebP decode | BSD-3-Clause | [`licenses/libwebp-BSD-3-Clause.txt`](licenses/libwebp-BSD-3-Clause.txt) |
| libogg | bundled by pygame-ce (SDL2_mixer) | Ogg container support | BSD-3-Clause | [`licenses/libogg-BSD-3-Clause.txt`](licenses/libogg-BSD-3-Clause.txt) |
| libopus / libopusfile | bundled by pygame-ce (SDL2_mixer) | Opus audio decode | BSD-3-Clause-style | [`licenses/libopus-and-opusfile-BSD.txt`](licenses/libopus-and-opusfile-BSD.txt) |
| WavPack | bundled by pygame-ce (SDL2_mixer) | WavPack audio decode | BSD-3-Clause | [`licenses/WavPack-BSD-3-Clause.txt`](licenses/WavPack-BSD-3-Clause.txt) |
| PortMidi | bundled by pygame-ce | pygame's MIDI backend (not used directly by ToroidAMP, but present in the ONEDIR) | MIT-style (PortMedia project) | [`licenses/PortMidi.txt`](licenses/PortMidi.txt) |

## Audio Playback — Conventional (MP3/WAV/OGG/FLAC)

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| soundfile | 0.14.0 | Python decoder wrapper (conventional formats and the startup voice-line WAV) | BSD 3-Clause | [`licenses/soundfile-python.txt`](licenses/soundfile-python.txt) |
| libsndfile | bundled by soundfile | The actual native decode engine | LGPL v2.1 (dynamically linked) | [`licenses/libsndfile-LGPL-2.1.txt`](licenses/libsndfile-LGPL-2.1.txt) |
| sounddevice | 0.5.6 | Python audio-output wrapper (music playback and the startup voice-line) | MIT | [`licenses/sounddevice-python.txt`](licenses/sounddevice-python.txt) |
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

## Additional Native Libraries

| Component | Version | Purpose | License | Full text |
|---|---|---|---|---|
| OpenSSL — `libcrypto-3.dll`/`libssl-3.dll` | 3.5.7 | Python 3.14's own bundled TLS/crypto support (backs the stdlib `ssl`/`hashlib` modules); traced to `C:\Python314\DLLs\` on the build machine (RC-069-003C) | Apache License 2.0 | [`licenses/OpenSSL-Apache-2.0.txt`](licenses/OpenSSL-Apache-2.0.txt) |
| OpenSSL — `libcrypto-3-x64.dll`/`libssl-3-x64.dll` | 3.5.4 | Satisfies the filename Qt's `qopensslbackend.dll` TLS plugin expects; traced to the build machine's Git for Windows mingw64 OpenSSL build (RC-069-003C) — a build-environment artifact of where PyInstaller's dependency walker found a matching filename on PATH, not a deliberately chosen ToroidAMP dependency | Apache License 2.0 | [`licenses/OpenSSL-Apache-2.0.txt`](licenses/OpenSSL-Apache-2.0.txt) |

---

**This is a good-faith, evidence-based inventory — not a legal
guarantee.** See the legal-readiness matrix in
`docs/release/RC_069_003C_final_license_closure.md` for the final
per-component status of every redistributed component.
