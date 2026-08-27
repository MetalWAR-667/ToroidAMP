# ToroidAMP — UX-001 Daily Use Ergonomics

> **When the human clicks halfway through a song, go halfway through the damn song.**

---

## 1. Human-Observed Issues

Three concrete friction points surfaced during real daily desktop use:

| # | Observation | Expected |
|---|-------------|----------|
| A | Single-click on the seek timeline groove does nothing | Immediate seek to clicked position |
| B | Hovering the Windows taskbar icon shows three window previews (chassis, VIS, PL) | One preview — the chassis |
| C | MINI strip is too narrow; shows only elapsed time | Wider strip; elapsed / total visible |

---

## 2. Click-to-Seek Root Cause

`UnifiedChassis._init_normal_view` built the timeline as a plain `QSlider`.

`QSlider` emits `sliderMoved` only when the **handle** is dragged. A click anywhere else on the groove does nothing by default — Qt's built-in behavior moves by `pageStep`, which for a 0–1000 range produces large jumps rather than a precise seek, and it uses `valueChanged`, not `sliderMoved`. The `seek_changed` signal was wired only to `sliderMoved`:

```python
self.normal_seek_slider.sliderMoved.connect(self.seek_changed.emit)
```

So a direct click emitted neither `sliderMoved` nor `seek_changed` — it silently failed.

---

## 3. Seek Interaction Fix

### SeekSlider

A `SeekSlider(QSlider)` subclass was added to `chassis.py`. It overrides `mousePressEvent`:

1. **Detect click target.** `QStyle.hitTestComplexControl` identifies whether the press landed on `SC_SliderHandle` or elsewhere on the groove.
2. **Handle → fall through.** If the press is on the handle, `super().mousePressEvent(event)` handles it normally (drag starts, `sliderMoved` fires as usual).
3. **Groove → direct seek.** If the press is on the groove:
   - Compute usable slider travel using `subControlRect(SC_SliderGroove)` and `subControlRect(SC_SliderHandle)` — this uses Qt's actual style metrics and accounts for handle half-width on each end.
   - Compute `ratio = offset / usable_width`, clamped to `[0.0, 1.0]`.
   - `setValue(value)` to move the visual handle.
   - `sliderMoved.emit(value)` — the existing seek pathway fires; `WindowManager._on_seek` receives it and calls `player_engine.seek(target_seconds)`.

**Seek is still one authority.** `_on_seek` in `WindowManager` performs the actual `player.seek()`. `SeekSlider` only ensures the signal reaches it via the existing channel.

### Seek Safety

`WindowManager._on_seek` already guards:

```python
def _on_seek(self, slider_val: int):
    duration = self.player_engine.duration
    if duration > 0.0:
        target_sec = (slider_val / 1000.0) * duration
        self.player_engine.seek(target_sec)
```

No track loaded or `duration == 0` → no-op. This is unchanged.

### Drag Regression

Handle drag is unchanged. `super().mousePressEvent(event)` is called for handle-hits, and the `sliderMoved` connection to `seek_changed` remains intact.

---

## 4. Window / Taskbar Root Cause

`ModuleShell.__init__` was:

```python
super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
```

`WindowManager` created modules with `parent=None`:

```python
self.vis_mod = VisualizerModule()
self.pl_mod = PlaylistModule(self.playlist)
```

With `parent=None`, both modules become root-level top-level windows in Win32 terms — Windows allocates each its own taskbar button. Three windows with `Qt.Window` and no owner → three taskbar entries.

---

## 5. Qt Ownership Decision

**Mechanism:** Pass `chassis` as the Qt parent when constructing modules.

```python
self.vis_mod = VisualizerModule(parent=self.chassis)
self.pl_mod = PlaylistModule(self.playlist, parent=self.chassis)
```

In Win32, a top-level window with an owner (a HWND set via the owner-window parameter) is an "owned" window. Windows does not give owned windows their own taskbar buttons — only the owner (the chassis) appears.

Qt implements this ownership exactly: when a `QWidget` with `Qt.Window` flag is given a non-None parent, Qt sets the parent as the Win32 owner on Windows, while still allowing independent positioning. The modules remain visually and spatially independent; only their OS taskbar identity is collapsed into the chassis.

