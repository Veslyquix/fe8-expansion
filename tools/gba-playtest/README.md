# GBA headless playtest fingerprints

`gba_playtest.py` replays a strict JSON input scenario through libmGBA, captures
named framebuffer/RAM checkpoints, and emits deterministic JSON. It is intended
to compare behavior when ROM bytes or link addresses legitimately change.
Every capture binds the behavior to machine-readable ROM provenance: SHA-1,
byte size, header title, and header game code. The backend executes the same
immutable temporary ROM copy that is hashed, avoiding a hash/load path race.

The tool does not load save files, screenshots, or savestates. Framebuffer hashes
are FNV-1a-64 over canonical 24-bit RGB bytes (alpha/padding and host endianness
are excluded). The small C backend is compiled into a temporary directory for
each command, so no emulator-generated binary is left in the tree.
Compiler, pkg-config, and emulator processes all have bounded timeouts with
actionable diagnostics. `--retries N` (default 0, i.e. a single attempt) adds
up to `N` additional attempts, capped at `MAX_RETRIES_CAP` (5) regardless of
the requested value, and applies only to a process **time-out** -- the one
condition here that can plausibly be transient host scheduling/load. A
non-zero exit code, a malformed backend/compiler diagnostic, or a fingerprint
mismatch are deterministic outcomes and are never retried by any code path in
this tool; retrying those would silently launder a real, reproducible failure
into intermittent-looking flake. Every retried attempt (not just the final
one) is printed to stderr with its attempt number, so a flaky time-out is
always visible even when a later attempt succeeds.

## Dependencies

Python 3.10+ is sufficient for parsing, serialization, diagnostics, and host tests.
Capture/verify additionally require a C compiler and libmGBA development files.

Linux (Debian/Ubuntu):

```sh
sudo apt-get install build-essential libmgba-dev
python3 tools/gba-playtest/gba_playtest.py backend-check
```

macOS (Homebrew):

```sh
brew install pkg-config mgba
python3 tools/gba-playtest/gba_playtest.py backend-check
```

If libmGBA or the compiler is unavailable, `capture`, `verify`, and
`backend-check` fail with exit status 2 and an installation diagnostic. They
never silently pass. The backend integration unit test is the only test that may
skip, and its skip reason includes the backend diagnostic.

## Commands

```sh
# Host tests (no ROM and no libmGBA needed, except the explicit integration test)
python3 -m unittest discover -s tools/gba-playtest/tests -v

# Capture sorted, reproducible JSON
python3 tools/gba-playtest/gba_playtest.py capture \
  --rom fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/boot.json \
  --output build/boot-capture.json

# Replay and compare every checkpoint/hash/probe
python3 tools/gba-playtest/gba_playtest.py verify \
  --rom fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/boot.json \
  --expected tools/gba-playtest/fingerprints/boot.json

# Explicit migration comparison: report both ROM identities but compare behavior
python3 tools/gba-playtest/gba_playtest.py verify \
  --policy behavior \
  --rom candidate.gba \
  --scenario tools/gba-playtest/scenarios/boot.json \
  --expected tools/gba-playtest/fingerprints/boot.json
```

Exit statuses are 0 for success, 1 for a valid-but-different fingerprint, and 2
for malformed input, missing dependencies, or backend/setup failure. Verify
diagnostics identify the exact JSON path, expected value, and captured value.

### Baseline refresh policy

