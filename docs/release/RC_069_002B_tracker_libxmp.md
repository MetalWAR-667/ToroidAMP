# RC-069-002B — Tracker Backend Feasibility & Migration: libmodplug → libxmp

> **Status: MIGRATION SUCCEEDED.** `TrackerDecoder.is_available()` is now
> `True` in this development environment for the first time this entire
> session. Real MOD/XM/IT files decode, play, seek, and feed the unchanged
> `AnalysisHandoff`/`AudioFrame` reactivity pipeline correctly. S3M is
> architecturally identical but untested — no real S3M fixture was
> available anywhere in this environment (honestly reported, not faked).

## 1. The libmodplug Blocker (context)

RC-069-001 found `TrackerDecoder.is_available()` returned `False`.
RC-069-002 confirmed the root cause precisely: `libmodplug-1.dll`/
`libmodplug.dll` do not exist anywhere reasonably searchable on this
machine, but `pygame-ce` — an existing, required ToroidAMP dependency —
already bundles a *different* tracker library, `libxmp.dll`, which the
old code never looked for at all (wrong filename, and a structurally
incompatible C API even if it had).

## 2. Why libxmp Was Considered

It costs nothing to bundle — it already ships inside a dependency
ToroidAMP requires anyway (`pygame-ce`). Migrating removes the need to
source, license-clear, and bundle an entirely separate native binary
(libmodplug), which RC-069-002 left as an open, unresolved acquisition
problem. If libxmp can satisfy the same `TrackerDecoder` contract, this is
strictly simpler for both this cut and RC-069-003's packaging story.

## 3. Phase-0 Feasibility Audit — Answers

All ten questions were answered **empirically**, against the real,
installed `libxmp.dll` (version 4.6.3, confirmed via `xmp_version`/
`xmp_vercode` — see §4), using **real MOD/XM/IT tracker files** sourced
locally from the sibling `MetalWar-Installer` directory (never copied into
this repository), not synthetic buffers:

| # | Question | Answer |
|---|---|---|
| 1 | Can libxmp load MOD/XM/IT/S3M? | **Yes for MOD/XM/IT** (verified with 4 real files: 1 `.it`, 1 `.xm`, 2 `.mod`, all `xmp_load_module_from_memory` returning `0`). **S3M untested** — libxmp's public API (`xmp_get_format_list`) advertises S3M support and there is no code-level reason to doubt it, but no real `.s3m` file was found anywhere on this machine to prove it, and none was fabricated. |
| 2 | Can it render PCM continuously? | Yes — `xmp_play_buffer` called repeatedly in a loop produces continuous, real, non-silent audio across all 4 real files tested. |
| 3 | Can output be configured to 44100 Hz stereo? | Yes — `xmp_start_player(ctx, 44100, 0)` returned `0` (success) for every file; format flag `0` is libxmp's own documented default (16-bit signed stereo). |
| 4 | What PCM sample format does it produce? | **Signed 16-bit interleaved stereo** — confirmed directly by viewing the raw output buffer as `numpy.int16` and observing plausible, varied, non-degenerate audio sample values. |
| 5 | Can it seek by time sufficiently? | Yes, via `xmp_seek_time(ctx, ms)` — **pattern/row-granular, not sample-accurate** (a seek to 60000ms landed real playback at ~53904ms in one real test — see §8). Documented as an explicit, isolated limitation, not silently hidden. |
| 6 | Can duration be obtained reliably? | Yes — `xmp_get_frame_info`'s `total_time` field (ms), stable and consistent across repeated calls, matched a musically plausible ~3:21 runtime for the real `.it` file tested. |
| 7 | Can playback be restarted/reset cleanly? | Yes — `xmp_restart_module` confirmed to reset elapsed time back near zero; more generally, calling `load()` again on the *same* `TrackerDecoder` instance for a *different* file was also verified to work cleanly (§10) — the actual reuse pattern `PlayerEngine` needs. |
| 8 | Can the library be loaded reproducibly in dev and future frozen builds? | Yes in dev (confirmed). For frozen builds: same discovery strategy as before (search inside `pygame`'s own install directory first) — see §12 for the exact PyInstaller implication, carried into RC-069-003. |
| 9 | License/redistribution obligations? | See §13 — **not independently verified from a locally-available authoritative source in this pass**; reported honestly as a recalled-but-unconfirmed data point, not a legal guarantee. |
| 10 | Does migration reduce packaging complexity vs. introducing libmodplug? | **Yes, unambiguously** — libxmp requires bundling *zero* additional native binaries (it rides along with the already-required `pygame-ce` dependency); libmodplug would have required sourcing, vetting, and separately bundling an entirely new DLL from scratch (RC-069-002 left this as an open, unresolved BLOCKED acquisition problem). |

**No critical capability was found missing.** Migration proceeded.

## 4. A Real Bug Found and Fixed During This Audit

Before any of the above could be trusted, the very first attempt to call
`xmp_version()` and `xmp_vercode()` as ordinary C functions crashed with an
access violation. Direct inspection of the DLL's PE export table (a small
pure-Python export-directory parser was written for this, since no
`dumpbin`/`objdump`/`nm` were available in this environment) revealed why:
both symbols are **exported DATA variables** (`xmp_version` sits in
`.data`, `xmp_vercode` in `.rdata`), not functions — calling them jumped
into non-executable memory. Fixed by reading them as global variables
instead (`ctypes.c_char_p.in_dll(lib, "xmp_version")`), confirming
`version = "4.6.3"`. This is the same category of caution this session has
repeatedly needed for undocumented-locally native APIs — verify behavior,
don't assume signatures from memory.

