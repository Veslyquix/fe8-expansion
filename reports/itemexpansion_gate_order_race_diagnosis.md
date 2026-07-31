# Item-expansion gate-order race diagnosis (Issue #18 branch-local report)

## Reported symptom

An intermittent, branch-local failure of

```
python3 -m scripts.upstream_port verify --jobs 2
```

at the `modern-itemexpansion-check-debug` gate, with the underlying error

```
gItemExpansionProbe not found
```

reported to occur only sometimes, and only after the preceding
`modern-linker-check-debug`/`modern-linker-check-release` gates had already
run against the same build root. `gItemExpansionProbe` is the EWRAM probe
symbol defined in `src/expansion_itemtest.c` under
`#if FE8_EXPANSION_ITEMTEST_ENABLED`; `tools/gba-playtest/run_item_expansion_checks.py`'s
`resolve_symbol()` performs an `nm -S` lookup for it before booting anything,
so "not found" specifically means the linked debug ELF that
`modern-itemexpansion-check-debug` picked up did not have the probe compiled
in (or the check ran against a stale/mismatched ELF/object set left over
from the immediately-preceding, cap/itemtest-unset `modern-linker-check-*`
gates).

## What this investigation actually reproduced, and what it did not

**Not reproduced:** despite extensive empirical reproduction attempts
(isolated `MODERN_BUILD_ROOT`s, the real shared default build root, `-j2`,
`-j16`, cold and semi-warm starts, dozens of repeated trials across both
`modern-linker-check-*` → `modern-itemexpansion-check-*` orderings), the
exact reported `gItemExpansionProbe not found` failure could not be made to
happen in this sandbox environment. This report does not claim to have
captured a byte-for-byte live repro of the reported failure, and is
deliberately written so as not to overstate that it did.

**Reproduced (a real, distinct bug of the same general class):** while
running the literal command sequence the report/task asked to be compared
(`expansion-modern-linker-check` debug, in an isolated, freshly created
`MODERN_BUILD_ROOT`, at higher parallelism), `expansion-modern-linker-check`
itself intermittently failed with:

```
error: nm failed for .../shiftcheck/shift-0x40000/shifted.elf: file format not recognized
error: shifted layout verification failed
make: *** [modern.mk:2765: expansion-modern-shifted-check] Error 2
```

