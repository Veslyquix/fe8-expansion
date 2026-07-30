# Framework configuration and ROM identity (issue #8)

This document is the single reference for the expansion framework's
configuration surface: the committed `config.mk` file, the
`MODERN_CONFIG`/`MODERN_ABI`/`MODERN_ROM_SIZE`/`MODERN_TEXT_SHIFT` build
presets, the deterministic per-build metadata generated under `build/`,
the embedded `ExpansionMetadata` record in every modern ROM, and exactly
which settings are compatibility-relevant (fold into the config
fingerprint) and why. It only covers the **modern** (GCC-based) build
path; the legacy agbcc build is unaffected and keeps its hardcoded
defaults (see "Legacy build path" below).

## Settings reference

### `config.mk` (root, committed)

| Setting | Constraint | Default | Affects |
| --- | --- | --- | --- |
| `EXPANSION_VERSION_MAJOR` | integer, `[0, 255]` | `0` | framework version (fingerprint) |
| `EXPANSION_VERSION_MINOR` | integer, `[0, 255]` | `1` | framework version (fingerprint) |
| `EXPANSION_VERSION_PATCH` | integer, `[0, 255]` | `0` | framework version (fingerprint) |
| `EXPANSION_ROM_TITLE` | up to 12 printable-ASCII bytes | `FIREEMBLEM2E` | ROM header, embedded metadata (fingerprint) |
| `EXPANSION_ROM_GAME_CODE` | exactly 4 printable-ASCII bytes | `BE8E` | ROM header, embedded metadata (fingerprint) |
| `EXPANSION_ROM_MAKER_CODE` | exactly 2 printable-ASCII bytes | `01` | ROM header, embedded metadata (fingerprint) |
| `EXPANSION_ROM_REVISION` | integer, `[0, 255]` | `0` | ROM header "software version" byte (fingerprint) |
| `EXPANSION_BUILD_ID` | empty, or 4-40 hex characters | empty | embedded build commit override |
| `EXPANSION_SAVE_COMPAT_EPOCH` | integer, `[0, 65535]` | `1` | save-format compatibility gate (see `docs/save_format.md`); **not** part of the fingerprint above |
| `EXPANSION_ENABLED_LOCALES` | comma-separated subset of the stable `ExpansionLocaleId` list (`scripts/localization/schema.py`); must include `en` | `en` | issue #18 localization (fingerprint) -- which locales this ROM ships/enables at runtime |
| `EXPANSION_DEFAULT_LOCALE` | must be a member of `EXPANSION_ENABLED_LOCALES` | `en` | issue #18 localization (fingerprint) -- the locale `src/expansion_locale.c`'s runtime resolver starts in |
| `EXPANSION_PSEUDO_LOCALE` | `0` or `1`; must be `1` if and only if `qps-ploc` is in `EXPANSION_ENABLED_LOCALES` | `0` | issue #18 localization (fingerprint) -- enables the deterministic ASCII pseudo-locale test harness (`scripts/localization/pseudo.py`), never a real translation |
| `EXPANSION_MECHANICS_HOOKS` | `0` or `1` | `0` | issue #6 starter feature (fingerprint) -- link the public battle-stat mechanics hook registry |
| `EXPANSION_MECHANICS_SAMPLE` | `0` or `1` | `0` | issue #6 starter feature (fingerprint) -- register the content-free sample mechanic; requires `EXPANSION_MECHANICS_HOOKS=1` |
| `EXPANSION_DANGER_OVERLAY_MENU` | `0` or `1` | `0` | issue #6 starter feature (fingerprint) -- expose the player danger/range overlay map-menu surface |
| `EXPANSION_STARTER_CONTENT` | `0` or `1` | `0` | issue #6 starter feature (fingerprint) -- link the bundled generated-data content example; requires `EXPANSION_MECHANICS_HOOKS=1` **and** an item ID cap reaching `ITEM_EXPANSION_CE` (`FE8_ITEM_ID_CAP=0xCE` or higher) |

Every value has a `?=` default, so overriding on the `make` command line
(e.g. `make expansion-modern-rom EXPANSION_ROM_TITLE=MYHACK`) or via the
environment changes the built ROM's identity without editing the file.
`config.mk` deliberately does **not** duplicate `MODERN_CONFIG`,
`MODERN_ABI`, `MODERN_ROM_SIZE`, or `MODERN_TEXT_SHIFT` -- those remain
owned by `modern.mk`, which already had working presets for them before
issue #8; `config.mk` only owns the values that had no committed home
before this issue (semantic version, ROM identity, and the build-id
override).

