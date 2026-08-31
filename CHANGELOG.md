# Changelog

All notable user-facing changes to ToroidAMP are documented here.
Format loosely inspired by [Keep a Changelog](https://keepachangelog.com/).

ToroidAMP has **not yet had a formal public release**.

**A note on the version number:** ToroidAMP has been downgraded from the
internal working version 0.69 to **v0.666**. This is intentional, not a
typo and not a mistake by whatever tooling generated this file. Development
briefly got ahead of itself before Linux support, packaging, and basic UX
polish actually existed; the version number now reflects that honestly.
Progress will resume when morale improves.

## [Unreleased]

### Added
- Official GPU/GLSL visualizers (Toroid Identity, Cyber Bloom, Audio
  Reactive Reference) now render directly in NORMAL mode, right alongside
  the CPU visualizers, instead of showing a RETINA-only placeholder.
  Arbitrary user shaders remain exclusive to RETINA MELT and the GLSL Lab.
- Playlist and Visualizer now compose into a single ToroidAMP window on
  Wayland instead of independent, separately-positioned top-level windows
  (RELEASE-BLOCKERS-001, see Fixed below for the root cause).

### Fixed
- Startup voice playback no longer depends on pygame.mixer/SDL: that
  backend's Linux device lifecycle remained unreliable across repeated
  launches even after explicitly reconfiguring and quitting the mixer
  each time (UBUNTU-WAYLAND-002) — synthesis always succeeded, audible
  playback intermittently did not. Voice playback now decodes the
  synthesized WAV via `soundfile` (the same library music playback
  already uses) and plays it through `sounddevice`, sharing the exact
  device-selection policy already validated for reliable Ubuntu/PipeWire
  music playback. Windows SAPI5 synthesis is unaffected.
- Playlist and Visualizer appeared centered/overlapping instead of docked
  beside NORMAL under Wayland. Root cause: both were independent
  `Qt.Window` top-level surfaces, and Wayland's xdg-shell protocol gives a
  client no way to set an independent top-level's absolute position at
  all — only an interactive drag, already used for NORMAL/MINI via
  `startSystemMove()`. There is no portable Qt-level fix for
  *positioning* a second independent top-level, so on Wayland specifically
  Playlist and Visualizer are now hosted as embedded child widgets inside
  the chassis's own single top-level window instead — Qt's ordinary child-
  widget layout, not compositor window placement, so it sidesteps the
  protocol limitation entirely rather than working around it. Windows and
  X11 keep the existing independent-top-level windows, completely
  unchanged.
- Added a diagnostic to the GLSL Authoring Lab: a user shader that
  compiles and links successfully but paints an all-black frame (reported
  on Ubuntu/Mesa/Intel HD 5500 for some `user_shaders/` content, not
  reproducible on this cut's Windows dev environment despite testing this
  repo's own sample shaders end-to-end on a real GL driver) now logs a
  clear diagnostic and surfaces it in the Lab's error panel, instead of
  looking identical to normal operation. This does not change shader
  compilation or rendering — it only makes an otherwise-silent black
  frame loudly diagnosable.
- A Linux-only bug where a user-provided shader loaded correctly in the
  GLSL Lab but rendered black in RETINA MELT: RETINA's local-shader loader
  called `load_shader_file()` before making the GPU canvas the visible
  page, so on platforms where a hidden `QOpenGLWidget`'s context isn't
  realized yet, the load silently deferred compilation instead of running
  it. Reordered to match the already-correct official-visualizer path.
- Production startup now requests an explicit OpenGL 3.3 Core Profile
  surface format (previously only the GLSL Lab's own entry point did),
  removing a real divergence between the Lab and the production hosts.
- Audible intermittent stuttering during Linux playback on bare-metal
  hardware (validated on an Intel/Mesa Mint machine): the output stream
  requested a fixed 512-frame block size instead of letting PortAudio
  negotiate its own; and PortAudio's ALSA `default` device routes through
  an extra userspace buffering chain (dmix/rate/plug) sitting below
  PipeWire's own graph, invisible to `pw-top`'s XRUN accounting. ToroidAMP
  now lets PortAudio negotiate its own block size and prefers a device
  literally named `pipewire` when present, falling straight through to
  the previous behavior everywhere else (Windows, macOS, non-PipeWire
  Linux). Also removed a per-sample Python loop from the real-time audio
  callback's fade-envelope calculation (now vectorized) — real, if minor,
  extra safety margin on modest hardware.
- The startup voice-identity line could fail on Linux with `ReferenceError:
  weakly-referenced object no longer exists` raised from a `pyttsx3`/eSpeak
  ctypes callback: the synthesis engine was explicitly deleted immediately
  after `runAndWait()` returned, racing a trailing native callback that
  hadn't finished yet. The engine is now kept alive for its natural
  lifetime instead. Windows SAPI5 playback is unaffected.
- Pressing STOP could sometimes skip straight to the next track instead of
  just stopping. Root cause: a fade-out stop completes asynchronously in
  the audio callback (well after `stop()` already returned) by setting the
  same `STOPPED` state a natural end-of-track uses, and the playlist's
  auto-advance check couldn't tell the two apart. Natural end-of-track now
  sets an explicit, one-shot flag that only genuine decoder exhaustion
  raises; STOP (and pause, and seeking) never do.
- Seeking while a track was playing called the decoder's `seek()`
  synchronously from the UI thread, racing the audio callback's own
  unsynchronized `read_frames()` call on the same decoder handle — audible
  as a sluggish, sometimes-interrupted timeline drag, and rarely, a
  corrupted read that looked like the track had spuriously ended. Seeking
  while playing now hands the target to the audio callback, which is the
  only thread that touches the decoder while playback is active; rapid
  successive drags naturally coalesce to the latest position instead of
  each queuing a separate decoder seek.
- The MINI volume popup couldn't be closed by clicking the speaker button
  a second time — Qt's own popup auto-dismiss (any outside click,
  including that second click) fires before the button's own click
  handler runs, so the handler always saw "already hidden" and reopened
  it. Fixed with the standard debounce for this Qt popup pattern.
- The startup voice line synthesized correctly on Ubuntu (confirmed by
  playing the temporary WAV manually) but was never actually heard from
  ToroidAMP itself: `pygame.init()` (already called elsewhere for CPU
  visualizer support) silently initializes `pygame.mixer` with its own
  auto-negotiated defaults before the voice line ever plays, so
  VoiceService's own `if not get_init(): init(our_settings)` guard never
  actually applied its intended configuration in the real startup order.
  The mixer is now explicitly (re)configured every time. A genuine
  "no channel available" case now also logs a clear warning instead of
  the same success message a real playback would produce.
- The frameless NORMAL window couldn't be dragged under Wayland: the
  existing drag implementation computed a target position from global
  mouse coordinates and called `move()`, which Wayland's compositor
  security model doesn't allow a client to do to itself. Dragging now
  uses `QWindow.startSystemMove()` — the portable, Qt-documented
  mechanism for this — specifically on Wayland; X11 and Windows keep the
  existing move()-based drag (including MINI's edge-snapping), which
  already works correctly there.
- A GPU resource warning (`QOpenGLTexturePrivate::destroy() called
  without a current context`) could appear on shutdown: the two
  `GLVisualizerCanvas` instances (NORMAL and RETINA MELT) are child
  widgets, not top-level windows, so closing their parent windows never
  actually delivered `closeEvent()` (and its explicit GPU cleanup) to
  them — their only cleanup path was each canvas's own GL context
  destruction signal, whose timing relative to CPython's own interpreter
  shutdown isn't guaranteed. Shutdown now releases both canvases' GPU
  resources explicitly and deterministically while their contexts are
  still current, before the window/event-loop teardown begins.
- `QApplication.setDesktopFileName("toroidamp")` is now declared at
  startup — the portable Qt mechanism a Wayland/X11 desktop uses to
  associate a running window with an installed `.desktop` file's icon.
  A source checkout still won't get a custom dock icon on desktops like
  GNOME that resolve it strictly through an *installed* `.desktop` file
  (a packaging task, not a code one), but the declared identity is now
  correct and ready for when one ships.
- The startup voice line could synthesize a valid WAV but produce no
  audible sound on later launches (first launch after boot often worked;
  a subsequent close-and-relaunch often didn't): nothing in ToroidAMP ever
  called `pygame.mixer.quit()`, so the mixer's audio/PipeWire connection
  was only ever released implicitly on abrupt process exit — a fast
  relaunch could initialize against a connection the previous process
  hadn't fully released yet, which "succeeds" without error but doesn't
  actually flow audio. The mixer is now explicitly quit once this service
  is done with it each time, giving PipeWire a deterministic disconnect
  signal. Also serialized the mixer's init/play/quit cycle process-wide
  (a global, not per-instance, lock) and made the success/warning logging
  more honest: a channel reporting instantly idle after `play()` is now
  logged as a failure rather than counted as success, since pygame/SDL has
  no portable API to confirm a channel was ever actually audible.
- The Playlist and Visualizer windows opened centered on Wayland instead
  of docked beside NORMAL (Playlist right, Visualizer below). Root cause:
  both are `Qt.Window` top-level surfaces, and the base Wayland/xdg-shell
  protocol has no request for a client to set a toplevel's absolute
  position — only an interactive move (drag), the same operation
  `startSystemMove()` already uses for NORMAL/MINI. Compositors are free
  to place every toplevel themselves; GNOME/Mutter centers them regardless
  of any `move()` call, before or after `show()`. The existing docking
  math (already correct, and unchanged) continues to work on Windows and
  X11; on Wayland this is a genuine protocol limitation with no portable
  Qt-level workaround, documented in place rather than worked around with
  a compositor-specific hack.
- The GLSL Lab's LOAD dialog could appear behind the Lab window on
  Wayland, effectively hidden. The dialog's parent was already correct
  (standard Qt ownership); the likely cause is Qt's native Linux file
  dialog routing through the `org.freedesktop.portal.FileChooser` DBus
  service, whose parent-window (xdg-foreign) handoff isn't reliably wired
  up in this environment (this same platform's log shows the app's own
  portal registration failing at startup). The Lab's file dialogs
  (load shader, save/load preset) now force Qt's own non-native dialog
  specifically on Wayland, giving them the same Qt-managed transient-
  parent stacking every other ToroidAMP window already relies on, without
  depending on the portal at all. Windows and Linux/X11 keep the native
  dialog, unaffected.

### Known Limitations (Wayland)
- Auxiliary module windows (Playlist, Visualizer) cannot be positioned by
  the client on Wayland; only the compositor decides toplevel placement.
  This is a protocol-level restriction, not expected to be fixable without
  a Wayland extension outside Qt's portable API surface.

## [0.666] — Post Launch Hell & Welcome Linux Users

### Added

- **Core player**: NORMAL and MINI interface scales, session persistence
  (window layout, volume, theme, playlist), tray minimize/restore/quit
  lifecycle, live theme switching, a startup voice-identity line.
- **Audio playback**: MP3, WAV, OGG, and FLAC via `soundfile`; MOD, XM,
  IT, and S3M tracker module playback via `libxmp`; automatic decoder
  failure recovery (a bad file logs a clear error and cleanly advances
  the playlist instead of crashing or hanging).
- **Playlist**: add/remove/clear, shuffle, repeat, M3U/M3U8 save and
  load, Unicode filename support.
- **Visualizers**: several CPU visualizers plus official GPU visualizers
  (Toroid Identity, Cyber Bloom, Audio Reactive Reference), all cycled
  the same way; a fullscreen **RETINA MELT** mode for the GPU visualizer
  family.
- **Shader LAB** (RETINA-only): load any external `.frag` shader file,
  hot-reload it from disk with `R`, safely roll back to the previous
  working shader on a compile error, tune discovered typed parameters
  (float/bool/color) live, save/load JSON parameter presets, and bind
  any float parameter to a live audio source (bass/mids/treble/RMS/peak/
  beat) with an adjustable amount.
- **Safe const promotion**: shaders that tune themselves with
  `const float NAME = value;` constants automatically get LAB sliders for
  those values too — no shader edits required, and the original file on
  disk is never modified.
- **Runtime literal parameterization**: shaders that use a direct
  `iTime * value` time-scale multiplier, or a simple
  `float name = value;` local constant, also get automatically generated
  LAB controls for those — again with zero changes to the shader file.
- **MUSICALIZE**: a one-click action that generates bounded, deterministic
  audio bindings for a shader's eligible parameters — a fast starting
  point for making an arbitrary shader musically reactive without hand-
  tuning every control. Clearly marked `[AUTO]` in the LAB so it's
  obvious which bindings were generated versus set by hand; a dedicated
  **CLEAR AUTO** action removes only the generated ones, leaving any
  manual work untouched.
- **AUTO REACT**: a separate, generic presentation-layer audio reaction
  mode for Shadertoy-style shaders that don't author their own musical
  behavior.
- **Themes**: DEFAULT and CYBER YELLOW, switchable live, each with its
  own palette, chrome imagery, and (for CYBER YELLOW) a bundled display
  font.
- **Persistent logging**: a rotating log file at
  `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`, so a problem can be
  diagnosed after the fact instead of only in a console window.
- **Packaging**: a working PyInstaller ONEDIR build proof-of-concept —
  `ToroidAMP.exe` now runs standalone, from any folder, without a Python
  install.
- **Licensing**: ToroidAMP is released under the MIT License; a
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) inventories the
  open-source components the packaged build redistributes.
- **Linux support**: ToroidAMP now runs on Linux (validated on Linux Mint
  under VirtualBox) — startup, audio playback, system TTS, the PySide6 UI,
  and the official GPU/GLSL visualizers all confirmed working.
- **Playlist multi-selection**: standard desktop selection semantics in the
  playlist — click, Ctrl+click (additive), Shift+click (range) — with
  Delete/Backspace and the existing -DEL button now removing the entire
  selected set in one action instead of one track at a time.

### Changed

- Tracker (MOD/XM/IT/S3M) playback now uses `libxmp` instead of the
  originally-planned `libmodplug` — `libxmp` is already bundled by the
  existing `pygame-ce` dependency, so tracker playback requires no
  additional native library to source or install.
- Packaged Windows builds now launch windowed (no console window) —
  diagnostics remain fully available via the existing rotating log file at
  `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`. Running from source
  (`python -m toroidamp`, the `toroidamp` console script) is unaffected.
- NORMAL mode's breathing chassis border is noticeably more perceptible
  (wider amplitude swing plus a soft outer glow), so the window is easier
  to spot in peripheral vision among other desktop windows. MINI mode's
  deliberately understated presence is unchanged.
- Visualizer/reactivity analysis (RMS, bass/mids/treble, beat detection) is
  now derived from the decoded audio signal independent of the playback
  volume slider and independent of the fade-in/out envelope's amplitude
  contribution beyond true silence — lowering the volume no longer sedates
  the visualizers; genuine silence (e.g. a completed fade-out) still reads
  as silence.
- RETINA MELT is now an owned/transient window of the main chassis (like
  the Visualizer and Playlist modules already were), improving taskbar/dock
  grouping — a single ToroidAMP presence rather than one entry per window,
  where the desktop environment honors that relationship.
- The project version is now set consistently everywhere from one source
  (`pyproject.toml`'s `[project].version`, already the sole source
  `toroidamp/_version.py` reads at runtime) instead of drifting between the
  repository, the running application, and packaging metadata.

### Fixed

- A missing tracker backend used to fail silently (the selected track
  would just sit there, not playing, with no error and no automatic
  skip to the next track). It now fails exactly like any other bad file:
  a clear log entry, and a clean automatic advance to the next playlist
  entry.
- `ThemeDefinition` was used in two UI modules' type annotations without
  being imported — invisible on newer Python (3.14's deferred annotation
  evaluation) but a hard `NameError` on Python ≤3.13, including on Linux.
- Two official GPU shaders were checked in with a UTF-8 byte-order mark,
  which strict GLSL compilers (Mesa, used on Linux) rejected as an invalid
  token after ToroidAMP's own header got prepended to the shader source,
  while lenient Windows GPU drivers silently tolerated it. Shader files are
  now read BOM-safely regardless of platform.
- Running bare `pytest` from the repository root (rather than
  `python -m pytest`) failed to collect three experimental test modules;
  the project's pytest configuration now makes both invocations equivalent.
- A rare native crash (observed as an access violation on Windows, a
  segfault on Linux) during a full test-suite run was traced to a test
  leaving a real background audio thread running unattended, racing later
  GUI/GL work on the main thread. Also hardened: OpenGL cleanup could run
  twice per visualizer widget; the process-wide `ThemeManager` singleton
  could retain a live signal connection to an already-destroyed window.

### Known Limitations

- **Tracker seek is approximate, not sample-accurate.** Tracker module
  formats address playback position by pattern/row, not by arbitrary
  time offset, so seeking lands near the requested time rather than
  exactly on it. This is a structural property of the format, not a bug.
- **S3M real-file validation is still pending.** S3M loads through the
  exact same code path already validated for MOD/XM/IT, but no real S3M
  test file has been available yet to confirm it end-to-end.
- **GPU visualizers and RETINA MELT require a working OpenGL 3.3 Core
  driver.** The base player (playback, playlist, CPU visualizers) remains
  fully usable without one; there is not yet a polished in-app message
  explaining *why* RETINA is unavailable if a suitable GPU isn't present.
- **Packaging is not yet public-release-ready.** A working ONEDIR build
  exists, but it has not yet been through a clean-machine validation
  pass, a public license text for two third-party components is not yet
  fully finalized (see `THIRD_PARTY_NOTICES.md`), and no installer or
  single-file (`ONEFILE`) build has been produced.
- **Playlist drag-and-drop reordering is not yet implemented.** Multi-
  selection and bulk removal are; reordering by dragging a selection
  within the list was evaluated for this cut but intentionally deferred —
  `PlaylistManager` is a plain ordered list, not a Qt item model, so
  wiring Qt's native multi-item drag-reorder to it safely (without risking
  playback identity or playlist-order correctness) is a small architecture
  change in its own right, not a bounded polish item.
- **Linux requires one manually-installed system package**: `libxcb-cursor0`
  (see the README's Linux prerequisites) for Qt's `xcb` platform plugin.
  This cannot be resolved via `pip`.
