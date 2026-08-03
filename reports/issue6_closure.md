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
| data | `ITEM_EXPANSION_CE` authored in `src/data/items_expansion.json`; **no shared message is added** (`texts/texts.txt` and `include/constants/msg.h` are byte-identical to the merge parent) |
| schema | symbolic `MSG_*` text IDs remain available for records that point at an existing message (`scripts/generated_data/items/schema.py`, `scripts/generated_data/validators.py`); the content record uses none |
| text | `authoringName` in the same authored record -> `scripts/generated_data/items/content_text.py` -> a build-local, content-profile-only text table -> the typed accessor `ExpansionStarterContentItemName()` -> the unmodified production `GetItemName()` (`src/bmitem.c`, `#if FE8_EXPANSION_STARTER_CONTENT`) |
| hook | `include/expansion_starter_content.h`, `src/expansion_starter_content.c`, installed from the one existing `ExpansionMechanicsInstallBuiltins()` |
| evidence | extended `include/expansion_itemtest.h` / `src/expansion_itemtest.c` probe + `tools/gba-playtest/run_item_expansion_checks.py` |

## Frozen criteria -> evidence

### A. Original, opt-in, generated content

* The 207th record is a genuine authored example, not a placeholder:
  `ITYPE_ITEM`, `maxUses 3`, `attributes IA_UNSELLABLE`, `iconId 222`. It is
  produced **only** by the ordinary generated-data pipeline;
  `build/generated/data/data_items.c` is never hand-edited (it is git-ignored
  build output).
* **Original authoring identity, with no default-build cost.** The record
  binds **no** message ID (`nameTextId`/`descTextId`/`useDescTextId` all stay
  `0`) and reuses no vanilla message, name or icon design. Its original
  display name is authored as literal text in the same JSON record and
  travels the config-gated generated-content text path (next section), so a
  default build's shared message table is untouched.
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
* **Symbolic text IDs (generic schema capability, unused by this record).**
  A record *may* author `"nameTextId": "MSG_*"` and have it resolved against
  `include/constants/msg.h`, with an unknown symbol failing the data build
  actionably. The bundled content record deliberately uses none of that: a
  framework-authored record must not consume a slot in the shared message
  table (see "Policy remediation" below). The 206 vanilla records keep their
  numeric form and still round-trip byte-for-byte against `src/data_items.c`.
* **Config-gated content text.** The original display name lives in the same
  authored record (`"authoringName": "Sample Charm"`, schema-validated:
  expansion records only, printable 7-bit ASCII, trimmed, bounded, never
  combined with a `nameTextId`). `scripts/generated_data/items/content_text.py`
  emits it -- only at `EXPANSION_STARTER_CONTENT=1`, and only into
  `build/generated/data/` -- as a typed, `ItemId`-keyed C89 table plus an
  audit catalog. At flag `0` the generator writes nothing and removes any
  artifact a previous content build left behind. `gItemData[]` is
  byte-identical with or without the authoring fields.
* **One narrow production seam.** `src/bmitem.c`'s `GetItemName()` -- the one
  function every item-name consumer (menu, trade, shop, stat screen, popups,
  `[Item]` substitution) already goes through -- consults the typed public
  accessor `ExpansionStarterContentItemName(ItemId)` inside
  `#if FE8_EXPANSION_STARTER_CONTENT` and falls through unchanged on `NULL`.
  A default build has no declaration, no call, no data and no include-path
  entry for the generated header: the object is the vanilla one.
* **Honest boundary.** The vanilla description/help UI is addressed only by
  message ID, and this framework adds no messages, so the item's
  `descTextId`/`useDescTextId` stay `0` and its help box shows no text. No
  vanilla description is borrowed to fake one; the authored descriptions are
  emitted into the generated audit catalog and labelled there as not shown in
  game.
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