### `modern.mk` build presets

| Variable | Supported values | Default | Affects |
| --- | --- | --- | --- |
| `MODERN_CONFIG` | `debug`, `release` | `debug` | optimization/debug info, `NDEBUG`, `FE8_EXPANSION_DEBUG`/`_ASSERTIONS_ENABLED`/`_LOGGING_ENABLED` (fingerprint) |
| `MODERN_ABI` | `aapcs`, `apcs-gnu` | `aapcs` | calling convention / struct layout (fingerprint) |
| `MODERN_ROM_SIZE` | `16M`, `32M`, or an exact byte count equal to one of those | `16M` | output ROM size / padding (fingerprint) |
| `MODERN_TEXT_SHIFT` | non-negative integer, 4-byte aligned | `0` | link-time padding before `.text` (fingerprint) |

`MODERN_CONFIG=debug` compiles with `-Og -g3` and no `-DNDEBUG`, enabling
`FE8_EXPANSION_DEBUG`/`FE8_EXPANSION_ASSERTIONS_ENABLED`/
`FE8_EXPANSION_LOGGING_ENABLED` (see "C configuration header" below).
`MODERN_CONFIG=release` compiles with `-O2 -g0 -DNDEBUG`, disabling all
three by default -- this preserves the pre-existing `NDEBUG` convention
already used by `include/gba/isagbprint.h`'s `AGB_ASSERT`/`AGB_WARNING`
macros; subsystems added later should gate development-only code on
`FE8_EXPANSION_DEBUG` rather than re-deriving it from `NDEBUG` themselves.

## Build-ID resolution (deterministic, no timestamps/branch names)

The embedded build commit is resolved with this precedence, entirely in
`scripts/modernize/expansion_config.py`'s `resolve_build_commit()`:

1. **Explicit override** -- `EXPANSION_BUILD_ID` in `config.mk`, or a
   `make ... EXPANSION_BUILD_ID=...`/environment override. Must be 4-40
   hex characters (a git commit SHA or a SHA prefix); this is enforced by
   `validate_build_id_override()`, which rejects anything else (including
   timestamps and branch names) with an actionable error.
2. **`git rev-parse HEAD`**, run with `cwd` set to the repository root.
   This resolves identically for a normal branch checkout and a detached
   HEAD (e.g. a CI checkout of a tag or PR merge commit), so no special
   detached-HEAD handling is needed.
3. **`"unknown"` sentinel** -- used when git is unavailable, the checkout
   has no `.git` directory (a downloaded source archive/tarball), or `git
   rev-parse` otherwise fails. This is the only fallback; the build never
   substitutes a timestamp, branch name, or host path.

## Deterministic per-build metadata

Every modern build resolves and validates the full identity, then
generates:

```
build/expansion-modern/<MODERN_CONFIG>/<MODERN_ABI>/generated/expansion_build_metadata.json
build/expansion-modern/<MODERN_CONFIG>/<MODERN_ABI>/generated/expansion_build_metadata.mk
```

Both are **generated build outputs**, never committed source -- they live
entirely under `build/`, are regenerated by
`scripts/modernize/expansion_config.py generate`, and are only rewritten
when their content actually changes (so an unrelated rebuild does not
touch their mtimes). The `.json` file is the canonical machine-readable
record (also consumed by `finalize_rom_header.py` and
`verify_rom_header.py`); the `.mk` file feeds `MODERN_BUILD_COMMIT`,
`MODERN_CONFIG_FINGERPRINT`, `MODERN_VERSION_PACKED`, and
`MODERN_VERSION_STRING` back into `modern.mk` for use in `MODERN_CFLAGS`
`-D` defines.

## The config identity fingerprint

`compute_fingerprint()` produces the first 16 hex characters of a
SHA-256 digest over a canonical (sorted-key, fixed-separator) JSON
encoding of the fields returned by `ExpansionIdentity.fingerprint_fields()`.
Because the encoding is canonical, identical inputs always produce the
same fingerprint on any host, and the fingerprint only changes when a
compatibility-relevant setting changes.

