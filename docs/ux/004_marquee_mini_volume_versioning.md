# ToroidAMP — UX-004 Marquee Titles, MINI Volume & Version Cadence

> A title that fits: **stays still.** A title that does not: **show me the rest.**
> Volume in MINI: **one click away.**
> Version numbers: **change when work actually closes, not when an agent gets excited.**

---

## 1. Human Requirements

1. Long track titles must horizontally scroll in both NORMAL and MINI; short titles stay static.
2. MINI's speaker control must expose the real volume slider without expanding to NORMAL.
3. ToroidAMP moves to `0.2.0` and gains an explicit, deterministic version-bump workflow for future closed cuts.
4. The five known test-suite failures inherited from prior cuts are audited and classified, not silently skipped.

---

## 2. Marquee Interaction Contract

New component: [`src/toroidamp/ui/marquee.py`](../../src/toroidamp/ui/marquee.py) — `MarqueeLabel(QLabel)`, a drop-in replacement used for both `UnifiedChassis.normal_title_marquee` and `UnifiedChassis.mini_title_marquee`. One reusable widget, not two independent timer/state machines.

**Ping-pong state machine** (only active while overflowing):

```text
PAUSE_START --1.2s--> SCROLL_FORWARD --> PAUSE_END --1.2s--> SCROLL_BACKWARD --> repeat
```

* `PAUSE_MS = 1200` — dwell at each endpoint.
* `SCROLL_SPEED_PX_S = 55.0` — calm, readable horizontal speed, not a ticker crawl.
* `TICK_MS = 30` — ~33fps animation tick, only while an overflowing title is visible.

