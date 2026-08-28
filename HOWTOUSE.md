# ToroidAMP — How to Use

*It really warps the toroid's ass!*

ToroidAMP is a compact, musically reactive audio player with a built-in
demoscene visualizer engine and a live GLSL shader authoring lab. This
guide assumes you've just downloaded/extracted it and want to play music
and make it look ridiculous.

## 1. Getting Started

- Extract the ToroidAMP folder anywhere you like (Desktop, a portable
  drive, wherever) — it doesn't need to be installed.
- Run `ToroidAMP.exe`. No Python install, no extra setup.
- On first launch there's no music loaded yet and no saved settings —
  ToroidAMP creates its own settings file automatically at
  `%LOCALAPPDATA%\ToroidAMP\` (see §11).

## 2. Loading Music

**Conventional formats**: MP3, WAV, OGG, FLAC.
**Tracker formats**: MOD, XM, IT, S3M (classic tracker modules).

Add files via the playlist panel, or drop files directly onto the
window. Playlists can be saved and reloaded as M3U/M3U8.

## 3. Playback Controls

Play/Pause, Stop, Previous/Next, a seek bar, and a volume slider — all
in the main transport row. A short crossfade smooths track changes by
default (toggleable).

## 4. Interface Modes

- **NORMAL** — the full-size player window.
- **MINI** — a compact, always-on-top-friendly scale for when you want
  ToroidAMP out of the way.
- **RETINA** — fullscreen, GPU-visualizer-only mode (see §6).

Switch between them from the mode controls in the player chrome.

## 5. Visualizers

ToroidAMP cycles through several built-in visualizers — some run on the
CPU, some on the GPU. Cycling works the same way regardless of which
kind is currently active. Every visualizer reacts to whatever's
playing — bass, mids, treble, and beat all visibly drive the motion.

## 6. RETINA / GPU Visualizers

RETINA is the fullscreen home for ToroidAMP's GPU-accelerated
visualizers (Toroid Identity, Cyber Bloom, Audio Reactive Reference, and
anything you load yourself — see §7). It needs a GPU with OpenGL 3.3
Core support; the rest of the player works fine without one.

Cycle through the official GPU visualizers the same way you cycle CPU
ones. Each is a small self-contained demo of a different way ToroidAMP
can make a shader musically reactive.

## 7. Shader LAB

LAB is where you load, tune, and author GLSL shaders live, without
restarting anything.

- **LOAD** an external `.frag` file (yours, or one you found online).
- ToroidAMP automatically discovers any tunable parameters the shader
  exposes — explicit ones the author declared, *and* some it can safely
  find on its own (see the note on `[CONST]`/`[AUTO PARAM]` below).
- Each discovered parameter gets a **BASE** slider — drag it, the shader
  changes immediately.
- Each parameter can also be bound to a live **AUDIO** source (bass,
  mids, treble, RMS, peak, beat, strong beat) with an **AMOUNT** slider
  controlling how strongly that source pushes the value away from BASE.
- Press **R** to hot-reload the shader straight from disk after editing
  it in a text editor — your BASE values and AUDIO bindings survive the
  reload where possible.
- If a shader fails to compile, LAB tells you why and keeps whatever was
  working before — it never leaves you looking at a broken screen.
- **AUTO REACT** is a separate, simpler toggle for external shaders that
  don't expose their own tunable parameters: it applies a generic,
  presentation-level audio reaction on top of the shader as-is.

**About the `[CONST]` and `[AUTO PARAM]` badges**: some parameter cards
show one of these labels next to the name. It just means ToroidAMP found
that control automatically (a constant the shader author hard-coded, or
a literal value used directly in an expression) rather than the shader
explicitly declaring it as a tunable parameter. Functionally it behaves
exactly like any other parameter — drag it, bind it, whatever you like.

## 8. MUSICALIZE

Loaded an external shader and don't want to hand-tune five sliders
before it reacts to anything? Press **MUSICALIZE**.

- It picks a small, bounded set of the shader's parameters and assigns
  each one a conservative audio binding automatically — enough to give
  an arbitrary shader a musically reactive first pass without you doing
  anything.
- Every card MUSICALIZE touches gets an **`[AUTO]`** tag next to its
  AUDIO source, so you always know which bindings were generated versus
  set by hand.
- The deviations MUSICALIZE creates are deliberately small (roughly
  5–15%) — it's meant to be a tasteful starting point, not a dramatic
  transformation. Not every shader lights up equally; some just don't
  have much to work with, and that's expected, not a bug.
- **Manually adjust anything MUSICALIZE generated** — the moment you
  touch its AUDIO source or AMOUNT yourself, it stops being `[AUTO]` and
  becomes your own setting.
- **CLEAR AUTO** removes only the still-`[AUTO]`-tagged bindings,
  leaving anything you've manually configured completely untouched.
  Parameters with no binding just sit at BASE.

## 9. Themes

ToroidAMP ships with **DEFAULT** and **CYBER YELLOW** themes. Switch
between them live from the theme control — no restart needed. Your
choice is remembered for next time.

## 10. System Tray

Minimizing ToroidAMP sends it to the system tray rather than closing it,
so playback keeps going in the background. Click the tray icon to
restore the window; use its menu (or the window's own close control) to
actually quit.

## 11. Files Created by ToroidAMP

Everything ToroidAMP writes lives under:

```
%LOCALAPPDATA%\ToroidAMP\
    session.json     - your window layout, volume, theme, playlist
    logs\toroidamp.log  - a rotating diagnostic log (a few MB max)
    shaders\         - default location for LAB's LOAD/SAVE dialogs
                        (your own shaders and saved presets — the
                        official bundled shaders are separate and
                        always available regardless of this folder)