**Compatibility-relevant settings folded into the fingerprint** (and why):

| Field | Why it is compatibility-relevant |
| --- | --- |
| `version` (major/minor/patch) | marks an intentional framework/config-identity change |
| `abi` | affects calling convention and struct layout (ABI compatibility) |
| `config_preset` | debug vs. release changes optimization, assertions, and logging -- runtime behavior differs |
| `rom_size_bytes` | affects ROM data layout/padding |
| `text_shift` | affects link-time ROM layout |
| `rom_title`, `rom_game_code`, `rom_maker_code`, `rom_revision` | ROM identity; changing these produces a distinguishable ROM (e.g. for emulator save matching, patch tooling) |
| `enabled_locales`, `default_locale`, `pseudo_locale_enabled` | issue #18 localization settings; the normalized enabled-locale set, default locale, and pseudo-locale flag each change which/how many locale catalog entries link into the ROM and how the runtime resolver starts up -- behaviourally distinguishable. Diagnostic/UI identity only -- see `docs/localization.md`; never touches the save format (`EXPANSION_SAVE_COMPAT_EPOCH` stays independent, see below) |
| `features.mechanics_hooks`, `features.mechanics_sample`, `features.danger_overlay_menu`, `features.starter_content` | issue #6 starter-feature opt-ins; each links different code and/or data, so two builds that differ in any of them are behaviourally distinguishable. Diagnostic identity only -- see `docs/starter_features.md`; none of them touches the save format |

Settings that are **not** folded into the fingerprint (e.g. the resolved
`build_commit`) are informational only: two builds from different commits
but with identical compatibility-relevant settings share a fingerprint,
since the commit does not by itself imply an incompatible change. Save
data compatibility is intentionally out of scope for this fingerprint;
`EXPANSION_SAVE_COMPAT_EPOCH` (see table above) is issue #2 slice 1's
independent save-compatibility key -- see `docs/save_format.md` for the
on-media format it gates and exactly when to bump it. It is deliberately
excluded from `fingerprint_fields()`: this fingerprint is allowed to
contain diagnostics-only settings (like `config_preset`'s debug/release
choice) that must never make an otherwise-identical save look
incompatible, so save compatibility needed its own, narrower key.

## C configuration header

`include/expansion_config.h` is C89/agbcc-safe and reachable from any
translation unit that includes `global.h` first (this repository's
existing include convention). It defines:

- `FE8_EXPANSION` -- unconditional marker that a translation unit is part
  of the expansion framework.
- `FE8_EXPANSION_VERSION_MAJOR`/`_MINOR`/`_PATCH`/`_STRING`/`_PACKED` --
  semantic version components, string, and the packed
  `(major << 16) | (minor << 8) | patch` value.
- `FE8_EXPANSION_BUILD_COMMIT`, `FE8_EXPANSION_CONFIG_FINGERPRINT`,
  `FE8_EXPANSION_CONFIG_PRESET`, `FE8_EXPANSION_ABI` -- deterministic
  build metadata.
- `FE8_EXPANSION_ROM_TITLE`/`_GAME_CODE`/`_MAKER_CODE`/`_REVISION`/
  `_SIZE_BYTES` -- ROM identity.
- `FE8_EXPANSION_DEBUG`, `FE8_EXPANSION_ASSERTIONS_ENABLED`,
  `FE8_EXPANSION_LOGGING_ENABLED` -- release-aware switches for later
  subsystems, derived from `NDEBUG` by default.