**No Win32 API hacks.** No `WS_EX_NOACTIVATE`, no `SetWindowLong`, no ctypes. Clean cross-platform Qt model.

**What is preserved:**
- Independent module dragging ✓
- Floating modules ✓
- Docking and magnetic snap ✓
- Visibility toggles ✓
- Module restoration ✓
- Multi-monitor positioning ✓
- Chassis shutdown ownership ✓
- FIX-002 native close routing ✓

---

## 6. MINI Layout Adjustment

### Previous Dimensions

`380 × 36 px`

### New Dimensions

`460 × 36 px`

Width increase: **+80 px**. Height unchanged.

The additional 80 px primarily benefits:
- Track title readability (wider title marquee stretch area)
- Elapsed / total time display (needs ~90 px for `00:00 / 00:00` at monospace 9px)

Controls remain compact. No button sizes were changed.

The `MINI_WIDTH` and `MINI_HEIGHT` are now defined as class constants on `UnifiedChassis` to make future changes explicit and testable:

```python
MINI_WIDTH = 460
MINI_HEIGHT = 36
NORMAL_WIDTH = 420
NORMAL_HEIGHT = 135
```

---

## 7. Time Display Contract

### Before UX-001

`update_telemetry` truncated the time string for MINI:

```python
self.mini_time_display.setText(
    time_str.split(" / ")[0] if " / " in time_str else time_str
)
# e.g. "02:15 / 06:34" → "02:15"
```

### After UX-001

```python
self.mini_time_display.setText(time_str)
# e.g. "02:15 / 06:34" → "02:15 / 06:34"
```

The full elapsed / total string reaches the MINI display unchanged.

### Stable-Width Formatting

`mini_time_display` has `setMinimumWidth(90)` and `Qt.AlignRight | Qt.AlignVCenter`. Digit changes do not shift adjacent layout elements.

### Long Tracks (>= 1 hour)

`WindowManager._tick` formats time as `MM:SS / MM:SS`. For tracks >= 1 hour, `p_min` and `d_min` exceed 59, producing `70:30 / 90:00`-style output — sensible and correct. No special hour-format handling was introduced in this cut. The 90 px minimum width comfortably accommodates these values.

---

## 8. Session Geometry Compatibility

### Problem

Session files persist `chassis_pos.w` and `chassis_pos.h`. Old sessions stored `w=380`. New MINI is `w=460`.

Previous restoration sequence:

```
clamp_to_screen(cx, cy, session_w=380, session_h=36)   ← stale width
chassis.move(cx, cy)
chassis.set_mode("mini")                                ← makes chassis 460 wide
```

If the chassis was near the right edge of the screen (`x = screen_right - 380`), after `set_mode` the chassis would extend 80 px off-screen.

### Fix

Set scale mode **before** clamping:

```
chassis.set_mode("mini")                                ← authoritative 460 × 36
clamp_to_screen(cx, cy, chassis.width(), chassis.height())  ← real dimensions
chassis.move(cx, cy)
```

Now clamping always uses the live chassis size. Old sessions restore cleanly: position is honoured, dimensions are upgraded to current.

### Invariant

Position persists. Authoritative current dimensions always win.

---

## 9. Tests

`tests/test_ux_001.py` covers:

| # | Test | What it asserts |
|---|------|-----------------|
| A1 | `TestSeekSliderPositionConversion` | `SeekSlider` subclasses `QSlider`; `sliderMoved` is the seek channel |
| A2 | `TestSeekSliderPositionConversion.test_chassis_uses_seeksider` | `normal_seek_slider` is a `SeekSlider` instance |
| A3 | `TestSeekSliderPositionConversion.test_seek_value_clamped` | Ratio-to-value conversion stays within `[min, max]` |
| A4 | `TestClickToSeekSafety` | `_on_seek` guard: no-op when `duration == 0`; seeks when `duration > 0` |
| A5 | `TestDragSeekUnaffected` | `sliderMoved` → `seek_changed` connection intact |
| B1–B4 | `TestModuleWindowFlags` | Modules carry `Qt.Window`; modules have chassis as parent |
| C1–C3 | `TestMiniTimeDisplay` | MINI shows full `elapsed / total`; no truncation |
| C4–C6 | `TestMiniWidth` | MINI width >= 440; height == 36; `MINI_WIDTH` constant matches live width |
| D1–D2 | `TestSessionGeometryCompatibility` | `set_mode` always applies `MINI_WIDTH` regardless of stale state |
| E1–E2 | `TestLifecycleSemantics` | `closeEvent` ignores event and emits `close_requested`; all signals present |