Root cause: `expansion-modern-shifted-check` and
`expansion-modern-localization-runtime-shifted-check` are both **undeclared-
order sibling prerequisites** of `expansion-modern-linker-check` (see that
target's own prerequisite list in `modern.mk`). Under `make -jN` with N>1
(exactly what `verify --jobs N` passes through per gate), GNU Make is free
to run sibling prerequisites concurrently. Both targets used to pass the
exact same literal `$(MODERN_SHIFTED_OUTDIR)` as `SHIFTCHECK_OUTDIR` to
`scripts/shiftcheck/modern_shifted_boot.sh`, which links straight to a fixed
`"$OUTDIR/shifted.elf"` path with no temp-file-plus-rename step. Two
concurrent `arm-none-eabi-ld` invocations racing on that one path produced a
torn ELF, which `nm`/`verify_shifted_layout.py` then correctly rejected as
unreadable.

This is the *same class* of bug as commit `92ed1b6b` (a shared,
non-isolated output path torn by concurrent sibling Make recipes,
previously fixed for `expansion_msg_ids.h` via GNU Make 4.3 grouped `&:`
targets) -- just recurring on a different pair of targets/paths that were
not covered by that earlier fix. It is **not** the exact reported symptom
(it fails `modern-linker-check-*` itself, with an unrelated-looking `nm`
message about `shifted.elf`, not `modern-itemexpansion-check-debug` with
`gItemExpansionProbe not found`), so this report does not claim it *is* the
literal cause of the originally reported failure. It is reported and fixed
here because:

1. It is a real, reproducible bug encountered while doing exactly the
   comparison work the task asked for (running the real
   `modern-linker-check-*` gates, isolated, repeated, at `-jN>1`).
2. It demonstrates that sibling-prerequisite races over shared,
   non-isolated build-root output paths **do occur in this exact command**
   (`expansion-modern-linker-check`, the gate immediately preceding
   `modern-itemexpansion-check-*` in `verify`'s own gate order), which is
   directly relevant supporting evidence for the general failure class
   the reported bug belongs to, even without a byte-identical repro.
3. Leaving a known-reproducible race unfixed while only speculatively
   hardening an unconfirmed one would be irresponsible.

## Structural weakness identified and hardened (defensive fix)

Independent of the reproduced shifted-check race, `$(MODERN_ELF)`'s own
link rule was found to guarantee "relink whenever the compiled objects or
the cap/itemtest/config compile-settings changed" **only implicitly**:

```make
$(MODERN_ELF): expansion-modern-link-prepare $(MODERN_ELF_LINK_SETTINGS)
```

`expansion-modern-link-prepare` is `.PHONY`, so GNU Make always reruns it
and, as a direct structural consequence, always reruns `$(MODERN_ELF)`'s own
recipe too. This is empirically correct today (confirmed with a standalone
test Makefile reproducing the same phony-prerequisite-forces-rerun
semantics), and `$(MODERN_COMPILE_SETTINGS)` already correctly participates
as a real, content-addressed prerequisite of every C/data object
(including the `item_id_cap`/`item_expansion_itemtest` fields), so no
object-staleness bug was actually found here either. But the *link* rule's
own "never link stale objects/settings" guarantee rested entirely on that
phony side effect rather than on a direct, explicit dependency edge --
fragile and non-obvious, and one bad refactor away from silently breaking
(e.g. trimming `expansion-modern-link-prepare`'s own prerequisite list for
build-speed, without realizing this rule's correctness depended on it
staying unconditionally phony).

## Fixes applied

1. **`modern.mk`: `$(MODERN_ELF)` now lists `$(MODERN_ALL_OBJECTS)` and
   `$(MODERN_COMPILE_SETTINGS)` as explicit, direct prerequisites**, in
   addition to (not instead of) `expansion-modern-link-prepare`. This turns
   "the link must observe the current cap/itemtest/config compile flags"
   into an ordinary, self-enforcing Make dependency edge instead of a side
   effect of another rule's phoniness. No observable build-output change:
   the link already always reran.
2. **`modern.mk`: `expansion-modern-shifted-check` and
   `expansion-modern-localization-runtime-shifted-check` now write to two
   distinct output directories** (`MODERN_SHIFTED_OUTDIR_BOOT` /
   `MODERN_SHIFTED_OUTDIR_LOCALE`, both derived from the previously-shared
   `MODERN_SHIFTED_OUTDIR`) instead of racing on one shared path. This
   directly fixes the reproduced race (confirmed below).

Both changes are pure hardening / bug fixes to `modern.mk`; no gate, probe,
or test assertion was weakened, reordered, or skipped to make this
"pass" -- `expansion-modern-linker-check`, `expansion-modern-itemexpansion-check`,
and every scenario/fingerprint they assert on are unchanged and still run
in the same order with the same pass/fail criteria.

## Verification of the fix

Before the fix, an isolated cold `MODERN_CONFIG=debug` build of
`expansion-modern-linker-check` at `-j16` failed as shown above (reproduced
on demand). After the fix, the identical isolated cold build (fresh
`MODERN_BUILD_ROOT`, same `-j16`) passed cleanly (`rc=0`, zero
`make: ***`/`Error 2`/"file format not recognized" occurrences in the
log), and both `MODERN_SHIFTED_OUTDIR_BOOT`/`MODERN_SHIFTED_OUTDIR_LOCALE`
were observed to be created as the expected, separate directories.

The full reported gate sequence -- `expansion-modern-linker-check` (debug,
then release), then `expansion-modern-itemexpansion-check` (debug, then
release, with `FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1
EXPANSION_STARTER_CONTENT=1 EXPANSION_MECHANICS_HOOKS=1
EXPANSION_MECHANICS_SAMPLE=1`) -- was run, once, against a single isolated
`MODERN_BUILD_ROOT` (so every gate after the first necessarily reused that
same build root's objects/ELF, exactly like `verify` does), at `-j2`
(matching `verify --jobs 2`'s own default). All four gates passed;
`arm-none-eabi-nm -S` on the resulting debug ELF confirmed exactly one,
properly defined (non-`U`) `gItemExpansionProbe` symbol. See
`scripts/modernize/tests/test_modern_itemexpansion_gate_order_race.py` for
the permanent, toolchain-gated regression that now runs this exact sequence
and asserts on it.

## Regression added

`scripts/modernize/tests/test_modern_itemexpansion_gate_order_race.py`
(new file, following the style precedent of
`test_modern_localization_header_bootstrap.py` from commit `92ed1b6b`):

* Fast, always-run, toolchain-independent structural tests pinning both
  `modern.mk` edits above (the explicit `$(MODERN_ELF)` prerequisites, and
  the two distinct `SHIFTCHECK_OUTDIR` variables/call sites) so neither can
  silently regress without a test failure.
* One real, toolchain-and-libmGBA-gated integration test that runs the
  actual reported gate sequence once, end to end, in a single isolated
  `MODERN_BUILD_ROOT`, and asserts each gate's exit code plus a direct `nm`
  lookup of `gItemExpansionProbe` on the resulting ELF (never trusting the
  higher-level scripts' own exit code alone for that specific assertion).

**Cost note:** the real integration test costs roughly 10-12 minutes on
this environment's toolchain (dominated by the two full
`expansion-modern-linker-check` runs, which each aggregate ~20 boot/runtime
sub-checks). It is deliberately run **once** per config pairing rather than
in a repeated stress loop -- like the pre-existing
`test_modern_localization_header_bootstrap.py` real-build tests, it is
toolchain-gated (skips cleanly without `arm-none-eabi-gcc`/`ld`/`objcopy`/
`nm` or without a working libmGBA backend) and is not wired into
`scripts/upstream_port/verify.py`'s automated gate list -- following the
same precedent, `scripts/modernize/tests/*.py` files other than
`test_build_default_lane.py`/`test_quickstart.py` are manual/ad hoc
regressions, run on demand (see `docs/upstream-porting.md`'s own gate list,
which only names those two files explicitly), not part of the CI-mirrored
gate sequence itself. A much larger, repeated (20+ iteration) empirical
stress loop was used ad hoc during the investigation described above but is
intentionally **not** checked in as a standing regression, to keep ongoing
cost reasonable.

## Honest residual uncertainty

Because the exact reported `gItemExpansionProbe not found` failure was not
reproduced live, it remains possible that its true trigger is something
this investigation did not encounter locally (a different environment's
filesystem timestamp granularity, a different, older GNU Make version's
scheduling behavior, transient CI-runner resource contention producing a
different interleaving than anything tried here, or an ambient
`FE8_ITEM_ID_CAP`/`FE8_EXPANSION_ITEMTEST` environment-variable leak into a
`verify.py` gate that does not itself set one -- see `_split_env_prefix` in
`scripts/upstream_port/verify.py`, noted as a theoretical but unconfirmed
vector). The fixes above are submitted as genuine, defensible hardening of
the `modern.mk` DAG (one from an actually-reproduced sibling-output race in
the same command, one closing a real-but-previously-implicit-only
dependency edge on the exact rule the reported symptom's object set flows
through), plus a permanent regression exercising the reported gate order
end to end -- not as a claim that the reported failure's root cause has
been conclusively proven and eliminated.
