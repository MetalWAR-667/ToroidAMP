# RC-069-003B — LICENSE, Third-Party Notices & User Documentation Closure

> **Status: SUCCEEDED (with explicit ACTION REQUIRED / NEEDS VERIFICATION
> items — see §10 Legal-Readiness Matrix).** ToroidAMP now has a proper MIT
> `LICENSE`, an evidence-based `THIRD_PARTY_NOTICES.md` and `licenses/`
> bundle covering the RC-069-003 frozen ONEDIR payload, a `CHANGELOG.md`,
> a user-facing `HOWTOUSE.md` (including a consolidated Validation /
> Self-Test Checklist), a focused `README.md` alignment pass, and a
> packaging spec that bundles all of the above into the frozen build. This
> is a documentation/licensing closure cut — **no runtime, audio, or GPU
> behavior was changed.**

## 0. Precondition Check

- RC-069-003 (PyInstaller ONEDIR PoC) status confirmed **SUCCEEDED**
  (`docs/release/RC_069_003_pyinstaller_onedir.md`): ~198MB, ~370 files,
  `ToroidAMP.exe` launches standalone and relocated, real MOD/XM playback
  via bundled libxmp validated.
- Git working tree was clean before starting this cut.
- **Metal's explicit, closed licensing decision: ToroidAMP SHALL USE THE
  MIT LICENSE.** This cut does not revisit that decision; it implements it
  correctly and audits what it obligates ToroidAMP to disclose about its
  dependencies.
- The existing `LICENSE` file was incomplete — a bare copyright line with
  no grant, no permission text, no warranty disclaimer. Not a valid MIT
  license as shipped.

## 1. Mission A — ToroidAMP's Own License

`LICENSE` was replaced with the canonical MIT License text, keeping the
existing copyright holder/year already established in the repository
(`Copyright (c) 2026 MetalWAR`) rather than inventing a new entity. No dual
licensing, no CLA, no custom restrictions were introduced — exactly the
canonical, unmodified MIT text.

`pyproject.toml` was updated to declare this via **PEP 639 license
expressions**: `license = "MIT"` plus `license-files = ["LICENSE"]`. An
initial attempt also added a `"License :: OSI Approved :: MIT License"`
classifier, which broke `pip install -e .` outright:

```
setuptools.errors.InvalidConfigError: License classifiers have been
superseded by license expressions (see https://peps.python.org/pep-0639/).
Please remove: License :: OSI Approved :: MIT License
```

The classifier was removed (modern setuptools — 84.0.0 in this
environment — rejects the combination). Verified fixed via a clean
`pip install -e . --no-deps` (exit 0) and
`importlib.metadata.metadata('toroidamp')['License-Expression']` returning
`"MIT"`.

## 2. Mission B — Third-Party Audit Methodology

Evidence order applied throughout, strictly:

1. A license file physically shipped inside the installed package (or, for
   native DLLs, alongside the wheel that bundles them).
2. Package metadata (`pip show`, `importlib.metadata`).
3. Authoritative upstream repository/site (fetched live via WebSearch/
   WebFetch this cut — not recalled from training data).
4. Authoritative project documentation.

Anything not confidently resolved through this chain is marked `NEEDS
VERIFICATION` in `THIRD_PARTY_NOTICES.md` and in the matrix below — never
guessed. The audit scope was the **actual RC-069-003 frozen ONEDIR
payload** (`dist/ToroidAMP/`), not merely everything present in `.venv`.

## 3. libxmp — Special Attention

The mission explicitly required this be re-verified from authoritative
sources rather than recalled from memory, since RC-069-002B had left it
as an unverified recollection.

- **Bundled version confirmed**: **4.6.3** (previously confirmed in
  RC-069-002B via the DLL's own `xmp_version`/`xmp_vercode` data symbols;
  re-confirmed here as the version this audit applies to).
