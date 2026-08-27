# ToroidAMP — UX-002 Always-Visible Player Contract

> **ToroidAMP does not disappear — it gets smaller.**

---

## 1. Core Rule

While ToroidAMP is running, the chassis is always visible on screen. The minimum presence is MINI mode. The only way for the chassis to leave the screen is the terminal CLOSE operation, which ends the process.

**States the running player can be in:**

| State | Description | Always-on-top |
|-------|-------------|---------------|
| MINI | Compact 460×36 strip — minimum presence | Yes |
| NORMAL | Full 420×135 chassis with transport controls | No |
| RETINA MELT | Fullscreen immersive visualizer | No |
| CLOSE | Process terminated | — |

There is no hidden state. There is no hide-to-tray lifecycle.

---

## 2. Human-Observed Problems (Before UX-002)

| # | Observation | Expected |
|---|-------------|----------|
| A | NORMAL ─ button hides the chassis to tray; player disappears | Switch to MINI, not disappear |
| B | MINI strip contains a redundant ─ (hide) button | MINI is already minimum presence; no hide button needed |
| C | Native OS minimize (Win+M, taskbar click) hides chassis | Intercept and redirect to MINI |
| D | Tray "Show" cycles through hide/show logic | Just raise and activate the visible chassis |
| E | `is_hidden_to_tray` flag threads through neon tick, save_session, etc. | No hidden state → no flag needed |

---

## 3. Part A — NORMAL ─ Button Semantics

### Before UX-002

```python
btn_min.setToolTip("Minimize to Tray (Keep Playing)")
btn_min.clicked.connect(self.minimize_requested.emit)
# In WindowManager._wire_signals:
self.chassis.minimize_requested.connect(self.hide_to_tray)
```

`hide_to_tray()` set `is_hidden_to_tray = True` and called `self.chassis.hide()`.

### After UX-002

```python
btn_min.setToolTip("Compact to MINI strip")
btn_min.clicked.connect(self.minimize_requested.emit)
# In WindowManager._wire_signals:
self.chassis.minimize_requested.connect(lambda: self.chassis.set_mode("mini"))
```

The `minimize_requested` signal still exists. The signal contract is unchanged; only the receiver changed. No `hide()` is called. The chassis switches from NORMAL to MINI and remains visible.

---

## 4. Part B — MINI Strip Controls

### Removed

The `btn_mini_hide` (─) button was removed from `_init_mini_view`:

```python
# REMOVED — UX-002
btn_mini_hide = QPushButton("─", self.mini_widget)
btn_mini_hide.setToolTip("Minimize to Tray (Keep Playing)")
btn_mini_hide.setFixedSize(16, 16)
btn_mini_hide.clicked.connect(self.minimize_requested.emit)
layout.addWidget(btn_mini_hide)
```

MINI is the minimized form. A hide button in MINI would hide the minimum presence — violating the always-visible contract and leaving the user with no UI.

### MINI Controls After UX-002

`◄◄` | `►` | `▶▶` | [LCD: title / elapsed / total] | 🔊 | `▲ NORMAL` | `⛶` | `✕`

The ✕ (close) button remains — it is the only path out of the running state.

---

## 5. Part C — Native OS Minimize Interception

### Problem

Windows minimize events (taskbar button click, Win+M, keyboard shortcut) reach the Qt window as a `WindowStateChange` event with `Qt.WindowMinimized` in the window state. Qt's default response is to hide the window — violating the always-visible contract.

### Fix — `changeEvent` Override in `UnifiedChassis`

```python
def changeEvent(self, event):
    if event.type() == QEvent.Type.WindowStateChange:
        if self.windowState() & Qt.WindowMinimized:
            self.setWindowState(Qt.WindowNoState)
            if self.mode != "mini":
                self.set_mode("mini")
            event.accept()
            return
    super().changeEvent(event)
```

**Sequence:**
1. OS minimize event arrives → `changeEvent` fires.
2. Detect `Qt.WindowMinimized` in window state.
3. Immediately cancel the minimize: `setWindowState(Qt.WindowNoState)`.
4. If not already MINI, call `set_mode("mini")` — chassis stays visible.
5. `event.accept()` and return without calling `super()`.