Rendering is done in a custom `paintEvent` using `QFontMetrics`/`QPainter.drawText` at a computed pixel offset — no destructive string slicing, no mutation of the canonical title text. `QLabel.setText()`/`.text()` still work normally (the label's own text is kept in sync via `super().setText()`) for anything that reads `.text()`; only the *painted* representation is offset.

Public API: `set_marquee_text(text)` replaces `setText(text)` as the entry point applications should use.

---

## 3. Overflow Detection

`MarqueeLabel._recompute_overflow()` compares `QFontMetrics(self.font()).horizontalAdvance(text)` against `self.width()`. Marquee state only activates if `text_width > available_width`; otherwise the label renders once, statically, with zero timer overhead (`_STATIC` state, no `QTimer` running).

Reevaluated automatically on:
* **track change** — `set_marquee_text()` short-circuits only if the text is byte-identical; any real change resets `_offset = 0` and forces the state back through `_STATIC -> PAUSE_START`, so a title changed mid-scroll never inherits the previous title's offset or motion phase.
* **experience scale change** — NORMAL and MINI each own an independent `MarqueeLabel` instance; `QStackedWidget` hides the inactive one (`hideEvent`/`showEvent` pause/resume the timer accordingly, so a hidden marquee costs nothing).
* **widget width change** — `resizeEvent` triggers `_recompute_overflow()`.
* **font metric change** — `_recompute_overflow()` reads `self.font()` fresh each call; a stylesheet-driven font change is picked up the next time overflow is recomputed (title change or resize).

**Fixed bug found during implementation**: the first draft only reset `_offset`, not `_state`, on a text change — a title that changed while mid-scroll would keep its old scroll-direction state and jump straight into continuing motion rather than the readable start-pause. Caught by manual verification (see §12) and fixed before this cut closed.

---

## 4. MINI Volume UX

The MINI speaker icon (`🔊`) was a decorative, non-interactive `QLabel`. It is now `UnifiedChassis.mini_vol_btn`, a flat `QPushButton` wired to `_toggle_mini_volume_popup()`.

Click behavior:
* **Click speaker** → `UnifiedChassis.volume_popup` (a `QWidget(self, Qt.Popup)`) is resynced from the current authoritative value and shown, anchored just below the speaker button (`mapToGlobal`).
* **Drag the popup's slider** → volume changes immediately (`valueChanged` fires per pixel, same as the existing NORMAL slider).
* **Click outside** → the popup closes on its own. `Qt.Popup` is the correct Qt-native mechanism for this — it grabs the pointer and closes automatically on any outside click or focus loss, with no custom event filtering and no Win32-specific code.
* **Click speaker again** → per spec, either close-or-reopen is acceptable; because `Qt.Popup`'s own outside-click handling can already dismiss the popup before the button's own `clicked()` signal fires, the observed behavior is "stays open" rather than a guaranteed toggle-close. This was a deliberate, spec-permitted simplification rather than adding click-sequencing logic to force a strict toggle.

`Qt.Popup` windows do not register their own taskbar entry (same class of window Qt uses for combo-box dropdowns and tooltips) — no Win32 ownership tricks were needed, unlike the module-window taskbar fix in UX-001.

**MINI's authoritative footprint is untouched.** The popup is a separate top-level widget; `UnifiedChassis.setFixedSize(MINI_WIDTH, MINI_HEIGHT)` is never touched by any popup code path.

---

## 5. Shared Volume Authority

There remains exactly one authoritative volume value — `PlayerEngine.volume`, set via `WindowManager._on_volume_changed`, itself driven by the single `UnifiedChassis.volume_changed` signal. Both `normal_vol_slider` and the new `mini_pop_slider` are two views/controllers of that one signal — no separate MINI volume state was created.

Synchronization:
* **MINI → NORMAL (live)**: `mini_pop_slider.valueChanged` is wired to `_on_mini_volume_slider_changed`, which immediately calls `self.normal_vol_slider.setValue(value)` *and* emits `volume_changed` — so the NORMAL slider reflects a MINI change the instant it happens, not just next time it's redrawn.
* **NORMAL → MINI (on open)**: `_toggle_mini_volume_popup()` resyncs `mini_pop_slider` from `normal_vol_slider.value()` (with signals blocked to avoid a redundant emit) every time the popup opens — guaranteeing correctness regardless of how the value last changed (drag, session restore, etc.), rather than depending on a fragile continuous cross-wire.
* **Session persistence**: unchanged — `WindowManager.save_current_session()`/`_apply_restored_session()` still read/write `PlayerEngine.volume` through `chassis.set_volume()`, which now also updates `mini_pop_slider` in the same call as `normal_vol_slider`.

No EQ, balance, mute, or gain-curve changes were made — the existing `0.0–1.0` volume range and `int(volume * 100)` slider scaling are unchanged.

---

## 6. Version 0.2.0

`pyproject.toml`'s `[project].version` moved from `0.1.0` to `0.2.0` — an explicit, human-authorized minor bump, executed via `tools/bump_version.py minor` (see §8), reflecting the accumulated functional baseline (UX-001 through UX-003, POLISH-001).

---

## 7. Canonical Version Source

**Audit of prior version strings**, both now resolved to one authority:

| Location | Before | After |
|---|---|---|
| `pyproject.toml` `[project].version` | `"0.1.0"` | `"0.2.0"` (canonical) |
| `src/toroidamp/__init__.py` `__version__` | hardcoded `"0.1.0"` | `resolve_version()` — derived |
| `src/toroidamp/__main__.py` startup log | hardcoded `"Starting ToroidAMP v0.1.0 ..."` | `f"Starting ToroidAMP v{__version__}"` |
| `src/toroidamp/ui/chassis.py` header label | hardcoded `"TOROIDAMP // v0.1 CORE"` | `f"TOROIDAMP // v{__version__} CORE"` |

New module: [`src/toroidamp/_version.py`](../../src/toroidamp/_version.py) — `resolve_version()`.

**Why not `importlib.metadata` alone**: measured directly during this cut — editable-install metadata (`importlib.metadata.version("toroidamp")`) is a snapshot written at `pip install -e .` time. Editing `pyproject.toml` afterward (exactly what `tools/bump_version.py` does) does **not** update it without a reinstall:

```text
pyproject.toml edited to 0.2.0-test -> importlib.metadata.version("toroidamp") still reports 0.1.0
```

So `resolve_version()` reads `pyproject.toml` directly first (walking up from `_version.py`'s own location — correct for this project's actual usage pattern, a development checkout, not a distributed wheel), falling back to `importlib.metadata` only if `pyproject.toml` can't be found (e.g. a real non-editable install where it isn't shipped), and finally to a `"0.0.0-dev"` sentinel if neither resolves. This keeps the bump tool's edits visible immediately, with no reinstall step, while remaining correct for a genuinely packaged/distributed install — `PACKAGE-001` in `docs/ARCHITECTURE.md` remains `DEFERRED`, but this doesn't foreclose it.