- **Historical complication**: full (non-lite) libxmp was, in older
  releases, LGPL-tainted overall because of a small number of bundled
  LGPL-licensed third-party components — an embedded unzip implementation,
  an LZW depacker used by the Digital Symphony loader, and several
  "deadcode" format loaders (`fcm_load.c`, `ftm_load.c`, `hvl_load.c`,
  `polly_load.c`, `ssmt_load.c`, `stc_load.c`) — even though the large
  majority of individual source files were themselves MIT-licensed.
- **Resolution confirmed via upstream repository (GitHub issue #387 and
  the project's own version history)**: as of **libxmp 4.6.1**, upstream
  removed all LGPLv2+ code. The resulting overall license for 4.6.1+ is a
  fully permissive combination: **0BSD AND BSD-3-Clause AND ISC AND MIT
  AND Public Domain.**
- Since ToroidAMP bundles **4.6.3**, which postdates the 4.6.1 LGPL
  removal, the bundled libxmp is **fully permissive** — no LGPL
  obligations attach to it. This is a materially different (and better)
  conclusion than RC-069-002B's unverified placeholder.
- Verbatim upstream MIT copyright/grant text (`Extended Module Player /
  Copyright (C) 1996-2026 Claudio Matsuoka and Hipolito Carraro Jr`) is
  recorded in [`licenses/libxmp.txt`](../../licenses/libxmp.txt), with a
  provenance note documenting this verification chain.

## 4. Qt / PySide6 — LGPL Review

- PySide6's own installed package metadata declares:
  `License-Expression: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`.
- ToroidAMP's actual build model (RC-069-003's ONEDIR spec) keeps
  Qt/PySide6 as **separate DLL files** alongside `ToroidAMP.exe` — never
  statically merged or relinked into the application binary. This is the
  standard, low-friction **dynamic-linking** distribution model, which is
  the compliance route LGPL is specifically designed to make
  straightforward: an end user can, in principle, replace the shipped
  Qt DLLs with a compatible build of their own, without ToroidAMP's own
  source needing to be disclosed.
