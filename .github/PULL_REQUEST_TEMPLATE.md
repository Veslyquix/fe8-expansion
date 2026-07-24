## Frozen scope

- Issue: <!-- exact https://github.com/laqieer/fireemblem8-expansion/issues/N -->
- [ ] Scope is itemized and non-goals are explicit.

## Validation commands

List every command exactly as run from the repository root (no prose, no chaining):

```
python3 scripts/artifact_guard.py --revision HEAD
python3 -m unittest discover -s scripts/artifact_guard_tests -p 'test_*.py'
make generated-data-check
make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs
make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs
```

- [ ] All commands above (or the subset relevant to this change) pass.
- Runtime/playtest evidence (scenario, environment, command, result): <!-- required only when behavior changes -->

## Compatibility impact

- [ ] Save format / migration
- [ ] Generated data and committed inventories
- [ ] Debug configuration
- [ ] Release configuration

## Baseline/fingerprint review

- [ ] No `reports/baseline/`, `tools/gba-playtest/fingerprints/`, or
      `scripts/shiftcheck/tas/fingerprint.lua` path changed; **or**
- [ ] Such a change is intentional, investigated, and explained above (see
      [`docs/issue-resolution-policy.md`](../docs/issue-resolution-policy.md)).

## Prohibited artifacts

- [ ] No ROM, save, savestate, ROM patch, or other build/runtime artifact is
      newly tracked. `python3 scripts/artifact_guard.py --revision HEAD` was run.
- [ ] I am not claiming any tracked source asset (e.g. `graphics/`, `sound/`)
      is legally cleared; see [`docs/issue-resolution-policy.md`](../docs/issue-resolution-policy.md).

## Review boundary

> Passing CI or the artifact checker is not human approval. CODEOWNERS can
> request a reviewer but only branch protection/rulesets can require it.

- [ ] A human review is requested for protected-path changes.