Editable install verified still functional (`pip show toroidamp` still resolves `Editable project location`; `import toroidamp; toroidamp.__version__` returns `0.2.0` without reinstalling after the bump).

---

## 8. Version Bump Workflow

New tool: [`tools/bump_version.py`](../../tools/bump_version.py).

```bash
python tools\bump_version.py patch
python tools\bump_version.py minor
python tools\bump_version.py major
```

* Reads the current `version = "X.Y.Z"` from `pyproject.toml` via a narrow, targeted regex (only that one line — nothing else in the file is touched, comments/formatting survive).
* Computes the new version via **semantic integer parsing and arithmetic** (`major, minor, patch = int(...); minor += 1; patch = 0`), not string manipulation — `0.9.4 + minor -> 0.10.0` is correct because it's integer math, not text substitution that could confuse `9` and `10`.
* Writes the new version back to `pyproject.toml` and prints a one-line summary (`ToroidAMP version: 0.1.0 -> 0.2.0 (minor)`).
* **Performs no Git operation whatsoever** — no `subprocess`, no `os.system`, no staging/commit/tag/push. Metadata-only, by design; Metal owns Git.

This tool was used to execute the actual `0.1.0 -> 0.2.0` bump for this cut (`python tools/bump_version.py minor`), both delivering the required version change and validating the tool against a real transition.

---

## 9. Version Policy

