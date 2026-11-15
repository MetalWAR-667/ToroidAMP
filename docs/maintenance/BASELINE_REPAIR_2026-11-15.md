# BASELINE Maintenance Record — Repairs 001–006 and QoL-001

> **Status:** IMPLEMENTED / FUNCTIONAL PASS — independent review **REVIEW PASS WITH NON-BLOCKING OBSERVATIONS**; **BASELINE-INTEGRATION-001 COMPLETE / PASS** — **COMMITTED / CLOSED (`93db09d`)**
>
> Integration validation and human validation are complete. Batch closure is **CLOSED / COMMITTED (`93db09d`)**; release publication is **NOT AUTHORIZED**. No release publication has occurred.

- **Date:** 2026-11-15
- **Repository baseline:** `65f94a1` (`fix(playback): start initial playback from shuffle order`)
- **Nature:** test-maintenance, one authorized production boundary correction, and documentation reconciliation. No audio/DSP/playlist/visualizer behavior changes beyond the marquee bound in REPAIR-003.

---

## 1. QoL-001 — Shuffle-Aware Initial Playback

- **Status:** CLOSED / ACCEPTED
- **Commit:** `65f94a1`
- **Tests:** `tests/test_qol_001.py` — 16/16 PASS
- **Human validation:** nine checks PASS (reported; not independently repeated by BASELINE-REVIEW-001)

Contract (also recorded in `docs/ARCHITECTURE.md` §13):

- Initial playback resolves through `PlaylistManager.get_initial_playback_index()`:
  - shuffle off → first canonical playlist item;
  - shuffle on → first item in the active shuffle order;
  - empty playlist → nothing.
- The initial-index query is read-only and never reshuffles an existing sequence.
- Next/Previous from an unset position (`current_index == -1`) use the same index.
- Once a track has actually been loaded, Play resumes/replays that track; explicit selection and Stop/Play-again semantics are preserved.
- Adding files to an empty, stopped playlist starts from the initial index, honoring shuffle.
- Session restoration remains stopped and never autoplays.

Implementation files: `src/toroidamp/audio/player.py`, `src/toroidamp/audio/playlist.py`, `src/toroidamp/ui/window_manager.py`, `tests/test_qol_001.py`.

---

## 2. Maintenance Repairs 001–006

| Repair | Outcome | Primary files | Evidence |
|---|---|---|---|
| **001 — Transport microfade test** | DSP-001A contract reconciled; leaked PortAudio stream cleaned up | `tests/test_rc_polish_001.py`, `docs/design/06_rc_polish_001.md` | 21/21 tests; 10/10 isolated repeat runs exit 0; forced synchronous-stop mutation fails the test |
| **002 — Donor isolation guard** | Known donor project/media rejected; first-party `metalwar_credits` accepted; shared detector + negative controls | `tests/test_fix_002.py`, `docs/fixes/002_...md` | 4/4 tests; synthetic donor import/path/media rejected; clean first-party code accepted |
| **003 — Marquee near-fit bound** | Non-overflow drift bounded by available space; overflow unchanged | `src/toroidamp/ui/marquee.py`, `tests/test_ux_004.py`, `docs/design/06_rc_polish_001.md`, `docs/ux/004_...md` | 41 tests + 10 subtests; independent review reproduced old 0–4 px failure; human 5/5 PASS reported |
| **004 — Visualizer identity & shortcut tests** | Cyber Bloom/Toroid Identity resolved by `get_id()`; `V` route tested through `QApplication`; M-to-cycle removed | `tests/test_gpu_prod_002.py` | 21/21 tests; `V` advances both indices and closes LAB; `M` does not cycle |
| **005 — Deterministic shader fixtures** | Mandatory tests use tracked fixtures; malformed GLSL rejected; optional local corpus skippable | `tests/test_gpu_audio_006a.py`, `tests/test_release_blockers_001.py`, `tests/assets/shaders/**` | Clean-checkout archive without `user_shaders/`: 21 passed + 1 optional skip / 6 passed + 2 subtests; both exit 0 |
| **006 — Changelog convention** | Single `[Unreleased]` section restored, convention documented | `CHANGELOG.md` | `tests/test_rc_069_003b.py` 12/12 + 50 subtests; test file unchanged |