* `scripts/generated_data/tests/test_items_expansion.py` (29 tests):
  default-206/no-expansion, opt-in-207, un-opted rejection; the authored
  record class -- **no shared message slot consumed** (the three `*TextId`
  keys are absent and resolve to `0`), no vanilla message index reused, a
  direct `MSG_COUNT == 0x0D56` guard, meaningful+bounded item fields, an
  existing icon slot, no text field emitted into the generated C, and the
  `uses<<8|id` packing; the authoring-text class -- the literal is carried,
  never reaches `gItemData[]` (generated C compared with and without the
  fields), is rejected on a vanilla record, is rejected alongside a
  `nameTextId`, and is bounded/printable-ASCII/trimmed; and the content-text
  generator itself -- only authored expansion records collected, nothing at
  the default cap, the exact literal and capacity in the header, an honest
  catalog, and hard flag/cap errors. Plus the symbolic-text-ID form
  (unknown symbol rejected actionably, numeric form still accepted,
  `MSG_COUNT` not usable as a text ID).
* `scripts/modernize/tests/test_expansion_config.py` (102 tests): the new
  flag's default, both dependencies, invalid values, fingerprint impact,
  epoch independence, metadata JSON, idspace constant agreement, and the
  compile-time contract's presence in the headers and `modern.mk`.
* `tools/gba-playtest/tests/test_expansion_starter_content.py` (26 tests):
  no raw numeric content ID, no `//` comments, public-API-only registration,
  a single install point, a content-free `bmbattle.c`, a bounded effect, a
  distinct stat, probe field order matching the C struct, u32-scalar-only
  probe fields, **zero data/bss in the disabled TU**, both compile-time
  dependency errors -- plus the config-gated text half: the default profile
  generates nothing and deletes a stale artifact, the content profile emits
  the exact authored literal with a capacity that fits the module buffer,
  output is deterministic and path-independent, no committed C hand-holds the
  authored text, `texts/texts.txt`/`msg.h` carry no `MSG_EXPANSION_*` at all,
  a default-compiled `bmitem.o`/content object has no content symbol and no
  authored bytes, the content-profile objects have both, and over-long
  authoring text fails the static assert.
* `tools/gba-playtest/tests/test_expansion_mechanics.py`: now links the real
  `src/expansion_starter_content.c` into its drivers, so the registry host
  tests still execute the real, unmodified sources.

Runtime (semantic scalars only -- no pointer, no framebuffer oracle):

* debug, content profile: `stagesCompleted=0x7f`, `configuredCap=0xce`,
  `dataNumber=0xce`, `dataNameTextId=0`, `dataDescTextId=0` (no shared
  message bound), `dataIconId=0xde`, `dataWeaponType=0x9`, `dataMaxUses=3`,
  `dataAttributes=0x10`, `madeItem/eventItem/arenaItem/gameSaveItem/
  suspendItem/gameSavePackedField/suspendPackedField=0x03ce`,
  `legacyDataNumber=0xcd`, `uiDescId=0`, `uiIconId=0xde`,
  **`uiNameLen=0xc` and `uiNameHash=0xc357f410`** -- the exact length and
  FNV-1a 32 of what the production `GetItemName()` returned, recomputed by
  the runner from `authoringName` (`'Sample Charm'`), i.e. the original
  authored text really is what the UI reads,
  `contentEnabled=1`, `contentItemId=0xce`, `contentMechanicsCount=2`,
  `contentSampleIndex=0`, `contentMechanicIndex=1`, `contentRegisterOk=2`,
  `contentRegisterErr=0`, `contentLastResult=0`, `contentBearerPid=1`,
  `contentBearerItemSlot=3`, `contentBearerAvoidDelta=5`,
  `contentBearerDefenseDelta=1`, `contentControlPid=2`,
  `contentControlItemSlot=0xffffffff`, `contentControlAvoidDelta=0`,
  `contentControlDefenseDelta=1`, `contentApplyCount=2`,
  `contentSampleTriggerCount=2`, and the build-local active contract
  cross-check `cap 0xCE, 207 record(s)`.
* release, content profile: the boot-half values only -- `configuredCap=0xce`
  with the build-local active contract `cap 0xCE, 207 record(s)`, the whole
  authored record as `GetItemData()` returns it, `contentEnabled=1`,
  `contentItemId=0xce`, `contentMechanicsCount=2`, `contentRegisterOk=2`,
  `contentRegisterErr=0`. It deliberately claims **no** live-map chain in
  release: that limitation predates this work (`docs/id_space.md`,
  "Release-configuration limitation"), and the frozen mechanics/QoL runtime
  proof in a real release ROM stays with the starter runtime scenarios.