Durable rule (also encoded as this section — no separate policy file, to avoid enterprise release bureaucracy this project doesn't need):

```text
PATCH   completed routine UX / FIX / POLISH / VIS cut  (default for 0.x closures)
MINOR   explicit human-authorized milestone or meaningful feature stage
MAJOR   reserved for future stable compatibility/release decisions
```

**Version changes happen at cut CLOSURE, not implementation.** An agent starting, implementing, testing, or even completing human validation on a work unit does not itself justify a version bump — the bump is a deliberate, separate step taken once a cut is genuinely closed. Bumping is manual (`tools/bump_version.py`), not automatic, and not triggered by any test/CI/agent-completion event. This cut's `0.2.0` was explicitly authorized by the human in the mission brief, which is precisely the exception path (`MINOR requires explicit human/project decision`) — routine future closures default to `PATCH`.

---

## 10. Previous Test Failure Classification

Five failures were inherited from before this cut. All five, audited and resolved:

| # | Test | Classification | Resolution |
|---|------|----------------|------------|
| 1 | `test_fix_001.py::test_lifecycle_separation_mini_minimize_close` | **A — OBSOLETE TEST** | Asserted `wm.is_hidden_to_tray`, `wm.restore_from_tray()` — both removed by UX-002's always-visible lifecycle. Rewritten to assert the current contract (MINIMIZE routes to MINI, stays visible; MINI is 460×36 via the live `MINI_WIDTH`/`MINI_HEIGHT` constants, not a hardcoded literal). |
| 2 | `test_production_core.py::test_tracker_decoder` | **C — ENVIRONMENT / OPTIONAL NATIVE DEPENDENCY** | The `.xm` test asset exists on this machine (`Metalwar-Installer/dalezy-lotus_drei_remix.xm`), but `libmodplug` does not — construction of `TrackerDecoder()` raises `RuntimeError`. Added `TrackerDecoder.is_available()` (a new `@staticmethod`, refactored from the existing `_discover_libmodplug` without changing its logic) and an explicit `pytest.skip(...)` guard when it returns `False`. Tracker coverage itself (duration, title extraction, PCM shape/dtype/range) is fully preserved and will run whenever the native library is actually present — this is not a weakened production guarantee, only an honest skip. |
| 3 | `test_production_cut1b.py::test_audio_and_decoders` | **C — ENVIRONMENT / OPTIONAL NATIVE DEPENDENCY** | Same root cause as #2, inside a test that also covers `ConventionalDecoder` and the `AudioFrame` contract. Rather than skipping the whole test, only the tracker-specific block is now guarded by `TrackerDecoder.is_available()` — the mp3/AudioFrame assertions run unconditionally. |
| 4 | `test_production_cut1b.py::test_ui_experience_scales` | **A — OBSOLETE TEST** | Hardcoded `wm.chassis.width() == 380` — MINI was widened to 460 in UX-001. Fixed to compare against `wm.chassis.MINI_WIDTH`/`MINI_HEIGHT` (the actual authoritative constants) instead of a stale literal. |
| 5 | `test_production_cut2.py::test_desktop_lifecycle_tray_and_shutdown` | **A — OBSOLETE TEST** | Called `wm.handle_close_action()`, asserted `wm.is_hidden_to_tray` and `wm.restore_from_tray()` — all removed by UX-002. Rewritten around the current lifecycle (`minimize_requested` → MINI, `_focus_chassis()` for the tray "Show" action, `shutdown()`), preserving the original test's real intent (playback survives MINI compaction, session saves correctly on shutdown). |

**No real regression (classification B) was found** among the five — all were either stale assertions from superseded UX contracts or an honest environmental gap. No test was merely marked skipped to manufacture a green run; each A-classified test was rewritten to assert current authoritative behavior, and each C-classified test gained an explicit, documented skip condition rather than a blanket skip.

A sixth, previously-latent issue surfaced *during this cut's own work*: `MarqueeLabel` initially didn't call the base `QLabel.setText()`, silently breaking `.text()` for anything relying on it (including the pre-existing `test_fix_001.py::test_startup_empty_state_and_session_restore`, which asserts `wm.chassis.normal_title_marquee.text() == "♫ No Track Loaded"`). Caught immediately by running the full suite after introducing `MarqueeLabel`, and fixed in the same pass (§2) — not left as a new red test.

---

## 11. Tests

`tests/test_ux_004.py` — 24 tests, all passing:

| # | Test | What it asserts |
|---|------|-----------------|
| 1 | `test_short_title_does_not_marquee` | Fits → `_STATIC`, `_overflow_px == 0` |
| 2 | `test_long_title_activates_marquee` | Overflows → non-static state, `_overflow_px > 0` |
| 3 | `test_marquee_resets_on_title_change` | Mid-scroll state + offset both reset when the text actually changes |
| — | `test_unchanged_text_does_not_reset` | Setting the *same* text is a no-op (regression guard for the state/offset reset fix) |
| — | `test_text_accessor_stays_accurate` | `.text()` reflects the canonical title (regression guard, §10) |
| — | `test_resize_reevaluates_overflow` | Shrinking the widget activates overflow that wasn't there at a wider size |
| 4 | `test_normal_title_is_marquee_label` | `chassis.normal_title_marquee` is a `MarqueeLabel` |
| 5 | `test_mini_title_is_marquee_label` | `chassis.mini_title_marquee` is a `MarqueeLabel` |
| — | `test_update_telemetry_drives_both_marquees` | `update_telemetry()` updates both labels' text |
| 6 | `test_popup_opens_from_speaker_control` | Click toggles `volume_popup` visible |
| 7 | `test_popup_has_no_taskbar_identity` | `volume_popup` carries the `Qt.Popup` flag |
| 8 | `test_mini_volume_changes_authoritative_volume` | Dragging the popup slider emits `chassis.volume_changed` |
| 9 | `test_normal_slider_reflects_mini_change` | MINI drag → `normal_vol_slider.value()` updates live |
| 10 | `test_mini_popup_reflects_normal_change_on_open` | `set_volume()` (NORMAL-driven) then opening the popup shows the same value |
| — | `test_set_volume_updates_both_views` | `set_volume()` updates both sliders in one call |
| 11 | `test_mini_stays_460x36_with_popup_open` | Chassis dimensions unaffected by popup open/close |
| 12 | `test_version_resolves_to_0_2_0` | `toroidamp.__version__ == "0.2.0"` |
| — | `test_pyproject_matches_package_version` | `pyproject.toml` and the resolved package version agree |
| 13 | `test_main_module_uses_canonical_version_string` | `__main__.py` source contains no hardcoded `"0.1.0"` and references `__version__` |
| 14 | `test_patch_bump` | `0.2.0+patch->0.2.1`, `0.2.9+patch->0.2.10` |
| 15 | `test_minor_bump` | `0.2.9+minor->0.3.0`, `0.9.4+minor->0.10.0` |
| — | `test_major_bump` | `0.9.4+major->1.0.0` |
| — | `test_read_and_write_version_roundtrip` | Targeted regex replace preserves unrelated `pyproject.toml` lines |
| 16 | `test_bump_tool_performs_no_git_operation` | Tool source contains no `subprocess`/`os.system`/`os.popen` |

Full suite after this cut: **116 passed, 1 skipped** (the honestly-classified `libmodplug`-unavailable case), 0 failed — vs. the prior baseline's 5 known failures.

---

## 12. Manual Validation

Performed programmatically against an offscreen (`QT_QPA_PLATFORM=offscreen`) `QApplication` instance — no live windowed session was available in this working environment (consistent with the precedent set in UX-001 through UX-003).

* **Scenario 1 (short title)**: `"Short"` at both NORMAL and MINI title widths resolves to `_overflow_px == 0`, `_STATIC` — confirmed no timer runs.
* **Scenario 2 (long title)**: a deliberately long title against a narrow widget produces the full `PAUSE_START -> SCROLL_FWD -> PAUSE_END -> SCROLL_BACK` cycle, driven and observed tick-by-tick via `_tick()` and `_offset`/`_state` inspection.
* **Scenario 3 (track change mid-scroll)**: forced a mid-scroll state (`_offset=40`, `_state=SCROLL_FWD`), then changed the title — confirmed immediate reset to `_offset=0`, `_state=PAUSE_START` (this is the exact bug caught and fixed during implementation, §3/§10).
* **Scenario 4 (MINI volume)**: `_toggle_mini_volume_popup()` opens the popup while MINI is `460x36`; confirmed dimensions unchanged after open/close; confirmed `mini_pop_slider.setValue()` immediately emits `chassis.volume_changed`.
* **Scenario 5 (volume sync)**: drove both directions — MINI slider drag updates `normal_vol_slider.value()` live; `chassis.set_volume()` (simulating a NORMAL-driven, WindowManager-authoritative update) followed by opening the popup shows the exact same value on `mini_pop_slider`.
* **Scenario 6 (popup dismissal)**: not independently re-verified beyond confirming the `Qt.Popup` window flag is set — Qt's outside-click/focus-loss dismissal for `Qt.Popup` is native platform behavior, not custom code, and (per UX-001's own precedent) this class of behavior requires a live desktop to fully confirm.
* **Scenario 7 (taskbar)**: confirmed structurally (`Qt.Popup` flag) — as in prior cuts, actual single-taskbar-entry rendering needs a live Windows session to visually confirm.
* **Scenario 8 (version)**: `logger.info(f"Starting ToroidAMP v{__version__}")` produces exactly `Starting ToroidAMP v0.2.0`.
* **Scenario 9 (lifecycle)**: `test_ux_002.py`'s existing coverage (untouched by this cut) plus the rewritten `test_fix_001.py`/`test_production_cut2.py` tests (§10) jointly re-confirm NORMAL↔MINI, MINIMIZE→MINI, and CLOSE→shutdown are all intact.