## 5. Backend Discovery Strategy

```python
@staticmethod
def _discover_libxmp() -> str | None:
    # 1. Inside pygame's own install directory (Windows: libxmp.dll —
    #    where pygame-ce actually bundles it, confirmed directly).
    # 2. ctypes.util.find_library("xmp") — system-wide discovery.
    # 3. A short hardcoded fallback candidate list.
```

Identical *shape* to the prior libmodplug discovery (same three-tier
strategy, same "check inside pygame's own directory first" design intent
that no longer matched reality for libmodplug but does for libxmp) — only
the target filenames changed. No developer-machine-specific absolute path
is ever hardcoded. Safe across: a source checkout (confirmed), a normal
installed package (same mechanism, `pygame.__file__` resolves into
`site-packages` either way), and a future PyInstaller build (§12).

## 6. API Subset Used

Only the minimum surface needed — not a full library wrapper:

```text
xmp_create_context()                              -> ctx (opaque handle)
xmp_free_context(ctx)
xmp_load_module_from_memory(ctx, data, size)       -> int (0 = success)
xmp_release_module(ctx)
xmp_scan_module(ctx)                                -- populates accurate total_time
xmp_start_player(ctx, rate, format)                 -> int (0 = success; format=0 = default 16-bit signed stereo)
xmp_play_buffer(ctx, buf, buf_size_bytes, loop)     -> int (0 = ok; negative = EOF/error)
xmp_get_frame_info(ctx, info_buf)                   -- writes into an oversized raw buffer (see §7)
xmp_seek_time(ctx, ms)                              -> int (position index / error)
xmp_restart_module(ctx)
xmp_end_player(ctx)
```

Every ctypes `argtypes`/`restype` is set explicitly (`_bind_functions()`)
— no implicit conversions relied upon. `xmp_load_module_from_memory` was
deliberately chosen over `xmp_load_module` (a file-path-taking variant):
ToroidAMP reads the file itself via Python's own `open()` (correct,
native Unicode path handling) and hands libxmp only raw bytes, exactly
mirroring the prior libmodplug decoder's `ModPlug_Load(data, len(data))`
pattern and its reasoning — this sidesteps any native `char*`/codepage
path-encoding pitfall entirely, for any filename in any language.

## 7. `struct xmp_frame_info` — Empirically Verified, Not Assumed

ToroidAMP does not ship libxmp's header (`xmp.h`), so the struct's true
field layout was **derived empirically, not trusted from memory**, and the
implementation defends against getting it wrong:

1. **Oversized raw buffer**: `xmp_get_frame_info` is passed an 8192-byte
   raw `ctypes.create_string_buffer`, far larger than the true struct
   (a few hundred bytes even with a 64-entry channel-info array) — an
   incorrect assumed size can never overflow this buffer and corrupt
   memory.
