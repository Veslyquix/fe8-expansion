# Issue resolution policy

This is the single authoritative Wave 0 governance document for closing
issues and reviewing changes in this repository. It replaces the earlier
Wave 0 candidate's machine evidence schema, baseline diff engine, and
closure-discovery tooling with GitHub-native review controls plus one small,
auditable checker (`scripts/artifact_guard.py`) that reads immutable Git
objects.

## Issue closure evidence

Closing an issue is a human decision, not a checker's output. Before closing,
the linked pull request or issue comment should record, in plain prose:

- the frozen, itemized scope and any explicit non-goals;
- every validation command that was actually run, and its result (paste
  output or link a CI run; do not summarize as "tests pass");
- runtime/playtest evidence when the change can affect boot, save, or
  gameplay behavior: the scenario, environment, exact command, and result;
- which of save format, generated data, debug build, and release build were
  affected, and how they were checked.

There is intentionally **no machine-readable evidence schema or validator**.
Human-readable evidence in the issue/PR thread, reviewed by a person, is the
contract. See [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
for the checklist shape.


Documentation itself is fail-closed in CI: every recognized Markdown extension
is inventoried, links/anchors and offline external-URL registry coverage are
checked, and documented Make targets must exist. The fixed upstream-port
verifier mirrors all 11 current-master gates;
the independent documentation workflow gate is additional and deliberately
not part of `verify.gates()`. Passing either is evidence, not an issue-closure
decision.

## Baseline and fingerprint review

`reports/baseline/`, `tools/gba-playtest/fingerprints/`, and
`scripts/shiftcheck/tas/fingerprint.lua` are reviewed oracles, not generated
output that tooling should silently normalize. A mismatch is a signal to
investigate the change, not to regenerate the fingerprint. Any pull request
that touches these paths must explain, in the PR description, why the oracle
itself is changing and what was independently verified. `CODEOWNERS` names
`@laqieer` for these paths so GitHub requests that reviewer; it does not by
itself gate merging (see below).

This repository does **not** ship an automated baseline diff/history engine.
Reviewing a baseline/fingerprint change is a human judgment call assisted by
`git diff` and normal CI, not a bespoke comparison tool.

## Legal and copyright boundary

`scripts/artifact_guard.py` rejects ROM/GBA and ELF files, saves/SRAM,
savestates, patches, generated `.lz`/`.4bpp`/`.8bpp`/`.gbapal` files,
prohibited path segments such as `build/`, and the exact repository-root
outputs `fireemblem8.map`, `fireemblem8_relocs.map`, and `objects.lst`. It does
not reject arbitrary `.map`, `.a`, `.d`, or `.hex` files, and narrowly permits
the repository's already-tracked source-asset classes (for example
`.png`/`.agbpal`/`.pal`/`.mar`/`.tmap`/`.tsa` under `graphics/`, `.png` under
`preview/`, and `.aif`/`.mid`/`.pcm` under `sound/`) so that ordinary
decompilation and graphics/sound source work keeps functioning.

**This is a structural-compatibility allowance only.** Passing the checker
does not mean any tracked asset is confirmed to be legally cleared,
appropriately licensed, or authorized for redistribution. No Wave 0 change
makes, or should be read as making, that legal determination. Contributors
and reviewers who have provenance/license concerns about a specific tracked
file should raise them as their own issue rather than relying on this
checker's silence.

## Enforcement: branch protection, not CODEOWNERS alone

`CODEOWNERS` can request `@laqieer` as a reviewer for the paths listed in
[`.github/CODEOWNERS`](../.github/CODEOWNERS). By itself, **CODEOWNERS does
not require or block anything** — a repository administrator must configure
GitHub branch protection or a repository ruleset on `master` that requires a
pull request, requires that code-owner review, and requires the `Build CI`
status, for any of this to be enforced. A green `Build CI` run or a passing
`scripts/artifact_guard.py` is not, by itself, human approval.

## Supported modern path vs. archival decomp path

Per [`README.md`](../README.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md),
this repository has two build paths:

- the **supported modern path** — `arm-none-eabi` GCC/AAPCS,
  `make expansion-modern-*` targets, no byte-identical requirement to the
  original ROM; this is what CI builds and boot-verifies; and
- the **archival/decomp agbcc path** — the original `fireemblem8.gba` target,
  used only for decomp-matching work described in `CONTRIBUTING.md`, and not
  the default quickstart or CI path.

Issue evidence and reviewers should say which path a change targets, since
compatibility expectations (ABI, struct layout, legacy constraints) differ
between them.

## No source-release allowlist in Wave 0

Wave 0 makes no decision about which files constitute a distributable
"source release," and `scripts/artifact_guard.py` intentionally implements no
release manifest or allowlist beyond the narrow tracked-source-asset
allowance above. That provenance/release-scope decision, if the project
wants one, belongs to a future, separately-tracked change (issue #9). Treat
any resemblance between this policy and a release manifest as unintentional
and out of scope.