**No recursion risk.** `setWindowState(Qt.WindowNoState)` fires another `WindowStateChange`, but the second event carries `Qt.WindowNoState`, not `Qt.WindowMinimized` — the guard does not trigger again.

### Known Limitation — Win+D (Show Desktop)

Win+D is an OS shell operation that temporarily lowers all windows to reveal the desktop. It does not send a WM_SYSCOMMAND/SC_MINIMIZE message; it does not set `WS_MINIMIZE`. Qt does not receive a `WindowStateChange` for it. The chassis will be visually obscured while the desktop is shown. Pressing Win+D again or clicking any taskbar button restores it. This is an accepted OS-level limit — no clean interception path exists without Win32 shell hooks.

---

## 6. Part D — Tray Icon Semantics

### Before UX-002

`tray_icon.restore_requested` → `restore_from_tray()` — this toggled `is_hidden_to_tray = False`, called `chassis.show()`, and re-showed modules.

### After UX-002

```python
self.tray_icon.restore_requested.connect(self._focus_chassis)

def _focus_chassis(self):
    """Raises and activates the chassis window (tray Show action)."""
    self.chassis.raise_()
    self.chassis.activateWindow()
```

Because the chassis is always visible, "Show" just raises it to the foreground and gives it focus. No hide/show cycle, no module state restoration needed.

The tray icon remains. It still provides play/pause, prev, next, and exit controls. "Show" in the tray context menu is retained as a convenience to bring a MINI chassis to the foreground from behind other windows.

---

## 7. Part E — Removed: `hide_to_tray`, `restore_from_tray`, `handle_close_action`, `is_hidden_to_tray`

### Methods Removed from `WindowManager`

| Method | Was | Now |
|--------|-----|-----|
| `hide_to_tray()` | Hid chassis; set `is_hidden_to_tray = True` | **Deleted** |
| `restore_from_tray()` | Showed chassis; cleared flag | **Deleted** — replaced by `_focus_chassis()` |
| `handle_close_action()` | Conditional hide-or-shutdown (dead code) | **Deleted** |

### Flag Removed

`self.is_hidden_to_tray = False` initialization removed from `__init__`. All references to `is_hidden_to_tray` eliminated.

### Neon Tick Guard Removed

**Before:**
```python
if not self.is_hidden_to_tray:
    frame = self.handoff.get_audio_frame(44100) if is_playing else None
    ...neon update...
```

**After:**
```python
# Chassis is always visible — neon always runs.
frame = self.handoff.get_audio_frame(44100) if is_playing else None
...neon update...
```

The `# Zero CPU/GPU visualizer waste when hidden to tray or in MINI mode` comment was also removed — in MINI, the `if self.vis_mod.isVisible()` guard already prevents visualizer DSP from running; there is no extra cost from always running the neon update.

---

## 8. Session State

### Before UX-002

Session could theoretically persist a `hidden` state. On startup with a hidden session, the chassis would remain invisible until tray interaction.

### After UX-002

Session persists `scale` — one of `"mini"` or `"normal"`. Startup always shows the chassis via `_apply_restored_session` → `self.chassis.set_mode(st.scale, animated=False)` → `self.chassis.show()`. No hidden startup path exists.

---

## 9. Tests

`tests/test_ux_002.py` covers:

| # | Test Class | What it asserts |
|---|-----------|-----------------|
| A1 | `TestNormalMinimizeRouting` | `minimize_requested` signal exists |
| A2 | `TestNormalMinimizeRouting` | NORMAL ─ button emits `minimize_requested`, not `close_requested` |
| A3 | `TestNormalMinimizeRouting` | MINI strip has no ─ hide button |
| B1–B4 | `TestWindowManagerNoHiddenState` | `hide_to_tray`, `restore_from_tray`, `handle_close_action` removed; `_focus_chassis` present |
| D1 | `TestChangeEventMinimizeInterception` | `changeEvent` is overridden in `UnifiedChassis` |
| D2 | `TestChangeEventMinimizeInterception` | Minimize state → switches to MINI |
| D3 | `TestChangeEventMinimizeInterception` | Minimize while already MINI → no error, stays MINI |
| D4 | `TestChangeEventMinimizeInterception` | Non-minimize state change → passes through, mode unchanged |
| E1 | `TestTrayRestoreRouting` | `_focus_chassis` calls `raise_()` and `activateWindow()` |
| F1–F5 | `TestLifecycleStates` | MINI↔NORMAL transitions; `close_requested` present; MINI always-on-top; NORMAL not always-on-top |
| G1 | `TestNeonTickUnconditional` | `is_hidden_to_tray` absent from `WindowManager` source |
| R1–R4 | `TestUX001Regression` | SeekSlider, MINI time display, MINI width=460, closeEvent routing all intact |