Every macro has a hardcoded `#ifndef` fallback matching `config.mk`'s own
defaults exactly, so a legacy agbcc/old_agbcc build -- which never
receives the modern build's `-D` flags -- keeps today's exact ROM
identity and behavior unchanged. The modern build supplies every one of
these as a `-D` command-line define (see `modern.mk`'s "Framework
configuration and ROM identity" section), computed from `config.mk` plus
`MODERN_CONFIG`/`MODERN_ABI`/`MODERN_ROM_SIZE` and the resolved build
commit/fingerprint, so the `#ifndef` fallback is never reached for a
modern build.

## Embedded ROM metadata record

`include/expansion_metadata.h` defines `struct ExpansionMetadata`, and
`src/expansion_metadata.c` defines a single `const` instance
(`gExpansionMetadata`) populated entirely from the `FE8_EXPANSION_*`
macros above, marked so it is linked into every modern ROM's `.rodata`
(not just present in a generated header that never reaches the binary).
The record begins with the fixed 4-byte magic `"FE8M"`, followed by the
semantic version (components, packed value, and string), the build
commit, the config fingerprint, the config preset, the ABI, and the
configured ROM identity (title, game code, maker code, revision, and ROM
size in bytes) -- so the ROM itself unambiguously exposes its own
framework identity without needing an external metadata file.

`scripts/modernize/verify_rom_header.py` locates this record by scanning
the ROM for the magic bytes (`find_expansion_metadata`), parses it
(`parse_expansion_metadata`), and verifies it against a generated
`expansion_build_metadata.json` (`verify_expansion_metadata`, and the
`verify_rom_header()`'s `expected_metadata` keyword argument / the CLI's
`--metadata-json` flag). A ROM with no embedded record, a truncated
record, or a record whose contents disagree with the expected metadata
fails verification with a specific field-level diagnostic.

## GBA header parameterization and checksum

`scripts/modernize/finalize_rom_header.py` patches a freshly `objcopy`'d
flat ROM image's title (12-byte NUL-padded ASCII), game code (4 ASCII
bytes), maker code (2 ASCII bytes), and revision byte in place, then
recomputes and writes the GBA header complement checksum (the byte at
offset `0xBD`, computed over `0xA0..0xBC`, per the standard GBA header
format). Every field is validated **before** any byte of the ROM is
touched; on any invalid field the script exits non-zero and leaves the
ROM file completely untouched. This runs as part of `modern.mk`'s
`$(MODERN_ROM)` recipe, immediately after `objcopy`, and is immediately
followed by `verify_rom_header.py` re-checking the result (title, game
code, maker code, revision, fixed byte, ROM size, checksum, and the
embedded metadata record); if verification fails, the ROM file is deleted
so a stale, invalid image is never left behind.

This mechanism (generated bytes patched into the ROM image post-link, not
a preprocessed `src/rom_header.s` or a build-time macro) was chosen
because `src/rom_header.s` is the **legacy** header source, consumed by
the legacy agbcc/old_agbcc build and by `make compare`; the modern build
path already produces its own separate flat ROM image via `objcopy` from
the modern ELF (which still carries whatever placeholder identity
`rom_header.s`'s modern-compiled object last had), so patching that
post-link output in place is the smallest, safest change that doesn't
touch the legacy path or `ldscript.txt`.

## Legacy build path

The legacy agbcc/old_agbcc build (`make fireemblem8.gba`) is entirely
unaffected: `src/rom_header.s` keeps its own hardcoded identity, and none
of `config.mk`'s values or `MODERN_CFLAGS`'s `-D` defines reach the
legacy `CFLAGS`. `include/expansion_config.h`'s `#ifndef` fallbacks match
today's legacy identity exactly, so any legacy-built object that happens
to include it (directly or transitively) observes unchanged values.

## Debug and release presets

| | `MODERN_CONFIG=debug` | `MODERN_CONFIG=release` |
| --- | --- | --- |
| Optimization / debug info | `-Og -g3` | `-O2 -g0` |
| `NDEBUG` | not defined | defined |
| `FE8_EXPANSION_DEBUG` | `1` | `0` |
| `FE8_EXPANSION_ASSERTIONS_ENABLED` | `1` | `0` |
| `FE8_EXPANSION_LOGGING_ENABLED` | `1` | `0` |
| `config_fingerprint` | distinct from release (preset is compatibility-relevant) | distinct from debug |

Both presets are exercised end-to-end by
`expansion-modern-rom MODERN_CONFIG=debug|release`, each producing a
verified ROM with a distinct, deterministic `config_fingerprint`.

## Validation and failure behavior

`scripts/modernize/expansion_config.py` validates every field (title,
game code, maker code, revision, ROM size, semantic version, build-id
override, preset, ABI) and rejects any malformed value or incompatible
combination with a specific, actionable `ConfigError` message, entirely
**before** any C/assembly compilation or linking is attempted (`modern.mk`
runs `validate`/`resolve` as part of evaluating the makefile itself, so a
bad value fails the `make` invocation immediately) and before any ROM
byte is patched (`finalize_rom_header.py` validates first, then patches).
Invalid values are never silently normalized or clamped.