- Given dynamic linking, the applicable license for ToroidAMP's purposes
  is **LGPL-3.0-only** (the least restrictive of the three metadata
  options, and the one PySide6/Qt's own LGPL packaging targets).
- A separate `LicenseRef-Qt-Commercial.txt`-style file ships inside every
  PySide6 wheel; this was confirmed to be standard informational
  boilerplate present regardless of which license route is actually used
  — not evidence that ToroidAMP is using, or needs, a commercial Qt
  license.
- **This review does not conclude, and is not intended to conclude,
  that ToroidAMP's own MIT license must change.** ToroidAMP's own source
  code remains MIT; the LGPL obligation is scoped to the Qt/PySide6
  components themselves (attribution + full license text + preserving the
  dynamic-linking arrangement), which is exactly what
  `THIRD_PARTY_NOTICES.md` and `licenses/` now provide.
- **Open item**: the full canonical LGPL-3.0 text could not be reliably
  fetched this cut (see §9 for the tooling failure) and was deliberately
  **not** reconstructed from memory for a document with real legal
  weight. `licenses/Qt-PySide6-LGPL-3.0.txt` is currently a reference-only
  file with the exact upstream URL (`https://www.gnu.org/licenses/lgpl-3.0.txt`)
  and an explicit `STATUS: ACTION REQUIRED` marker — see the matrix.

## 5. pygame-ce / SDL2 Stack Audit

- **pygame-ce 2.5.8**: `pip show pygame-ce` reports `License: LGPL v2.1`.
  The wheel itself ships no license file, so the canonical FSF LGPLv2.1
  text was sourced from a package that *does* ship it verbatim
  (`soundfile`'s bundled `libsndfile` `COPYING` file — the same standard
  document, reused with a pygame-ce-specific provenance note in
  `licenses/pygame-ce-LGPL-2.1.txt`).
- **SDL2 core**: zlib License, confirmed via live upstream fetch
  (`Copyright (C) 1997-2026 Sam Lantinga <slouken@libsdl.org>`), recorded
  verbatim in `licenses/SDL2.txt`.
- **SDL2_image / SDL2_mixer / SDL2_ttf and their own bundled codec
  helpers** (libjpeg, libpng, libtiff, libwebp, libogg, libopus,
  libwavpack, FreeType): all are established, permissively-licensed
  upstream projects, but their individual exact license texts were **not
  re-verified file-by-file this cut** — flagged `NEEDS VERIFICATION`
  rather than assumed.

## 6. Conventional Audio Stack Audit

| Component | License | Evidence |
|---|---|---|
| soundfile 0.14.0 | BSD 3-Clause | package-shipped license file |
| libsndfile (bundled by soundfile) | LGPL v2.1 | package-shipped `COPYING` (verbatim FSF text) |
| sounddevice 0.5.6 | MIT | package-shipped license file |
| PortAudio (bundled by sounddevice) | MIT-style permissive | upstream verified (`Copyright (c) 1999-2006 Ross Bencina and Phil Burk`), including the community's characteristic non-binding attribution-request clause |

A ToroidAMP-specific note was added to `licenses/PortAudio.txt` flagging
that the sounddevice wheel bundles ASIO-variant DLL artifacts that
reference the Steinberg ASIO SDK in their build metadata; ToroidAMP does
not use or license the ASIO SDK itself, and this is noted rather than
silently ignored.

## 7. Tracker Stack Audit

Covered in full in §3 (libxmp). No other native tracker dependency exists
— `TrackerDecoder` loads `libxmp.dll` directly via `ctypes.CDLL`
(RC-069-002B), and it is the only tracker-format native library present in
the frozen build.

## 8. Python / NumPy / Windows-Support Stack Audit

| Component | License | Evidence |
|---|---|---|
| Python 3.14 (embedded interpreter) | PSF License (permissive) | package-shipped license file |
| NumPy 2.5.2 | BSD-3-Clause (+ a few permissive sub-component licenses within NumPy itself) | package-shipped license file |
| pyttsx3 2.99 | MPL-2.0 | package-shipped license file |
| pywin32 312 | PSF-derived / permissive | package-shipped license file |
| comtypes 1.4.16 | MIT | package-shipped license file |

## 9. Additional Native Libraries Found in the Frozen Build

- **OpenSSL** (`libcrypto-3*.dll`, `libssl-3*.dll`): present in
  `dist/ToroidAMP/`. License itself is well-established (Apache License
  2.0 for OpenSSL 3.x). **Provenance not conclusively traced this cut** —
  `.venv` was searched exhaustively for a matching DLL (no hits), the
  PyInstaller `warn-toroidamp.txt` build log makes no mention of it, and
  `C:\Windows\System32` was checked as a sanity comparison (a
  non-matching `libcrypto.dll` was found there, unrelated to this build).
  Most likely origin is Python 3.14's own bundled TLS support, but this is
  not confirmed. Recorded as `NEEDS VERIFICATION` (provenance only — the
  license itself is not in doubt).

## 10. Legal-Readiness Matrix

| Component | Redistributed? | License verified? | Notice included? | Full text included? | Release status |
|---|---|---|---|---|---|
| ToroidAMP (own code) | Yes | Yes (MIT, own decision) | Yes (`LICENSE`) | Yes | **READY** |
| Python 3.14 | Yes | Yes (PSF) | Yes | Yes | **READY** |
| PySide6 / Qt6 6.11.2 | Yes (DLLs, dynamic-linked) | Yes (LGPL-3.0-only) | Yes | **No — reference/URL only** | **ACTION REQUIRED** |
| NumPy 2.5.2 | Yes | Yes (BSD-3-Clause) | Yes | Yes | **READY** |
| pygame-ce 2.5.8 | Yes | Yes (LGPL v2.1) | Yes | Yes | **READY** |
| SDL2 core | Yes (bundled by pygame-ce) | Yes (zlib) | Yes | Yes | **READY** |
| SDL2_image/mixer/ttf codec helpers (libjpeg, libpng, libtiff, libwebp, libogg, libopus, libwavpack, FreeType) | Yes (bundled) | Established upstream, not individually re-verified this cut | Yes (grouped) | No (grouped, not itemized) | **NEEDS VERIFICATION** |
| soundfile 0.14.0 | Yes | Yes (BSD-3-Clause) | Yes | Yes | **READY** |
| libsndfile (bundled) | Yes | Yes (LGPL v2.1) | Yes | Yes | **READY** |
| sounddevice 0.5.6 | Yes | Yes (MIT) | Yes | Yes | **READY** |
| PortAudio (bundled) | Yes | Yes (MIT-style) | Yes | Yes | **READY** |
| libxmp 4.6.3 | Yes | Yes (permissive family, re-verified this cut, post-LGPL-removal) | Yes | Yes | **READY** |
| pyttsx3 2.99 | Yes | Yes (MPL-2.0) | Yes | Yes | **READY** |
| pywin32 312 | Yes | Yes (PSF-derived) | Yes | Yes | **READY** |
| comtypes 1.4.16 | Yes | Yes (MIT) | Yes | Yes | **READY** |
| Quantum font (CYBER YELLOW theme) | Yes | Yes (SIL OFL 1.1) | Yes | Yes | **READY** |
| Branding icon / GPU texture / theme chrome images / official `.frag` shaders | Yes | Yes (original ToroidAMP work) | Yes (N/A — no third-party license applies) | N/A | **READY** |
| PyInstaller 6.22.2 | **No** (build tool only, never in `dist/`) | Yes (GPL-2.0-or-later + bootloader exception) | Yes (reference only) | Reference only | **NOT REDISTRIBUTED** |
| OpenSSL (`libcrypto`/`libssl` DLLs) | Yes | Yes (Apache-2.0) — **provenance unconfirmed** | Yes | No | **NEEDS VERIFICATION** |

**Two items must be resolved before a public release**, in priority order:

1. **ACTION REQUIRED** — embed the full canonical LGPL-3.0 text into
   `licenses/Qt-PySide6-LGPL-3.0.txt` (fetch verbatim from
   `https://www.gnu.org/licenses/lgpl-3.0.txt`; do not transcribe from
   memory).
2. **NEEDS VERIFICATION** — trace the OpenSSL DLL provenance and confirm/
   correct its listing; individually verify the SDL2 helper codec
   libraries' exact license texts.

## 11. Asset / Shader Provenance Audit

Every asset actually shipped in the distributed product was checked at
the source, not assumed:

- **Official GPU shaders** (`src/toroidamp/assets/official_shaders/*.frag`
  — `audio_reactive_reference.frag`, `cyber_bloom.frag`,
  `minimal_reference.frag`, `toroid_identity.frag`): all four carry their
  own `Author:` header comments identifying them as original ToroidAMP/
  team work (`ToroidAMP Team`; `Jack (Demoscene Visual Engineer) &
  ToroidAMP Team`; `Jack ... & Metal (ToroidAMP)`). Three of the four
  additionally carry an explicit `License: MIT` header line in their own
  source. **No Shadertoy-derived or externally-authored shader content is
  part of the distributed official set.** This was checked directly
  rather than assumed from "shaders commonly get adapted from Shadertoy"
  — per the mission's explicit instruction not to assume public
  availability implies redistribution rights.
- **Branding/theme images, GPU texture assets**: no external attribution
  found in `docs/branding/001_application_icon_identity.md` or anywhere
  else in the repository; consistent with original ToroidAMP creative
  material.
- **Quantum font** (CYBER YELLOW theme,
  `src/toroidamp/assets/themes/cyber_yellow/fonts/`): genuine third-party
  asset. `license.txt`/`readme.txt` in that directory identify it as
  created by **Alexandros Tsitlakidis** via **Fontstruct** ("TK Greko"),
  under the **SIL Open Font License 1.1**, which explicitly permits
  bundling and redistribution with software. Copied verbatim to
  `licenses/Quantum-font-OFL-1.1.txt`.
- **User-loadable shaders** (via Shader LAB's LOAD, or `user_shaders/`):
  explicitly **not** part of ToroidAMP's distributed product merely
  because the LAB can load them — no license claim is made or needed for
  content a user supplies themselves.
- **No release blockers found** in this category — the one genuine
  third-party asset (Quantum font) has clean, explicit,
  redistribution-permitting licensing, and all official shaders/images
  are confirmed original work.

## 12. `THIRD_PARTY_NOTICES.md` Structure

Root-level file, organized by subsystem: Core Runtime, Visualizer/Media
Engine, Audio Playback (Conventional), Audio Playback (Tracker), Voice
(SAPI5), Bundled Assets, Build-Time-Only Tool (explicitly separated,
explicitly not part of the distributed product), Additional Native
Libraries (the OpenSSL open item). Each entry: Component, Version,
Purpose, License, and a link to its full text in `licenses/`. Closes with
an explicit "not a legal guarantee" disclaimer pointing back to this
document and its matrix.

## 13. `licenses/` Structure

15 files, root `licenses/` directory — see the Legal-Readiness Matrix
(§10) for exactly which are complete canonical texts versus reference/
status files. Every file is either a byte-for-byte copy of a real license
file shipped by the actual installed package (or, for libxmp/PortAudio/
SDL2, verbatim text fetched live from the authoritative upstream source
this cut and reproduced with a provenance header), or — for the one
incomplete item (Qt/PySide6 LGPL-3.0) — an honest reference file rather
than a risked, from-memory reconstruction of a ~7000-word legal text.

## 14. `CHANGELOG.md` Design

Single `[Unreleased]` section (0.69 has not shipped), Keep-a-Changelog-
inspired categories (Added / Changed / Fixed / Known Limitations),
summarizing the full accumulated user-visible feature set from the
session to date at a capability level (core player, audio formats,
playlist, visualizers, Shader LAB, safe const promotion, runtime literal
parameterization, MUSICALIZE, AUTO REACT, themes, persistent logging,
packaging, MIT licensing) — deliberately not a log of individual internal
GPU-AUDIO-00X/RC-069-00X cuts. Known Limitations section is explicit about
tracker seek being approximate and S3M real-fixture validation still
being pending (no `.s3m` test file has been available in this
environment).

## 15. `HOWTOUSE.md` Design

Twelve numbered sections (Getting Started through Troubleshooting)
targeted at a first-time end user with no source checkout — plain
language throughout, e.g. MUSICALIZE is explained as "picks a small,
bounded set of parameters and assigns each one a conservative audio
binding automatically," not in terms of its internal implementation.
Followed by a consolidated **Validation / Self-Test Checklist** (Basic
Playback, Tracker, Reactivity, RETINA, Shader LAB Parameter, MUSICALIZE,
External Shader, Theme, Frozen Build test groups) rewritten from the
durable HUMAN test protocols previously scattered across the
GPU-AUDIO-003/004/005/006B and RC-069-002B/003 design docs, and a short,
clearly-separated **Developer Validation** section using only commands
already confirmed to exist in this repository (`pytest tests/test_<name>.py
-q`, `pyinstaller packaging/toroidamp.spec --noconfirm`) — no invented
commands.

## 16. README Alignment

Focused edits only, no rewrite:

1. Added a license/docs link line under the title (MIT / HOWTOUSE /
   CHANGELOG / THIRD_PARTY_NOTICES).
2. Corrected the decoding-backend description (removed a stale
   `miniaudio` mention; now correctly says `soundfile` (libsndfile)).
3. Added one paragraph after the Shader Lab section introducing safe
   const promotion, runtime literal parameterization, and MUSICALIZE/
   CLEAR AUTO, linking to HOWTOUSE.md for the full walkthrough.
4. Replaced the stale `## 11. Development & Testing` code fence (which
   referenced a `py -3.13 -m unittest discover -s tests` invocation not
   actually used by this project's current per-file pytest convention)
   with a pointer to HOWTOUSE.md's Validation/Self-Test Checklist and
   Developer Validation sections.

## 17. Packaging License Inclusion

`packaging/toroidamp.spec` was extended with an explicit `_RELEASE_DOCS`
block (inserted after `collect_data_files("toroidamp")`, before the
version-metadata `copy_metadata` call) that walks and bundles `LICENSE`,
`THIRD_PARTY_NOTICES.md`, `HOWTOUSE.md`, `CHANGELOG.md`, and the entire
`licenses/` directory into the frozen build's `_internal/` folder.
CHANGELOG was included (small, and directly useful to an end user
checking what changed) rather than left checkout-only; developer-only
material (`docs/`, `tests/`, `experiments/`) is deliberately **not**
collected.

Verified via a real rebuild:

```bash
rm -rf build dist && pyinstaller packaging/toroidamp.spec --noconfirm
```

Confirmed `dist/ToroidAMP/_internal/` contains `LICENSE`,
`THIRD_PARTY_NOTICES.md`, `HOWTOUSE.md`, `CHANGELOG.md`, and all 15 files
under `_internal/licenses/`. Frozen size: **~198MB** (unchanged from
RC-069-003 — no size optimization was attempted, per the mission's
explicit non-goal).

A live relaunch-and-verify smoke test was then performed against the
rebuilt `ToroidAMP.exe` (fresh log file, launched from `dist/ToroidAMP/`,
process confirmed running via `Get-Process`, then cleanly stopped). The
resulting log tail showed an identical-to-RC-069-003 clean startup
sequence: version 0.3.1 correctly resolved, session loaded from the
correct AppData path, both theme QSS files loaded, Quantum font
registered, tray icon created, WindowManager initialized, and the startup
voice line genuinely announced via pyttsx3/SAPI5. This confirms the
spec-file change to bundle release documentation introduced **no runtime
behavior change** — the automated check for this (test #10/#11 in
`tests/test_rc_069_003b.py`) validates the spec's static content; this
manual relaunch is what actually validates runtime behavior stayed
identical.

## 18. Automated Tests

`tests/test_rc_069_003b.py` — 12 tests (30 subtests), all passing:

1. LICENSE contains the canonical MIT grant.
2. `THIRD_PARTY_NOTICES.md` exists and is substantive.
3. `licenses/` directory exists with all 15 expected files.
4. README references MIT and links `LICENSE`.
5. README links `HOWTOUSE.md`.
6. README links `CHANGELOG.md`.
7. README links `THIRD_PARTY_NOTICES.md`.
8. `HOWTOUSE.md` contains the Validation/Self-Test Checklist and Developer
   Validation sections.
9. `CHANGELOG.md` contains the `[Unreleased]` pre-release structure.
10. `packaging/toroidamp.spec` collects the release docs (`_RELEASE_DOCS`
    block + each expected file/dir reference).
11. `pyproject.toml` declares `license = "MIT"` / `license-files` cleanly,
    without the classifier that previously broke installation.
12. All 15 required license text files are present and non-trivially
    sized (> 50 bytes).

**These are presence/structure checks, not proof of legal compliance** —
this is stated explicitly in both the test file's docstring and
`THIRD_PARTY_NOTICES.md` itself, per the mission's explicit instruction
not to overstate what automated checks can prove.

Full regression run (per-file, this repository's established convention
— the whole suite in one process triggers an unrelated native GL
resource-accumulation artifact, not a logic bug): **all pre-existing test
files pass**, except `tests/test_ux_004.py`, which shows 3 pre-existing
failures (`TestMarqueeLabel`, `TestMarqueeTravelAmplitude`,
`TestNormalMarqueeInRealLayout` — all font-metrics/overflow measurement
assertions on a marquee text widget). **This failure is unrelated to
RC-069-003B**: none of the files modified or created in this cut touch
UI, font, or marquee code (the only files touched are `LICENSE`,
`pyproject.toml`, `licenses/`, `THIRD_PARTY_NOTICES.md`, `CHANGELOG.md`,
`HOWTOUSE.md`, `README.md`, `packaging/toroidamp.spec`, and
`tests/test_rc_069_003b.py`). Most likely explanation is
environment-dependent font-metrics/DPI sensitivity in this development
machine's font substitution behavior, not a regression this cut
introduced. Flagged here rather than silently ignored, and left for a
separate, correctly-scoped cut to investigate (out of scope for a
licensing/documentation closure mission with an explicit no-runtime-
change constraint).

## 19. `docs/CURRENT_STATE.md` Policy Decision

**NOT_REQUIRED.** Consistent with RC-069-001/002/003's precedent: this cut
adds licensing and user-facing documentation and does not change
ToroidAMP's architecture, phase status, runtime behavior, or any
previously-recorded architectural decision. `CURRENT_STATE.md` exists to
track current-truth-affecting operational/architectural state; a
LICENSE/docs closure pass does not affect that state.

## 20. Human Gate Protocol

The following should be manually reviewed by Metal before this is
considered release-ready:

- **TEST A — LICENSE**: Open `LICENSE`. Confirm it reads as a complete,
  unmodified MIT license with the correct copyright line, and that this
  matches your intent.
- **TEST B — THIRD PARTY**: Open `THIRD_PARTY_NOTICES.md`. Confirm the
  component list matches your understanding of what ToroidAMP actually
  ships, and that the two open items (Qt/PySide6 LGPL text, OpenSSL
  provenance) are acceptable to leave open for this cut versus needing
  immediate resolution.
- **TEST C — LICENSE TEXTS**: Spot-check a few files under `licenses/`
  (recommended: `libxmp.txt`, `Qt-PySide6-LGPL-3.0.txt`,
  `pygame-ce-LGPL-2.1.txt`) to confirm the provenance notes read clearly
  and the texts look correct.
- **TEST D — ASSETS/SHADERS**: Confirm the official-shader and
  branding-asset provenance conclusions in §11 match your own knowledge
  of how those assets were created.
- **TEST E — HOWTOUSE**: Read `HOWTOUSE.md` as if you were a brand-new
  user. Confirm the MUSICALIZE/Shader LAB explanations are understandable
  without implementation knowledge, and that the Validation/Self-Test
  Checklist would actually catch a regression you care about.
- **TEST F — CHANGELOG**: Confirm `CHANGELOG.md`'s Known Limitations
  section is honest and nothing there should already have been fixed.

## 21. Unresolved Items Carried Forward

1. `licenses/Qt-PySide6-LGPL-3.0.txt` needs the full canonical LGPL-3.0
   text fetched from `https://www.gnu.org/licenses/lgpl-3.0.txt` and
   substituted for the current reference-only content.
2. OpenSSL DLL provenance in the frozen build is unconfirmed (license
   itself — Apache-2.0 — is not in doubt).
3. SDL2_image/mixer/ttf's individual bundled codec-helper libraries
   (libjpeg, libpng, libtiff, libwebp, libogg, libopus, libwavpack,
   FreeType) have not been individually re-verified this cut.
4. `test_ux_004.py`'s 3 pre-existing marquee-measurement failures (§18)
   are unrelated to this cut but remain unresolved and should be
   triaged separately.