A checked-in fingerprint (`--expected`) is a reviewed oracle, never output
`verify` can write, rewrite, or otherwise refresh itself -- there is no
`verify --write-baseline`-style flag anywhere in this tool, on either a
passing or a failing comparison (see
`tools/gba-playtest/tests/test_baseline_no_autorefresh.py`). Refreshing a
baseline is exclusively a human-run, explicit `capture -o <path>` invocation
followed by the ordinary reviewed-commit process for that changed file --
matching `docs/issue-resolution-policy.md`'s "Baseline and fingerprint
review": a mismatch is a signal to investigate the behavior change, not to
silently regenerate the fingerprint. Before committing a refreshed
fingerprint, record in the commit/PR: which checkpoints changed, the old vs.
new hash/probe values, and the semantic reason (the "fingerprint capture 必须
显式" contract for this harness).

### Verification policy

`verify` defaults to `--policy exact-rom`. This is the safe regression policy:
ROM SHA-1, size, title, game code, scenario identity, hashes, and probes must all
match. Accidentally testing the wrong ROM is therefore a hard mismatch.

`--policy behavior` is the explicit baseline-vs-candidate migration mode. It
compares scenario/checkpoint behavior while intentionally allowing ROM
provenance to differ, and always prints both complete identities. Use it only
when changed ROM bytes are expected; it never silently turns off identity
reporting. Capture JSON always contains provenance under `"rom"` regardless of
the later verification policy. Scenario schema version remains 1; provenance is
mandatory in fingerprint format version 2.

## Scenario format

A scenario is one strict JSON object. Unknown fields, duplicate JSON keys,
overlapping/out-of-order frame ranges, duplicate checkpoints/probes, malformed
expectations, and invalid key/address names are errors.

```json
{
  "schema_version": 1,
  "name": "example",
  "description": "Optional human context.",
  "frames": [
    {"start": 90, "end": 95, "keys": ["A", "RIGHT"]},
    {"start": 150, "end": 155, "keys": ["START"]}
  ],
  "checkpoints": [
    {
      "name": "after-input",
      "frame": 180,
      "framebuffer": true,
      "expected_framebuffer_hash": "fnv1a64-rgb24:0123456789abcdef",
      "probes": []
    }
  ]
}
```

Frame ranges are inclusive. `keys` is the complete held-key state for that
range: keys are pressed at `start` and released after `end`; gaps mean all keys
released. Valid names are `A`, `B`, `SELECT`, `START`, `RIGHT`, `LEFT`, `UP`,
`DOWN`, `R`, and `L`. For frame N, input is applied, one frame runs, and then a
checkpoint at N is captured.

Probes may be 1, 2, or 4 aligned bytes in EWRAM
(`0x02000000`-`0x0203ffff`) or IWRAM
(`0x03000000`-`0x03007fff`). Address strings always have eight hex digits.
Optional probe values are lowercase, fixed-width little-endian integer
renderings. Optional inline expectations make capture fail immediately; normal
regression verification uses a separate checked-in fingerprint.
Only probe documented semantic state whose address and meaning remain stable
under the intended compiler/linker migration. Arbitrary region-base words,
allocator scratch, and relocated pointers are not valid behavioral oracles.
The boot/title scenarios intentionally use framebuffer-only checkpoints. The
source-generated integration fixture uses `0x02000000` only because its own
documented program explicitly mirrors KEYINPUT there.

Disabled schema-ready stubs additionally use `"disabled": true` and a non-empty
`"blocker"`. They may have no checkpoints, and capture rejects them explicitly.

## Initial coverage and limits

`boot.json` is a no-input early boot capture. `title-progression.json` uses the
same deterministic six-frame A/START tap concept as
`scripts/shiftcheck/mgba_oracle.c`, with attribution retained in `backend.c`.
Modern GCC uses configuration-specific
`title-progression-modern-{debug,release}.json` fingerprints because
optimization changes later title-animation timing. Shifted links must match
the baseline for their own configuration. The legacy fingerprints were
captured with libmGBA 0.10.2 from the baseline ROM whose project checksum is
`c25b145e37456171ada4b0d440bf88a19f4d509f`; the modern title fingerprints
record the debug/release ROM provenance directly. An emulator-version change
that alters rendered pixels is intentionally reported as a fingerprint
difference and should be reviewed rather than normalized away.
`tests/homebrew_fixture.py` generates a tiny original homebrew ROM in a
temporary directory and drives released/A-held/released frames, pixels, and a
semantic RAM value through capture and both verification policies. Only
generator source is committed.

### Deterministic runtime scenario coverage (issue #13)

Every scenario below is reached from a clean boot with no committed
savestate/save file; every non-framebuffer claim of "arrival" is proven by a
semantic probe (an EWRAM/SRAM field, or a whole-SRAM hash) derived from this
build's own symbol table or a documented struct offset, never framebuffer
similarity alone.

| Scenario | Proves | Config(s) |
| --- | --- | --- |
| `boot.json` | Early boot progress | debug + release (behavior policy) |
| `title-progression.json` | Title/intro/menu progression | debug + release |
| `new-game.json` | Ordinary Save-Menu New Game creation: New Game -> Easy -> first empty slot, with a before/after whole-SRAM hash proving the real `SaveMenuWriteNewGame`/`WriteGameSave`-class write happened, and `gPlaySt.chapterIndex`/`faction` probes confirming the created game begins at the Prologue (`CHAPTER_L_PROLOGUE`, player phase) | debug + release |
| `debugtools-hub-modern-{debug,release}.json` (issue #11) | The debug-only "Fast Boot: Chapter 2" launcher's deterministic clean-boot chapter/map **arrival**: reaches an interactive first stable Player Phase on the real Chapter 2 map, proven via relocation-independent cursor/phase/proc-state/hub-count semantic probes plus per-slot `struct Unit.state` fields and a stable fixture-seeded whole-SRAM hash (no unit `pCharacterData` ROM pointer is asserted as an oracle); release mirror proves the hub/launcher are compiled out and inert | debug (live) / release (negative) |
| `debugtools-map-hub-modern-{debug,release}.json` (issue #11) | The map-phase debug hub stays reachable and leaves the real, interactive Chapter 2 map genuinely interactive afterward | debug (live) / release (negative) |
| `debugtools-{prep,timer,ch4-prep-launch}-*` (issue #11) | Additional debug-tool launcher/hotkey/diagnostics behavior and their release-inert negatives -- see `docs/debugtools.md` | debug + release, per file |
| `savecompat-current.json` / `savecompat-dialog-back.json` / `savecompat-erase.json` | Save-compatibility classification, non-destructive Back, and confirmed Erase across all `SaveCompatState` values | debug + release |
| `savesuspend-resume-modern-debug.json` | Full write -> soft-reset -> reload round trip: an ordinary Map Menu **Suspend**, a real soft-reset key combo, and **Resume** through `ReadSuspendSave()`, with `gPlaySt.chapterIndex`/`faction`/cursor and a unit-item probe proving the exact manually-saved state (not the earlier auto-save) was restored | debug only (depends on the debug-only Chapter 2 launcher) |
| `combat.json` (issue #13) | The chapter's own scripted `FIGHT` in Chapter 4 resolved by the REAL battle engine (`Event3F_ScriptBattle`, `EV_CMD_SCRIPT_BATTLE`): the target enemy `gUnitArrayRed[0]` is alive at full HP (`maxHP` `0x0202eba6` and `curHP` `0x0202eba7` both `15`), `curHP` transitions `15 -> 0` at the resolving SCRIPT_BATTLE frame while `maxHP` stays `15`, then `pCharacterData` (`0x0202eb94`) is cleared to a null `0x00000000` (death) -- relocation-independent semantic HP scalars and a null-field marker, never a nonzero pointer, framebuffer, or timing | debug only (debug-only Fast Boot launcher) |
| `save-load.json` (issue #13) | Normal (non-Suspend) game-save write + load: SaveMenu New Game -> slot 0 write, a real A+B+SELECT+START soft reset, then SaveMenu RESTART -> `PostSaveMenuHandler` -> `ReadGameSave(0)`; `playthroughIdentifier` (`0x020210bc`)/`chapterModeIndex` (`0x020210bf`) go `1 -> 0 -> 1`, `gameSaveSlot` (`0x020210b0`) `== 0`, and before/after whole-SRAM hashes differ | debug only (debug-calibrated soft-reset) |
| `debugtools-ch4-prep-positive-modern-debug.json` (issue #11) | Live prep-screen arrival + SELECT+B prep hotkey: rests `gProcScr_SALLYCURSOR` in `PrepScreenProc_MapIdle` and fires the hotkey; `prepScreenObservedCount` (`0x02031854`) `0 -> 1` (reachable only from MapIdle, so it is the relocation-independent proof the hotkey fired live), `PLAY_FLAG_PREPSCREEN` held throughout, idempotent 2nd press, safe return to prep -- no proc ROM-pointer oracle | debug only (debug-only launcher + hotkey) |
| `debugtools-tools-modern-{debug,release}.json` (issue #11) | The five shipped bounded tools driven **live** from the real Chapter 2 map hub: each of Unit Inspect/Edit, Convoy Inspect/Edit, Flag/Chapter, RNG Inspect/Control, and Save Compatibility/State Inspect is triggered from its real hub row with an asserted semantic effect (Unit heal transaction; Convoy count `0 -> 1`; Flag `0 -> 1`; RNG seed `0x0000ee77 -> 0x0000690b`; Save read-only, count `0 -> 1` and unchanged on Back) and a safe hub return (`hubOpenCount 2 -> 9`), ending with the map still interactive (player cursor `0x06 -> 0x07`); probe-only, relocation-independent. Release mirror proves the hub/tools are compiled out (`gDebugToolsProbe` all-zero) | debug (live) / release (negative) |

New-game, chapter/map arrival, combat, and normal save/load are all enabled,
verified scenarios -- see the coverage table above. **No `*.stub.json` files
remain in the repository** (the `scenarios/stubs/` directory is gone):
`combat.json` and `save-load.json` replaced the former combat/save stubs, and
`debugtools-ch4-prep-positive-modern-debug.json` proves the live prep-screen
arrival. `tools/gba-playtest/tests/test_stub_scenarios.py` now asserts that no
stub scenarios remain and that `combat.json`/`save-load.json` are enabled with
semantic (non-framebuffer) checkpoints; no test treats a stub as success. A
savestate or save binary remains prohibited as a shortcut: every scenario is
reached from a clean boot and proves the intended state via a semantic probe
(an EWRAM/SRAM field or a whole-SRAM hash), never framebuffer/timing
similarity alone.

### Supported CI host matrix

CI (`.github/workflows/build.yml`) runs on `ubuntu-latest` only, in two
separate jobs: a fast `host-tests` lane (this test suite only, no
`arm-none-eabi` toolchain) and a `build` lane (the full modern ROM/linker
gate, both `debug` and `release`, `MODERN_ABI=aapcs` only -- see
`docs/config_identity.md`). macOS (Homebrew) is documented above for local
development but is not exercised by CI. The archival/decomp `agbcc`
`fireemblem8.gba` path (see `docs/issue-resolution-policy.md` "Supported
modern path vs. archival decomp path") continues to build locally, unrelated
to and unaffected by this harness, but it is not part of any CI gate here and
must never be read as a substitute runtime gate for the modern path.