* content-DISABLED negatives, at three levels and with no extra ROM build:
  * registry counts -- the `starter-hook-*` scenarios assert
    `registerOkCount=1` on the flags-on starter profile ROM (exactly one
    built-in) against `contentMechanicsCount=2`/`contentRegisterOk=2` in the
    content profile, in both configs;
  * artifacts -- `expansion-modern-starter-hook-check` now also asserts, on
    that same already-built profile ELF/ROM, that neither the content
    callback nor the content name accessor is linked, that the authored text
    appears **nowhere** in the ROM image, and that `gItemData` is still the
    vanilla-cap table (`Content-disabled artifact negative passed`, debug and
    release);
  * default build -- the probe TU is not linked at all
    (`FE8_EXPANSION_ITEMTEST=0`), the default ROM stays at cap `0xCD` with
    206 records, and the `starter-hook-*-negative` scenarios still show every
    mechanics counter at zero on it in both configs.

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

## Policy remediation -- default text leakage removed, baselines restored

**Retraction.** An earlier revision of this branch appended three original
messages (`MSG_EXPANSION_STARTER_ITEM_{NAME,DESC,USE_DESC}`) to
`texts/texts.txt`, and this report argued that the resulting **shared
Huffman table re-encode** was an acceptable cost and that re-deriving the
affected framebuffer baselines was a legitimate, reviewed refresh. **That
argument is withdrawn.** It is wrong on two counts:

1. `texts/texts.txt` is unconditional. Three content-only messages therefore
   changed the text blob -- and the transient framebuffer timing -- of every
   build, **including a default, feature-free ROM**. An opt-in feature that
   moves the default ROM is not opt-in.
2. Re-deriving 14 committed savecompat fingerprints to match the new ROM
   moved the oracle to fit the change. Even a reviewed, field-by-field
   refresh weakens a baseline whose entire purpose is to notice exactly this
   class of drift.

**What was done instead (this revision):**

* The three messages are gone. `texts/texts.txt` and
  `include/constants/msg.h` are **byte-identical to the merge parent**
  `bdd9add3` (`MSG_COUNT` is back to `0x0D56`), so `src/msg_data.c` and the
  Huffman-compressed text blob regenerate identically.
* All **14** `savecompat-*` fingerprints were restored to their `bdd9add3`
  contents with `git checkout bdd9add3 -- <path>` -- an exact restore, not a
  re-capture. No hash was refreshed, recorded or substituted, and the
  Sprint 1 `configFingerprint` normalization plus the semantic world-map
  negatives that were merged before this work are untouched.
* No default-lane gate needed a baseline edit to pass, which is the point:
  the default ROM is the same ROM again.
* The bundled content keeps its **original authored text**. It is authored as
  literal text in `src/data/items_expansion.json` and emitted by the
  generated-data pipeline into a **build-local, content-profile-only** text
  table; a default build generates and links no such string at all (see
  "Config-gated content text" in `docs/starter_features.md`).

The linker budget baselines (`reports/linker-budget/modern-{debug,release}.json`)
did **not** drift and were not touched.

## Validation run (this branch, this tree)

Re-run in full after the policy remediation, in CI order, on this tree.

| Gate (CI order) | Result |
| --- | --- |
| 1. `GBA_PLAYTEST_HOST_ONLY=1 ... tools/gba-playtest/tests` | 350 tests, OK (11 skipped) |
| 2. `... tests/upstream_port` | 144 tests, OK |
| 3. `scripts/artifact_guard.py --revision HEAD` | pass (silent, rc=0) |
| 4. `test_build_default_lane.py` | 15 tests, OK |
| 5. `test_quickstart.py` | 15 tests, OK |
| 6. `make generated-data-check` | 13 tables, 722 records, no manifest drift; census clean (1077 hits, 1052 audited, 25 reviewed exclusions); id-space + active contract up to date (cap 0xCD, 206 records) |
| 7. `expansion-modern-linker-check MODERN_CONFIG=debug` | pass (budget, overlay audit, starter runtime matrix incl. the new content-disabled artifact negative, boot/title/debugtools/newgame/combat/saveload/savefmt/shifted, shift+offset scan, raw-pointer audit) |
| 8. `expansion-modern-linker-check MODERN_CONFIG=release` | pass (same, release variants) |
| 9. item-expansion + content gate, debug | pass, `stages=all content=1`, active contract `cap 0xCE, 207 record(s)`, `uiNameLen=0xc`/`uiNameHash=0xc357f410` |
| 10. item-expansion + content gate, release | pass, `stages=boot content=1`, active contract `cap 0xCE, 207 record(s)` |

