# ToroidAMP — BRAND-001: Application Icon Identity

> **The artwork may become a visualizer someday. The icon has one job: at 16 pixels, still look like ToroidAMP.**

---

## 1. Human Direction

ToroidAMP's first official visual identity: a red/white checkerboard toroid with a deliberate retro-computing / Amiga-era wink. Two assets were prepared and needed integrating cleanly — without redesigning the UI, touching audio/visualizers, or committing.

---

## 2. Brand Concept

A glossy, checkerboard-textured torus (donut) rendered with a cyan rim-light accent, on a transparent background. The checkerboard pattern is the primary motif; the cyan edge glow echoes the existing electric-cyan neon identity established in POLISH-001, giving the mark a visual link to the rest of the instrument without literally reusing chassis chrome.

---

## 3. Source vs Operational Asset

**Authoritative distinction — durable, load-bearing for this cut and any future branding work:**

```text
CREATIVE SOURCE            !=      RUNTIME BRANDING ASSET
assets/images/                     assets/branding/
ToroidAMP.png                      toroidamp_icon.png
1254x1254, full-res                512x512, operational master
never loaded at runtime            the only thing the app ever reads
preserve untouched, always         source for every derived icon size
```

### A note on where the files actually were

Both assets exist and match their described purpose exactly (verified: `toroidamp_icon.png` is 512×512 RGBA; `toroidAMP.png` is 1254×1254 RGBA) — but neither lived at the mission's stated repo-root paths. They were found at `tests/assets/branding/toroidamp_icon.png` and `tests/assets/images/toroidAMP.png` (note the lowercase `toroidAMP.png`, not `ToroidAMP.png`), evidently placed under the test-fixtures tree rather than a repo-root `assets/` directory that didn't yet exist.

Rather than guessing or fabricating paths, the actual files were located, verified, and **copied** (not moved — the `tests/assets/` originals were left in place, untouched) byte-for-byte to the mission's stated authoritative locations:

```bash
assets/images/ToroidAMP.png              # sha256 987706... — identical to tests/assets/images/toroidAMP.png
assets/branding/toroidamp_icon.png       # sha256 f3dc93... — identical to tests/assets/branding/toroidamp_icon.png
```

Both hash-verified byte-identical to the originals immediately after copying (see §9, Part 8 tests). This discrepancy is flagged here for the human's awareness — it doesn't block the cut, but the `tests/assets/` copies are now redundant with the real `assets/` tree and could be removed by a future cleanup if desired (not done here — no destructive action was taken on files not explicitly asked about).

---

## 4. Runtime Icon Integration

New module: [`src/toroidamp/branding.py`](../../src/toroidamp/branding.py) — the single resolution point for the official icon.

```python
resolve_branding_icon_path() -> Path | None
resolve_branding_icon() -> QIcon | None
```

**Resolution order** (packaging-safe, CWD-independent — verified by launching from `~` with a different `sys.path` insertion, see §9 Part 2):

1. **Package-internal copy**: `importlib.resources.files("toroidamp") / "assets" / "branding" / "toroidamp_icon.png"`. This resolves correctly both for an editable dev install (`pip install -e .`, which still points at the real `src/toroidamp/` files on disk) *and* a real installed wheel that ships the asset as package data (§7) — no repo-root assumptions at all.
2. **Repo-root checkout fallback**: `Path(__file__).resolve().parents[2] / "assets" / "branding" / "toroidamp_icon.png"` — for a dev tree where the package-internal copy hasn't been synced from the human-facing master. Same technique UX-004's `_version.py` already established and documented for the same class of problem (editable-install staleness).

`resolve_branding_icon()` wraps this with a `QIcon` load and returns `None` (logging a warning, never raising — see §8) if the file can't be found or fails to load as a valid image.