2. **Only two fields are ever read**, both located and confirmed
   *behaviorally*, not by trusting an assumed field order alone:
   - **`time` at byte offset 28**: confirmed by observing it increase by
     ~1000-1012ms across 5 consecutive 1-second `xmp_play_buffer` calls —
     unambiguous, since no other plausible field would track elapsed
     playback time that precisely.
   - **`total_time` at byte offset 32**: confirmed by observing it stay
     *exactly constant* (200991, unchanged) across the same 5 calls, while
     matching a musically plausible ~3:21 duration for the real `.it` file
     under test.
3. Every other struct field (pos, pattern, row, bpm, buffer pointer,
   channel_info array, ...) is **never read** — not needed by
   ToroidAMP's minimal contract, and therefore never a source of risk even
   if their assumed positions were wrong.

## 8. Decoder Contract Mapping

`TrackerDecoder`'s public surface is **completely unchanged** — still
exactly `AudioDecoder`'s abstract contract
(`load`/`read_frames`/`seek`/`get_duration`/`get_title`/
`get_sample_rate`/`close`), and `PlayerEngine` was not taught anything
libxmp-specific (backend details stay entirely inside `TrackerDecoder`).
One internal constructor parameter was renamed for accuracy:
`PlayerEngine.__init__(..., custom_modplug_path=...)` →
`custom_tracker_lib_path=...` (verified unused anywhere outside
`player.py` itself before renaming — no public/test breakage).

| Method | libxmp mapping |
|---|---|
| `load(filepath)` | read bytes -> `xmp_load_module_from_memory` -> `xmp_scan_module` -> `xmp_start_player(44100, 0)` -> `xmp_get_frame_info` for `total_time` |
| `read_frames(n)` | `xmp_play_buffer(ctx, buf, n*4, loop=1)` -> reshape int16 interleaved -> float32 `/32768.0` |
| `seek(seconds)` | `xmp_seek_time(ctx, int(seconds*1000))` |
| `get_duration()` | cached `total_time/1000.0` from `load()` |
| `close()` | `xmp_end_player` -> `xmp_release_module` (keeps the context alive for reuse — see §9) |

## 9. Duration / Position Behavior

`total_time` (ms) is read **once**, immediately after `xmp_start_player` +
`xmp_scan_module`, and cached — it is static per module (confirmed:
identical across every subsequent `xmp_get_frame_info` call in testing),
so there is no need to re-query it per frame. No duration was ever faked
or estimated by ToroidAMP itself; if libxmp cannot determine one, this
would surface as `0.0` (unknown/streaming), matching `AudioDecoder`'s own
documented contract for that value — not observed with any of the 4 real
test files, all of which reported a sane, plausible duration.

## 10. Seek Behavior — Documented Limitation

`xmp_seek_time` works, but **tracker seek is pattern/row-granular, not
sample-accurate** — this is a real, structural characteristic of tracker
module formats (positions are addressed by pattern/row, not by arbitrary
sample offset), not an implementation shortcut. Empirically observed: a
seek to 60000ms landed real playback at ~53904ms in one real test on the
`.it` file (a ~6-second offset, on a song with correspondingly large
patterns). **This limitation is isolated entirely inside
`TrackerDecoder.seek()`** — `ConventionalDecoder`'s (MP3/WAV/OGG/FLAC) seek
precision is completely unaffected, unchanged, and not degraded in any way
by this cut.

## 11. EOF / Error Semantics

- **Malformed/garbage file**: `xmp_load_module_from_memory` returns a
  distinct negative error code (`-3` observed for garbage bytes, `-6` for
  a nonexistent path passed via the file-path variant during audit) —
  never crashes. `TrackerDecoder.load()` raises a clean `RuntimeError`
  with the code included.
- **EOF**: confirmed empirically that `xmp_play_buffer`'s `loop` argument
  must be `1` (not `0`, which loops indefinitely and never signals end) —
  with `loop=1`, the call immediately after the module's natural end
  returns a negative code (`-1`, matching libxmp's documented `XMP_END`
  constant), and `read_frames()` maps this to an empty array, satisfying
  `AudioDecoder`'s own documented EOF contract exactly.
- **Player-level recovery** (RC-069-002's own fix, unmodified by this
  cut, verified still correct here): a tracker load failure — whether from
  a missing library or, now that the library is present, a genuinely
  malformed module — sets `PlayerEngine._decoder_failed`/
  `_last_error_msg` through the exact same path every other decode
  failure uses, so `WindowManager._tick()`'s existing clean
  log-and-auto-advance behavior applies uniformly. Verified directly:
  loading a garbage `.mod` file raises cleanly, sets `decoder_failed`, and
  a subsequent conventional (MP3) load recovers normally with
  `decoder_failed` cleared.