**Note on native minimize tests:** `TestChangeEventMinimizeInterception.test_minimize_state_redirects_to_mini_mode` manually sets the window state and calls `changeEvent` directly. This exercises the guard logic without relying on the OS sending the event. Manual Windows validation is required to confirm the full interception path (see §10).

---

## 10. Manual Validation Scenarios

### SCENARIO 1 — NORMAL ─ Button

```
Play any track
Press ─ in the NORMAL chassis header
Expected: chassis switches to MINI, remains visible
NOT: chassis disappears to tray
```

### SCENARIO 2 — MINI Strip Controls

```
Enter MINI mode
Expected controls: ◄◄ ► ▶▶ [LCD] 🔊 ▲NORMAL ⛶ ✕
NOT expected: a ─ button in the MINI strip
```

### SCENARIO 3 — Native OS Minimize (Windows)

```
Open ToroidAMP in NORMAL mode
Click the taskbar button to minimize
Expected: chassis switches to MINI, stays visible on desktop
NOT: chassis disappears

Press Win+M (minimize all)
Expected: chassis switches to MINI (may be briefly obscured; restores on Win+M again)

Press Win+D (show desktop)
Expected: chassis may be obscured temporarily; restores on Win+D again
        (Win+D is a known OS-level limit — cannot be intercepted cleanly)
```

### SCENARIO 4 — Native OS Minimize (Keyboard)

```
Open ToroidAMP in NORMAL mode
Press Alt+Space → N (native minimize via system menu)
Expected: chassis switches to MINI, stays visible
```

### SCENARIO 5 — Tray Show

```
Open ToroidAMP in MINI mode behind other windows
Right-click tray icon → Show
Expected: chassis raised to foreground, gains focus
NOT: chassis hidden and re-shown (no flicker)
```

### SCENARIO 6 — Tray Exit

```
Right-click tray icon → Exit
Expected: shutdown sequence executes, process exits cleanly
```

### SCENARIO 7 — Retina Melt → Return

```
NORMAL → ⛶ MELT → fullscreen visualizer
Press Esc or exit button
Expected: chassis returns to NORMAL mode, visible
```

### SCENARIO 8 — FIX-002 Lifecycle Regression

```
Minimize (─) → chassis switches to MINI, playback continues
✕ → shutdown sequence, process exits
Alt+F4 → same shutdown sequence
Tray → Exit → same shutdown sequence
```

---

## 11. Known Limitations

### Win+D (Show Desktop)

Win+D is handled by the Windows shell, not via `WM_SYSCOMMAND`. Qt does not receive a `WindowStateChange` for it. The chassis will be temporarily obscured behind the desktop until Win+D is pressed again or the user clicks back to it. This is a documented OS-level limit — no clean interception without Win32 shell hooks, which are out of scope.

### Tray Visibility on Mono-Tray Setups

The system tray icon is always visible while ToroidAMP is running. On setups with very limited tray space, the tray icon may be hidden in the overflow. The chassis, being always visible on screen, remains the primary interaction point regardless.

### Module Visibility in MINI

When switching from NORMAL to MINI, VIS and PL modules are hidden (as before UX-002). The `saved_vis_visible` and `saved_pl_visible` flags in `WindowManager` correctly restore module visibility on return to NORMAL. This behavior is unchanged.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

UX-002 is a lifecycle simplification within the existing ACTIVE Production Cut 3 phase. No phase changed, no decision gate changed. Operational baseline remains STABLE.