**Wired in three places:**
* `src/toroidamp/__main__.py` — `app.setWindowIcon(brand_icon)` right after `QApplication` construction, before any window is built. This is the default icon inherited by any window that doesn't set its own — covers module windows and the fullscreen RETINA MELT window automatically, with zero extra per-window code.
* `src/toroidamp/ui/chassis.py` — `UnifiedChassis.__init__` also explicitly calls `self.setWindowIcon(brand_icon)`. Technically redundant given the `QApplication`-level default, but added defensively for certainty on the one primary owner window, independent of any `Qt.FramelessWindowHint`/platform icon-inheritance quirk.

No icon-setting code was added to `VisualizerModule`, `PlaylistModule`, or `RetinaMeltWindow` — they correctly inherit the `QApplication` default, and Part C explicitly scoped this cut to OS/application identity, not per-window decoration.

---

## 5. Tray Integration

[`src/toroidamp/ui/tray.py`](../../src/toroidamp/ui/tray.py)'s `ToroidTrayIcon.__init__` now resolves the official icon first, falling back to the existing procedural cyan/magenta generator (`_create_procedural_icon`, unchanged) only if resolution fails:

```python
official_icon = resolve_branding_icon()
self.setIcon(official_icon if official_icon is not None else self._create_procedural_icon())
```

The procedural generator was kept exactly as before, per Part G's explicit allowance ("the old procedural tray icon MAY remain as an internal fallback if retaining it is trivial and useful") — it's a five-line static method with zero maintenance cost, and it's the difference between "no tray icon at all" and "a usable one" if the branding asset is ever missing.

**Legibility at small sizes** (Part D requires reporting rather than redesigning if this degrades): the master was rendered at 16/24/32/48px and visually inspected directly (not just measured). At 32px and 48px the checkerboard pattern and cyan rim read clearly. At 24px the checkerboard is still perceivable as texture, if a little noisy. **At 16px, the checkerboard detail is essentially lost** — it reads as a red/white ring/blob with a cyan-tinted edge, recognizable as *a* colored ring icon and distinguishable from other tray icons by color and silhouette, but the checkerboard motif itself does not survive at the smallest common Windows tray size. This is reported as instructed rather than redesigned; see §11.

---

## 6. Windows ICO Generation

New tool: [`tools/generate_ico.py`](../../tools/generate_ico.py).

```bash
python tools\generate_ico.py
```

Generates `assets/branding/toroidamp.ico` (and a packaged copy at `src/toroidamp/assets/branding/toroidamp.ico`) directly from the 512×512 master via Pillow, with sizes:

```text
16x16   24x24   32x32   48x48   64x64   128x128   256x256
```

Verified present in the output `.ico` (`PIL.Image.open(...).info["sizes"]`). Each requested size is generated by Pillow resampling the **master image independently per entry** — not through repeated downsampling of a progressively smaller intermediate — preserving crispness and alpha transparency at every resolution. The creative source (`assets/images/ToroidAMP.png`) is never touched by this tool.

**Pillow was added as a dev-only optional dependency** (`pyproject.toml` `[project.optional-dependencies] dev = ["Pillow>=10.0"]`) — required only to *run this generator script*, never to run ToroidAMP itself. Qt's own image plugins already handle reading PNG for runtime `QIcon`/`QPixmap` use without any new runtime dependency; Pillow's `ICO` writer with per-size resampling is simply the standard, reliable tool for producing a correct multi-resolution Windows icon, which Qt does not offer a clean equivalent for.

This `.ico` is preparation only — it is not yet wired into any packaging step (`PyInstaller`/`Nuitka`), per the explicit instruction not to introduce executable packaging in this cut.

---

## 7. Packaging Considerations

Audited `pyproject.toml` and the package layout. `assets/` lives at the repo root, a **sibling** of `src/`, so standard `package_data`/`include_package_data` mechanisms (which only pick up files *inside* a discovered package directory) cannot include it for a wheel build as-is — this matches Part F's anticipated scenario exactly.