Additional (not CI commands):

| Check | Result |
| --- | --- |
| `make generated-data-test` | 633 tests, OK (613 before issue #6; +20 net authoring/content-text/policy tests) |
| `make expansion-modern-savefmt-check` (debug + release) | all 9/8 save-format runtime scenarios pass against the **restored** `bdd9add3` fingerprints |
| `make expansion-modern-starter-hook-check` (debug + release) | positive `registerOk=1/apply=2/sampleTrigger=2` on the profile ROM, all-zero negative on the default ROM, plus `Content-disabled artifact negative passed` |
| `python3 -m scripts.upstream_port verify --dry-run` | exactly 10 gates, in order, argv-identical to `build.yml` |

**Default text-blob identity, proven by isolated regeneration.**
`texts/texts.txt` and `include/constants/msg.h` are byte-identical to the
merge parent (`git diff bdd9add3 -- texts include/constants/msg.h` is empty).
Regenerating the message table from a **pristine `bdd9add3` extraction**
(`git archive bdd9add3 texts scripts/texttools include/constants/msg.h` into a
scratch tree, then `scripts/texttools/textprocess.py`) produces a
`msg_data.c` with sha256
`529ecdaf268d8ff091de489fdf580505921d5afe97fcaac397ba4144a1125180` -- exactly
the sha256 of this tree's regenerated `src/msg_data.c`. The Huffman-compressed
text blob is therefore bit-identical to the pre-content baseline, and
`MSG_COUNT` is back to `0x0D56`.

**Baseline files: restored, not re-captured.** `git diff bdd9add3 --
tools/gba-playtest/fingerprints/` is empty for all 14 `savecompat-*` files.
They were restored with `git checkout bdd9add3 -- <path>`; no capture was run
and no hash was substituted. Gates 7 and 8 then verified a freshly built
default ROM against those restored fingerprints in both configs -- the default
ROM behaves exactly like the pre-content baseline again.

**Isolated build roots and determinism** (`MODERN_CONFIG=debug`):

| Build | Root | sha1 | `gItemData` | Content symbols | `"Sample Charm"` in ROM |
| --- | --- | --- | --- | --- | --- |
| content (`cap 0xCE`, content on) | `build/iso-content` | `6662959fcf9bd588f4ec51b658e48a67426047b5` | 0x1d1c = 7452 B = **207** | `ExpansionStarterContentItemName` + `...CharmEvade` linked | 1 occurrence |
| default (`cap 0xCD`, all flags off) | `build/iso-default` | `6d2d67396a712de6e5104726b115519d0685f635` | 0x1cf8 = 7416 B = **206** | only the 3 disabled stubs; no name accessor, no callback | **0 occurrences** |

The content ROM built in the isolated root is **byte-identical** (same sha1)
to the one the CI-order gate produced in the default root, so the
content profile is deterministic and the roots do not contaminate each other.
The default ROM is a distinct artifact that contains none of the authored
content text and no probe symbol (`gItemExpansionProbe` absent).

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
* **No message is added to the shared text table**, by design -- so the
  content item's in-game description/help box shows no text, because that UI
  is addressed by message ID only. Building a config-specific message table
  for one bundled example is explicitly out of scope; no vanilla description
  is borrowed in its place, and the authored descriptions stay in the
  generated audit catalog.
* No committed baseline, fingerprint or oracle was re-captured, relaxed or
  refreshed by this work. The 14 that a previous revision had moved are
  restored to `bdd9add3`.
* No claim that the release configuration exercises a live battle map: the
  release item/content gate proves the boot half only, and the release
  runtime proof for the frozen mechanics/QoL behaviour stays with the starter
  runtime scenarios.
* This report does not close the issue; it is candidate evidence for review.
