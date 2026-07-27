# Issue #6 Sprint 1 foundation -- evidence

Branch `agent/issue6-starter-features` (HEAD `30d41f6f1ada6db62b244da54f252f1bb924684f`), built on
`origin/master` `c717da36c51f94bc6051ec8954bed4ccec2b76fd`. This sprint ships
the runtime/config/hook/QoL **foundation only**. It does **not** implement a
generated-content example -- that waits for issue #10's typed expanded IDs
landing on `master`.

**#10 dependency (read-only monitor).** `origin/agent/issue10-extensible-ids`
is at `dfecd10208f6609c7269daa302fd0d16994b2763` (prefix `dfecd102`). It is monitored read-only; no unmerged
code was copied, cherry-picked, or transcribed. No raw numeric content IDs and
no hand-edited generated C were introduced.

## Requirement -> evidence

### A. Individual validated config identity (foundation only)
* Three independent `0/1` flags following the `EXPANSION_*` / `FE8_EXPANSION_*`
  conventions: `EXPANSION_MECHANICS_HOOKS`, `EXPANSION_MECHANICS_SAMPLE`
  (default 0; sample=1 with hooks=0 is a hard error), and
  `EXPANSION_DANGER_OVERLAY_MENU` (default 0). No dead content flag.
* Consistent across `config.mk` defaults, `expansion_config.py`
  (parse/validate/dataclass/JSON/fingerprint/CLI), `modern.mk`
  (resolve+generate args, `-D` defines, compile-settings recompile stamp), and
  `include/expansion_config.h` fallbacks + compile-time relationship guard.
* Invalid values (`-1`, `2`, text) and the sample->hooks contradiction fail
  with actionable messages, at both the tool and the Make level.
* Flags enter JSON + fingerprint deterministically; `ExpansionMetadata` struct
  layout unchanged; `EXPANSION_SAVE_COMPAT_EPOCH` stays 1 and is not folded into
  the fingerprint.

