# ToroidAMP — AGENTS.md

> **It really warps the toroid's ass!**

## 0. Your Mission

Your mission is simple:

> **Build a music player capable of bringing tears to the eyes of former Future Crew members.**

Not because ToroidAMP imitates the past.

Not because it fills the screen with gratuitous effects.

But because it remembers something important:

**computers are allowed to be fun.**

ToroidAMP should play music reliably, disappear when the user wants it out of the way, and occasionally make somebody stare at the screen and wonder why a tracker module is causing a violently illuminated toroid to rotate through hyperspace.

That is acceptable behavior.

Possibly desirable behavior.

---

# 1. Project Identity

ToroidAMP is a lightweight, open-source, cross-platform desktop audio player written primarily in Python.

Primary targets:

* Windows
* Linux

Core identity:

```text
Local music
+
Current playlist
+
Classic tracker modules
+
Real-time visualization
+
Compact desktop UX
```

Visualization is not decoration.

It is a first-class subsystem.

Tracker music is not legacy baggage.

It is invited.

Toroids are not mandatory in every visualizer.

But they should always remain possible.

---

# 2. Prime Directive

The most important architectural rule in ToroidAMP is:

> **Playback must remain boring enough to be reliable.
> Visualization may be as ridiculous as necessary.**

Never sacrifice audio stability for visual complexity.

A visualizer may:

* drop frames;
* reduce quality;
* fail;
* be disabled;
* explode metaphorically.

Playback should continue.

---

# 3. Read Before Working

Before making significant changes, inspect the relevant project documentation.

At minimum:

```text
docs/CURRENT_STATE.md
docs/ARCHITECTURE.md
docs/SCOPE.md
```

Use `docs/VISION.md` when product intent or project identity matters.

Use `docs/ARCHIVE.md` when historical context is required.

Do not infer current architecture from old experiments when current documentation already defines it.

---

# 4. Documentation Responsibilities

Each document has a specific responsibility.

## `VISION.md`

Defines what ToroidAMP is and why it exists.

Do not modify product identity casually.

## `SCOPE.md`

Defines active product boundaries and V1 commitments.

A technically interesting feature is not automatically in scope.

## `ARCHITECTURE.md`

Contains current architectural truth.

Update it when an established architectural decision changes.

Do not use it as a chronological development log.

## `CURRENT_STATE.md`

Contains current operational state:

* active phase;
* active cut;
* open decisions;
* blockers;
* relevant recent decisions;
* next cut.

Keep it concise.

## `ARCHIVE.md`

Contains compressed historical context:

* completed cuts;
* superseded decisions;
* discarded experiments;
* relevant information removed from `CURRENT_STATE.md`.

---

# 5. CURRENT_STATE Policy

At the end of every significant implementation or investigation cut, evaluate whether operational project state changed.

If it did not change:

```text
CURRENT_STATE_UPDATE: NOT_REQUIRED
```

Do not modify the file merely to record that work happened.

If operational state changed, update it.

Examples include:

* phase changed;
* cut closed;
* decision gate closed;
* blocker appeared or disappeared;
* ACTIVE/PENDING/DEFERRED/CLOSED state changed;
* Next Cut changed;
* an architectural decision materially changed immediate work.

When information is no longer operationally useful, compress it into `ARCHIVE.md` rather than allowing `CURRENT_STATE.md` to grow indefinitely.

---

# 6. Architecture Rules

ToroidAMP should favor:

* explicit responsibilities;
* small modules;
* replaceable subsystems;
* portable code;
* simple data flow;
* evidence-driven abstraction.

Avoid:

* speculative frameworks;
* unnecessary service layers;
* premature plugin systems;
* unnecessary databases;
* giant manager classes;
* hidden global state;
* platform-specific assumptions leaking into core logic.

Do not create abstractions merely because abstraction feels architectural.

Create them when actual responsibilities require separation.

---

# 7. Core System Boundaries

Maintain the conceptual separation:

```text
Playback
    │
    ▼
Audio Analysis
    │
    ▼
Normalized Audio Data
    │
    ▼
Visualization
```