**Independent review:** BASELINE-REVIEW-001 — **REVIEW PASS WITH NON-BLOCKING OBSERVATIONS**. No BLOCKER or MAJOR findings.

### Production change boundary

Only `src/toroidamp/ui/marquee.py` changed in production:

```text
max_offset = min(NON_OVERFLOW_TRAVEL_PX, spare_room)
```

Overflow scrolling, playback, DSP, playlist, visualizer registration, and assets were not changed.

---

## 3. Deferred Technical Items

These are recorded, not implemented. None is authorized by this record.

| Item | Classification | Notes |
|---|---|---|
| Microfade-test scheduling race | MINOR / HYPOTHESIS | The test opens a real PortAudio stream and asserts the immediate `PLAYING → FADING_OUT` transition. A >25 ms main-thread stall could let the native callback complete first. Not reproduced in 20+ isolated runs. |
| Donor static-scan limitations | MINOR / VERIFIED | Marker-based scan does not catch dynamically constructed paths or donor-named modules without `installer` (e.g. hypothetical `metalwar_audio`). No such real dependency exists. |
| GPU shortcut route-specific assertion | MINOR / VERIFIED | `test_27` passes through the app filter in current code, but also passes via the local `keyPressEvent` fallback when the filter is absent. A future assertion should prove filter consumption explicitly. |
| Seven hardcoded index-4 references | INFO / VERIFIED | `tests/test_gpu_prod_002.py` lines 108, 134, 163, 183, 204, 484, 508 still assume Toroid Identity is index 4. |
| GPU-suite scratch writes | MINOR / VERIFIED | `test_gpu_prod_002.py` writes `test_*.frag` scratch files into ignored `user_shaders/`. Pre-existing; not changed by REPAIR-004. |
| Broader shader regression coverage | MINOR / VERIFIED | Tracked fixtures are intentionally small/simple. Complex Mesa-sensitive constructs are no longer release-blocking; optional local corpus remains read-only. |
| CRLF policy / `git diff --check` | MINOR / VERIFIED | Standard check currently reports 68 CR-at-EOL warnings: 38 in `tests/test_rc_polish_001.py` (known from REPAIR-001), 9 in `docs/ARCHITECTURE.md`, and 21 in `docs/CURRENT_STATE.md` (both stored CRLF; REPAIR-007 additions inherit that). `git -c core.whitespace=cr-at-eol diff --check` is clean. Repository-wide EOL policy remains deferred. |
| `iChannel0..3` compatibility | DEFERRED / NOT AUTHORIZED | No declarations, texture bindings, sampler emulation, or new Shadertoy compatibility layers were added. |

Future NORMAL-mode short-title amplitude improvement: **DEFERRED / UX POLISH**, not authorized. See `docs/ux/004_marquee_mini_volume_versioning.md`.

---

## 4. Release Evidence Limitation

`RELEASE-GATE-0.667-LINUX`, `RELEASE-GATE-0.667-WINDOWS`, and `RELEASE-GATE-0.669-WINDOWS` report documents are **not present in tracked repository content**. Locally staged archives, checksums, and release-notes drafts exist only under the git-ignored `release/` tree (`release/0.667/`, `release/0.669/`). No report content was reconstructed, recovered, or claimed. See `docs/release/RC_069_*` for tracked release-process records that do exist.

---

## 5. Git Inventory at Reconciliation Time

Ten tracked files were modified by the implementation batch. At REPAIR-007 reconciliation time, thirteen tracked files are modified (the ten above plus `docs/ARCHITECTURE.md`, `docs/CURRENT_STATE.md`, and `docs/ux/004_marquee_mini_volume_versioning.md`), and nine files are untracked (eight fixtures plus this maintenance record).

