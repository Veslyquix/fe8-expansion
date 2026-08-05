# Expansion save format (issue #2)

This document is the single reference for the expansion-owned save
metadata record, the raw-byte compatibility classifier, the destructive
boot-path fix, the host-side `scripts/modernize/save_format_tool.py` CLI
(issue #2 slice 1), and the global save-menu compatibility gate/UI, its
generated text, its diagnostic probe, and its `tools/gba-playtest`
runtime-test coverage (issue #2 slice 2).

Slice 1 defined the on-media format and made detection non-destructive.
Slice 2 (this document's "Save-menu compatibility gate" section) adds the
player-facing UI that slice 1's own docs previously described as future
work, and the deterministic runtime/host test coverage that gates it in
CI. Neither slice provides automatic in-console structural migration of
older *current-format* save layouts -- see "Limitations" below, which
remains true after slice 2.

## On-media format

### Where it lives

`struct SaveBlocks` (`include/bmsave.h`) previously reserved a 4-byte
`reserved` field at SRAM offset `0x73A0` followed by an unused 0x5C-byte
pad at `0x73A4`, ending exactly where `xmap` begins at `0x7400`:

```c
/* 0x73A0 */ u8 reserved[4];
/* 0x73A4 */ u8 _pad_[0x7400 - 0x73A4];   /* was: unused, 0x5C bytes */
/* 0x7400 */ struct ExtraMapSaveHead xmap;
```

This slice replaces only that pad with `struct ExpansionSaveMeta`
(`include/save_format.h`), which is exactly 0x5C bytes -- every other
offset in `struct SaveBlocks` (including `reserved` at `0x73A0` and `xmap`
at `0x7400`), and the struct's total size, is unchanged:

```c
/* 0x73A0 */ u8 reserved[4];
/* 0x73A4 */ struct ExpansionSaveMeta expansionSaveMeta;
/* 0x7400 */ struct ExtraMapSaveHead xmap;
```

`include/sram-layout.h` derives `SRAM_OFFSET_EXPANSION_SAVE_META` /
`SRAM_SIZE_EXPANSION_SAVE_META` from the pre-existing `SRAM_OFFSET_XMAP`
enum rather than a bare magic number.

### `struct ExpansionSaveMeta` layout

Fixed-width, explicit little-endian (native GBA byte order), zero implicit
padding -- every byte of the 0x5C-byte record is accounted for by a named
field (`STRUCT_PAD` fills the small alignment gaps between them):

| Offset | Size | Field | Kind |
| --- | --- | --- | --- |
| `0x00` | 4 | `magic` (`"FSAV"`, not NUL-terminated) | compatibility gate |
| `0x04` | 1 | `formatVersion` | compatibility gate |
| `0x05` | 1 | *(pad)* | -- |
| `0x06` | 2 | `compatEpoch` | compatibility gate |
| `0x08` | 1 | `abiId` (0=apcs-gnu, 1=aapcs) | diagnostic only |
| `0x09` | 3 | *(pad)* | -- |
| `0x0C` | 4 | `frameworkVersionPacked` | diagnostic only |
| `0x10` | 17 | `configFingerprint` (16 hex chars + NUL) | diagnostic only |
| `0x21` | 3 | *(pad)* | -- |
| `0x24` | 9 | `buildCommitShort` (8 hex chars + NUL) | diagnostic only |
| `0x2D` | 1 | *(pad)* | -- |
| `0x2E` | 2 | `checksum` (`Checksum16` over `[0x00, 0x2E)`) | -- |
| `0x30` | 44 | `reserved` (`struct ExpansionUserPrefs` at offset `0x00`-`0x0B` since issue #18 sprint 2, see below; remaining `0x0C`-`0x2B` still zero-filled headroom) | -- |

Total: `0x5C` bytes exactly.

### `struct ExpansionUserPrefs` (issue #18 sprint 2)

The player's own persisted locale selection is a distinct, independently
versioned/checksummed sub-record living at a **fixed byte offset inside
`ExpansionSaveMeta.reserved`** (`EXPANSION_USER_PREFS_META_OFFSET`, currently
`0`) -- it does **not** move `SRAM_OFFSET_EXPANSION_SAVE_META`, resize
`ExpansionSaveMeta` (still exactly `0x5C` bytes), change any `0x00`-`0x2F`
field's offset, or touch `xmap`/any other `SaveBlocks` field. See
`include/expansion_save_prefs.h`.

| Offset (within `reserved`) | Size | Field |
| --- | --- | --- |
| `0x00` | 1 | `magic` (`0xA5`) |
| `0x01` | 1 | `version` (`EXPANSION_USER_PREFS_VERSION_CURRENT`, currently `1`) |
| `0x02` | 1 | `localeId` (`ExpansionLocaleId`) |
| `0x03` | 1 | `flags` (bit 0 = `EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT`) |
| `0x04` | 4 | `reserved[4]` (always `0`, headroom for near-future fields) |
| `0x08` | 2 | `checksum` (`Checksum16` over `[0x00, 0x08)`, its own independent domain -- never covered by `ExpansionSaveMeta`'s own checksum) |

`sizeof(struct ExpansionUserPrefs) == 0x0C` (`ALIGN(4)` forces legacy agbcc
and modern AAPCS-conformant GCC to agree on this size -- the same class of
cross-compiler layout fix already used for `struct BonusClaimSaveData`,
`include/bmsave.h`). This leaves `EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES
== 0x20` (32 bytes) of `reserved` tail still free for future sub-records;
`scripts/modernize/tests/test_save_format_layout.py` proves the headroom
computation never goes negative and that every existing `0x00`-`0x2F` field
offset is unchanged.

**No-wipe contract.** None of `ExpansionUserPrefs_Build/ValidateRaw/Load/
Normalize/StoreRaw` (`src/bmsave-lib.c`) ever calls `WipeSram()` or touches
any byte outside this record's own `0x0C`-byte window. An all-zero record
(every pre-sprint-2 "current" save's `reserved` tail, always deterministically
zeroed by `BuildCurrentExpansionSaveMeta()`) or all-`0xFF` record (the
documented blank-SRAM fill pattern) classifies `EXPANSION_USER_PREFS_UNSET`,
never `EXPANSION_USER_PREFS_CORRUPT` -- so an old save that predates this
sprint, or a never-yet-saved slot, is never misdiagnosed as damaged.
`EXPANSION_USER_PREFS_CORRUPT` (bad magic/checksum/future version),
`EXPANSION_USER_PREFS_UNKNOWN_LOCALE` (locale id outside this build's known
slots), and `EXPANSION_USER_PREFS_DISABLED_LOCALE` (a known but currently
disabled locale) likewise never mutate SRAM: `ExpansionUserPrefs_Normalize`
resolves all four of these non-`VALID`/non-`MIGRATED` states down to this
build's configured default locale (`FE8_EXPANSION_DEFAULT_LOCALE_ID`) with
`requiresPrompt = TRUE`, so a runtime caller falls back safely and can
re-prompt the player instead of silently trusting (or erasing) an unusable
record. `EXPANSION_USER_PREFS_MIGRATED` (a well-formed older-version record)
and `EXPANSION_USER_PREFS_VALID` both resolve with `requiresPrompt = FALSE`.

`ExpansionUserPrefs_Store` (`src/expansion_save_prefs.c`, modern-only linked --
see the file header comment) is the only function that ever writes this
record: it builds a fresh checksummed record in a local temporary, rejects
an unsupported/disabled `localeId` before touching SRAM at all, and reuses
the exact same bounded single `ReadSramFast`/`WriteAndVerifySramFast`-based
existing-API write path `BuildCurrentExpansionSaveMeta`'s callers already
use. `ExpansionUserPrefs_StoreRaw()` also requires the outer save to classify
`SAVE_COMPAT_CURRENT`, so a nested preference repair can never modify a
legacy/newer/corrupt/config-incompatible image before the global gate. There
is no new parallel SRAM-write mechanism, source/destination buffer overlap,
or `WipeSram()` call on any validation failure. On a successful store it
calls `ExpansionLocale_SetCurrent()` (which internally invalidates the
runtime resolver's cache), so a UI that just persisted a selection can
immediately observe it without a reboot.

Host-side (`scripts/modernize/save_format_tool.py`) mirrors this exact
struct/classification/checksum logic in Python (`ExpansionUserPrefs`
dataclass + `classify_user_prefs_raw`/`classify_user_prefs_bytes`/
`normalize_user_prefs`), and
`cmd_migrate` **preserves** an existing source's `reserved` bytes (hence
its prefs record) verbatim across a v1(+)->current migration -- only a
true v0/vanilla source (nothing to preserve) gets a fresh default record.
`scripts/modernize/tests/test_expansion_user_prefs_native.py` cross-checks
the real C implementation (extracted verbatim from `src/bmsave-lib.c` and
compiled/run as a host probe) against the Python mirror across the full
9-case state matrix (blank-`0xFF`, unset-zero, valid, unknown-locale,
disabled-locale, corrupt-magic, corrupt-checksum, corrupt-newer-version,
migrated-older-version).

### Compatibility vs. diagnostic fields

Only three fields ever gate compatibility: `magic`, `formatVersion`, and
`compatEpoch`. Every other field (`abiId`, `frameworkVersionPacked`,
`configFingerprint`, `buildCommitShort`) is stored **only** for
diagnostics/tooling and **never** influences classification. This is a
deliberate design constraint (issue #2 slice 1's DON'T guardrails):

* The framework's full issue #8 config fingerprint mixes in settings
  (e.g. `config_preset` debug/release) that do not affect the save
  layout at all. Gating save compatibility on it would make an otherwise
  identical save look incompatible after a routine debug/release rebuild.
* `EXPANSION_SAVE_COMPAT_EPOCH` (see below) is therefore its own,
  independent, rarely-bumped value: it changes only when a save-layout or
  serialization change actually requires it.

`ClassifySaveCompatRawTests.test_diagnostic_field_differences_never_change_classification`
(`scripts/modernize/tests/test_save_format_tool.py`) proves this directly:
two metadata records with identical `magic`/`formatVersion`/`compatEpoch`
but completely different diagnostic fields both classify `SAVE_COMPAT_CURRENT`.

### `EXPANSION_SAVE_COMPAT_EPOCH`

A new, independent setting in `config.mk` (default `1`), exposed to C as
`FE8_EXPANSION_SAVE_COMPAT_EPOCH` (`include/expansion_config.h`) via the
same `#ifndef`-guarded-fallback pattern issue #8 established for the other
`FE8_EXPANSION_*` values, and validated/parsed by
`scripts/modernize/expansion_config.py` (`validate_save_compat_epoch()`,
range `[0, 65535]`) alongside the existing issue #8 settings -- see
`docs/config_identity.md`'s settings table.

**Bump `EXPANSION_SAVE_COMPAT_EPOCH` whenever a save-layout or
serialization change makes an existing save's raw bytes no longer mean
what this build's code assumes they mean** -- e.g. reordering/resizing/
reinterpreting fields inside any current save-block struct, changing a
checksum domain, or changing how a block is packed. Do **not** bump it for
build/title/debug/ROM-size-only changes; those must never make a current
save look incompatible (this is the entire reason it is independent of
the issue #8 config fingerprint).

**Fixed (review finding #4):** `modern.mk` now threads
`EXPANSION_SAVE_COMPAT_EPOCH` through the same
`scripts/modernize/expansion_config.py resolve` shell-out used for the
other `FE8_EXPANSION_*` values, adds
`-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=$(MODERN_SAVE_COMPAT_EPOCH)` to
`MODERN_CFLAGS`, and includes `save_compat_epoch=...` in
`MODERN_COMPILE_SETTINGS` (the issue #8 content-addressed recompilation
stamp). This means `make ... EXPANSION_SAVE_COMPAT_EPOCH=2` changes the
value a modern build compiles in *and* invalidates every previously-built
object observing `include/expansion_config.h`, without requiring `make
clean` first. The legacy (non-modern) build still always uses the
`#ifndef` fallback from `include/expansion_config.h` (never receives any
`-D` override), matching every other `FE8_EXPANSION_*` value's treatment.
As with the rest of these settings, `EXPANSION_SAVE_COMPAT_EPOCH` remains
excluded from `ExpansionIdentity.fingerprint_fields()`/the issue #8
config fingerprint -- it is a distinct, independent compatibility gate,
never something a build/title/debug/ROM-size-only change can perturb.
See `scripts/modernize/tests/test_save_compat_epoch_modern_build.py` and
`scripts/modernize/tests/test_expansion_config.py`'s
`test_resolve_save_compat_epoch_override_changes_token_not_fingerprint`.

## Raw-byte compatibility classifier

`enum SaveCompatState` (`include/save_format.h`) has 8 explicit states.
All non-EMPTY states are decided in this precedence order by
`ClassifySaveCompatRaw()` (`src/bmsave-lib.c`) from **only** the global save
header (`struct GlobalSaveInfo`) and the metadata record above -- never by
interpreting any current save-block struct (game/suspend/arena/xmap).
`ClassifySramSaveCompat()` additionally scans the full chip as opaque bytes
before allowing the destructive EMPTY result:

1. **`SAVE_COMPAT_EMPTY`** -- the full 32 KiB SRAM image has one consistent
   erased fill: either entirely `0xFF` (hardware/`WipeSram()` fill) or
   entirely `0x00` (deterministic emulator/movie reset fill), excluding
   only the four-byte `gSram->reserved` hardware probe that `SramInit()`
   deliberately overwrites before classification. Erased-looking
   header/metadata bytes can therefore never hide surviving game/suspend/
   arena/xmap data. This is the **only** state that may trigger an
   automatic full-SRAM wipe.
2. **`SAVE_COMPAT_HEADER_CORRUPT`** -- not blank, and the header itself
   fails the existing `ReadGlobalSaveInfo()`-style validation (name,
   `magic32`, `magic16`, checksum).
3. **`SAVE_COMPAT_VALID_LEGACY_OR_VANILLA`** -- header is valid, but the
   metadata record's `magic` is not `"FSAV"`. Covers both true vanilla FE8
   saves and legacy expansion saves written before this slice (the old
   pad was never written, so it reads back as whatever was already in
   that SRAM byte range -- typically `0xFF` from the last wipe, but this
   state does not require it to be).
4. **`SAVE_COMPAT_METADATA_CORRUPT`** -- metadata magic present, but its
   own checksum does not match.
5. **`SAVE_COMPAT_NEWER_UNSUPPORTED`** -- valid metadata whose
   `formatVersion` is greater than this build's `SAVE_FORMAT_VERSION_CURRENT`.
6. **`SAVE_COMPAT_MIGRATABLE_OLDER`** -- valid metadata whose
   `formatVersion` is less than current.
7. **`SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE`** -- metadata is at the
   current `formatVersion`, but `compatEpoch` does not match
   `FE8_EXPANSION_SAVE_COMPAT_EPOCH`.
8. **`SAVE_COMPAT_CURRENT`** -- everything above passed.

Two independent implementations share this exact precedence and must be
kept in lockstep if it ever changes:

* **C** (shipped): `ClassifySaveCompatRaw()`/`ClassifySramSaveCompat()` in
  `src/bmsave-lib.c`, declared in `include/save_format.h`. The pure raw
  helper trusts its already-derived blank flags; every destructive live
  caller goes through `ClassifySramSaveCompat()` and its full-chip check.
* **Python** (host tooling): `classify_save_compat_raw()`/
  `classify_image()` in `scripts/modernize/save_format_tool.py`. The raw
  helper classifies isolated same-fill header/metadata pairs; the CLI and
  every full save-image operation use `classify_image()`, which mirrors the
  complete SRAM check.

`ClassifySramSaveCompat()` also treats `IsSramWorking() == false` (SRAM
hardware not confirmed working) as `SAVE_COMPAT_HEADER_CORRUPT` rather than
`SAVE_COMPAT_EMPTY`, so a hardware fault can never be mistaken for a
genuinely blank cart and trigger an automatic wipe.

## Destructive boot-path fix

`EraseSramDataIfInvalid()` (`src/bmsave-lib.c`, called from `AgbMain()` in
`src/main.c`) previously wiped **all 32 KiB** of SRAM (via
`InitGlobalSaveInfodata()` -> `WipeSram()`) whenever
`ReadGlobalSaveInfo(NULL)` returned false -- true for corrupt, vanilla,
newer, older, and save-config-incompatible data alike, not just genuinely
blank SRAM. It now gates the wipe on `ClassifySramSaveCompat() ==
SAVE_COMPAT_EMPTY` instead, so every other state is left byte-for-byte
untouched for later UI/tooling (slice 2 and the host-side CLI below).
Modern builds return before the bonus/rank/sound-room/link-arena repair
calls and `LoadAndVerfySuspendSave()` unless the image was already CURRENT
or EMPTY was just initialized to CURRENT. They also skip the legacy
`EraseInvalidSaveData()` converter before classification. A boot-scoped
`gSramBootFlags` write-allowed bit remains clear for every non-current
state and also blocks nested locale-preference stores and automatic
sound-room unlock writes before the compatibility dialog. The archival
build retains its original behavior byte-for-byte.

`InitGlobalSaveInfodata()` (the genuinely-blank-SRAM initializer) now also
builds and writes a current `ExpansionSaveMeta` record
(`BuildCurrentExpansionSaveMeta()`) immediately after writing the global
header, so a freshly-initialized save is classified `SAVE_COMPAT_CURRENT`
from that point on.

### Requirement 11 scan: coupled boot/save-init call sites

The same "invalid means wipe" pattern was found in three call sites
outside `EraseSramDataIfInvalid()` itself:

* `src/sio_event.c`'s `EraseSaveData` -- an explicit, user-facing "erase
  save" feature. Wiping *is* the intended behavior here, so this one is
  deliberately left as-is (it is not a bug).
* `src/classchg-sel.c`'s `Check3rdTraineeEnabled` -- **fixed**.
* `src/bmsave-bwl.c`'s `SavePlayThroughData` -- **fixed**.

Both fixed call sites previously did:

```c
if (!ReadGlobalSaveInfo(&info)) {
    InitGlobalSaveInfodata();
    ReadGlobalSaveInfo(&info);
}
```

which silently equated "the header struct failed to read" with "SRAM is
blank" -- exactly the same bug `EraseSramDataIfInvalid()` had, just
reachable from class-change and chapter-completion instead of boot. Both
now call the shared `EnsureGlobalSaveInfoLoaded()` helper
(`src/bmsave-lib.c`, declared in `include/bmsave.h`), which only
initializes when the raw classifier proves SRAM is genuinely
`SAVE_COMPAT_EMPTY`, and otherwise returns `false` without touching or
reinterpreting SRAM -- `Check3rdTraineeEnabled` then returns `false`
(trainee locked) and `SavePlayThroughData` returns without saving,
instead of wiping or writing progress on top of unrecognized data.
`InitGlobalSaveInfodata()` itself is no longer called directly from
either file. See `scripts/modernize/tests/test_save_format_call_site_safety.py`
for the regression coverage (source-scan proof that the unsafe pattern
is gone, plus a byte-exact behavioral mirror of the guard across all 8
classifier states).

## Host-side CLI: `scripts/modernize/save_format_tool.py`


Python-stdlib-only (no new dependencies), following this repository's
existing `scripts/modernize/*.py` conventions.

```
save_format_tool.py [--repo-root PATH] inspect  <path>
save_format_tool.py [--repo-root PATH] validate <path> [--expect STATE ...]
save_format_tool.py [--repo-root PATH] migrate  <source> <dest> [--force]
```

* **`inspect`** prints the classification plus every diagnostic field.
  It never fails on classification itself, only on I/O (wrong size,
  unreadable file).
* **`validate`** exits non-zero if the classification is not one of the
  accepted `--expect` states (repeatable; default: `SAVE_COMPAT_CURRENT`).
* **`migrate <source> <dest> [--force]`** is strictly out-of-place and
  host-side only:
  1. Refuses `source == destination` (compared via resolved real paths,
     not string equality -- this catches symlink and relative-path
     aliases) before touching either file. A hard link to the source is
     a *distinct* path that resolving alone cannot recognize as the same
     file (there is no symlink to follow), so it is caught separately by
     device+inode identity (`os.path.samefile`) and refused with the same
     exit code `6` -- in both cases regardless of `--force`, since
     `--force` only governs overwriting an unrelated existing
     destination, never migrating a source onto an alias of itself.
  2. Refuses an already-existing `dest` unless `--force` is given. This
     early check is a cheap, human-friendly precondition (it avoids doing
     a full read/classify/rebuild just to report an obviously-already-
     existing destination) -- it is **not** the actual enforcement; see
     step 7.
  3. Reads the full 0x8000-byte source image into an in-memory
     `bytearray` -- the source file is **never** opened for writing.
  4. Classifies the source. `SAVE_COMPAT_VALID_LEGACY_OR_VANILLA`
     (the v0 state), `SAVE_COMPAT_MIGRATABLE_OLDER` (including the real
     version-1/epoch-1 -> current version-2/epoch-2 case), and already-
     `SAVE_COMPAT_CURRENT` (a no-op re-migration) are migratable. Every other
     classification is a precondition failure; nothing is written and the
     source remains untouched. For older/current metadata, the existing
     `reserved` bytes -- including any prefs record -- are preserved verbatim.
  5. Builds a current `ExpansionSaveMeta` record (mirroring
     `BuildCurrentExpansionSaveMeta()`; diagnostic fields use documented
     placeholders since a host tool has no live build context -- they
     never affect compatibility) and stamps it into the in-memory copy.
  6. Re-classifies the in-memory result. It must come back
     `SAVE_COMPAT_CURRENT`, or the migration is aborted with **nothing**
     written to `dest`.
  7. Publishes atomically: the full image is written to a temporary file
     created in `dest`'s own directory (so the final publish step is a
     same-filesystem operation), flushed and `fsync`'d, then re-read and
     re-verified byte-for-byte and by classification. Publication itself
     is then **OS-enforced, not merely precondition-checked**: without
     `--force`, the temp file is published via `os.link(temp, dest)`, an
     atomic fail-if-exists operation, so even a destination created by a
     concurrent writer strictly *after* the step-2 precheck still causes
     the publish itself to fail (exit code `7`) rather than clobbering
     it; with `--force`, the temp file is published via
     `os.replace(temp, dest)`, which unconditionally and atomically
     overwrites any existing destination. Either way, the temporary file
     is always removed afterward (whether publish succeeded, lost the
     no-force race, or failed outright), `dest` is never opened for
     writing directly, and any I/O failure -- including
     `tempfile.mkstemp()` itself failing -- is handled deterministically
     rather than propagating an uncaught exception. The published
     destination is re-read and re-verified once more after a successful
     publish.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `1` | I/O error (file not found, unreadable, unwritable, wrong size, temp-file creation/write/publish failure, ...) |
| `2` | argparse usage error (reserved by Python's `argparse`; this tool never raises it directly) |
| `3` | `validate`: classification not in the accepted `--expect` set |
| `4` | `migrate`: source classification is not migratable |
| `5` | `migrate`: post-migration re-verification did not come back `SAVE_COMPAT_CURRENT` |
| `6` | `migrate`: source and destination are the same file (refused) -- either by resolved canonical path (symlink/relative-path alias) or by device+inode identity (hard-link alias); enforced regardless of `--force` |
| `7` | `migrate`: destination already exists (refused; pass `--force` to overwrite). Raised either by the early precondition check (step 2 above) or by the OS-enforced `os.link()` publish itself losing a race against a concurrently created destination -- either way the destination is left completely untouched. |

## Save-menu compatibility gate (issue #2 slice 2)

### The gate itself

`StartSaveMenu()` (`src/savemenu.c`) -- the only normal entry point into
`ProcScr_SaveMenu`, the real save menu -- classifies SRAM with
`ClassifySramSaveCompat()` *before* doing anything else. `SAVE_COMPAT_CURRENT`
proceeds into the existing save menu completely unchanged (same
`Proc_StartBlocking`/init call, same behavior as before this slice). Every
other state is diverted to `StartSaveCompatMenu()`
(`src/save_compat_menu.c`) instead, and `StartSaveMenu()` returns
immediately -- the real save menu proc is never started for a non-CURRENT
state. `SAVE_COMPAT_EMPTY` cannot normally reach this gate as a non-CURRENT
state: `EraseSramDataIfInvalid()` (see above) already auto-converts either
erased fill pattern to `SAVE_COMPAT_CURRENT` at boot. `StartSaveMenu()` also
rechecks and initializes EMPTY as a defensive fallback before routing every
other non-CURRENT state to the compatibility menu.

`scripts/modernize/tests/test_save_format_call_site_safety.py` and
`tools/gba-playtest/tests/test_save_compat_gate_safety.py` both statically
scan the shipped source (no execution required) to prove: (1)
`StartSaveMenu()` is the sole directly-coupled entry point into
`ProcScr_SaveMenu` reachable from any proc script, and it classifies and
diverts before calling `Proc_StartBlocking(ProcScr_SaveMenu, ...)`; and (2)
`src/save_compat_menu.c` never references `IsSaveValid`,
`ReadSaveBlockInfo`, `ReadGameSave`, `ReadGameSavePlaySt`,
`ReadGameSaveCoreGfx`, `InvalidateGameSave`, or `struct SaveBlockInfo`
anywhere in its compiled code.

### Compatibility proc / UI

`StartSaveCompatMenu()` is a small, self-contained blocking `Proc`
(`gProcScr_SaveCompatMenu`) that:

1. Shows a state-specific diagnostic `HelpBox`, dismissed by A/B/R.
2. Then shows a two-item menu, **Back** (always the default/first cursor
   position) and **Erase All Save Data**.
3. **Back** (or a B-press, which the menu def also treats as Back) calls
   `SetNextGameActionId(GAME_ACTION_5)` -- the exact existing "no save data
   selected" signal `GameControl_SwitchPostSaveMenu()` already uses -- and
   returns to the title/game-control path byte-for-byte, with **no SRAM
   writes performed anywhere on this branch**.
4. **Erase All Save Data** requires an explicit Yes/No confirmation
   submenu (a dedicated menu def, not the shared item-discard
   `gYesNoSelectionMenuDef`, whose "Yes" handler is hardcoded to a
   different, unrelated flow). The authored irreversible-erase warning
   (`MSG_SAVE_COMPAT_ERASE_CONFIRM`, "Erase all save data? This cannot be
   undone.") is rendered in its own `HelpBox` alongside the Yes/No submenu
   (same `StartHelpBoxExt_Unk`/`LoadHelpBoxGfx` pattern used for the
   state-specific diagnostic), closed unconditionally on either outcome.
   Choosing **No** (or B) returns to the Back/Erase list; nothing is
   written. Only choosing **Yes** calls `InitGlobalSaveInfodata()` -- the
   same format-independent whole-chip wipe/current initializer
   `EraseSramDataIfInvalid()` already uses for genuinely blank SRAM --
   which always reclassifies as `SAVE_COMPAT_CURRENT`, and then re-invokes
   `StartSaveMenu()`, which now falls straight through into the normal
   save menu. No per-slot erase and no in-game migration are offered
   anywhere in this proc (both are explicitly out of scope; see
   "Limitations").

### State-specific diagnostic messages

Each non-`SAVE_COMPAT_CURRENT`, non-`SAVE_COMPAT_EMPTY` state gets its own
generated message constant (`texts/texts.txt` -> `include/constants/msg.h`
via the existing text-generation pipeline; no hardcoded numeric IDs):

| `SaveCompatState` | Message |
| --- | --- |
| `SAVE_COMPAT_VALID_LEGACY_OR_VANILLA` | `MSG_SAVE_COMPAT_LEGACY` |
| `SAVE_COMPAT_HEADER_CORRUPT` | `MSG_SAVE_COMPAT_HEADER_CORRUPT` |
| `SAVE_COMPAT_METADATA_CORRUPT` | `MSG_SAVE_COMPAT_METADATA_CORRUPT` |
| `SAVE_COMPAT_MIGRATABLE_OLDER` | `MSG_SAVE_COMPAT_OLDER` |
| `SAVE_COMPAT_NEWER_UNSUPPORTED` | `MSG_SAVE_COMPAT_NEWER` |
| `SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE` | `MSG_SAVE_COMPAT_CONFIG_INCOMPATIBLE` |
| (defensive fallback only; never reachable in practice) | `MSG_SAVE_COMPAT_UNKNOWN` |

The modern build now draws the **Back** and **Erase All Save Data** rows from
issue #18's expansion catalog (`EXP_MSG_FRAMEWORK_BACK` and
`EXP_MSG_SAVE_COMPAT_MENU_ERASE_ALL`). The state diagnostics and irreversible-
erase confirmation remain the existing vanilla-message-table constants above;
they are not silently claimed as localized. `qps-ploc` is a QA transform, not
a translation -- see [`localization.md`](localization.md).

### Read-only diagnostic probe

`include/save_compat_menu.h` exposes two `EWRAM_DATA` bytes for
deterministic runtime tests, without changing any persisted SRAM layout:

* `gSaveCompatMenuActive` -- nonzero for exactly as long as the
  compatibility proc is blocking the normal save menu.
* `gSaveCompatMenuLastState` -- the `SaveCompatState` that most recently
  triggered (or would have triggered) the proc; retained after the proc
  ends so a test can observe which state was diagnosed.

EWRAM budget: 2 bytes total, in line with existing per-slice diagnostic
globals (e.g. `gBoolSramWorking`). Both are zero-initialized because
`ewram_data` is a `NOLOAD` linker section (`ldscript.txt`) -- no
EWRAM_DATA global's non-zero compile-time initializer is ever actually
applied, on real hardware or under emulation. `gSaveCompatMenuLastState`
therefore reads `0` (`== SAVE_COMPAT_EMPTY`) before the gate has ever run;
callers/tests must only trust it once `gSaveCompatMenuActive` has been
observed nonzero at least once.

### Generated-fixture / runtime-test policy

No binary SRAM fixture, ROM, savestate, or fingerprint containing
copyrighted payload is ever committed. Instead:

* **`tools/gba-playtest/tests/sram_fixture.py`** generates synthetic,
  exact 0x8000-byte SRAM images for every `SaveCompatState` (plus a
  `migrate_fixture()` helper that shells out to the real
  `save_format_tool.py migrate` CLI) purely from Slice 1's own format
  implementation/contracts -- never duplicated magic numbers -- and always
  into an ignored build/temp directory, generated fresh at test/build
  time.
* **`tools/gba-playtest/gba_playtest.py`**/**`backend.c`** support an
  optional `--sram-image` (exact 0x8000 bytes, validated) loaded before
  frame 0 via the real, installed mGBA `mCoreLoadSaveFile(..., temporary=true)`
  API (a one-time in-memory copy -- `temporary=false` would instead treat
  the fixture file as a live backing store that all SRAM writes flush
  back to, silently corrupting it across runs), plus SRAM bus probes
  bounds-checked to `0x0E000000..0x0E007FFF`.
* **Committed scenarios** (`tools/gba-playtest/scenarios/savecompat-*.json`)
  and **committed fingerprints**
  (`tools/gba-playtest/fingerprints/savecompat-*-{legacy,modern-debug,modern-release}.json`)
  contain only small textual hashes (`framebuffer_hash`/`sram_hash`), never
  raw framebuffer or SRAM payloads, matching this repository's existing
  `boot.json`/`title-progression.json` convention. Framebuffer/SRAM symbol
  addresses are **not** stable across build configs/toolchains (confirmed:
  `gSaveCompatMenuActive`/`gSaveCompatMenuLastState` sit at different EWRAM
  addresses in the legacy, modern-debug, and modern-release builds), so
  committed scenarios never probe raw EWRAM addresses -- only
  hash-verified framebuffer/SRAM state, which is portable.
* **`tools/gba-playtest/run_save_compat_checks.py`** orchestrates: (1)
  fixture generation, (2) the host migration check (a v0 vanilla fixture
  migrated via the real CLI, proving `SAVE_COMPAT_CURRENT`), and (3) the
  committed scenarios against a given ROM (legacy or modern AAPCS
  debug/release, identically -- no ABI scoping), `verify --policy
  behavior` matched against the fingerprint for that ROM's config,
  covering all eight `SaveCompatState` values plus confirmed erase and the
  migrated-v1 load. Every failure names the exact fixture/state/checkpoint
  that failed.
* **`tools/gba-playtest/tests/test_save_compat_scenarios.py`** proves the
  same coverage as a `python3 -m unittest`-discoverable host test, run
  independently against all three supported ROMs (legacy, modern-debug,
  modern-release -- one `TestCase` subclass per ROM, generated
  programmatically); each ROM's coverage skips cleanly (never a false
  pass) if that particular ROM has not been built, or if libmGBA is
  unavailable.

### SRAM hash policy: exact vs. normalized

`tools/gba-playtest/gba_playtest.py`/`backend.c` support two SRAM-hash
algorithms for a checkpoint's `sram_hash`, distinguished by the algorithm
name embedded in the hash text itself (never ambiguous downstream):

* **`fnv1a64-sram:<hex>`** -- the exact, whole-0x8000-byte FNV-1a hash.
  This is the **default** (no `sram_hash_exclude_ranges` declared) and is
  **mandatory** for any checkpoint that must prove SRAM was preserved
  byte-for-byte, e.g. every checkpoint in `savecompat-dialog-back.json`
  (dismissing the compatibility dialog and selecting **Back** must be
  fully non-destructive -- see "Runtime scenarios" below). Nothing may
  ever declare `sram_hash_exclude_ranges` on a Back/non-destructive
  checkpoint.
* **`fnv1a64-sram-normalized:<hex>`** -- the same FNV-1a construction with
  a checkpoint-declared, ordered, non-overlapping set of byte ranges
  skipped entirely (never substituted/zeroed -- just excluded from the
  running hash). A checkpoint opts in via the scenario schema's
  `sram_hash_exclude_ranges` field (a non-empty array of `{"offset",
  "length"}` objects, each within `[0, 0x8000)`, strictly ordered and
  non-overlapping, capped at 64 ranges per checkpoint to match
  `backend.c`'s plan-format limit). This exists only for ROM-generated
  `SAVE_COMPAT_CURRENT` checkpoints (`savecompat-current.json`'s
  no-dialog checkpoint, `savecompat-erase.json`'s post-erase checkpoints,
  and the migrated-v1-load reuse of `savecompat-current.json`) whose SRAM
  legitimately contains intentionally build-variable diagnostic bytes:
  `ExpansionSaveMeta.configFingerprint` (17 bytes, absolute SRAM offset
  29620 / `0x73B4`), `ExpansionSaveMeta.buildCommitShort` (9 bytes,
  absolute SRAM offset 29640 / `0x73C8`) and its dependent metadata
  `checksum` (2 bytes, absolute SRAM offset 29650 / `0x73D2`) -- see
  "`struct ExpansionSaveMeta` layout" above. The three ordered,
  non-overlapping ranges are `{29620, 17}`, `{29640, 9}`, `{29650, 2}`.
  Without normalization, a committed fingerprint for one of these
  checkpoints would break on every legitimate follow-up commit
  (`buildCommitShort` embeds this build's live `FE8_EXPANSION_BUILD_COMMIT`,
  and the checksum's domain covers it) or on any config-schema change
  (`configFingerprint`; see below).

**Why `configFingerprint` is excluded (issue #6 sprint-1 remediation).**
`configFingerprint` is a purely diagnostic field: it records which
compatibility-relevant config settings
(`scripts/modernize/expansion_config.py`'s `fingerprint_fields()`) a build
was compiled with, but it **never** gates classification (see
"Compatibility vs. diagnostic fields" above) and, critically, config
feature flags change runtime **behaviour/identity without changing the
save layout or `compatEpoch`**. An earlier revision deliberately left it
*in* the normalized hash on the assumption it "does not vary per-commit".
Issue #6 disproved that: adding a config feature flag -- even one
defaulting to OFF -- changes the config-schema fingerprint (which is also
preset-derived, so debug and release already differ: `2295d6fc2407d1be`
vs `89415b300f350ce6`). That drifted the "same persisted save" normalized
hash and produced a false gate failure with **zero** change to the actual
save bytes. Because a behaviour-comparison fingerprint asks "is this the
same *persisted save*", not "was this the same *build config*",
`configFingerprint` is now normalized out alongside
`buildCommitShort`/`checksum`; doing so converges the debug and release
normalized hashes onto a single build-independent value (proven in
`tools/gba-playtest/tests/test_sram_hash_normalization.py`). This does not
weaken the oracle: exact ROM identity is still verified by the fingerprint
`rom` provenance/ROM fields, and savecompat semantics are still proven by
the classifier probes, the `SaveCompatState`, and every other SRAM byte.
`magic`, `formatVersion`, and `compatEpoch` (the three fields that
actually gate compatibility) and `frameworkVersionPacked` are **never**
excluded; a normalized hash must still change if any of those, or any
save-payload byte, is corrupted -- exactly as the exact hash does, and as
that test suite asserts.

**Excluding the checksum bytes from the hash does not weaken corruption
detection.** `save_format_tool.py`'s `classify_image()` independently
recomputes and compares `ExpansionSaveMeta.checksum` against the
metadata's own `[0x00, 0x2E)` domain on every load, regardless of which
SRAM-hash algorithm a playtest checkpoint happens to use --
`SAVE_COMPAT_METADATA_CORRUPT` is still raised the same way either way.
The hash and the classifier are two independent proofs: the hash proves
"this checkpoint's persisted image is the one we expect, modulo declared
build-variable bytes"; the classifier proves "this image's metadata is
internally self-consistent". Excluding the checksum's storage bytes from
the first proof has no effect on the second.

**Mechanics.** The scenario parser (`gba_playtest.py`'s
`parse_scenario_data()`) validates `sram_hash_exclude_ranges` at parse
time -- requires `sram_hash: true`, rejects a missing/empty/non-list
value, validates each range's `offset`/`length` as in-bounds integers
that don't overshoot the 0x8000-byte image, rejects overlapping or
out-of-order ranges, and rejects more than 64 ranges for a single
checkpoint (matching `backend.c`'s `read_plan()` limit, so a scenario
that would be silently truncated or rejected by the backend is instead
rejected immediately with a clear `PlaytestError` naming the checkpoint
and the 64-range limit) -- before any plan file is generated. The ranges
are then carried through the generated plan file: plan format version 2
adds a per-checkpoint exclude-range count and `offset length` pair list
(before that checkpoint's probe list) that `backend.c`'s `read_plan()`
parses into `struct ByteRange`; `hash_sram()` skips those bytes via
`offset_excluded()` while hashing, and `run()` selects the
`fnv1a64-sram-normalized:` vs. `fnv1a64-sram:` algorithm name purely from
whether the checkpoint declared any exclude ranges. A malformed plan
(oversized exclude-range count, truncated range list, or an
out-of-bounds/zero-length range) is a `read_plan()` parse failure
(`goto fail`), diagnosed the same way as any other malformed plan file
-- never a silent truncation or a hash computed over the wrong bytes.

**This is not a general stability escape hatch.** `sram_hash_exclude_ranges`
exists to encode exactly two currently-known, narrowly-scoped,
intentionally build-variable byte ranges -- it must never be used to
paper over a genuinely non-deterministic or flaky checkpoint (that is a
scenario-design bug to fix at its source, not something to hide behind
an exclusion), and every exclusion must be justified in the scenario's
`description` (as `savecompat-current.json`/`savecompat-erase.json` do)
by naming the specific field and why it is legitimately variable. Adding
a new exclusion range anywhere requires the same justification and, per
`tools/gba-playtest/tests/test_sram_hash_normalization.py`, host-only test
coverage proving the normalized hash stays invariant to that field alone
while remaining sensitive to every other byte in the image.

### Runtime scenarios

| Scenario | Proves |
| --- | --- |
| `savecompat-current.json` | `SAVE_COMPAT_CURRENT` (or auto-repaired `SAVE_COMPAT_EMPTY`): no compatibility dialog appears; the normal save menu is reached directly. Also reused for the migrated-v1-load proof (a host-migrated v0->v1 image classifies `CURRENT` and loads through the normal path). |
| `savecompat-dialog-back.json` | For a given non-CURRENT state: the dialog appears with a state-specific message, dismissing it and selecting **Back** leaves the game on the title/game-control path, and SRAM is byte-for-byte unchanged across all three checkpoints (dialog-shown / after-dismiss / back-returned). |
| `savecompat-erase.json` | Selecting **Erase All Save Data** shows the irreversible-erase warning alongside the Yes/No submenu; confirming **Yes** wipes SRAM to a fresh, valid `SAVE_COMPAT_CURRENT` image, and the normal save menu becomes reachable afterward. |
| `savesuspend-resume-modern-debug.json` (debug-only) | A genuine ordinary-UI manual **Suspend** (Map Menu) -> real **soft-reset** combo -> **Resume** (Save Menu) round trip, from a clean boot via #11 Slice 1's debug-only Chapter 2 launcher: proves the manual save is a distinct write from the automatic auto-save, SRAM changed and remains valid CURRENT-format, and the restored live game state matches the manually-saved one exactly. See "Save/load acceptance status" below. |
| `save-load.json` (debug-only, issue #13) | A NORMAL (non-Suspend) game-save write + load, distinct from the Suspend round trip above: SaveMenu New Game -> slot 0 write, a real A+B+SELECT+START soft reset, then the top-level SaveMenu **RESTART** item -> `PostSaveMenuHandler` -> `ReadGameSave` of slot 0 (`src/savemenu.c`; RESTART is `main_sel_bitfile & 0x82`). Proven by `playthroughIdentifier` (`0x020210bc`)/`chapterModeIndex` (`0x020210bf`) going `1 -> 0 -> 1` (created / soft-reset-cleared / loaded), `gameSaveSlot` (`0x020210b0`) `== 0`, and differing before/after whole-SRAM hashes. See "Save/load acceptance status" below. |

Committed fingerprints exist per-scenario/state for all three supported
ROMs -- `-legacy`, `-modern-debug`, and `-modern-release` -- covering all
eight `SaveCompatState` values (the `CURRENT`/`EMPTY` and six non-CURRENT
dialog states), confirmed erase, and the migrated-v1 load: 27 fingerprint
files under `tools/gba-playtest/fingerprints/`, plus one dedicated
`savesuspend-resume-modern-debug.json` fingerprint (debug-only, no
`-legacy`/`-modern-release` counterpart since the launcher it depends on
is debug-only).

### Save/load acceptance status (requirement 8)

`savecompat-current.json`'s `no-dialog-normal-savemenu` checkpoint (and
its migrated-v1-load reuse) is this slice's deterministic proof that a
generated `SAVE_COMPAT_CURRENT` save -- whether freshly erased, or
host-migrated from a v0 vanilla/legacy image -- **is loaded into the
intended game/save-menu state**: the checkpoint asserts both a
`framebuffer_hash` (the normal save-menu screen is actually reached, not
merely inferred) and a `sram_hash` (a stable, checkpointed runtime
state, not input-playback-only evidence). This is verified against all
three supported ROMs (legacy, modern-debug, modern-release).

A full **write -> reset -> reload/read** scenario is now implemented:
`savesuspend-resume-modern-debug.json` (`tools/gba-playtest/scenarios/`)
drives, from a clean boot, a genuine ordinary-UI manual **Suspend** ->
**soft-reset** -> **Resume** round trip and checkpoints that the restored
live game state matches exactly what was manually saved -- closing the
acceptance gap the previous revision of this section reported.

The scenario reuses #11 Slice 1's debug-only "Fast Boot: Chapter 2" title
hotkey/launcher (see `docs/debugtools.md`) to reach a fixed, deterministic
Chapter 2 map state from a clean boot -- this is the general clean-boot
game-state launcher this slice previously lacked, now available and
depended upon exactly as intended, without this slice re-implementing any
part of it. Because that launcher is debug-only (absent from release
builds by design; see `docs/debugtools.md`), this scenario is likewise
debug-only: `tools/gba-playtest/run_save_compat_checks.py` only runs it
for `MODERN_CONFIG=debug`, and release's `SaveCompatState`/migrated-load
coverage above is completely unaffected and unchanged.

After reaching the interactive map, the scenario replays only ordinary
input -- cursor movement and `A`/`DOWN` taps -- to open the real Map Menu
and select **Suspend** -> **Yes**, which calls the same `WriteSuspendSave()`
the in-game Player Phase's own automatic auto-save calls; no test hook or
direct C call was added. Two facts distinguish this from a no-op replay of
that automatic auto-save:

- `WriteSuspendSave()`'s alternating-slot mechanism
  (`GetNextSuspendSaveId()`/`WriteSwappedSuspendSaveId()` in
  `src/bmsave.c`) writes the manual Suspend to a **different**
  `SaveBlockInfo` slot (`SAVE_ID_SUSPEND_ALT`) than the automatic
  Player-Phase-start auto-save (`SAVE_ID_SUSPEND`), which the scenario's
  `suspend-confirmed` checkpoint probes directly (both slots' magic/kind
  bytes, proving both are valid CURRENT-format `SaveBlockInfo` records).
- Each slot's own stored cursor-position bytes differ: the automatic
  auto-save's stored cursor reflects wherever the cursor was at
  Player-Phase start, while the manual Suspend's stored cursor exactly
  matches the live cursor position at the moment Suspend was confirmed --
  proof the manual write is the newer, distinct one.

The same checkpoint also asserts the debug-only suppression probe
(`gDebugToolsProbe.bootstrapSuppressionActive`) reads `0` and that the
checkpoint's `sram_hash` differs from the initial synthetic fixture's own
hash (proven by `tests/test_savesuspend_resume_scenario.py`'s runtime
test, using the same byte-exact FNV-1a mirror the hash-normalization
tests use) -- i.e. SRAM demonstrably changed as a result of the manual
save, and remains valid CURRENT-format immediately afterward.

The scenario then replays the real **A+B+SELECT+START** soft-reset combo
(held long enough for `SoftResetIfKeyComboPressed()` to observe it),
confirms genuine reboot via the boot logo, and replays the same ordinary
cold-boot title tap cadence `savecompat-current.json` already uses. With a
valid Suspend save present, this ordinary cadence alone navigates
title -> save menu -> **Resume** automatically and calls the real
`ReadSuspendSave()` path (`src/savemenu.c`'s existing
`main_sel_bitfile & 1` UI branch -- not a test hook); no scripted "select
Resume" input was needed or added. `IsValidSuspendSave()`/`ReadSuspendSave()`
read the most-recently-written slot first
(`GetLastSuspendSaveId()`/`GetNextSuspendSaveId()`), so Resume naturally
restores the newer manual save, not the earlier automatic one.

The final `resumed-chapter2` checkpoint proves the restored state reached
the intended condition via stable, symbol-derived probes (not raw
framebuffer similarity or input-playback alone): `gPlaySt.chapterIndex`,
`gPlaySt.faction`, `gPlaySt.xCursor`/`yCursor` (matching the manually
saved cursor position, not the automatic auto-save's), a unit item probe
(`gUnitArrayBlue[1]`'s Rapier), and both `SaveBlockInfo` slots' magic/kind
bytes (CURRENT-format validity persists post-resume).

**Issue #2 acceptance is now complete.** Every previously-deferred proof
point -- format, migration, the global compatibility gate/UI, all-state
coverage, and this deterministic write -> reset -> reload scenario -- is
implemented and verified against a real, ordinary UI path.

Separately, a NORMAL (non-Suspend) game-save write-and-load is now also
proven by `save-load.json` (issue #13, `tools/gba-playtest/scenarios/`;
host test `tools/gba-playtest/tests/test_save_load_scenario.py`; gate
`expansion-modern-saveload-check`, debug-only because its soft-reset timing
is debug-calibrated). It exercises the top-level SaveMenu **RESTART** item
-> `PostSaveMenuHandler` -> `ReadGameSave` of slot 0 (`src/savemenu.c`;
RESTART is `main_sel_bitfile & 0x82`) -- a different code path from both
Suspend/`ReadSuspendSave()` and the initial New-Game write, with its own
`playthroughIdentifier`/`chapterModeIndex` `1 -> 0 -> 1` discriminants and a
before/after whole-SRAM hash difference (write proof). FE7/8's own
post-chapter-clear "Would you like to save?" flow (`StartSaveMenuPostChapter`)
is still `asm/`-only in this codebase; it is a distinct, separate path and
is **not required** for normal save/load coverage, which is now proven the
legitimate way above via SaveMenu RESTART -> `ReadGameSave`.

### Host migration workflow (recap)

The host `save_format_tool.py migrate <source> <dest>` CLI supports v0
(`SAVE_COMPAT_VALID_LEGACY_OR_VANILLA`) -> current, older-format
(`SAVE_COMPAT_MIGRATABLE_OLDER`) -> current, and current -> current. The real
issue #18 version-1/epoch-1 input exercises the older-format path; its reserved
bytes are carried forward rather than replaced. The compatibility proc itself
never performs or offers in-console migration
(see "Limitations"); a player whose save is `SAVE_COMPAT_MIGRATABLE_OLDER`
sees `MSG_SAVE_COMPAT_OLDER` (which explains that an external tool is
required) and their only in-console options are Back or a full erase.

> **Documentation correction (supersedes wording in commit `795d2abdb22e6ad80e1c4f0eea04534263e5348f`'s own message, which is left verbatim/unedited per policy):** that commit's message describes a pre-sprint-2 save as classifying `SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE`. That was inaccurate against the actual, unchanged classifier precedence (magic -> `formatVersion` -> `compatEpoch`, documented in "Raw-byte compatibility classifier" above and unchanged by that commit): the row below is this document's corrected, authoritative account -- such a save classifies `SAVE_COMPAT_MIGRATABLE_OLDER`, because `formatVersion` alone already resolves the classification before `compatEpoch` is ever checked.
>
### Format / compatibility bump table

| What changed | Bump | Player-visible effect on an old save |
| --- | --- | --- |
| Any `FE8_EXPANSION_*` build/title/debug/ROM-size-only setting | neither `SAVE_FORMAT_VERSION_CURRENT` nor `EXPANSION_SAVE_COMPAT_EPOCH` | none -- these never gate compatibility |
| A save-layout/serialization-compatible addition (e.g. a new optional field with a documented default) | `SAVE_FORMAT_VERSION_CURRENT` (metadata `formatVersion`) | old saves classify `SAVE_COMPAT_MIGRATABLE_OLDER` -> `MSG_SAVE_COMPAT_OLDER`; a newer save loaded on an older build classifies `SAVE_COMPAT_NEWER_UNSUPPORTED` -> `MSG_SAVE_COMPAT_NEWER` |
| A save-layout/serialization-incompatible change (reordered/resized/reinterpreted fields, changed checksum domain, changed packing) | `EXPANSION_SAVE_COMPAT_EPOCH` (`config.mk`) | saves built under the old epoch classify `SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE` -> `MSG_SAVE_COMPAT_CONFIG_INCOMPATIBLE` |
| Concrete instance: issue #18 sprint 2 stamped `struct ExpansionUserPrefs` into the previously-always-zero `reserved` tail and started reading it at boot -- an on-media semantic change to what a "current" save's bytes mean, even though `ExpansionSaveMeta`'s own `0x00`-`0x2E` checksum domain/fields are untouched | `SAVE_FORMAT_VERSION_CURRENT` `1`->`2` **and** `EXPANSION_SAVE_COMPAT_EPOCH` `1`->`2` (both bumped together, out of caution -- a v1 save's `reserved` tail was always zero-filled so it is also valid `EXPANSION_USER_PREFS_UNSET` input; the epoch bump adds no *further* observable classification change on its own here, since `ClassifySaveCompatRaw()`'s `formatVersion` check already fires first and settles the classification below -- it is carried anyway so a future config-only, format-unchanged epoch bump on top of this one stays auditable rather than silent, per this table's own `EXPANSION_SAVE_COMPAT_EPOCH`-only row above) | a genuine pre-sprint-2 save (`formatVersion` `1`, `compatEpoch` `1`) classifies `SAVE_COMPAT_MIGRATABLE_OLDER` -> `MSG_SAVE_COMPAT_OLDER` -- **not** `SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE` -- because `ClassifySaveCompatRaw()`'s fixed precedence (magic -> `formatVersion` -> `compatEpoch`; see "Raw-byte compatibility classifier" above) checks `formatVersion` strictly *before* `compatEpoch`, and `formatVersion` `1` `<` current `2` alone already resolves the classification; this save's stale `compatEpoch` `1` is never even reached/evaluated. (`SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE` only ever applies to a save already *at* the current `formatVersion` whose `compatEpoch` alone is stale -- not this slice's case, since the format bump always takes precedence.) Either way it must go through the host `migrate <source> <dest>` CLI (host/runtime migration is out-of-place and non-destructive -- it never wipes/erases the source, and preserves any bytes already in `reserved`, so a hypothetical already-populated future field would survive; today's v1 saves have nothing there to preserve) to reach `SAVE_COMPAT_CURRENT`; the in-console gate itself never performs or offers this migration (see "Limitations") -- only Back or a full erase |
| Corrupted `GlobalSaveInfo` header | (detected, not a bump) | `SAVE_COMPAT_HEADER_CORRUPT` -> `MSG_SAVE_COMPAT_HEADER_CORRUPT` |
| Corrupted `ExpansionSaveMeta` (bad checksum) | (detected, not a bump) | `SAVE_COMPAT_METADATA_CORRUPT` -> `MSG_SAVE_COMPAT_METADATA_CORRUPT` |
| No metadata record at all (true vanilla, or pre-slice-1 expansion save) | (detected, not a bump) | `SAVE_COMPAT_VALID_LEGACY_OR_VANILLA` -> `MSG_SAVE_COMPAT_LEGACY` |

## Limitations

* **No automatic in-console structural migration.** The host-only
  `migrate` command can stamp v0 metadata and refresh the supported additive
  version-1 metadata to current while preserving its reserved tail. The console
  itself cannot transform an older current-format save safely: a general
  structural migration would need to reinterpret and rewrite live save-block structs
  in place, and **no safe scratch SRAM block exists today** to do that
  atomically -- a partial in-place rewrite that is interrupted (power
  loss, reset) could corrupt the save beyond what any classifier can
  detect. Building that requires a future SRAM transaction/storage
  redesign, explicitly out of scope for this slice.
* **In-console incompatible-data recovery is diagnose-and-erase only, by
  design.** Slice 2's compatibility proc (`src/save_compat_menu.c`) shows a
  state-specific diagnostic and offers only **Back** or a fully-confirmed
  **Erase All Save Data** -- it never offers per-slot erase and never
  performs or offers in-game migration, for the same "no safe scratch SRAM
  block exists today" reason as the bullet above. A player whose save is
  `SAVE_COMPAT_MIGRATABLE_OLDER` must use the host-side `migrate` CLI (or
  wait for a future in-console migration built on a real SRAM transaction
  design) -- the in-console UI cannot safely do this for them yet.

## Cross-compiler persisted-struct-layout compatibility

Every persisted save struct (the full `struct SaveBlocks` chain, reachable
from `gameSaveBlocks`/`suspendSaveBlocks`/`multiArenaSaveBlock`) is proven
byte-for-byte identical -- every nested struct's `sizeof` and every direct
member's `offsetof` -- across legacy `agbcc` (APCS) **and** all four
modern cross-toolchain build cells (`debug`/`release` x `aapcs`/
`apcs-gnu`), by `scripts/modernize/tests/test_save_format_layout.py`'s
`test_layout_in_all_modern_cells`. Two distinct root causes were found and
fixed to make this true (both are general lessons for any future
persisted struct, not just the two structs below):

1. **Bitfield storage-unit packing (`struct Dungeon`,
   `include/bmdifficulty.h`).** Legacy `agbcc`'s old-APCS bitfield
   allocator packs bits contiguously across a `u32` storage-unit boundary;
   AAPCS-conformant modern GCC refuses to let a bitfield straddle a
   storage unit sized to its declared type, so declaring 10 `u32`
   bitfields without `BITPACKED` produced 12 bytes under `agbcc` but 16
   bytes under modern AAPCS. Fix: add `BITPACKED` (`include/prelude.h`;
   `aligned(4), packed`), matching the existing convention already used on
   `PlaySt`/`PlaySt_30`/`PlaySt_OptionBits`. The `aligned(4)` half of
   `BITPACKED` also preserves ARM7 unaligned-access safety for any
   sub-word field within the packed struct.
2. **Struct-size rounding (`struct BonusClaimSaveData`,
   `include/bmsave.h`).** Legacy `agbcc` **always rounds every struct's
   total size up to a 4-byte multiple**, regardless of member alignment
   -- a general, previously-undocumented old-ARM-APCS convention (verified
   with a minimal repro: `struct { char a, b, c; }` is `sizeof==4` under
   `agbcc` but `sizeof==3` under modern GCC). Modern AAPCS GCC only rounds
   a struct's size to its own natural (max-member) alignment; a struct
   whose unpadded size already happens to be a multiple of that alignment
   (as `BonusClaimSaveData`'s 0x142/322-byte natural size is, being a
   multiple of its own 2-byte `u16` alignment) is left un-rounded, unlike
   `agbcc`'s 0x144. Fix: add `ALIGN(4)` (`include/prelude.h`;
   `aligned(4)`), matching the existing precedent already used for this
   exact reason on `struct GMapSaveInfo` (`include/bmsave.h`).

**General rule for any future persisted struct:** if its *unpadded* size
(summing member sizes plus only alignment-driven internal gaps) is not
already a multiple of 4 bytes, it will diverge between legacy `agbcc`
(always rounds to 4) and modern AAPCS GCC (rounds only to its own natural
alignment) -- unless its natural alignment already happens to be 4 (e.g.
it contains a `u32`/pointer member) or `ALIGN(4)`/`BITPACKED` is applied
explicitly. This is a **distinct** failure mode from the bitfield-boundary
issue that `BITPACKED` was originally added for -- `ALIGN(4)` alone (no
`packed`) is the correct minimal fix when there is no bitfield-boundary
issue, since `packed` would also strip any inter-member alignment padding
that may be structurally required.

`test_save_format_layout.py`'s probe asserts `sizeof` for every persisted
nested struct type and `offsetof` for every direct member of the three
largest containers (`GameSaveBlock`, `SuspendSaveBlock`,
`MultiArenaSaveBlock`), plus the full `SaveBlocks`/`ExpansionSaveMeta`
top-level chain -- compiled and run under legacy `agbcc` and all four
modern cells, wired into the repository's standard host test discovery
(`python3 -m unittest discover -s scripts/modernize/tests`).

Because the layout is now provably identical everywhere,
`expansion-modern-savefmt-check` and
`tools/gba-playtest/tests/test_save_compat_scenarios.py` run and verify
**all eight** `SaveCompatState` values, confirmed erase, and the
migrated-v1 load against the real, compiled modern AAPCS ROM (`debug` and
`release`) exactly as they do against legacy `agbcc` -- no ABI scoping,
no legacy-only carve-out.

* The classifier's precedence logic cannot be executed as real embedded
  C in this sandbox (no GBA emulator, and the real include chain is not
  portable to a host-native compiler without heavy stubbing). Its
  structural correctness (struct offsets/sizes/checksum domain) is proven
  by the layout probes above; its actual decision logic is proven by the
  thoroughly-unit-tested Python mirror in
  `scripts/modernize/save_format_tool.py`, which is explicitly documented
  (both here and in its own module docstring) as a mirror that must be
  kept in sync with the C implementation, not a substitute for testing the
  shipped code directly.

## Tests

* `scripts/modernize/tests/test_expansion_config.py` -- `EXPANSION_SAVE_COMPAT_EPOCH`
  parsing/validation/generation, extending the existing issue #8 suite.
* `scripts/modernize/tests/test_save_format_layout.py` -- struct-offset/size
  static assertions (legacy `agbcc`, always runs; modern cross-toolchain,
  all four cells, skips gracefully only if the toolchain itself is
  absent).
* `scripts/modernize/tests/test_save_format_tool.py` -- `Checksum16` mirror,
  blank-region detection, all 8 classifier states and their precedence,
  diagnostic-field independence, CLI `inspect`/`validate`/`migrate` exit
  codes, migration source preservation on failure, and successful
  out-of-place v0 -> v1 migration.
* `tools/gba-playtest/tests/test_save_compat_gate_safety.py` -- static
  proof that `StartSaveMenu()` is the sole gate into `ProcScr_SaveMenu`,
  that `src/save_compat_menu.c` never calls any slot/block/current-struct
  accessor, and that the erase-confirm warning message
  (`MSG_SAVE_COMPAT_ERASE_CONFIRM`) is actually rendered (not dead code)
  strictly before the destructive erase step in script order.
* `tools/gba-playtest/tests/test_sram_fixture.py` -- the synthetic SRAM
  fixture generator itself (every `SaveCompatState`, plus migration).
* `tools/gba-playtest/tests/test_save_compat_scenarios.py` -- all eight
  `SaveCompatState` values, Back-preservation, confirmed erase, and the
  migrated-v1 load, run independently against all three supported ROMs
  (legacy, modern-debug, modern-release); each ROM's coverage skips
  cleanly if that ROM is not built or libmGBA is unavailable.
* `tools/gba-playtest/run_save_compat_checks.py` -- the orchestrator behind
  `expansion-modern-savefmt-check` (`modern.mk`), run against the modern
  AAPCS ROM for both `debug` and `release`; wired into
  `expansion-modern-linker-check` and therefore into CI
  (`.github/workflows/build.yml`).

Run the host suite:

```sh
cd scripts/modernize
python3 -m unittest discover -s tests -p "test_*.py"
```

Run the playtest suite (includes the save-compat gate/scenario tests):

```sh
python3 -m unittest discover -s tools/gba-playtest/tests -p "test_*.py"
```

That is normal mode: the live save-compat scenarios run against whichever
ROMs are present in the worktree (legacy, modern debug, modern release) and
skip explicitly for the ones that are not built. CI runs the same suite with
`GBA_PLAYTEST_HOST_ONLY=1`, which skips those live scenarios by mode instead
of by artifact presence -- their runtime coverage lives in
`make expansion-modern-savefmt-check` / `expansion-modern-linker-check`. See
`tools/gba-playtest/README.md`, “Host-only test mode”.

Run the full modern CI-equivalent check (build + fixtures + host migration
check + runtime scenarios, both debug and release):

```sh
make expansion-modern-savefmt-check MODERN_CONFIG=debug MODERN_ABI=aapcs
make expansion-modern-savefmt-check MODERN_CONFIG=release MODERN_ABI=aapcs
```