---

## 13. Known Limitations

* **No live-desktop pass.** As with UX-001 through UX-003, popup dismissal-on-outside-click and single-taskbar-entry rendering are Qt/OS-native behaviors verified structurally (correct flags set) but not visually confirmed on a live Windows desktop.
* **MINI volume popup "toggle-close" is best-effort.** Per spec, clicking the speaker again while the popup is open may not reliably close it (`Qt.Popup`'s own outside-click handling can close it before the button's `clicked()` signal completes, at which point the handler's toggle logic reopens it). The spec explicitly permits this ("toggle/close is acceptable"); no additional click-sequencing logic was added to force a strict toggle, to avoid overengineering a transient control.
* **Marquee speed/pause values are a first pass**, chosen via implementation judgement (`1200ms` pause, `55px/s`) rather than human-timed preference — worth a quick human read-check on a live desktop before considering the exact numbers final.
* **`resolve_version()`'s pyproject.toml path walk is checkout-shaped** (`parents[2]` from `src/toroidamp/_version.py`). It falls back cleanly to `importlib.metadata` if that path doesn't exist, but a future packaging change (`PACKAGE-001`) should re-verify this fallback still resolves correctly under whatever packaging shape is eventually chosen.

---

## 14. Follow-up — NORMAL Marquee Bug & Vertical MINI Volume

Human validation found UX-004 partially failed: NORMAL titles didn't scroll, and the MINI volume popup was a visually heavy horizontal panel where a minimal vertical control was wanted.

### 14a. NORMAL Marquee Root Cause

Both were investigated per Part A's checklist. `NORMAL` **did** use `MarqueeLabel`, and its available width **was** being reported correctly in isolated testing — but a real structural defect was found regardless: `MarqueeLabel.set_marquee_text()` calls `super().setText(text)` (to keep `.text()` accurate for other code — a fix from the original UX-004 pass, §10/§3 of this doc). Left unguarded, that gives the underlying `QLabel` a `minimumSizeHint()`/`sizeHint()` equal to the **full, unwrapped title's pixel width** — measured directly:

```text
QLabel with a long title set -> sizeHint() == minimumSizeHint() == QSize(996, 12)
```

For a widget whose entire purpose is "take whatever space the layout leaves after its siblings," having its layout-facing size demand grow with the length of its *content* is exactly backwards, and is a well-known Qt footgun for custom marquee/ticker widgets. In this specific chassis instance it didn't visibly distort the `QHBoxLayout` split (the fixed-width `UnifiedChassis` forced compression regardless), but it's a latent bug that easily could under different content/sibling-width combinations — and matches the bug checklist's own hint ("whether the label receives a fixed/expanding size policy that prevents overflow detection") precisely.

**Fix** (`src/toroidamp/ui/marquee.py`): `MarqueeLabel.__init__` now sets `QSizePolicy(Ignored, Preferred)`, and overrides `sizeHint()`/`minimumSizeHint()` to return a small, content-length-independent value (`QSize(40, fontHeight+4)` / `QSize(20, fontHeight+4)`). The label's actual painted width is still whatever the layout's stretch factor allocates at runtime (unaffected — `resizeEvent` already drives `_recompute_overflow()`); only the *demand* the label makes on the layout is now decoupled from title length.

A second, independent defensive fix was added to the same root cause class: `showEvent()` now unconditionally calls `_recompute_overflow()` rather than only resuming an existing timer. `set_marquee_text()` only recomputes on an actual text *change* — if a title is set before its label's surrounding layout has settled on a final width (e.g. the very first track right after startup, or a scale switch revealing a previously-hidden page mid-layout), a stale "fits" verdict from that race would otherwise persist for the entire time that title stays on screen, since nothing re-triggers the check while the text itself is unchanged. Re-measuring on every `showEvent` closes that window.

**No second marquee implementation was created.** Both NORMAL and MINI titles still go through the same `MarqueeLabel` contract, unchanged in interaction/timing model (§2 above still applies verbatim) — this was purely a layout-integration fix.

### 14b. MINI Vertical Volume & Minimal Chrome

`chassis.py`'s `_build_mini_volume_popup()` was rebuilt:

* **Orientation**: `mini_pop_slider` is now `QSlider(Qt.Vertical, ...)`, fixed at a nominal 90px length.
* **Chrome removed**: the popup's `QWidget` no longer carries `background-color: #0a0b10; border: 1px solid #00f0ff; border-radius: 4px;`. It is now `background: transparent; border: none;`, with `WA_TranslucentBackground` (unchanged from before) — the only thing that paints is the slider itself (thin cyan groove, white handle with cyan border, brighter cyan on hover — no glow, no fill gradient, no panel).
* **Anchor** (`_compute_volume_popup_pos()`, new method): horizontally centered over `mini_vol_btn` (`btn_center_x - popup_width/2`), vertically placed so the popup's *bottom* sits just above MINI's top edge (`btn_top.y() - popup_height - gap`). Falls back below the speaker if that would place the popup above the current screen's available geometry, and clamps the horizontal position to stay on-screen — matching Part C exactly (primary: above; graceful fallback: below; never detached/off-screen).
* **Dismissal (Part F)** is unaffected — still the same `Qt.Popup` flag, same outside-click/focus-loss native dismissal, same toggle button, same "no separate taskbar window" property (still just a `Qt.Popup`-flagged `QWidget`, structurally identical to before in every way except its content and styling).
* **Volume authority (Part B/§5) is unchanged** — `mini_pop_slider.valueChanged` still drives the same single `_on_mini_volume_slider_changed` → `volume_changed` signal path; only the widget's orientation and visual chrome changed, not its role in the shared-state wiring.

---

## 15. Follow-up Tests

`tests/test_ux_004.py` gained two new test classes (14 additional tests, 35 total in the file, all passing):

**`TestNormalMarqueeInRealLayout`** (exercises `MarqueeLabel` inside the real chassis widget tree, not an isolated instance):

| Test | What it asserts |
|---|---|
| `test_normal_long_title_activates_marquee` | A genuinely long title overflows NORMAL's actual LCD width and animates |
| `test_normal_short_title_remains_static` | A short title stays `_STATIC` in NORMAL |
| `test_normal_marquee_resets_on_track_change` | Offset/state reset when the NORMAL title changes mid-scroll |
| `test_marquee_size_policy_does_not_grow_with_text_length` | **Regression guard for the actual bug** — NORMAL's allocated width is identical for a short vs. a long title |
| `test_mini_marquee_unaffected_by_normal_fix` | MINI still overflows/animates correctly after the NORMAL fix |

**`TestMiniVolumePopupFollowUp`**:

| Test | What it asserts |
|---|---|
| `test_mini_volume_slider_is_vertical` | `mini_pop_slider.orientation() == Qt.Vertical` |
| `test_popup_is_frameless_and_translucent` | `WA_TranslucentBackground` set, stylesheet says `transparent`, no `background-color` |
| `test_popup_still_has_no_taskbar_identity` | `Qt.Popup` flag intact |
| `test_popup_anchors_above_speaker_when_space_allows` | Popup bottom at/above the speaker top, horizontally centered, when there's room |
| `test_popup_falls_back_below_when_no_room_above` | Chassis pinned near the screen top → popup falls back below instead of going off-screen |
| `test_popup_clamped_to_screen_horizontally` | Popup x-position stays within the screen's available geometry |

All pre-existing UX-004 volume-sync tests (§11 above) were re-verified unchanged and still pass — they're orientation-agnostic (they only touch `mini_pop_slider.value()`/`.setValue()`), confirming the volume-authority wiring survived the vertical-slider rebuild untouched.

Full suite after this follow-up: **127 passed, 1 skipped** (the same honestly-classified `libmodplug` case), 0 failed.

---

## 16. Follow-up Manual Validation

Again performed programmatically against an offscreen `QApplication` (no live windowed session available here):

* **Scenario 1**: a long `"Artist — Title"`-shaped string, driven through `update_telemetry()` into the real chassis (not an isolated `MarqueeLabel`), now measures `_overflow_px > 0` and a non-`_STATIC` state in NORMAL — confirmed via both the new automated test and an interactive script.
* **Scenario 2**: forced mid-scroll state, then a genuinely different long title — confirmed immediate reset (`_offset=0`, `_state=PAUSE_START`), same mechanism verified in the original UX-004 pass, now re-confirmed specifically for NORMAL's real layout.
* **Scenario 3**: `_toggle_mini_volume_popup()` with the chassis moved to have vertical room — popup appears above the speaker, `orientation() == Qt.Vertical` confirmed.
* **Scenario 4**: inspected `volume_popup.styleSheet()` and `WA_TranslucentBackground` — confirmed no `background-color` remains; only the slider's own groove/handle paint.
* **Scenario 5**: not independently re-verified beyond the `Qt.Popup` flag (native Qt outside-click dismissal, same as the original UX-004 pass) — genuinely requires a live desktop to visually confirm, consistent with every prior cut's limitation here.
* **Scenario 6**: `mini_pop_slider.setValue(37)` → `normal_vol_slider.value() == 37`, confirmed live in an interactive script and via the existing `TestVolumeSync` suite (unaffected by the vertical rebuild).

---

## 17. Follow-up Known Limitations

* **Exact NORMAL failure mode not conclusively reproduced in this environment.** The `sizeHint`/`minimumSizeHint` fix is a real, defensible structural correction (verified via direct `QLabel` measurement showing a 996px-wide minimum for a long title) matching the debugging checklist's own hint, and the `showEvent` re-measure closes a genuine race window — but this offscreen/headless environment's own layout arithmetic already produced correct overflow detection for NORMAL even *before* either fix, in every test constructed here. It's possible the live failure was also influenced by font-metric differences between this environment's font substitution and the real Windows font backing "monospace" (different actual glyph widths would shift exactly where the overflow threshold falls) — that variable can't be controlled for without a live Windows desktop. Both fixes are correct and worth keeping regardless of which factor dominated the originally-reported failure.
* **Popup anchor gap is approximate.** The intended 4px gap between the popup's bottom edge and MINI's top edge measured ~2px in one offscreen test run — a minor, cosmetic rounding difference (likely from `adjustSize()`/layout-margin interaction), not a functional defect; worth a glance on a live desktop.
* **No live-desktop pass**, as with every UX cut so far — popup dismissal-on-outside-click, the vertical slider's actual visual weight, and the "no visible opaque rectangle" criterion (Part D's core ask) are Qt/OS-native or purely visual properties that were verified structurally (flags, stylesheet content) but not eyeballed on a real screen.