```
$ python3 -m pytest scripts/modernize/tests/test_expansion_config.py -q
85 passed
$ python3 scripts/modernize/expansion_config.py resolve --config debug --abi aapcs --rom-size 16M --repo-root .
... MODERN_CONFIG_FINGERPRINT=2295d6fc2407d1be ... MODERN_SAVE_COMPAT_EPOCH=1   (flags off)
$ ...  --mechanics-hooks 1
... MODERN_CONFIG_FINGERPRINT=214d2d60a4e9a411 ... MODERN_SAVE_COMPAT_EPOCH=1   (fingerprint changed, epoch unchanged)
$ ...  validate --mechanics-sample 1   -> error: EXPANSION_MECHANICS_SAMPLE=1 requires EXPANSION_MECHANICS_HOOKS=1
$ ...  validate --mechanics-hooks 2    -> error: EXPANSION_MECHANICS_HOOKS 2 out of range [0, 1]
```
Real modern builds embed the config fingerprint: default `2295d6fc2407d1be`,
all-features-on `c475d781faae950f` (verify_rom_header.py reports "embedded
metadata valid" on the built ROM). test_verify_rom_header / test_abi_layout /
test_save_format_meta_bytes_native / test_save_compat_epoch_modern_build green.

### B. Public mechanics hook registry
* New `include/expansion_mechanics.h` + `src/expansion_mechanics.c`: fixed
  capacity (8), typed `struct BattleUnit*` + read-only-context callback (no
  void*/raw IDs), deterministic order, introspection, distinct
  disabled/null/length/duplicate/capacity/reentrant errors, copy-in lifetime
  safety, reentrancy guard.
* Narrow seam in `ComputeBattleUnitStats()` after vanilla stats / before
  effective stats, `#if`-gated so the disabled/legacy object has **zero**
  references (byte-identical vanilla battle math).
* Meaningful default-disabled sample ("Full-HP Guard", +1 bounded battleDefense,
  clamped, content-free) registered only through the public API.

```
$ python3 -m pytest tools/gba-playtest/tests/test_expansion_mechanics.py -q
11 passed
```
Covers capacity/order/duplicate/null/length/reentrancy, sample exact +1 /
below-full-HP no-op / clamp / idempotent install, disabled inert + all-zero
probe, compile-gated seam (default object has no mechanics reference), C89 shape
(no declaration-after-statement), arm AAPCS compile + symbol export, modern.mk
`-D` wiring. Full modern object build with HOOKS=1 SAMPLE=1 compiles clean under
the `-Werror` modern gates (453 objects built).

### C. Player QoL danger/range overlay
* Promoted `MapMenu_DangerZone_UnusedEffect` via a correct-signature wrapper +
  one gated `gMapMenuItems` entry (original label, `nameMsgId 0`), reusing the
  existing danger-zone range path unchanged. Disabled table byte-identical
  vanilla; enabled adds exactly one `MenuItemDef` within `MENU_ITEM_MAX`. No
  second router, no range-math rewrite, no persisted option/save field.

```
$ python3 -m pytest tools/gba-playtest/tests/test_expansion_danger_overlay.py -q
13 passed
```
Proves from compiled objects: disabled gMapMenuItems == vanilla size, enabled ==
+1 MenuItemDef within MENU_ITEM_MAX, compile-gated wrapper (default bmmenu has
no reference) delegating to the vanilla effect, always-linked QoL probe with
compile-gated writes, block-comment-only additions, arm AAPCS compile.

### D. Semantic runtime harness
* Reused issue #13 gba-playtest (no new framework). Always-linked semantic
  probes (`gExpansionMechanicsProbe`, `gExpansionDangerOverlayProbe`);
  pointer-oracle audit green.
* Mechanics-hook scenario + fingerprint (positive) and negative control, from
  **real libmGBA runs** of built modern debug ROMs over the Chapter 4 combat
  navigation:

| gExpansionMechanicsProbe | Enabled (profile ROM) | Disabled (default ROM) |
|---|---|---|
| registerOkCount | 1 | 0 |
| registerErrCount | 0 | 0 |
| applyCount | 2 | 0 |
| lastAppliedCount | 1 | 0 |
| lastDefenseDelta | 1 | 0 |
| sampleTriggerCount | 2 | 0 |
| lastResult | 0 (OK) | 0 |
| enemy maxHP/curHP (real combat) | 15/15 -> 15/0 | 15/15 -> 15/0 |

  Same real FIGHT both ways (the enemy dies), opposite semantic probe outcomes
  -- the counters come from the real seam, not a faked write, and are not
  framebuffer-only.
* `expansion-modern-starter-hook-check` Make gate builds a dedicated
  starter-foundation profile ROM to its own build root (never overwriting the
  flags-off baseline) and verifies positive-on-profile / negative-on-default.

```
$ STARTER_HOOK_ROM=<profile.gba> STARTER_HOOK_NEGATIVE_ROM=<default.gba> \
    python3 -m pytest tools/gba-playtest/tests/test_starter_features_scenarios.py -q
7 passed   (5 schema always-on + 2 libmGBA runtime verifications)
$ python3 tools/gba-playtest/gba_playtest.py verify --rom <profile.gba> \
    --scenario tools/gba-playtest/scenarios/starter-hook-modern-debug.json \
    --expected tools/gba-playtest/fingerprints/starter-hook-modern-debug.json --policy behavior
fingerprint verified: policy=behavior scenario=starter-hook-modern-debug checkpoints=3
```

### E. Docs/evidence
* `docs/starter_features.md` (public API, capacity/errors/order/reentrancy,
  sample, QoL keys/menu, safety, flags/fingerprint, no save epoch, extension
  steps, non-goals) and this report.

### F. Git discipline
* Small commits, each pushed immediately to `origin/agent/issue6-starter-features`
  with the remote SHA verified == HEAD after each. Every commit carries the
  required Co-authored-by + Copilot-Session trailers. No rebase/amend/reset/
  force; tree clean.

## Release-enable-ability

The features are not `NDEBUG`-gated -- they are controlled solely by their own
`0/1` flags, orthogonal to debug/release. All 453 modern objects build clean
with the flags on under the release-capable `-Werror` modern gates, and the
modern ELF/ROM links + boots with the features on (host + linked proof; the
default boot scenario passes under behavior policy on the feature-enabled ROM).

## Environmental prerequisite and honest scope

* The full modern **ELF/ROM link** requires the `mgfembp` submodule payload. A
  fresh worktree has the submodule uninitialised (the modern-ROM scenario tests
  legitimately *skip* when the ROM is not built). For the runtime captures here
  the payload was supplied from an already-built sibling worktree (identical,
  feature-independent build input); a CI/verifier environment that initialises
  the `mgfembp` submodule builds it normally. This is pre-existing and unrelated
  to the issue #6 code.
* Currently committed runtime scenarios are **debug**, mechanics-hook only
  (positive + negative control). The QoL menu-navigation scenario and the
  release-enabled libmGBA scenario are called out in the sprint escalation
  (they need per-ROM input-timing calibration beyond this slice); the QoL probe
  and release-enable-ability are proven at host + linked-build level in the
  meantime.