**Small, clean fix implemented** (not a packaging refactor): the operational branding master and its `.ico` derivative were additionally copied *inside* the package tree, at `src/toroidamp/assets/branding/`, and declared as package data:

```toml
[tool.setuptools.package-data]
toroidamp = ["assets/branding/*.png", "assets/branding/*.ico"]
```

This means a real wheel build now *would* include the branding assets correctly. The creative source (`assets/images/`) is deliberately **not** duplicated into the package or declared as package data — it's never loaded at runtime, so it has no packaging need (matches Part A: "do not load the huge creative source just to display a 16–32px icon").

**Known caveat, mirroring `_version.py`'s documented limitation**: the package-internal copy is a snapshot, synced by hand (copy + `tools/generate_ico.py`) whenever the repo-root master changes — there's no automatic sync tooling. This is intentionally minimal for a project this size; a future contributor changing the branding master should re-copy `assets/branding/toroidamp_icon.png` into `src/toroidamp/assets/branding/` and re-run `tools/generate_ico.py`. `resolve_branding_icon_path()`'s repo-root fallback (§4) means the app keeps working correctly even if that sync is forgotten during development — only a real packaged wheel build would actually need it current.

---

## 8. Fallback Behavior

Every accessor in `branding.py` is designed to never raise:

* `resolve_branding_icon_path()` wraps both resolution attempts in `try/except Exception: pass` and returns `None` if neither succeeds.
* `resolve_branding_icon()` logs a `logger.warning(...)` (not `error`) and returns `None` — both when the path can't be resolved and when `QIcon(...)` loads but reports `isNull()` (a corrupt/invalid image file).
* Every call site (`__main__.py`, `chassis.py`, `tray.py`) checks for `None` before using the result — `__main__.py` and `chassis.py` simply skip `setWindowIcon()` (Qt's own default empty icon applies); `tray.py` falls back to the procedural generator.

Verified directly: monkeypatching `resolve_branding_icon_path` to always return `None` produces the expected warning log, a `None` return from `resolve_branding_icon()`, a fully-functional tray icon (procedural fallback), and successful chassis construction with no exception anywhere in the chain.

---

## 9. Tests

`tests/test_brand_001.py` — 19 tests, all passing:

| # | Test | What it asserts |
|---|------|-----------------|
| 1 | `test_branding_master_exists` / `test_creative_source_exists` | Both authoritative assets exist at their documented paths |
| — | `test_package_internal_copy_matches_authoritative_master` | The packaged copy is byte-identical to the human-facing master |
| 2 | `test_resolution_independent_of_cwd` | Resolves correctly after `chdir(~)` |
| — | `test_resolution_does_not_use_relative_traversal_from_cwd` | Resolved path is absolute, not `.`-relative |
| 3 | `test_resolve_branding_icon_returns_non_null_qicon` / `test_application_can_receive_the_icon` / `test_chassis_carries_non_null_icon` | `QIcon` is non-null at every integration point |
| 4 | `test_tray_icon_is_non_null` / `test_tray_prefers_official_icon_over_procedural` | Tray uses the real icon, and the procedural generator is provably *not* invoked when the official asset resolves |
| 5 | `test_resolve_branding_icon_returns_none_when_unresolvable` / `test_tray_falls_back_to_procedural_icon_when_branding_missing` / `test_chassis_construction_does_not_raise_when_branding_missing` | Graceful degradation at every layer, no exceptions |
| 6 | `test_modules_remain_owned_windows_of_chassis` | `Qt.Window` flag + chassis-as-parent still hold — taskbar ownership architecture (UX-001) is completely unaffected by icon changes |
| 7 | `test_ico_exists` / `test_ico_contains_expected_sizes` / `test_package_internal_ico_matches_authoritative_ico` | `.ico` exists, contains all 7 expected sizes, packaged copy matches |
| 8 | `test_creative_source_matches_test_fixture_original` / `test_branding_master_matches_test_fixture_original` | Both assets are still byte-identical to their as-provided originals — nothing was resized/re-encoded during integration |

**Full suite result**: **151 passed, 1 skipped** (the same honestly-classified `libmodplug`-unavailable case from UX-004), **0 failed** — exactly the expected `132 passed / 1 skipped` baseline plus this cut's 19 new tests. The honest skip was not touched or converted.

---

## 10. Human Validation

All eight scenarios require visual/OS-level confirmation this environment cannot provide (no live Windows desktop — consistent with every prior UX cut's limitation) — what *was* verified programmatically:

* **Scenario 1 (NORMAL launch)**: `app.setWindowIcon()` receives a non-null `QIcon` from the branding master; confirmed via direct script execution mirroring `__main__.py`'s exact call sequence. Actual taskbar rendering needs a live desktop.
* **Scenario 2 (MINI)**: no icon-related code depends on `chassis.mode` — the icon is set once at construction and inherited by `QApplication`, so switching scales cannot affect it. Not independently re-driven through a mode switch given this structural guarantee.
* **Scenario 3 (modules)**: `test_modules_remain_owned_windows_of_chassis` confirms the exact UX-001 ownership mechanism (`Qt.Window` + chassis-as-`QWidget`-parent) that produces one taskbar identity is untouched. Actual single-taskbar-preview rendering needs a live desktop, same as every prior cut.
* **Scenario 4 (tray)**: confirmed the tray receives the official icon (not the procedural one) via `test_tray_prefers_official_icon_over_procedural`; visually inspected the icon at 16/24/32/48px directly (§5) — legible at 32px+, degraded at 16px (reported, not fixed).
* **Scenario 5 (Alt-Tab/taskbar preview)**: relies on the same `QApplication`/`QWidget` `windowIcon()` mechanism as Scenario 1 — no separate code path exists for preview rendering, so nothing additional was implemented or could be separately tested here.
* **Scenario 6 (shutdown)**: unrelated to this cut's changes (no lifecycle/shutdown code was touched); `test_modules_remain_owned_windows_of_chassis` exercises a full `WindowManager` construction and `shutdown()` without incident, and the full regression suite (including all UX-001/UX-002 lifecycle tests) passes unchanged.

---

## 11. Known Limitations

* **16px tray/taskbar legibility**: the checkerboard pattern is not distinguishable at 16×16 — the icon reads as a colored ring shape rather than a checkerboard specifically. Per Part D's explicit instruction, this is reported rather than redesigned in this cut. A simplified micro-icon variant (e.g., fewer/larger checker squares, or a bolder silhouette) could be considered later if human evaluation on a live desktop confirms it's actually a problem in practice — Windows commonly displays tray icons at 16px or sometimes smaller with additional OS scaling, so this is worth a real look.
* **Asset location discrepancy** (§3): the human's prepared files were found under `tests/assets/`, not the mission's stated repo-root `assets/` paths. Handled by verified byte-identical copying rather than guessing; the redundant `tests/assets/` copies were left in place (no destructive action taken).
* **Package-internal asset sync is manual** (§7): changing the branding master requires re-copying it into `src/toroidamp/assets/branding/` and re-running `tools/generate_ico.py` by hand. No automated sync/build-time hook was added, consistent with "do not perform a large packaging refactor."
* **No live-desktop pass**, as with every prior cut — actual taskbar/Alt-Tab/tray rendering was not visually confirmed on a real Windows session.

---

## 12. Version Status

Version remains **`0.2.0`** — unchanged, per explicit instruction that implementation, tests, and human validation do not themselves justify a bump. Per the version policy established in UX-004 (`docs/ux/004_marquee_mini_volume_versioning.md`), BRAND-001 becomes eligible for a `PATCH` bump (`0.2.1`) only after explicit human validation and closure — not performed here.

---

## 13. Follow-up — Tray Restore Semantics

Human validation found one UX defect, unrelated to the icon assets themselves: System Tray → **Restore Player** only raised/focused the chassis (`WindowManager._focus_chassis`) — it never actually left MINI. If ToroidAMP was in MINI, "Restore Player" appeared to do nothing.

### Fix

`WindowManager._focus_chassis()` (`src/toroidamp/ui/window_manager.py`) now checks the chassis mode first:

```python
def _focus_chassis(self):
    if self.chassis.mode == "mini":
        self.chassis.set_mode("normal")
    self.chassis.raise_()
    self.chassis.activateWindow()
```

`chassis.set_mode("normal")` is the **same authoritative MINI→NORMAL transition** the chassis's own `▲ NORMAL` button already uses — it emits `scale_changed`, which `WindowManager._on_scale_changed` is already wired to, and that's what restores previously-visible modules (`saved_vis_visible`/`saved_pl_visible`), redocks them if they were docked, and calls `realign_docked_modules()`. No second restoration path was created; this is a two-line addition ahead of the existing raise/activate calls, using infrastructure that already existed and was already tested (UX-002, UX-003).

Already-NORMAL now behaves exactly as before — `set_mode` is only called when actually leaving MINI, so a redundant `set_mode("normal")` call is never made when nothing needs to change.

Because module restoration goes through the exact same `_on_scale_changed` path as every other MINI→NORMAL transition, module geometry (`user_size`, per UX-003's "USER SIZE IS STATE" rule) is preserved automatically — no new code was needed for that guarantee, it falls out of reusing the authoritative transition rather than reimplementing restoration logic.

### What Was Deliberately Not Touched

Per the instruction: MINI button semantics, taskbar behavior, close/shutdown lifecycle, tray transport controls, branding assets, and module state preservation logic are all untouched — the diff is exactly the `if self.chassis.mode == "mini": self.chassis.set_mode("normal")` addition.

### Tests

`TestTrayRestoreSemantics` (new, 6 tests) in `tests/test_brand_001.py`:

| # | Test | What it asserts |
|---|------|-----------------|
| 1 | `test_restore_from_mini_switches_to_normal` | Restore while MINI → chassis ends up NORMAL |
| 2 | `test_restore_while_already_normal_stays_normal` | Restore while already NORMAL → stays NORMAL (no-op transition) |
| 3 | `test_restore_from_mini_restores_previously_active_modules` | VIS/PL become visible again, **with their exact pre-MINI user-resized geometry intact** |
| 4 | `test_restore_does_not_disturb_playback` | Playback state (`PlaybackState.PLAYING`) unchanged across the MINI→restore round-trip |
| 5 | `test_restore_still_raises_and_activates_chassis` | `raise_()` and `activateWindow()` still both fire |
| 6 | `test_restore_does_not_regress_minimize_or_close` | MINIMIZE (routes to MINI) and CLOSE (shutdown) both still work correctly around this change |

Full suite after this follow-up: **157 passed, 1 skipped** (same honestly-classified `libmodplug` case), 0 failed.

### Manual Validation

Programmatically driven (no live desktop here, consistent with every prior cut): constructed a `WindowManager`, opened VIS+PL, undocked and resized both to arbitrary user dimensions, switched to MINI (confirmed both modules hidden), called `_focus_chassis()` directly (the exact method the tray's `restore_requested` signal is wired to), and confirmed: chassis mode is NORMAL, both modules visible again at their exact prior sizes, `raise_()`/`activateWindow()` both invoked. Matches the requested manual scenario (`NORMAL + VIS + PL → MINI → tray → Restore Player → NORMAL returns, VIS+PL restore, audio unchanged`) exactly, modulo the live-desktop visual confirmation that remains outstanding as with every prior cut.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

BRAND-001 is a branding/integration cut within the existing ACTIVE Production Cut 3 phase. No phase changed, no decision gate changed, no architectural boundary moved. Operational baseline remains STABLE. This follow-up corrects a tray UX defect found in human validation; it does not change phase, scope, or architecture.