---

## 18. Follow-up 2 — NORMAL Marquee Travel Amplitude

Human validation confirmed direction/pause behavior was correct in both NORMAL and MINI, but displacement was too small to be useful — long `Artist — Title` strings didn't travel far enough to actually be read end-to-end.

### Root Cause

`MarqueeLabel` scrolled exactly to `overflow_px = text_width - visible_width` — the offset at which the *last pixel* of text just touches the viewport's right edge. That is technically "the end is visible," but perceptually it's barely distinguishable motion for a title that only slightly overflows (which is common in NORMAL's much wider LCD compared to MINI's) — the widget stops scrolling the instant the end merely arrives at the edge, with no visible confirmation that it got there.

### Fix

`MarqueeLabel._recompute_overflow()` (`src/toroidamp/ui/marquee.py`) now computes two separate values:

```python
overflow_px = max(0, text_width - visible_width)                              # gates activation, unchanged
max_offset  = overflow_px + END_REVEAL_MARGIN_PX if overflow_px > 0 else 0     # actual scroll travel target
```

`END_REVEAL_MARGIN_PX = 28` (within the suggested 20–40px range). `_tick()`'s forward-scroll target changed from `self._overflow_px` to `self._max_offset` — everything else (pause durations, scroll speed, ping-pong direction, activation threshold) is untouched, per the instruction not to fix this by increasing speed. Scrolling those extra 28px past the raw overflow point pushes the text a little further left than strictly necessary to reveal its last character, opening a small gap of blank space after the title before the pause — that gap is what makes "the end has been reached" visually legible, not just technically true.

