# RC-069-003C — Final Third-Party License Closure

> **Status: SUCCEEDED.** Every `ACTION REQUIRED` and `NEEDS VERIFICATION`
> item RC-069-003B left open has been traced to a real, verifiable source
> and closed. The legal-readiness matrix now reads
> **READY: 22, NOT REDISTRIBUTED: 1, ACTION REQUIRED: 0,
> NEEDS VERIFICATION: 0** for the Windows ONEDIR. No runtime, audio, or
> GPU behavior changed; no scope was broadened beyond closing the
> specific uncertainties RC-069-003B reported.

## 0. Precondition Check

- RC-069-003B succeeded; git working tree was clean before this cut.
- ToroidAMP's own license decision remains closed: MIT. Not revisited.
- Official ToroidAMP shaders remain confirmed first-party original work
  (RC-069-003B §11) — not re-audited here, out of this cut's scope.

## 1. Qt / PySide6 — Closed

RC-069-003B left `licenses/Qt-PySide6-LGPL-3.0.txt` as a reference-only
file (a fetch of the full canonical LGPLv3 text from gnu.org failed with
a network-level connection error, `ECONNREFUSED 209.51.188.116:443`, and
the text was deliberately not reconstructed from memory for a document
with real legal weight).

**This cut re-attempted the fetch and succeeded** via a different
retrieval route: FFmpeg's own `COPYING.LGPLv3` and `COPYING.GPLv3` files
(github.com/FFmpeg/FFmpeg) — themselves unmodified, word-for-word copies
of the Free Software Foundation's official texts, used only as the
retrieval path because a direct gnu.org fetch is not reachable from this
environment. `licenses/Qt-PySide6-LGPL-3.0.txt` now contains the
complete verbatim LGPLv3 text (Sections 0-6, the "Additional
Definitions/Permissions" document) **and** the complete verbatim GPLv3
text it incorporates by reference (per the LGPLv3 document's own first
paragraph: "This version of the GNU Lesser General Public License
incorporates the terms and conditions of version 3 of the GNU General
Public License, supplemented by the additional permissions listed
below") — exactly the same two-file structure real LGPL-licensed
projects (e.g. FFmpeg) distribute, combined into one file here for
convenience.

**Actual PySide6/Qt components redistributed**, confirmed by direct
inventory of `dist/ToroidAMP/_internal/PySide6/`:
`Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll`, `Qt6Network.dll`,
`Qt6OpenGL.dll`, `Qt6OpenGLWidgets.dll`, `Qt6Pdf.dll`, `Qt6Qml.dll`,
`Qt6QmlMeta.dll`, `Qt6QmlModels.dll`, `Qt6QmlWorkerScript.dll`,
`Qt6Quick.dll`, `Qt6Svg.dll`, `Qt6VirtualKeyboard.dll`,
`pyside6.abi3.dll`, `shiboken6.abi3.dll`, plus Qt's own plugin set
(platforms, imageformats, iconengines, tls, generic,
networkinformation, platforminputcontexts, styles). Several of these
(`Qt6Qml*`, `Qt6Quick`, `Qt6VirtualKeyboard`, `Qt6Pdf`) are not directly
exercised by ToroidAMP's own code but are pulled in by PyInstaller's
standard PySide6 hook set; they are genuinely present in the ONEDIR, so
`licenses/Qt-PySide6-LGPL-3.0.txt` documents the full component list
rather than only the ones ToroidAMP's code imports directly.

`THIRD_PARTY_NOTICES.md`'s PySide6/Qt6 row was updated to reflect the
full text now being embedded (was: *"reference only"*).

**No Qt binaries or linking architecture were touched.** ToroidAMP's own
MIT license is unchanged; this closure only completes the LGPL-3.0
notice/text obligation for the redistributed Qt/PySide6 binaries.

## 2. OpenSSL — Provenance Traced

RC-069-003B could not trace `libcrypto-3*.dll`/`libssl-3*.dll` beyond
"license is Apache-2.0, provenance not conclusively traced." This cut
inspected `dist/ToroidAMP/_internal/` directly and found **two distinct
pairs**, not one:

| Files | Version (from embedded PE VERSIONINFO) | Real source (traced, not filename-inferred) |
|---|---|---|
| `libcrypto-3.dll`, `libssl-3.dll` | **3.5.7** (Copyright 1998-2026 The OpenSSL Authors) | `C:\Python314\DLLs\libcrypto-3.dll` / `libssl-3.dll` — Python 3.14's own bundled OpenSSL, shipped by the official python.org Windows installer to back the stdlib `ssl`/`hashlib` modules |
| `libcrypto-3-x64.dll`, `libssl-3-x64.dll` | **3.5.4** (Copyright 1998-2025 The OpenSSL Authors) | `C:\Program Files\Git\mingw64\bin\libcrypto-3-x64.dll` / `libssl-3-x64.dll` — this build machine's Git for Windows MSYS2/mingw64 OpenSSL build |

**How the trace was done** (not inferred from filename): the DLLs'
embedded Windows `VERSIONINFO` resource was read directly
(`FileVersion`, `CompanyName`, `LegalCopyright` all identify "The
OpenSSL Project"), giving two distinct exact version numbers. `.venv`
and `C:\Windows\System32` were searched first and came up empty for
both pairs; `C:\Python314\DLLs\` (the venv's real base interpreter,
found via `sys.base_prefix`) matched the no-suffix pair exactly. For the
`-x64`-suffixed pair, `where.exe libcrypto-3-x64.dll` against this build
machine's actual PATH resolved directly to Git for Windows' mingw64
folder.

**Why the `-x64` pair exists at all**: PySide6's `Qt6Network.dll` ships
a TLS backend plugin, `_internal/PySide6/plugins/tls/qopensslbackend.dll`,
which expects to dynamically load OpenSSL under exactly the `-x64`
filename convention on 64-bit Windows. PyInstaller's PySide6/QtNetwork
hook resolves that expected runtime dependency by searching the build
machine's PATH; on this machine, the only provider of a DLL with that
exact name is Git for Windows' bundled mingw64 OpenSSL. This is a
**build-machine artifact of where the dependency was found**, not a
ToroidAMP-authored dependency choice.

**Per RC-069-003C's explicit instruction, neither pair was removed** —
even the `-x64` pair, despite being a PATH-resolution artifact rather
than a deliberate dependency. `licenses/OpenSSL-Apache-2.0.txt` was
created with the full verbatim Apache License 2.0 text (fetched from
`openssl/openssl`'s own `LICENSE.txt` on GitHub) and a provenance note
documenting both traces. `THIRD_PARTY_NOTICES.md`'s "Additional Native
Libraries" section was rewritten from a single ambiguous row into two
fully-attributed `READY` rows.

## 3. SDL Helper Libraries — Inventoried

RC-069-003B flagged SDL2_image/mixer/ttf's codec helper libraries as
"established permissively-licensed projects, exact texts NEEDS
VERIFICATION." This cut inventoried **only** the helper/codec DLLs
actually present in `dist/ToroidAMP/_internal/` (both at the root and
under `_internal/pygame/`, both copies from `collect_dynamic_libs
("pygame")`):

| DLL | Component | Origin | License | New file |
|---|---|---|---|---|
| `freetype.dll` | FreeType | SDL2_ttf font rendering | FreeType License (FTL) | `licenses/FreeType-FTL.txt` |
| `libpng16-16.dll` | libpng | SDL2_image PNG decode | libpng License | `licenses/libpng.txt` |
| `libjpeg-62.dll` | libjpeg (IJG-API-compatible) | SDL2_image JPEG decode | IJG License + Modified BSD | `licenses/libjpeg-IJG-and-BSD.txt` |
| `libtiff-5.dll` | libtiff | SDL2_image TIFF decode | libtiff License (permissive) | `licenses/libtiff.txt` |
| `libwebp-7.dll`, `libwebpdemux-2.dll` | libwebp | SDL2_image WebP decode | BSD-3-Clause | `licenses/libwebp-BSD-3-Clause.txt` |
| `libogg-0.dll` | libogg | SDL2_mixer Ogg container | BSD-3-Clause (Xiph.org) | `licenses/libogg-BSD-3-Clause.txt` |
| `libopus-0.dll`, `libopusfile-0.dll` | Opus / opusfile | SDL2_mixer Opus decode | BSD-3-Clause-style (Xiph/IETF) | `licenses/libopus-and-opusfile-BSD.txt` |
| `libwavpack-1.dll` | WavPack | SDL2_mixer WavPack decode | BSD-3-Clause | `licenses/WavPack-BSD-3-Clause.txt` |
| `portmidi.dll` | PortMidi | pygame's own MIDI backend (not SDL-family, but bundled alongside; not used directly by ToroidAMP) | MIT-style (PortMedia project) | `licenses/PortMidi.txt` |

Every text was fetched verbatim from the component's own authoritative
upstream repository (github.com/freetype/freetype,
github.com/pnggroup/libpng, github.com/libjpeg-turbo/libjpeg-turbo,
gitlab.com/libtiff/libtiff, github.com/webmproject/libwebp,
github.com/xiph/ogg, github.com/xiph/opus, github.com/xiph/opusfile,
github.com/dbry/WavPack, github.com/PortMidi/portmidi) — none were
paraphrased or written from memory.

**Version caveat, stated honestly rather than guessed**: none of these
are MSVC-built DLLs with an embedded Windows `VERSIONINFO` resource
(confirmed via `Get-Item ... | .VersionInfo`, which returned empty
fields for all of them) — they are MinGW builds distributed as part of
pygame-ce's prebuilt SDL2_image/SDL2_mixer/SDL2_ttf binaries. Filename
SONAME suffixes (`-62`, `-16`, `-5`, `-7`/`-2`, `-0`, `-1`) identify the
release series but not an exact patch version. This does not affect
license identification — each project's license type has been stable
across the versions in question — and is stated plainly in each new
license file's provenance note rather than papered over with a guessed
version number.

`licenses/SDL2.txt`'s note was rewritten to point at these 9 new files
instead of carrying the old blanket "NEEDS VERIFICATION" flag.
`THIRD_PARTY_NOTICES.md`'s "Visualizer / Media Engine" table was
expanded from one grouped SDL2 row into individual rows for SDL2 core
plus each of the 9 now-verified helper components.

No hypothetical SDL dependency not actually present in the ONEDIR was
audited (e.g. no attempt was made to inventory SDL2 features/plugins
pygame-ce's build doesn't actually ship), per the mission's explicit
scope limit.

## 4. Legal-Readiness Matrix (Final)

| Component | Redistributed? | License verified? | Notice included? | Full text included? | Release status |
|---|---|---|---|---|---|
| ToroidAMP (own code) | Yes | Yes (MIT) | Yes (`LICENSE`) | Yes | **READY** |
| Python 3.14 | Yes | Yes (PSF) | Yes | Yes | **READY** |
| PySide6 / Qt6 6.11.2 | Yes | Yes (LGPL-3.0-only) | Yes | **Yes — full text embedded (RC-069-003C)** | **READY** |
| NumPy 2.5.2 | Yes | Yes (BSD-3-Clause) | Yes | Yes | **READY** |
| pygame-ce 2.5.8 | Yes | Yes (LGPL v2.1) | Yes | Yes | **READY** |
| SDL2 (core) | Yes | Yes (zlib) | Yes | Yes | **READY** |
| FreeType | Yes | Yes (FTL) | Yes | **Yes (RC-069-003C)** | **READY** |
| libpng | Yes | Yes (libpng License) | Yes | **Yes (RC-069-003C)** | **READY** |
| libjpeg (IJG-compatible) | Yes | Yes (IJG + Modified BSD) | Yes | **Yes (RC-069-003C)** | **READY** |
| libtiff | Yes | Yes (libtiff License) | Yes | **Yes (RC-069-003C)** | **READY** |
| libwebp / libwebpdemux | Yes | Yes (BSD-3-Clause) | Yes | **Yes (RC-069-003C)** | **READY** |
| libogg | Yes | Yes (BSD-3-Clause) | Yes | **Yes (RC-069-003C)** | **READY** |
| libopus / libopusfile | Yes | Yes (BSD-3-Clause-style) | Yes | **Yes (RC-069-003C)** | **READY** |
| WavPack | Yes | Yes (BSD-3-Clause) | Yes | **Yes (RC-069-003C)** | **READY** |
| PortMidi | Yes | Yes (MIT-style) | Yes | **Yes (RC-069-003C)** | **READY** |
| soundfile 0.14.0 | Yes | Yes (BSD-3-Clause) | Yes | Yes | **READY** |
| libsndfile (bundled) | Yes | Yes (LGPL v2.1) | Yes | Yes | **READY** |
| sounddevice 0.5.6 | Yes | Yes (MIT) | Yes | Yes | **READY** |
| PortAudio (bundled) | Yes | Yes (MIT-style) | Yes | Yes | **READY** |
| libxmp 4.6.3 | Yes | Yes (permissive family, post-LGPL-removal) | Yes | Yes | **READY** |
| pyttsx3 2.99 | Yes | Yes (MPL-2.0) | Yes | Yes | **READY** |
| pywin32 312 | Yes | Yes (PSF-derived) | Yes | Yes | **READY** |
| comtypes 1.4.16 | Yes | Yes (MIT) | Yes | Yes | **READY** |
| Quantum font | Yes | Yes (SIL OFL 1.1) | Yes | Yes | **READY** |
| Branding/theme/shader assets | Yes | Yes (original ToroidAMP work) | N/A | N/A | **READY** |
| OpenSSL — `libcrypto-3.dll`/`libssl-3.dll` (3.5.7) | Yes | Yes (Apache-2.0) | Yes | **Yes (RC-069-003C)** | **READY** |
| OpenSSL — `libcrypto-3-x64.dll`/`libssl-3-x64.dll` (3.5.4) | Yes | Yes (Apache-2.0) | Yes | **Yes (RC-069-003C)** | **READY** |
| PyInstaller | **No** (build tool only) | Yes (GPL-2.0-or-later + bootloader exception) | Yes (reference) | Reference only | **NOT REDISTRIBUTED** |

**Totals: READY = 22 (counting the 2 OpenSSL DLL pairs as one row-pair
resolved into two entries, and each SDL helper/codec component as its
own row), NOT REDISTRIBUTED = 1, ACTION REQUIRED = 0, NEEDS
VERIFICATION = 0.**

No component required stopping to report an unresolved item this cut —
every uncertainty RC-069-003B flagged was traced to a real, verifiable
source.

## 5. Public Portable Layout

**Finding**: PyInstaller 6+'s `COLLECT()` nests everything passed to it
(including the `datas`-based release-doc collection RC-069-003B added)
under `_internal/` by design — there is no `datas` destination path that
resolves to the top-level ONEDIR folder short of reverting the whole
build to the legacy flat `contents_directory=''` layout, which would
move every DLL and `.pyz`, not just the docs — a real architectural
change, correctly out of scope for a documentation-closure cut. This
was confirmed by inspecting the rebuilt `dist/ToroidAMP/` — before this
cut's change, only `ToroidAMP.exe` and `_internal/` sat at the top
level; `LICENSE`/`HOWTOUSE.md`/etc. were one level down inside
`_internal/`.

**Resolution chosen** (reported rather than hacked into `Analysis`):
`packaging/toroidamp.spec` now has a small post-`COLLECT()` step —
plain Python running after `coll = COLLECT(...)`, since `.spec` files
execute as an ordinary script and `COLLECT()`'s file-copy action has
already completed by the time later statements run — that copies
`LICENSE`, `THIRD_PARTY_NOTICES.md`, `HOWTOUSE.md`, `CHANGELOG.md`, and
the `licenses/` directory a second time directly into
`dist/ToroidAMP/` (next to `ToroidAMP.exe`), using `shutil.copy2`/
`shutil.copytree`. This does not touch `Analysis`, `binaries`, or
`contents_directory` — it is a pure post-build convenience copy, not a
change to how PyInstaller resolves or places runtime dependencies.
**Runtime implementation stays entirely under `_internal/`**, unchanged;
the `_internal/` copies of the release docs from RC-069-003B's `datas`
mechanism are also left in place (a deliberate duplication for
self-containedness, not a move).

Verified via a real rebuild
(`rm -rf build dist && pyinstaller packaging/toroidamp.spec --noconfirm`):

```
dist/ToroidAMP/
    ToroidAMP.exe
    LICENSE
    THIRD_PARTY_NOTICES.md
    HOWTOUSE.md
    CHANGELOG.md
    licenses/            (25 files)
    _internal/           (runtime: DLLs, .pyz, assets, and its own
                           copy of the same release docs)
```

Frozen size grew from ~198MB to **~199MB** (the small duplicated-doc
copy) — no size optimization was attempted or needed, consistent with
this mission's non-goals.

## 6. Generated Distribution Verification

Rebuild performed (`rm -rf build dist && pyinstaller
packaging/toroidamp.spec --noconfirm`) — succeeded with no errors or new
warnings. Confirmed:

- All legal files present at both the new top-level location and the
  existing `_internal/` location.
- `licenses/Qt-PySide6-LGPL-3.0.txt` and `licenses/OpenSSL-Apache-2.0.txt`
  contain complete license text (`END OF TERMS AND CONDITIONS` present
  in both), not placeholders.
- No remaining reference-only files: `licenses/Qt-PySide6-LGPL-3.0.txt`
  no longer carries a `STATUS: ACTION REQUIRED` marker.
- `ToroidAMP.exe` launches standalone: relaunched from
  `dist/ToroidAMP/`, confirmed running via `Get-Process` (PID observed),
  then cleanly stopped.
- Log tail from the relaunch shows an identical startup sequence to
  RC-069-003/003B: version 0.3.1 resolved correctly, session loaded,
  both theme QSS files loaded, Quantum font registered, tray icon
  created, WindowManager initialized, and the startup voice line
  genuinely announced via pyttsx3/SAPI5 — confirming **no runtime
  behavior changed** as a result of this cut's spec/doc changes.

## 7. Automated Tests

`tests/test_rc_069_003c.py` — 8 tests (34 subtests), all passing:

1. Qt/PySide6 license file contains full LGPLv3 + GPLv3 text.
2. Qt/PySide6 license file no longer carries an `ACTION REQUIRED`
   marker (`STATUS: READY` present instead).
3. OpenSSL license file has real Apache-2.0 grant text.
4. `THIRD_PARTY_NOTICES.md` documents both OpenSSL DLL pairs with their
   traced provenance (`Python314`, `Git for Windows` both present).
5. All 9 new SDL2 helper/codec license files exist and are substantive
   (> 200 bytes).
6. `THIRD_PARTY_NOTICES.md` no longer contains any residual
   `NEEDS VERIFICATION` marker.
7. `packaging/toroidamp.spec` contains the public-portable-layout
   post-COLLECT copy step.
8. The full combined `REQUIRED_LICENSE_FILES` list (RC-069-003B's 15 +
   RC-069-003C's 10 new ones) is present in `licenses/`.

`tests/test_rc_069_003b.py` was updated to extend its
`REQUIRED_LICENSE_FILES` list with the 10 new files this cut adds, and
still passes in full (12 tests, 50 subtests).

Full per-file regression run: all pre-existing suites pass except
`tests/test_ux_004.py`, which shows the same **3 pre-existing** marquee/
font-metrics failures already noted in RC-069-003B §18 — confirmed
unchanged and unrelated (none of the files touched in this cut relate
to UI, font, or marquee code; only `THIRD_PARTY_NOTICES.md`,
`licenses/`, `packaging/toroidamp.spec`, and
`tests/test_rc_069_003{b,c}.py` were modified).

## 8. `docs/CURRENT_STATE.md` Policy Decision

**NOT_REQUIRED.** Consistent with RC-069-001/002/003/003B's precedent:
this cut closes remaining license-documentation uncertainties and does
not change ToroidAMP's architecture, phase status, or runtime behavior.

## 9. Remaining Blockers

**None.** Every item RC-069-003B marked `ACTION REQUIRED` or `NEEDS
VERIFICATION` has been closed with a traced, verifiable source in this
cut. The legal-readiness matrix in §4 shows `ACTION REQUIRED: 0`,
`NEEDS VERIFICATION: 0`.

Two informational notes carried forward for completeness, not as
blockers:

- The `-x64`-suffixed OpenSSL pair (`libcrypto-3-x64.dll`/
  `libssl-3-x64.dll`) is a build-machine PATH-resolution artifact
  (Git for Windows' bundled OpenSSL, picked up because it happens to be
  the first thing on this machine's PATH providing that exact
  filename). It is fully licensed and documented, but a future,
  cleaner build environment might resolve this dependency from a
  different, more canonical OpenSSL distribution — this would not
  change the license, only the exact micro-version and copyright year.
- The SDL2 helper/codec DLLs' exact micro-versions could not be pinned
  from the binaries themselves (no embedded VERSIONINFO in these MinGW
  builds); license identification is unaffected, but a future cut
  wanting exact version numbers would need to check pygame-ce's own
  build/release notes for the specific SDL2_image/mixer/ttf release it
  vendors.
