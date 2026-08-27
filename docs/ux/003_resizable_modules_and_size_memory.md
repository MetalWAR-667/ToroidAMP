# ToroidAMP — UX-003 Resizable Modules & Size Memory

> **If the user spends time making the visualizer the perfect size, ToroidAMP should remember that.**
> **If the user wants the factory dimensions back: click the little arrow.**

---

## 1. UX Goal

`VisualizerModule` and `PlaylistModule` were fixed-size (`420×240` / `270×240`) since Production Cut 1B. UX-003 makes both freely resizable while establishing the authoritative rule:

> **USER SIZE IS STATE.**

MINI/NORMAL transitions, docking, and RETINA MELT may hide or temporarily constrain a module's geometry, but none of them may silently discard the size the user chose.

---

## 2. Previous Fixed-Size Model

`ModuleShell.__init__` gave both modules no resize contract at all; subclasses called `self.setFixedSize(w, h)`, which clamps `minimumSize == maximumSize == (w, h)` — Qt refuses any resize attempt outright. `VisualizerModule` additionally hardcoded its offscreen Pygame render surface at `412×185`, entirely decoupled from the (fixed) viewport size.

---

## 3. Resize Interaction

`ModuleShell` (`src/toroidamp/ui/modules/base.py`) is frameless (`Qt.Window | Qt.FramelessWindowHint`), so there is no native OS edge-resize. A small hit-testing layer was added directly to the shell:

* `RESIZE_MARGIN = 6` px border strip is checked in `mousePressEvent`/`mouseMoveEvent` against the widget's own rect (`_edge_at`), returning the subset of `{left, right, top, bottom}` under the cursor.
* A press on an edge starts a resize drag; `mouseMoveEvent` computes a new `QRect` from the drag delta and calls `setGeometry`, clamping each edge so the module can never shrink below `MIN_SIZE`.
* Hovering (no button held) sets the matching Qt cursor (`SizeHorCursor`/`SizeVerCursor`/`SizeFDiagCursor`/`SizeBDiagCursor`) so the affordance is discoverable without a visible grip.
* The title bar (`y <= 24`) still drags the whole module, as before; edge hit-testing takes priority so the extreme top/left/right pixels resize rather than drag.
* All four corners plus all four edges are supported, matching the "at minimum: left, right, top, bottom, four corners" requirement.

This is a standard Qt-native approach (manual geometry via `setGeometry`), not a Win32-specific hack, and coexists cleanly with the existing title-bar drag and drag-to-undock behavior.

---

## 4. Repurposed Control — RESET SIZE

The module titlebar's small arrow/corner button (`⇲`/`⇱`, previously "Dock / Undock") is now **`↺` "Reset size"**, wired to `ModuleShell.reset_size()`:

```python
def reset_size(self):
    self._user_size = QSize(self.DEFAULT_SIZE)
    self.resize(self.DEFAULT_SIZE)
```

It does exactly one thing — restore `DEFAULT_SIZE` and record it as the new user size. It does not move, dock, undock, close, or touch playlist/visualizer content.

**Consequence for docking**: manual dock/undock toggling was the *only* thing that button did. It is now entirely automatic — dragging a floating module near the chassis magnetically docks it (`WindowManager._check_magnetic_snapping`, unchanged), and dragging a docked module undocks it (`ModuleShell.mouseMoveEvent` already emitted `undock_requested` on drag while docked — unchanged). No manual dock toggle exists anymore; this is a deliberate trade specified by this cut, not an oversight.

---

## 5. Visualizer Resize Behavior