```

Nothing is ever written inside the ToroidAMP folder itself, so you can
run it from a read-only location, a USB stick, or wherever you like.

## 12. Troubleshooting

- **ToroidAMP doesn't launch at all**: check
  `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log` for the last thing it
  logged before stopping — this is almost always the fastest way to see
  what went wrong.
- **No sound**: confirm Windows has a default playback device selected
  and it isn't muted; ToroidAMP uses whatever device is currently
  default in Windows.
- **A tracker file (MOD/XM/IT/S3M) won't load**: the log will say
  clearly whether the file itself is the problem or the native tracker
  library couldn't be found — either way playback of everything else is
  unaffected.
- **RETINA / GPU visualizers won't open or show nothing**: this usually
  means the GPU/driver on the current machine doesn't support OpenGL 3.3
  Core. The rest of the player (playback, CPU visualizers, playlist)
  works fine regardless.
- **An external shader won't compile in LAB**: the LAB diagnostic line
  shows the compiler's own error message, and the previously-working
  shader stays active — nothing is left broken.
- **Something else looks wrong**: `toroidamp.log` (§11) is always the
  first place to look.

---

## Validation / Self-Test Checklist

A practical checklist for "I changed something — what should I manually
verify?" Not a dump of the automated test suite (that's a separate,
much longer thing — see *Developer Validation* below) — just the human
checks that actually catch real regressions.

### Basic Playback Test
- Load an MP3. Play, pause, seek, stop.
- Next/Previous through a small playlist.

### Tracker Test
- Load a real MOD, then a real XM. Confirm both play.
- Load a real IT and, if you have one, a real S3M.
- Seek within a tracker file — expect it to land *near* the requested
  time, not exactly on it (this is normal, see §12/CHANGELOG).
- Switch from a tracker file back to an MP3 and confirm conventional
  playback still works normally.

### Reactivity Test
- Play an MP3 with a clearly reactive visualizer active — confirm bass/
  mids/treble/beat are all visibly driving it.
- Switch to a tracker file with the *same* visualizer — confirm it's
  still visibly alive (exact parity with the MP3 case isn't expected,
  but it shouldn't look "dead" or wildly over/under-scaled).

### RETINA Test
- Enter RETINA, cycle through the official GPU visualizers, exit back to
  NORMAL/MINI.

### Shader LAB Parameter Test
- Load a shader with known discoverable parameters.
- Move a BASE slider — confirm a visible change.
- Bind one parameter to BASS, adjust AMOUNT — confirm visible, bounded
  modulation.
- Hot-reload (R) — confirm your BASE/AUDIO settings survived.

### MUSICALIZE Test
- Load a compatible shader, press MUSICALIZE.
- Confirm `[AUTO]`-tagged cards appear and play music to confirm they
  visibly, if subtly, react.
- Press CLEAR AUTO — confirm those parameters return to BASE.

### External Shader Test
- Load an arbitrary `.frag` file you didn't write for ToroidAMP.
- Observe whether any `[CONST]`/`[AUTO PARAM]` controls were discovered
  automatically (not every shader will have any — that's expected).
- Deliberately load a shader with a syntax error — confirm the
  previously-working shader keeps rendering rather than breaking.

### Theme Test
- Cycle DEFAULT ↔ CYBER YELLOW — confirm both fully render (fonts,
  images, colors) with no missing-asset glitches.

### Frozen Build Test (if testing a packaged `ToroidAMP.exe`)
- Launch it directly, with no source checkout or Python install present.
- Launch it with the current directory set somewhere unrelated.
- Copy the whole folder somewhere else and launch it from there — same
  behavior expected.
- Confirm `%LOCALAPPDATA%\ToroidAMP\` gets a fresh `session.json` and a
  `logs\toroidamp.log` on first run.

---

## Developer Validation

For contributors working on the source checkout, the project's automated
test suite is run per-file (running the entire suite in one process can
trigger an unrelated native GL resource-accumulation artifact in this
environment — not a logic bug):

```bash
python -m pytest tests/test_<name>.py -q
```

Repository test/build configuration lives in `pyproject.toml`
(`[project.optional-dependencies] test = ["pytest>=8.0"]`,
`build = ["pyinstaller>=6.10"]`). Packaging is reproduced with:

```bash
pyinstaller packaging/toroidamp.spec --noconfirm
```

This section deliberately stays short — the *Validation / Self-Test
Checklist* above is the primary reference for confirming a change
actually works; the automated suite is a development-time safety net,
not user-facing documentation.