Surrounding systems include:

```text
UI
Playlist
Settings / Session
Platform Integration
```

These boundaries may evolve through explicit architectural decisions.

Do not casually collapse them.

---

# 8. Playback Rules

Playback owns audio reproduction.

It may handle:

* loading;
* decoding;
* play;
* pause;
* stop;
* seek;
* volume;
* playback position;
* duration;
* end-of-track state;
* PCM access.

Playback must not contain visualizer-specific behavior.

Never introduce logic equivalent to:

```python
if visualizer == "angry_toroid":
    increase_bass()
```

No matter how tempting.

---

# 9. Audio Analysis Rules

Audio Analysis converts playback data into normalized information useful to visualizers.

Potential data includes:

```text
waveform
rms
peak
spectrum
bass
mids
treble
beat
strong_beat
```

The final contract must be established through implementation evidence.

Visualizers should consume analysis results rather than independently decoding the audio source.

Analysis owns:

> **What is happening in the signal?**

Visualization owns:

> **What ridiculous thing should happen because of it?**

---

# 10. Visualizer Rules

Visualizers are experimental by nature.

Encourage experimentation.

Protect the rest of the application from it.

A visualizer should ideally depend only on:

* normalized audio data;
* timing;
* rendering context;
* its own configuration/state.

It should not need to understand:

* playlists;
* file dialogs;
* session persistence;
* system tray behavior;
* decoder implementation;
* application startup.

Adding a new visualizer should eventually become one of the easiest ways to contribute to ToroidAMP.

---

# 11. Existing MetalWar-Installer Code

MetalWar-Installer is a **donor**, not a dependency.

Existing code may contain valuable implementations for:

* playback;
* tracker modules;
* spectrum analysis;
* starfields;
* particles;
* geometric effects;
* beat-reactive behavior.

When extracting existing code:

```text
Inspect
   ↓
Identify dependencies
   ↓
Separate reusable behavior
   ↓
Adapt to ToroidAMP boundaries
   ↓
Validate
```

Do not blindly copy entire modules.

Do not rewrite working algorithms merely because they are old or stylistically imperfect.

Preserve useful behavior while removing inappropriate coupling.

---

# 12. Platform Rules

ToroidAMP targets Windows and Linux.

Use portable Python APIs whenever practical.

Prefer:

```python
pathlib
```

over manual platform-specific path manipulation.

Never hardcode user-specific or development-machine paths.

OS-specific behavior belongs behind platform boundaries.

Examples:

* system tray integration;
* media keys;
* application-data paths;
* notifications;
* media-session integration;
* file associations.

---

# 13. Persistence Rules

ToroidAMP currently requires lightweight persistence only.

Prefer simple formats such as JSON when sufficient.

Do not introduce a database unless a real requirement demonstrates that file-based persistence is inadequate.

The existence of SQLite is not itself a requirement to use SQLite.

---

# 14. Dependency Policy

Before adding an external dependency, determine:

* what requirement it solves;
* Windows support;
* Linux support;
* license;
* maintenance state;
* packaging implications;
* binary size implications;
* whether an existing dependency already solves the problem.

Dependencies are allowed.

Dependency archaeology is not a project objective.

---

# 15. Performance Priorities

Priority order:

```text
1. Stable audio playback
2. Responsive controls
3. Correct playlist/session behavior
4. Audio analysis
5. Visualizer frame rate
6. Visual extravagance
```

If necessary, visualization quality should degrade before playback reliability does.

When the visualizer is hidden or disabled, unnecessary rendering work should stop.

ToroidAMP should be comfortable remaining minimized in the background.

---

# 16. Failure Policy

Prefer graceful degradation.

Examples:

```text
Visualizer crashes
→ disable visualizer
→ playback continues

Metadata unavailable
→ show filename

Optional OS integration unavailable
→ player still works

Unsupported track
→ report it
→ continue safely
```

An optional subsystem should not unnecessarily become a single point of failure.

---

# 17. Scope Discipline

Before implementing an attractive new feature, check `SCOPE.md`.

V1 is not trying to become:

* Spotify;
* VLC;
* foobar2000;
* a music-library database;
* a streaming platform;
* a social network;
* a plugin marketplace.

Do not expand scope silently.

Ideas outside current scope may be documented for later consideration without becoming implementation commitments.

---

# 18. Technical Investigation Policy

When an architectural question is unresolved, prefer a **small executable probe** over speculative production code.

Examples:

```text
Can PySide6 host the visualizer cleanly?

Can backend X expose PCM while playing XM?

Can fullscreen visualization switch without interrupting audio?

Can Linux tray behavior match the required workflow?
```

Build the smallest experiment capable of answering the question.

Record the conclusion.

Discard experimental code when it does not belong in production.

---

# 19. Code Quality

Prefer readable code over clever code.

Functions should have clear responsibilities.

Names should describe intent.

Comments should explain **why**, not narrate obvious syntax.

Avoid giant files that accumulate unrelated responsibilities.

Do not refactor unrelated working code while implementing a focused cut unless the existing structure directly prevents the work.

---

# 20. Open-Source Mindset

Assume somebody unfamiliar with the project may eventually read the code.

Make subsystem boundaries discoverable.

Avoid unnecessary private conventions.

A contributor interested in writing:

```text
visualizers/flaming_hyper_toroid.py
```

should not need a personal guided tour of the entire repository.

Public extension APIs should nevertheless emerge from proven internal contracts.

Do not build a plugin framework before there is something stable worth plugging into.

---

# 21. Working-Cut Discipline

Each significant cut should have:

* a clear objective;
* explicit boundaries;
* validation criteria;
* a defined completion condition.

Do not quietly expand a cut because another interesting problem appeared nearby.

If new work is important but not required for the current objective, record it for later.

---

# 22. Validation

Do not report work as complete merely because code was written.

Validate the behavior relevant to the cut.

Depending on the work, validation may include:

* automated tests;
* manual playback;
* multiple audio formats;
* playlist behavior;
* fullscreen transition;
* visualization response;
* background playback;
* Windows/Linux behavior;
* performance observation.

Report what was actually validated.

Do not claim platform compatibility that was not tested.

---

# 23. Repository Hygiene

Keep generated files, caches, virtual environments, build output, and temporary artifacts out of version control unless explicitly required.

Do not commit:

```text
__pycache__/
.venv/
build/
dist/
```

or equivalent generated output without a deliberate reason.

Test music and visual reference assets must have clear licensing before becoming permanent repository content.

---

# 24. Commit Policy

Do not create commits unless explicitly instructed to do so.

Implementation and repository modification are separate actions from committing.

When working through an external coding agent, leave the working tree ready for review unless the current instruction explicitly grants commit authority.

---

# 25. Do Not Lie to the Documentation

If something is provisional, call it provisional.

If something was not tested, say it was not tested.

If an experiment failed, record the failure when it matters.

If the architecture changed, update architectural truth.

Do not preserve an outdated statement merely because changing documentation is inconvenient.

---

# 26. Personality Is Allowed

ToroidAMP is not enterprise payroll software.

Names, comments, documentation, and visual experiments may have personality.

Humor is welcome where it does not reduce technical clarity.

This is valid:

```text
# Prevent the toroid from achieving escape velocity.
```

This is less useful:

```text
# Magic happens here lol
```

Be entertaining.

Remain understandable.

---

# 27. The Future Crew Test

When evaluating a visual feature, ask:

> **Would this have made sense on a demoscene screen at 3 AM while an XM module was playing far too loudly?**

If yes, continue investigation.

If no, it may still be an excellent feature.

The test is inspirational, not normative.

---

# 28. Final Rule

The project exists because building software can itself be enjoyable.

Protect that.

Do not turn a compact music player into unnecessary infrastructure.

Do not turn experimentation into architectural chaos.

Do not turn architecture into an excuse to prevent experimentation.

And remember the mission:

> **Make the music play reliably.
> Make the code understandable.
> Make the screen do something unreasonable.
> Make Future Crew cry.**

## ToroidAMP

### **It really warps the toroid's ass!**