## 12. Real Module Validation Results

Real local fixture files (sourced from the sibling `MetalWar-Installer`
directory — **never copied into this repository**; licensing for these
specific files was not independently cleared, so they stay exactly where
they already were, referenced only by absolute path in tests, which skip
honestly if the directory is absent):

| Format | File | Load | PCM audible/non-degenerate | Duration | Seek | Player crossover |
|---|---|---|---|---|---|---|
| IT | `08_sad_song.it` | ✅ (`ret=0`) | ✅ (varied int16 samples, non-silent) | ✅ 200.991s (~3:21, plausible) | ✅ (row-granular, documented) | ✅ |
| XM | `dalezy-lotus_drei_remix.xm` | ✅ | ✅ | ✅ | not separately re-tested (same code path as IT) | ✅ |
| MOD | `alleviation-metal hr.mod` | ✅ | ✅ | ✅ | not separately re-tested | ✅ (via `PlayerEngine`, all 4 real files loaded successfully in sequence) |
| MOD | `tubularbells-metal hr.mod` | ✅ | ✅ | ✅ | not separately re-tested | ✅ |
| S3M | *(none available)* | **NOT TESTED** | — | — | — | — |

**Decoder-crossover, verified through the real `PlayerEngine`** (not just
`TrackerDecoder` in isolation): MP3 → MOD → MP3 (repeated load, each
succeeding, `is_tracker` flag correctly toggling); a deliberately malformed
tracker file injected mid-sequence raised cleanly, was tracked via
`decoder_failed`/`check_and_clear_error()`, and conventional (MP3)
playback recovered immediately afterward with the failure flag correctly
cleared.