Activation is unaffected: `overflow_px` (not `max_offset`) still gates whether the marquee animates at all, so a title that truly fits stays completely static — `max_offset` is only ever nonzero when `overflow_px` already is.

### Validation

Programmatically driven (`_tick()` called directly until `SCROLL_FWD` completes) against three cases in the real chassis, before/after comparison:

| Case | `visible_width` | `overflow_px` | `max_offset` | Reached |
|---|---|---|---|---|
| Moderate overflow (NORMAL) | 206px | 346px | 374px | 374px ✓ |
| Heavy overflow (NORMAL) | 206px | 994px | 1022px | 1022px ✓ |
| Same heavy title, MINI | 37px | 963px | 991px | (formula identical, not independently driven to completion in this run — confirmed via `test_normal_and_mini_use_identical_travel_formula_for_same_title`) |

MINI's own overflow/margin computation was confirmed unchanged and unregressed — it uses the exact same `_recompute_overflow()`/`_tick()` code path as NORMAL (no MINI-specific branch exists), so the fix that helped NORMAL applies identically and correctly to MINI's already-passing behavior.

### Tests

`TestMarqueeTravelAmplitude` (new, 5 tests) in `tests/test_ux_004.py`:

| Test | What it asserts |
|---|---|
| `test_max_offset_exceeds_raw_overflow_by_end_reveal_margin` | `max_offset == overflow_px + END_REVEAL_MARGIN_PX` for an overflowing title |
| `test_short_title_has_zero_max_offset` | A fitting title has `max_offset == 0` (no phantom travel) |
| `test_moderate_overflow_scrolls_past_raw_overflow` | A barely-overflowing title still travels the full margin-extended distance |
| `test_heavy_overflow_also_reaches_full_max_offset` | A heavily-overflowing title also completes its full (larger) travel |
| `test_normal_and_mini_use_identical_travel_formula_for_same_title` | Same formula applies identically in both chassis scales for the same title |

Full suite after this follow-up: **132 passed, 1 skipped** (same honestly-classified `libmodplug` case), 0 failed.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

UX-004 is an ergonomics/versioning-discipline cut within the existing ACTIVE Production Cut 3 phase. No phase changed, no decision gate changed, no architectural boundary moved. The version number itself changed (0.1.0 → 0.2.0), but per AGENTS.md/CURRENT_STATE.md policy this is a metadata change, not an operational-state change — CURRENT_STATE.md's own "Current Phase"/"Status" fields remain accurate as written. Operational baseline remains STABLE. Both follow-ups correct implementation defects found in human validation; neither changes phase, scope, or architecture.
