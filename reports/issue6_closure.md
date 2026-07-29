# Issue #6 Sprint 2 -- bundled generated-data content example: closure evidence

Branch `agent/issue6-starter-features`, built on `origin/master`
`976c71230788d73283bea3871116274c5a232565`. Sprint 1's foundation evidence
(config flags, mechanics registry, player QoL overlay, clean-boot runtime
route) stays in `reports/issue6_foundation_evidence.md`; this report covers
only the remaining Sprint 2 scope, the **generated-data content example**.

**#10 dependency: real, merged.** The typed/active ID platform this content
depends on is on `master` -- `origin/master`
`976c71230788d73283bea3871116274c5a232565` ("fix: self-heal active ID
contracts across cap flips"), merged into this branch at
`bdd9add31db305d1df6bef5975999821ec95c2f9`. Nothing was copied,
cherry-picked or transcribed from any unmerged branch; the content builds on
the merged `ItemId` / `ITEM_EXPANSION_CE` / `id_space_active.h` contracts as
published.

## What shipped

| Layer | Artifact |
| --- | --- |
| config | `EXPANSION_STARTER_CONTENT` / `FE8_EXPANSION_STARTER_CONTENT`, default `0` (`config.mk`, `include/expansion_config.h`, `scripts/modernize/expansion_config.py`, `modern.mk`) |
| data | `ITEM_EXPANSION_CE` authored in `src/data/items_expansion.json`; original messages in `texts/texts.txt` -> `include/constants/msg.h` |
| schema | symbolic `MSG_*` text IDs (`scripts/generated_data/items/schema.py`, `scripts/generated_data/validators.py`) |
| hook | `include/expansion_starter_content.h`, `src/expansion_starter_content.c`, installed from the one existing `ExpansionMechanicsInstallBuiltins()` |
| evidence | extended `include/expansion_itemtest.h` / `src/expansion_itemtest.c` probe + `tools/gba-playtest/run_item_expansion_checks.py` |

## Frozen criteria -> evidence

### A. Original, opt-in, generated content

* The 207th record is a genuine authored example, not a placeholder:
  `ITYPE_ITEM`, `maxUses 3`, `attributes IA_UNSELLABLE`, `iconId 222`, and
  three original text IDs. It is produced **only** by the ordinary
  generated-data pipeline; `build/generated/data/data_items.c` is never
  hand-edited (it is git-ignored build output).
* **Original authoring identity.** Name/description/use-description are new
  framework-authored English strings added through the repository's own
  supported text pipeline (`texts/texts.txt` ->
  `scripts/texttools/textprocess.py` -> `include/constants/msg.h` +
  `src/msg_data.c`) -- the same path the issue #2 save-compatibility UI
  already used for `MSG_SAVE_COMPAT_*`. No vanilla message index, item name
  or icon design is reused as a shortcut.
* **No new graphics asset.** `iconId 222` is the vanilla data's own unused,
  purely geometric placeholder tile (`item_icon_unused_9`: a hollow box with
  a diagonal cross). It was chosen precisely because it depicts nothing; the
  repository ships no new artwork for this example. This is the documented
  "neutral existing slot" choice.
* **No raw numeric IDs.** Every issue #6 implementation source names the item
  symbolically (`ITEM_EXPANSION_CE`) or reaches it through the typed
  `ExpansionStarterContentItemId()` accessor. Pinned by
  `tools/gba-playtest/tests/test_expansion_starter_content.py`
  (`test_no_raw_numeric_content_item_id`); the single permitted `0xCE`
  mention is the `#error` string that tells a contributor which
  `FE8_ITEM_ID_CAP` to pass, and that is asserted to stay actionable.
* **Symbolic text IDs.** `"nameTextId": "MSG_EXPANSION_STARTER_ITEM_NAME"`
  is resolved against `include/constants/msg.h`; an unknown symbol fails the
  data build with an actionable diagnostic naming `texts/texts.txt`. The 206
  vanilla records keep their numeric form and still round-trip byte-for-byte
  against `src/data_items.c`.
* **Round trip / counts.** Default cap `0xCD`: 206 records, no expansion
  record, committed manifest and inventory unchanged. Opt-in cap `0xCE`: 207
  records, the `[ITEM_EXPANSION_CE]` record emitted with
  `#include "constants/items_expansion.h"`, and the generated table's own
  static assertions bind the compiled cap to `ITEM_ID_ACTIVE_CONFIGURED_CAP`
  and the emitted record count to `ITEM_ID_ACTIVE_RECORD_COUNT`.

### B. Compile-time config / metadata

* A **new, individual** flag rather than reusing `FE8_ITEM_ID_CAP`: the cap
  is the ID-space platform's knob, and reusing it would bind the platform to
  the content. `EXPANSION_STARTER_CONTENT` defaults to `0`, is validated
  strictly `0`/`1` (`-1`, `2` and text each rejected with an actionable
  message), and flows through `--starter-content`, the `-D` define, the
  generated `expansion_build_metadata.json`, the config fingerprint, and the
  content-addressed `compile_settings.txt` recompile stamp.
* **Two dependencies, three fail-fast layers.** `EXPANSION_MECHANICS_HOOKS=1`
  and an active item cap reaching `ITEM_EXPANSION_CE` are each rejected in
  `expansion_config.py` (so Make fails before any compile) and are each a
  hard `#error` in C (`include/expansion_config.h` and
  `include/expansion_starter_content.h`). `modern.mk` passes the build's live
  `FE8_ITEM_ID_CAP` as `--item-id-cap`, so all three layers see one value.
* **One-way dependency.** Nothing in the #10 platform depends on the content
  flag, proven by
  `test_platform_stays_testable_at_any_cap_with_content_off` (caps
  default/`0xCD`/`0xCE`/`0xFF` all resolve with the flag off).
* **No save impact.** `EXPANSION_SAVE_COMPAT_EPOCH` stays `1`, no save field
  is added, and the flag is not part of the save-compatibility key
  (`test_flag_never_changes_the_save_compat_epoch`).
* **Cap constants cannot drift.** `expansion_config.py` restates the item cap
  boundary because it runs as a bare script; a test asserts it equals
  `scripts/generated_data/idspace.py`'s own values.

### C. Config + data + hook APIs, without a second framework

* The content mechanic is registered through the **public**
  `ExpansionMechanicsRegister()` API from the framework's single existing
  `ExpansionMechanicsInstallBuiltins()` install point. It never touches the
  registry's internals (asserted), `src/bmbattle.c` contains no content or
  item special case (asserted), and no second router, registry or harness
  exists.
* Inventory membership is read with the production accessor
  `GetUnitItemSlot()`, comparing a typed `ItemId` against the symbolic
  `ITEM_EXPANSION_CE`.
* The mechanic adjusts `battleAvoidRate`, deliberately a **different** stat
  from the pre-existing content-free sample's `battleDefense`, so both are
  independently observable and the existing sample keeps its exact previous
  standalone semantics. The Sprint 1 `starter-hook-*` scenarios still assert
  `registerOkCount=1` on the flags-on profile ROM -- which is precisely what
  proves the content mechanic is **not** registered when the content flag is
  off.
* Evidence rides the **existing** #10 gate
  (`expansion-modern-itemexpansion-check`) and its existing ROM build.
  `EXPANSION_STARTER_CONTENT=1 EXPANSION_MECHANICS_HOOKS=1
  EXPANSION_MECHANICS_SAMPLE=1` are added to the two commands CI already
  runs: no new workflow command, no new ROM build, no new harness.
* The danger-overlay QoL profile and its scenarios stay exactly as they were.

### D. Tests and clean build

Host:

* `scripts/generated_data/tests/test_items_expansion.py` (20 tests):
  default-206/no-expansion, opt-in-207, un-opted rejection, and the new
  authored-content class -- symbolic-only text IDs, framework-original
  `MSG_EXPANSION_*` messages, resolved values matching the header, messages
  beyond every vanilla index, meaningful+bounded item fields, an existing
  icon slot, every authored field present in the generated C, and the
  `uses<<8|id` packing. Plus the symbolic-text-ID form itself
  (unknown symbol rejected actionably, numeric form still accepted,
  `MSG_COUNT` not usable as a text ID).
* `scripts/modernize/tests/test_expansion_config.py` (102 tests): the new
  flag's default, both dependencies, invalid values, fingerprint impact,
  epoch independence, metadata JSON, idspace constant agreement, and the
  compile-time contract's presence in the headers and `modern.mk`.
* `tools/gba-playtest/tests/test_expansion_starter_content.py` (15 tests):
  no raw numeric content ID, no `//` comments, public-API-only registration,
  a single install point, a content-free `bmbattle.c`, a bounded effect, a
  distinct stat, probe field order matching the C struct, u32-scalar-only
  probe fields, **zero data/bss in the disabled TU**, and both compile-time
  dependency errors.
* `tools/gba-playtest/tests/test_expansion_mechanics.py`: now links the real
  `src/expansion_starter_content.c` into its drivers, so the registry host
  tests still execute the real, unmodified sources.

Runtime (semantic scalars only -- no pointer, no framebuffer oracle):

* debug, content profile: `stagesCompleted=0x7f`, `configuredCap=0xce`,
  `dataNumber=0xce`, `dataNameTextId=0xd56`, `dataDescTextId=0xd57`,
  `dataIconId=0xde`, `dataWeaponType=0x9`, `dataMaxUses=3`,
  `dataAttributes=0x10`, `madeItem/eventItem/arenaItem/gameSaveItem/
  suspendItem/gameSavePackedField/suspendPackedField=0x03ce`,
  `legacyDataNumber=0xcd`, `uiDescId=0xd57`, `uiIconId=0xde`,
  `contentEnabled=1`, `contentItemId=0xce`, `contentMechanicsCount=2`,
  `contentSampleIndex=0`, `contentMechanicIndex=1`, `contentRegisterOk=2`,
  `contentRegisterErr=0`, `contentLastResult=0`, `contentBearerPid=1`,
  `contentBearerItemSlot=3`, `contentBearerAvoidDelta=5`,
  `contentBearerDefenseDelta=1`, `contentControlPid=2`,
  `contentControlItemSlot=0xffffffff`, `contentControlAvoidDelta=0`,
  `contentControlDefenseDelta=1`, `contentApplyCount=2`,
  `contentSampleTriggerCount=2`, and the build-local active contract
  cross-check `cap 0xCE, 207 record(s)`.
* release, content profile: the same boot-half values
  (`configuredCap=0xce`, the whole authored record, `contentEnabled=1`,
  `contentItemId=0xce`, `contentMechanicsCount=2`, `contentRegisterOk=2`).
* default-disabled negatives: the probe is not linked at all in a default
  build (`FE8_EXPANSION_ITEMTEST=0` compiles the TU to an empty object), the
  default ROM stays at cap `0xCD` with 206 records and no expansion record,
  and the Sprint 1 `starter-hook-*-negative` scenarios still show every
  mechanics counter at zero on the default ROM in both configs.

### E. CI / Make non-redundancy

* `.github/workflows/build.yml` still has **exactly 10** correctness
  commands, in the same order; only the two item-expansion command strings
  gained the content profile variables. `scripts/upstream_port/verify.py`
  was updated in the same commit, and the live argv/order mirror test
  (`tests/upstream_port/test_verify.py`) passes.
* No extra ROM build: the item-expansion gate already rebuilt the affected
  objects for the cap flip via the content-addressed compile-settings stamp;
  adding the content variables changes that same one rebuild per config.
* The Sprint 1 starter runtime profile keeps its own build root
  (`build/expansion-modern-starter`), so there is no cross-profile build-root
  contamination.

## Baseline review (explicit; nothing auto-refreshed)

Adding three original messages changes the **shared, Huffman-compressed**
message table, so every build's text blob is re-encoded. Decoded strings are
identical -- but two *transient* menu framebuffers land on a different phase
of the same blinking-text cycle.

Diagnosis was empirical, not assumed:

1. A per-frame framebuffer scan (frames 1035..1075) showed the observed
   screen cycling through five hashes; the committed hash appeared at none of
   them, ruling out a simple frame offset.
2. An A/B ROM built with **only** the three messages reverted (content
   module, new flag and fingerprint change all kept) verified the committed
   fingerprint exactly, isolating the cause to the text-table addition.
3. A pixel diff of the two ROMs at the failing frame showed 264 differing
   pixels in one 13-row text band, toggling between the text colour and the
   background -- i.e. the same glyphs at a different blink phase.

The baselines were then re-derived through the sanctioned explicit
`capture -o` path and reviewed **field by field**. Across all 19 save-format
fingerprints the union of changed fields is exactly two:

* `checkpoints[1].framebuffer_hash` in the six `savecompat-dialog-back-*`
  pairs (12 files) and `checkpoints[0].framebuffer_hash` in the two
  `savecompat-erase-*` files -- the transient blink-phase frames above;
* `rom.sha1`, the informational provenance field (not compared under the
  `behavior` policy).

Everything else is bit-identical: all six state-specific diagnostic screens,
every returned screen, and **every single `sram_hash`** -- the scenario's own
primary assertion that passive display and confirmed Back leave SRAM
byte-for-byte unchanged, and that the confirmed erase changes it. No
checkpoint was removed, relaxed or moved, and no gate was weakened. The
`savecompat-current`, `savecompat-current-migrated` and
`savesuspend-resume` fingerprints had no semantic change and were left
untouched.

The linker budget baselines (`reports/linker-budget/modern-{debug,release}.json`)
did **not** drift and were not touched.

## Validation run (this branch, this tree)

Clean build: `build/expansion-modern`, `build/expansion-modern-starter`,
`build/generated` and `build/shiftcheck` were deleted before the four ROM
gates below, which then ran in CI order.

| Gate (CI order) | Result |
| --- | --- |
| 1. `GBA_PLAYTEST_HOST_ONLY=1 ... tools/gba-playtest/tests` | 339 tests, OK (11 skipped) |
| 2. `... tests/upstream_port` | 144 tests, OK |
| 3. `scripts/artifact_guard.py --revision HEAD` | pass (silent) |
| 4. `test_build_default_lane.py` | 15 tests, OK |
| 5. `test_quickstart.py` | 15 tests, OK |
| 6. `make generated-data-check` | 13 tables, 722 records, no manifest drift; census clean (1076 hits, 1051 audited, 25 reviewed exclusions); id-space + active contract up to date (cap 0xCD, 206 records) |
| 7. `expansion-modern-linker-check MODERN_CONFIG=debug` | pass (budget, overlay audit, starter runtime matrix, boot/title/debugtools/newgame/combat/saveload/savefmt/shifted, shift+offset scan, raw-pointer audit) |
| 8. `expansion-modern-linker-check MODERN_CONFIG=release` | pass |
| 9. item-expansion + content gate, debug | pass, `stages=all content=1`, active contract `cap 0xCE, 207 record(s)` |
| 10. item-expansion + content gate, release | pass, `stages=boot content=1`, active contract `cap 0xCE, 207 record(s)` |

Additional (not CI commands):

| Check | Result |
| --- | --- |
| `make generated-data-test` | 624 tests, OK (613 before this work; +11 authored-content/symbolic-text-ID tests) |
| `scripts/modernize/tests` (full) | 439 tests, OK (1 skipped) |
| `test_archival_lane_item_cap_guard.py` | 26 tests, OK |
| `test_idspace_active_check_gate_hermetic.py` | 6 tests, OK |
| `make expansion-modern-idspace-active-check` | pass, including the stale-ACTIVE-header self-heal and the cap/count divergence negative |
| `gba_playtest.py backend-check` | libMGBA backend available |
| `python3 -m scripts.upstream_port verify --dry-run` | exactly 10 gates, in order, argv-identical to `build.yml` |

**Isolated build roots and determinism.** The bundled-content ROM was rebuilt
into a separate root (`MODERN_BUILD_ROOT=build/iso-content`) and is
**byte-identical** to the one the CI-order gate produced in the default root
(`sha1 866c3f9a3c5a318e5715ac6440863174737bd2f2`). The default (cap `0xCD`,
all flags off) ROM built into its own root is a distinct ROM
(`sha1 f44b46b10a3469c3a5c882a7e04db275dd966a31`), so there is no
cross-profile build-root contamination.

**Artifact-level record counts**, read from the linked ELFs:

| Build | `gItemData` | Records | Probe symbol |
| --- | --- | --- | --- |
| default (cap `0xCD`, flags off) | 7416 bytes | 206 | `gItemExpansionProbe` absent (TU compiled out) |
| content (cap `0xCE`, content on) | 7452 bytes | 207 | present |

The content module's symbols exist in both ROMs, but the default build links
only the three stubs -- `ExpansionStarterContentCharmEvade` exists **only** in
the content build.

## Non-goals (explicitly not delivered)

* No growth UI, no convoy feature, no debug editor, no persisted option, no
  additional QoL surface, no broad rewrite.
* No new save field and no save-epoch bump (`EXPANSION_SAVE_COMPAT_EPOCH`
  stays `1`).
* No second router, registry or ROM harness; no extra CI command and no extra
  ROM build.
* No hand-edited generated C, no raw numeric content IDs, no copyrighted
  names/assets and no new graphics asset.
* Exactly one content example: one item and one mechanic. No new chapters,
  units, classes, scripted events or further items.
* This report does not close the issue; it is candidate evidence for review.