**Stop/replay and next/previous**: not separately exercised as dedicated
UI-level interactions in this cut (no `WindowManager`/transport-button
test was added specifically for tracker files) — `TrackerDecoder.load()`
being called repeatedly on the same instance (§9's "context reuse")
IS the mechanism `PlayerEngine`'s track-advance/replay logic already
uses uniformly for every decoder type, and was verified directly working
for 4 sequential real tracker loads.

## 13. Audio-Reactivity Validation

**Automated proxy (performed)**: real tracker PCM (from
`alleviation-metal hr.mod`) was pushed through the completely unmodified
`AnalysisHandoff` → `AudioFrame` pipeline exactly as any other decoder's
output would be. Result: genuinely alive, non-degenerate values —
`rms=0.246`, `peak=0.398`, `bass=0.192`, `mids=0.098`, `treble=0.006`,
51/64 non-zero spectrum bins, 128/128 non-zero waveform points. A
structural check confirms `AnalysisHandoff`'s own source contains **zero**
tracker-specific branching (`Tracker`, `libxmp`, `xmp_` all absent from
its source) — the decoder-agnostic architecture the mission required is
intact by construction, not merely by observed behavior.

**Human visual gate (NOT performed by this audit — requires a live GL
context and human eyes)**: TEST H in §16 below specifies the exact
protocol for Metal to confirm the GPU/CPU visualizers respond visibly and
plausibly (not "dead" or wildly under/over-scaled) to real tracker
playback, comparing against the same visualizer under MP3 playback.

## 14. libmodplug Removal

Migration succeeded per every criterion in §17 of the mission (A-F) — no
dual-backend was kept "just in case." `TrackerDecoder` now speaks libxmp
exclusively; every `_discover_libmodplug`/`ModPlug_*` reference was
removed from `tracker.py`. `PlayerEngine`'s constructor parameter was
renamed (§8). Stale "libmodplug" claims were corrected in
`docs/CURRENT_STATE.md`, `docs/ARCHITECTURE.md`, and `README.md` (all
three are meant to reflect *current* truth, unlike point-in-time
investigation/design-doc records elsewhere in `docs/`, which were left
untouched per this session's established "do not rewrite history"
practice). Two pre-existing tests (`tests/test_production_core.py`,
`tests/test_production_cut1b.py`) had stale "libmodplug" wording in
skip-reason strings, updated to match; their actual test logic required no
changes and now **genuinely passes** where it previously honestly skipped
(`test_tracker_decoder`: 3 passed+1 skipped → 4 passed, session-wide).

## 15. Packaging Implications for RC-069-003

- **Actual DLL location**: `<site-packages>/pygame/libxmp.dll` (Windows) —
  ships inside the already-required `pygame-ce` dependency, at a
  deterministic, discoverable path relative to the `pygame` package.
- **Does PyInstaller discover it automatically?** Likely **partially**:
  PyInstaller's pygame hook generally collects pygame's own bundled DLLs
  (it has to, for pygame to function at all) as part of normal binary
  collection — `libxmp.dll` sitting alongside `SDL2.dll` etc. in the same
  directory is plausibly swept up by the same mechanism. **However**, this
  is a *dynamic* `ctypes.CDLL(path)` load at runtime (not a static Python
  `import`), which PyInstaller's import-graph analysis cannot see directly
  — the DLL being physically present in the collected pygame directory
  (likely, via the hook) is a different question from whether
  `TrackerDecoder._discover_libxmp()`'s `os.path.dirname(pygame.__file__)`
  lookup still resolves correctly inside the frozen bundle's directory
  layout (should, since it's a plain `os.path` computation relative to
  wherever `pygame` itself actually landed — but **must be verified
  empirically once a real ONEDIR build exists**, not assumed).
- **Explicit binary inclusion likely needed?** Recommend RC-069-003
  include an explicit `--collect-binaries pygame` (or equivalent spec-file
  `binaries=[...]` entry covering `pygame/libxmp.dll` specifically) as a
  defensive, low-cost insurance measure even if the default hook turns out
  to already cover it — cheap to add, expensive to silently omit.
- **Runtime lookup expectation**: unchanged from dev — `_discover_libxmp()`
  first checks `os.path.dirname(pygame.__file__)`, which resolves
  correctly in any environment where `import pygame` itself succeeds,
  frozen or not, since it derives the path from the live `pygame` module
  object rather than any hardcoded location.
- **This is a concrete instruction, not a promise** — RC-069-003's
  clean-machine ONEDIR validation protocol (already specified in
  RC-069-001 §14) must include "play a real MOD/XM/IT file" as an
  explicit pass/fail gate, precisely because this dynamic-load path is the
  one part of this migration that cannot be fully proven from a source
  checkout alone.

## 16. Licensing Findings

**Not independently verified from a locally-available authoritative
source in this pass** — no bundled `LICENSE`/`COPYING`/`NOTICE` file ships
alongside `pygame-ce`'s wheel for its native dependencies (confirmed by
direct search of the installed package directory — a pre-existing
packaging gap on pygame-ce's own side, not something this cut can fix).
libxmp is recalled (not confirmed from a local source) to be distributed
under a permissive license (the project's own "libxmp license," broadly
BSD/MIT-family in character) as of its 4.x series — **this recollection is
not a legal guarantee**. **Recommendation**: before RC-069-003 finalizes
any third-party notices, verify the exact license text directly from the
libxmp upstream project (the library's own repository/release archive)
rather than relying on this document's recollection. Added to the
third-party notices checklist (§17, RC-069-002's own doc) as: *libxmp
(bundled via pygame-ce) — license type to be confirmed from upstream
before release; bundling appears practical (already shipping, zero
additional distribution burden) pending that confirmation.*

## 17. Files Modified / Created

**Modified**: `src/toroidamp/audio/decoders/tracker.py` (full
libmodplug → libxmp rewrite, same `AudioDecoder` contract),
`src/toroidamp/audio/player.py` (constructor parameter rename + a stale
comment correction), `docs/CURRENT_STATE.md` (AUDIO-002 decision + Current
Risks section corrected), `docs/ARCHITECTURE.md` (AUDIO-001/AUDIO-002
decision entries corrected — including the pre-existing stale `miniaudio`
mention in AUDIO-001, RC-069-002's own finding), `README.md` (one-line
tracker-backend mention corrected), `tests/test_production_core.py` /
`tests/test_production_cut1b.py` (stale skip-reason/comment wording only —
no test logic changed), `tests/test_rc_069_002.py` (two tests updated to
reference the renamed `_discover_libxmp` method instead of the now-removed
`_discover_libmodplug`).

**Created**: `tests/test_rc_069_002b.py`,
`docs/release/RC_069_002B_tracker_libxmp.md` (this document).

No shader, theme, or unrelated production file was touched. No version was
bumped.

## 18. Human Validation Protocol

**Recommended real file paths** (from the sibling `MetalWar-Installer`
directory used throughout this audit — substitute your own local files if
these are unavailable on Metal's machine):

```text
IT:  C:\ToroidAMP\Metalwar-Installer\08_sad_song.it
XM:  C:\ToroidAMP\Metalwar-Installer\dalezy-lotus_drei_remix.xm
MOD: C:\ToroidAMP\Metalwar-Installer\alleviation-metal hr.mod
MOD: C:\ToroidAMP\Metalwar-Installer\tubularbells-metal hr.mod
S3M: (none available — please supply one to complete this format's validation)
```

**TEST A — Backend availability**: confirm `TrackerDecoder.is_available()
== True` (already automated — `tests/test_rc_069_002b.py::test_01`).

**TEST B — MOD**: load and play `alleviation-metal hr.mod` (or
`tubularbells-metal hr.mod`); confirm audible playback.

**TEST C — XM**: load and play `dalezy-lotus_drei_remix.xm`; confirm
audible playback.

**TEST D — IT**: load and play `08_sad_song.it`; confirm audible playback.

**TEST E — S3M**: **not yet possible — no real file available.** If Metal
has or can obtain a real `.s3m` file, this is the one remaining format to
manually confirm; architecturally it is handled identically to the other
three (same `TrackerDecoder`, same `xmp_load_module_from_memory` call).

**TEST F — Seek/skip**: seek within a playing tracker file (expect
approximate, pattern-granular landing per §10, not sample-exact); use
Next/Previous to cycle between tracker and conventional tracks in a mixed
playlist.

**TEST G — Decoder crossover**: build a playlist mixing MP3 → XM → FLAC →
MOD (or similar) and play through it; confirm no failures, no leftover
audio glitches at transitions.

**TEST H — Reactive visualizer**: play an MP3 with Cyber Bloom (or the
Audio Reactive Reference shader) active; observe normal reactivity. Switch
to one of the real XM/MOD files above with the same visualizer active;
confirm bass/mids/treble visibly respond, beat/transient response exists,
and the visualizer does not look "dead" or absurdly under/over-scaled
compared to the MP3 case. Exact numeric parity is explicitly NOT required
— only musically plausible response.

**TEST I — Error handling**: attempt to load a deliberately malformed or
unsupported file with a tracker extension (e.g. rename a text file to
`.mod`); confirm ToroidAMP does not crash, logs a clear error, and
recovers cleanly to normal operation afterward.

## 19. Automated Tests

`tests/test_rc_069_002b.py` — **14/14 passed** (8 sub-tests across the 4
real fixture files within `test_06_07_08` alone), covering discovery,
unavailable-lib clean construction failure, ctypes signature validity,
context creation, malformed/nonexistent-file load isolation, PCM
float32/stereo/normalization-bounds verification against all 4 real
files, EOF detection, decoder reset via repeated `load()`, seek, duration,
`PlayerEngine` recovery after a tracker error, conventional-decoder
non-interference, and a structural + behavioral proof that
`AnalysisHandoff` received real tracker PCM through its completely
unmodified, decoder-agnostic contract.

**Full regression sweep**: zero regressions. `tests/test_production_core.py`
improved from 3 passed/1 skipped to **4 passed** (its pre-written,
untouched tracker test now genuinely executes and passes, session-wide,
for the first time). Same pre-existing, unrelated `test_ux_004.py` marquee
failures as every prior delivery this session; everything else unchanged.

---

## CURRENT_STATE_UPDATE: UPDATED (minimal)

`docs/CURRENT_STATE.md`'s AUDIO-002 decision entry and its "Cross-Platform
Library Loading" risk note were corrected — the previously-recorded
`libmodplug` decision was not merely stale, it described a library that
was never actually present in this project's toolchain, and the tracker
subsystem's real native backend has now genuinely changed (and been
validated) to `libxmp`. This is a material correction to a CLOSED
architectural decision entry the document itself presents as current,
operational truth (not a historical archive entry), warranting the
minimal update made — the "Validated with MOD, XM, IT, S3M" claim is now
corrected to honestly reflect MOD/XM/IT-only real validation, S3M
untested. `docs/ARCHITECTURE.md` received the equivalent, matching
correction for the same reason (it explicitly holds "current architectural
truth" per `CURRENT_STATE.md`'s own stated cross-reference).