* `VisualizerModule.DEFAULT_SIZE = QSize(420, 240)`, `MIN_SIZE = QSize(300, 180)` — the minimum leaves room for the title bar (22px), bottom bar (22px), margins/spacing, and a genuinely usable render area, while keeping the mode-switch and MELT buttons legible.
* `DOCK_LOCKED_AXIS = "width"` — while docked, width is not user-resizable (see §6); height is.
* The offscreen Pygame surface is no longer a hardcoded constant. `_sync_surface_size()` reads the actual `vis_label` viewport size on every `resizeEvent` and, if it changed, recreates `self.surface` and calls `visualizer.resize(w, h)` on **every** visualizer instance (not just the active one), so switching visualizers after a resize is still correct.
* `ToroidVisualizer.resize()` and `WaveformRibbonVisualizer.resize()` already existed (used previously only by the fullscreen window) and already recompute their center/geometry from `self.w`/`self.h` on every frame — no visualizer-internal changes were needed; they were already free of hardcoded projection centers.

---

## 6. Playlist Resize Behavior

* `PlaylistModule.DEFAULT_SIZE = QSize(270, 240)`, `MIN_SIZE = QSize(230, 200)` — sized to keep all six toolbar buttons (`+ADD -DEL CLR SHF REP M3U`) and the footer legible.
* `DOCK_LOCKED_EDGES = {"left", "top"}` — while docked, left/top are excluded (they anchor PL's position, see §7/§7a); right and bottom — i.e. **both width and height** — remain fully user-resizable while docked.
* `list_widget` was already added to the module's `QVBoxLayout` with `stretch=1`; no code change was needed for it to grow with the module — both wider (more title space) and taller (more visible rows) resizing "just works" through existing Qt layout stretch.

---

## 7. Docking Size Semantics

Docking topology is unchanged (Visualizer below chassis, Playlist to the right). What changed is how docked geometry interacts with user resize:

* **Visualizer, docked**: width is forced to the chassis width (`WindowManager.realign_docked_modules`) — the simplest predictable behavior, since the two edges must align visually. Height remains freely resizable while docked (it only pushes the bottom edge further down; nothing sits below it).
* **Playlist, docked**: only *position* is forced — x anchors to the chassis right edge, y anchors to the chassis top. **Size is never forced** (see §7a, follow-up correction). Width and height both remain freely resizable while docked.
* Resize-edge hit-testing respects docking constraints per module via `ModuleShell.DOCK_LOCKED_EDGES` (a set of edges disabled while docked): `ModuleShell._allowed_edges()` excludes those edges so the user cannot drag one that docking would fight. VIS excludes `{left, right}` (width is forced). PL excludes `{left, top}` (those anchor its position — dragging them would fight the position anchor on the next realign tick, not a size lock).

### 7a. Follow-up correction — Docked Playlist Vertical Resize

**Original UX-003 defect (human-validated)**: the first pass over-generalized "docking constrains one axis" from Visualizer to Playlist, giving `PlaylistModule.DOCK_LOCKED_AXIS = "height"` and having `realign_docked_modules()` force PL's height to `chassis.height()` (or the combined VIS+chassis stack height) on every realign tick. This made the single most useful Playlist interaction — "make it taller to see more queue rows" — impossible while docked, which is the module's normal state.

**Correction**: docking defines **attachment/position** for Playlist, not size.

* `WindowManager.realign_docked_modules()` — the PL block now only calls `self.pl_mod.move(core_geom.right() + 2, core_geom.top())`. The stack-height `resize()` call was removed entirely and not replaced with any other automatic height rule.
* `PlaylistModule.DOCK_LOCKED_EDGES` changed from (conceptually) `{"left", "right"}` (full width lock via the old axis model) to `{"left", "top"}` — the two edges that anchor PL's position. Right and bottom (width and height) are draggable while docked.
* `ModuleShell._allowed_edges()` was generalized from a `DOCK_LOCKED_AXIS: str | None` (which conflated "force this dimension" with "these two edges are off-limits") to an explicit `DOCK_LOCKED_EDGES: set[str]`, since VIS and PL now need different, non-axis-shaped edge exclusions.
* **User-size tracking while docked**: previously, `ModuleShell.resizeEvent` only updated `_user_size` when `not self.is_docked`, because until now every docked resize was a *forced* programmatic one (undesirable to record). Now that a docked module can have a *legitimate* user-driven resize (PL's bottom/right drag, and — as an included side-effect — VIS's already-allowed top/bottom drag while docked), `ModuleShell.mouseReleaseEvent` was extended to also record `_user_size = self.size()` when a completed edge-drag resize concludes, **regardless of dock state**. This is safe because a completed drag can only have happened on an edge `DOCK_LOCKED_EDGES` didn't exclude — the genuinely-forced edges (VIS left/right) are simply never reachable by mouse in the first place. Programmatic forced resizes (VIS width alignment in `realign_docked_modules`) don't go through mouse events at all, so they still never touch `_user_size`.
* A **visual consequence** the human validator should expect: Playlist may now extend below (or stop well short of) the Visualizer+chassis stack — an asymmetric silhouette is the intended result of PL's height being independent of the stack, not a bug.

---

## 8. Dock / Undock / Redock Preservation

`ModuleShell` tracks `_user_size` — the last size recorded while the module was **not** docked (`resizeEvent` only updates it when `not self.is_docked`). Programmatic resizes applied while docked (chassis-width alignment, stack-height alignment) do not corrupt this value.

* `WindowManager.dock_module()` no longer touches size directly beyond the realign pass — `_user_size` is left untouched.
* `WindowManager.undock_module()` now calls `module.restore_user_size()`, popping the module back to the exact floating size the user last chose.

Validated: float VIS at `700×430` → dock (width forced to chassis width, e.g. `420`) → undock → VIS returns to `700×430`.

---

## 9. MINI/NORMAL Preservation

No new code was required here — it falls out of Qt's own behavior. `_on_scale_changed` (`WindowManager`) already only calls `hide()`/`show()` on the modules when the chassis toggles MINI/NORMAL; `hide()`/`show()` do not alter a `QWidget`'s geometry. Since modules are no longer fixed-size, their last-set size simply persists across the hide/show cycle.

---

## 10. Restart Persistence

`SessionState.ModulePosition` gained `width: int = 0` and `height: int = 0` (`0` = "unset"). `WindowManager.save_current_session()` persists `module.user_size` (not live/possibly-docked-constrained geometry). `_apply_restored_session()` falls back to the module's `DEFAULT_SIZE` when the saved value is `0`, clamps to the current screen's available geometry, and applies it via `ModuleShell.set_user_size()` before positioning (so screen-clamping of position uses the real restored size, not a stale constant).

---

## 11. Default Size Contract

Defaults are stable class constants, not derived from runtime geometry:

| Module | `DEFAULT_SIZE` | `MIN_SIZE` |
|---|---|---|
| `VisualizerModule` | 420 × 240 | 300 × 180 |
| `PlaylistModule` | 270 × 240 | 230 × 200 |

---

## 12. Reset Size Control

See §4. Tooltip: **"Reset size"**.

---

## 13. Session Schema Changes

```text
ModulePosition (before)          ModulePosition (after)
├── x                            ├── x
├── y                            ├── y
├── is_docked                    ├── width   (NEW, default 0 = unset)
├── dock_edge                    ├── height  (NEW, default 0 = unset)
└── is_visible                   ├── is_docked
                                  ├── dock_edge
                                  └── is_visible
```

`SessionManager._safe_positive_int()` parses `width`/`height`: missing key, non-numeric value, or a value `<= 0` all collapse to `0`. `WindowManager._apply_restored_session()` treats `0` as "use `DEFAULT_SIZE`" and separately enforces the module's `MIN_SIZE` via `set_user_size()`. Old session files without `width`/`height` load without error.

---

## 14. Screen Geometry Recovery

Restored module width/height is clamped to the current screen's `availableGeometry()` before being applied, and position clamping (`SessionManager.clamp_to_screen`) now uses the *actual restored size* instead of the previous hardcoded `420×240` / `270×240` literals — so a module resized large on a bigger monitor, then restored on a smaller one, is both size- and position-clamped to stay reachable.

---

## 15. Tests

`tests/test_ux_003.py` — 16 tests, all passing in isolation and as part of the full suite:

| # | Test | What it asserts |
|---|------|-----------------|
| 1 | `test_visualizer_default_size` | VIS constructs at 420×240 |
| 2 | `test_playlist_default_size` | PL constructs at 270×240 |
| 3 | `test_visualizer_min_size_enforced` | Resize below min clamps to `MIN_SIZE` |
| 4 | `test_playlist_min_size_enforced` | Same for PL |
| 5 | `test_user_resize_survives_mini_normal_cycle` | Resize → MINI → NORMAL preserves both module sizes |
| 6 | `test_visualizer_dock_undock_preserves_floating_size` | Float→resize→dock (width forced)→undock restores floating size |
| 6b | `test_playlist_dock_undock_preserves_floating_size` | Same for PL |
| 7 | `test_serialize_includes_width_height` | Session JSON round-trips width/height |
| 8 | `test_old_session_without_dimensions_loads_safely` | Legacy session (no width/height keys) loads without error, defaults to 0/unset |
| 9 | `test_invalid_dimensions_clamp_safely` | Negative/non-numeric saved sizes collapse to 0/unset |
| — | `test_restart_restores_module_sizes` | Full save→reload round trip via `WindowManager` restores exact sizes |
| 10 | `test_reset_size_restores_default_dimensions` | Reset restores `DEFAULT_SIZE` |
| 11 | `test_reset_size_does_not_move_dock_or_close` | Reset changes only size; position/dock-state/visibility untouched |
| — | `test_reset_size_button_exists_and_is_wired` | `btn_reset` exists with a "reset" tooltip |
| 12 | `test_retina_melt_roundtrip_preserves_vis_module_size` | Enter/exit RETINA MELT does not touch `vis_mod` size |
| 13 | `test_modules_remain_owned_windows_of_chassis` | `Qt.Window` flag + chassis-as-parent still hold (taskbar ownership) |

**Follow-up — Docked Playlist Vertical Resize** (`TestDockedPlaylistVerticalResize`, 9 tests, using real simulated `QMouseEvent` drags via a `_drag_resize()` helper, not direct `.resize()` calls):

| # | Test | What it asserts |
|---|------|-----------------|
| F.1 | `test_docked_playlist_vertical_resize_enabled` | Dragging PL's bottom-right corner while docked actually resizes it |
| F.2 | `test_realign_docked_modules_preserves_playlist_height` | `realign_docked_modules()` moves PL's x/y but never touches its width/height |
| F.3 | `test_custom_docked_height_survives_mini_normal_cycle` | Docked custom height survives MINI → NORMAL |
| F.4 | `test_custom_docked_height_survives_restart` | Docked custom height survives save → reload |
| F.5 | `test_dock_undock_preserves_docked_custom_height` | A height set *while docked* survives undocking |
| F.6 | `test_reset_size_restores_default_docked_height` | Reset Size restores `DEFAULT_SIZE` even for a docked, custom-resized PL |
| F.7 | `test_core_movement_changes_position_not_size` | Moving the chassis changes docked PL's position, never its size |
| — | `test_docked_playlist_left_and_top_edges_locked` | `PlaylistModule._allowed_edges()` while docked == `{right, bottom}` |
| — | `test_visualizer_dock_locked_edges_unchanged` | Regression: VIS's `{left, right}` dock-lock is unaffected by this follow-up |

Test isolation note: `_make_window_manager()` always constructs an isolated tempfile-backed `SessionManager` unless the caller passes one explicitly — this suite never reads or writes the real per-user `session.json`, unlike some pre-existing tests in this repo that do.

---

## 16. Manual Validation

Manual validation was performed **programmatically**, driving the exact same code paths a human mouse interaction would hit, rather than through a live windowed session (no interactive desktop available in this working environment):

* **Scenario 1 (VIS resize)**: Simulated real `QMouseEvent` press/move/release on `VisualizerModule`'s bottom-right corner and left edge (not just calling `.resize()` directly) — confirmed `_resizing` state, edge detection, live geometry updates during drag, and min-size clamping all work end-to-end. `_sync_surface_size()` confirmed to recreate the Pygame surface and call `.resize()` on both `ToroidVisualizer` and `WaveformRibbonVisualizer` at small/default/wide/tall/large sizes.
* **Scenario 2 (PL resize)**: Confirmed `list_widget` grows via existing layout stretch at both wider and taller sizes; toolbar remains fixed-height and usable.
* **Scenario 3 (MINI memory)**: Full `WindowManager` instantiation, resize both modules, `chassis.set_mode("mini")` → `chassis.set_mode("normal")` — sizes exactly preserved.
* **Scenario 4 (restart)**: Full save → `shutdown()` → fresh `WindowManager` against the same session file → sizes exactly restored.
* **Scenario 5 (reset)**: Reset restores default size; position, dock state, and visibility confirmed unchanged.
* **Scenario 6 (dock/undock)**: Float at 700×430 → dock (width forced to chassis width) → undock → confirmed exact 700×430 restored.
* **Scenario 7 (RETINA MELT)**: Enter/exit fullscreen with a custom VIS size set — confirmed `vis_mod` size untouched (RETINA MELT's surface sizing is already fully independent, driven by `RetinaMeltWindow`'s own screen-geometry logic).
* **Scenario 8 (taskbar)**: Confirmed structurally (`Qt.Window` flag + chassis-as-`QWidget`-parent) — as in UX-001, no automated test can prove Windows renders a single taskbar preview; that requires a live desktop session and is **not claimed as tested** here.

Neon border rendering (§Part N) required no code change — `ModuleShell.paintEvent` already draws from `self.rect()`, which is correct at any size by construction; not independently re-verified visually in this pass.

**Follow-up validation** (Docked Playlist Vertical Resize), also driven by real simulated `QMouseEvent` drags against an offscreen application instance:

* **Dock PL right, resize vertically (short/medium/tall)**: confirmed the bottom-right corner drag actually changes PL's height while docked, and `realign_docked_modules()` (invoked on every chassis move / snap tick) does not snap it back — `pl_mod.height()` is stable across repeated realign calls.
* **VIS docked below, PL resized to extend well past the stack**: confirmed PL can be resized taller than `chassis.height() + vis_mod.height() + 2` with no forced clamp back to that value — asymmetric module dimensions are accepted.
* **Move chassis**: confirmed PL's x/y follow the chassis (`pos()` changes to track `core_geom.right()+2, core_geom.top()`) while its custom width/height are preserved exactly.

---

## 17. Known Limitations

* **No live-desktop manual pass.** All "manual validation" above was performed by driving real Qt events against an offscreen (`QT_QPA_PLATFORM=offscreen`) application instance, not a human clicking a visible window. Visual appearance (cursor icons rendering correctly, neon border crispness at extreme sizes, actual taskbar preview count) should still be spot-checked by a human on a live Windows session before considering this fully closed, matching the precedent already set in UX-001/UX-002.
* **Manual dock/undock toggle removed.** Docking is now purely a function of dragging (magnetic snap to dock, drag-away to undock). There is no button to dock/undock a module that is far from the snap zone without first dragging it there. This was a deliberate, spec-directed trade (the corner control had exactly one purpose to keep — Reset Size), not an oversight.
* **Top-edge resize is a thin 6px strip.** Because the title bar occupies the top ~22px and must remain draggable, top-edge resize only activates within `RESIZE_MARGIN` (6px) of the very top of the window — consistent with how most frameless-window resize implementations resolve this conflict, but worth knowing if a human "can't find" the top resize handle.
* **RESIZE_MARGIN (6px) hit-testing has no visual indicator** beyond the cursor shape change on hover — there's no visible grip/handle. This matches the existing chassis's minimal instrument aesthetic but may be a slightly narrow target on high-DPI displays.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

UX-003 is an ergonomics/persistence extension within the existing ACTIVE Production Cut 3 phase. No phase changed, no decision gate changed, no architectural boundary moved. Operational baseline remains STABLE.