**Note on taskbar tests:** No automated test can prove that Windows renders a single taskbar entry. `TestModuleWindowFlags` asserts the Qt ownership mechanism that produces this result. Manual Windows validation is required (see §10).

---

## 10. Manual Windows Validation

### SCENARIO 1 — Click-to-Seek

```
Play a long track (>3 min)
Single-click at ~25% of timeline groove
Expected: immediate seek to ~25% of track
Single-click at ~50%
Expected: immediate seek to ~50%
Single-click at ~75%
Expected: immediate seek to ~75%
```

### SCENARIO 2 — Drag Seek

```
Drag slider handle from left to right
Expected: smooth continuous seek (existing behavior preserved)
```

### SCENARIO 3 — Taskbar (PRIMARY GOAL)

```
Open ToroidAMP in NORMAL mode with VIS and PL visible
Hover Windows taskbar icon
Expected: ONE preview thumbnail (chassis only)
NOT: three separate previews

Test with modules DOCKED
Test with modules FLOATING
Both configurations must yield ONE taskbar identity
```

### SCENARIO 4 — Module UX After Taskbar Fix

```
Detach VIS (undock) → drag to new position → redock
Expected: no behavioral regression

Detach PL → drag → redock
Expected: no behavioral regression

Modules must remain independently draggable even with chassis as Qt parent
```

### SCENARIO 5 — MINI Time Display

```
Play any track
Press ▼ MINI to enter compact strip
Expected visible information:
  - prev / play-pause / next buttons
  - track title (truncated if long)
  - elapsed / total (e.g. "02:15 / 06:34")
  - volume icon
  - ▲ NORMAL button
  - ⛶ MELT button
  - minimize / close controls
```

### SCENARIO 6 — Long Title in MINI

```
Load a track with a very long filename
Enter MINI mode
Expected: title truncates sensibly; time display "00:00 / 00:00" remains readable
```

### SCENARIO 7 — Lifecycle Regression (FIX-002)

```
Minimize (─) → ToroidAMP hides to tray, playback continues
Restore from tray → correct window state restored

Close (✕) → shutdown sequence executes, process exits

Alt+F4 → same shutdown sequence

Tray → Exit → same shutdown sequence
```

---

## 11. Known Limitations

### Taskbar — Windows Only Validation

Qt's parent-as-owner mechanism is the correct cross-platform approach. On Linux (Wayland / X11), window management differs; the taskbar suppression effect of Qt parent ownership is platform-defined. Manual verification on Linux is pending. The Qt mechanism itself is harmless on Linux even if the taskbar grouping behavior differs.

### Click-to-Seek — Handle Edge Behavior

When clicking very close to the handle (but not exactly on it), `hitTestComplexControl` may classify the hit as `SC_SliderHandle` under some styles, deferring to normal drag behavior. This is correct — it avoids surprising the user by jumping when they meant to grab. The threshold is style-defined.

### MINI Title Truncation

`mini_title_marquee` uses a `QLabel` with no explicit `elideMode`. Long titles may overflow or truncate depending on Qt layout stretch behavior. A future cut should add explicit `elideMode = Qt.ElideRight` or a scrolling marquee. This is not introduced in UX-001 to stay within scope.

### Session Geometry — Module Positions

Module positions (`vis_module.x/y`, `pl_module.x/y`) are still clamped using hardcoded module sizes (420×240, 270×240). These are correct for the current module dimensions and are unchanged by UX-001.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

UX-001 corrects daily-use ergonomics within the existing ACTIVE Production Cut 3 phase. No phase changed, no decision gate changed. Operational baseline remains STABLE.
