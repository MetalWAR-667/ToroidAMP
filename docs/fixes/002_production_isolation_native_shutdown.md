# ToroidAMP — FIX-002: Production Isolation & Native Window Shutdown Report

> **"A normal production launch of ToroidAMP must not inspect, scan, import media from, or depend on MetalWar-Installer."**
> **"ALL real close/exit paths (custom X, MINI X, tray Exit, Taskbar thumbnail X, Alt+F4, WM_CLOSE) must converge onto the authoritative WindowManager shutdown sequence."**

---

## 1. Executive Summary

FIX-002 resolves two baseline production defects:
1. **Production Isolation**: Identified and eliminated hardcoded donor/development test media injection from `src/toroidamp/__main__.py`. Launching ToroidAMP with no existing session file and no CLI arguments now starts with an empty playlist (`len(playlist) == 0`), no pre-loaded audio, and zero runtime dependencies on `MetalWar-Installer`.
2. **Native Window Close (Taskbar Thumbnail X / Alt+F4 / WM_CLOSE)**: Intercepted `QWidget.closeEvent` on `UnifiedChassis` and routed all native OS close events directly to `WindowManager.shutdown()`. This prevents orphan processes or hung Qt loops when closing via the Windows taskbar thumbnail preview or `Alt+F4`.

---

## 2. Root Cause Analysis

### A. Playlist Contamination
* **Observed Symptom**: Deleting `session.json` and launching ToroidAMP resulted in `Burn The World Waltz.mp3` and `dalezy-lotus_drei_remix.xm` appearing in the playlist.
* **Root Cause**: `src/toroidamp/__main__.py` contained a development fallback block (`if len(playlist) == 0: ...`) that inspected `tests/assets/audio/` and `../../../Metalwar-Installer/` and populated sample tracks into the playlist.
* **Fix**: Removed the entire bootstrap fallback block. When no session or CLI arguments are provided, `PlaylistManager` remains cleanly empty (`current_index = -1`, `current_item = None`).

### B. Native Taskbar Close Hang
* **Observed Symptom**: Clicking the `✕` button on the Windows taskbar thumbnail preview closed/hid the visual window, but left the Python process running in the background.
* **Root Cause**: Windows taskbar thumbnail close sends a native `WM_CLOSE` event directly to the active top-level `QWidget` (`UnifiedChassis`). Because `UnifiedChassis` had no custom `closeEvent()` override, Qt executed default widget destruction, closing only the chassis while leaving `ToroidTrayIcon`, background timers (`render_timer`, `snap_timer`), and the `QApplication` event loop (`setQuitOnLastWindowClosed(False)`) active.
* **Fix**: Implemented `UnifiedChassis.closeEvent()` to ignore default widget closure and emit `self.close_requested`, which routes directly to `WindowManager.shutdown()`. Added an `_is_shutting_down` re-entrancy guard in `WindowManager.shutdown()` to ensure single, clean execution.

---

## 3. Lifecycle Convergence Matrix

| Close Trigger | Mechanism | Destination | Shutdown Result |
| :--- | :--- | :--- | :--- |
| **Normal Titlebar `✕`** | `QPushButton.clicked` | `close_requested.emit()` $\to$ `WindowManager.shutdown()` | **Complete process exit (0)** |
| **MINI Titlebar `✕`** | `QPushButton.clicked` | `close_requested.emit()` $\to$ `WindowManager.shutdown()` | **Complete process exit (0)** |
| **System Tray "Exit"** | `QAction.triggered` | `exit_requested.emit()` $\to$ `WindowManager.shutdown()` | **Complete process exit (0)** |
| **Taskbar Thumbnail `✕`** | `WM_CLOSE` | `closeEvent()` $\to$ `close_requested.emit()` $\to$ `shutdown()` | **Complete process exit (0)** |
| **Keyboard `Alt+F4`** | `QCloseEvent` | `closeEvent()` $\to$ `close_requested.emit()` $\to$ `shutdown()` | **Complete process exit (0)** |
| **Chassis Minimize `─`** | `QPushButton.clicked` | `minimize_requested.emit()` $\to$ `WindowManager.hide_to_tray()` | **UI hidden, audio keeps playing** |

---

## 4. Test Suite & Verification Results

* **Regression Test Suite**: [`tests/test_fix_002.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_fix_002.py)
  * `test_production_isolation_empty_startup`: **PASS** (Verifies clean empty playlist on startup with no session).
  * `test_no_donor_path_in_production_codebase`: **PASS** (Ensures no runtime donor references in `src/toroidamp/`).
  * `test_native_close_event_routing`: **PASS** (Verifies `QCloseEvent` routes to full `WindowManager.shutdown()`).
* **Existing Test Suites**:
  * [`tests/test_fix_001.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_fix_001.py): **PASS (100%)**
  * [`tests/test_production_cut2.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut2.py): **PASS (100%)**
  * [`tests/test_production_cut1b.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut1b.py): **PASS (100%)**

---

## 5. Manual Validation Summary

1. **Clean Startup**: Deleted `session.json` and launched `python -m toroidamp`. Verified startup voice announcement played, playlist was empty, marquee displayed `"♫ No Track Loaded"`, and audio engine remained stopped.
2. **Explicit Media Drag/Load**: Dragged a test track into the playlist and verified only the added track existed and played normally.
3. **Taskbar Thumbnail Close**: Started playback, hovered the taskbar icon, clicked thumbnail `✕`, and confirmed audio stopped immediately and the process exited cleanly (return code 0).
4. **Alt+F4**: Launched application and pressed `Alt+F4`; confirmed immediate full shutdown.
5. **Minimize `─`**: Started playback and pressed `─`; confirmed UI hid to tray while audio continued playing.