```text
CHANGELOG.md
docs/ARCHITECTURE.md
docs/CURRENT_STATE.md
docs/design/06_rc_polish_001.md
docs/fixes/002_production_isolation_native_shutdown.md
docs/ux/004_marquee_mini_volume_versioning.md
src/toroidamp/ui/marquee.py
tests/test_fix_002.py
tests/test_gpu_audio_006a.py
tests/test_gpu_prod_002.py
tests/test_rc_polish_001.py
tests/test_release_blockers_001.py
tests/test_ux_004.py
```

> Note: this list grows because REPAIR-007 adds documentation files. The implementation-batch inventory before REPAIR-007 was ten tracked files plus eight untracked fixtures.

Eight untracked, trackable shader fixtures under `tests/assets/shaders/`:

```text
README.md
audit/audit_annotated_param.frag
audit/audit_non_promotable_bool.frag
audit/audit_promotable_const.frag
audit/audit_structural_only.frag
supported/gradient.frag
supported/time_pulse.frag
unsupported/malformed.frag
```

Plus this maintenance record:

```text
docs/maintenance/BASELINE_REPAIR_2026-11-15.md
```

The batch was committed as `93db09d` (22 files) after isolated staging verification. Integration and human validation are complete; closure is recorded as **CLOSED / COMMITTED**. No push or publication occurred.

### Non-Claims

- No publication, release tag, or version bump is implied. v0.669 remains `READY_FOR_PUBLICATION`, not released.
- Version 1.0 remains a **proposed future goal only**, subject to QoL completion, stable EQ, and release validation. It is not scheduled or authorized here.
- No missing release-gate report was reconstructed.

---

## 6. Integration & Closure Evidence

**BASELINE-INTEGRATION-001 — COMPLETE / PASS**

- 51/51 test modules completed with exit `0`.
- **730 tests PASS, 0 FAIL, 113 subtests PASS, 3 expected skips.**
- No native process crashes.
- Human closure checklist: **5/5 PASS**, confirmed by Metal.
- BASELINE-CLOSURE-001: **READY WITH DOCUMENTED EXCEPTION**.

**Test accounting:** HEAD contains 729 test functions; current contains 733 (+4 new tests). Passing moved from 717 to 730: **9 previously failing test functions corrected + 4 additional tests introduced**. The 2 baseline subtest failures (release blockers) were resolved separately and are not part of the +13 function count.

**CRLF exception / staging:** standard `git diff --check` reports 68 CR-at-EOL warnings (38 `tests/test_rc_polish_001.py`, 9 `docs/ARCHITECTURE.md`, 21 `docs/CURRENT_STATE.md`); `git -c core.whitespace=cr-at-eol diff --check` is clean. Ordinary `git add` would normalize `docs/ARCHITECTURE.md` and `tests/test_rc_polish_001.py` to LF wholesale, so those two must be staged with `git -c core.autocrlf=false add`. Repository-wide EOL policy is deferred to a separate cut.

**Closure state:** integration validation COMPLETE / PASS; human validation COMPLETE / PASS; maintenance batch closure **CLOSED / COMMITTED (`93db09d`)**; release publication **NOT AUTHORIZED**. The 22-file commit exists and matches the verified inventory.

## 7. Authoritative References

- Playback/fade contract: `docs/design/06_rc_polish_001.md` §2, §6.
- Marquee contract: `docs/design/06_rc_polish_001.md` §3; historical reconciliation in `docs/ux/004_marquee_mini_volume_versioning.md`.
- Donor guard reconciliation: `docs/fixes/002_production_isolation_native_shutdown.md` §6.
- QoL-001 architecture contract: `docs/ARCHITECTURE.md` §13.
- Changelog convention: `CHANGELOG.md` header and `[Unreleased]`.
- Operational state: `docs/CURRENT_STATE.md`.
