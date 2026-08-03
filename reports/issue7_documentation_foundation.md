# Issue #7 closure evidence -- documentation foundation

**Status: candidate closure-mapping evidence for reviewer/verifier. GitHub
issue #7's state is not asserted or changed by this document, and no CI
run URL or merged state is claimed here.** This report maps issue #7's
own scope checklist to concrete, current-scope files, code, and tests in
this repository. The current source tree includes merged implementation for
#6, #10, #11, #13, and #18, documented in
[`docs/framework-support.md`](../docs/framework-support.md#merged-framework-contracts)
and [`docs/architecture.md`](../docs/architecture.md#public-extension-boundaries),
with narrow non-goals retained. Issue #9 remains future-only release work.
This source-state summary does not assert any GitHub issue state, and this
report does not itself claim full closure of issue #7.


## Current integration section (supersedes earlier status/gate snapshots)

This section describes the current master integration used for the issues
#7/#17 candidate, and supersedes later historical statements that call #6 or
#18 unmerged or describe 12 verifier gates. It does not close either issue.

| Current requirement | Current source of truth |
| --- | --- |
| Install -> configure -> author -> build -> test -> debug | `README.md`, `CONTRIBUTING.md`, `docs/README.md`, `docs/quickstart.md`, then `docs/config_identity.md`, `docs/generated_data_tutorial.md`, `docs/localization.md`, `docs/debugtools.md`, and `tools/gba-playtest/README.md` |
| Exact documentation inventory | `scripts/check_docs.py` discovers the case-insensitive `.md`/`.markdown`/`.mdown`/`.mkd`/`.mkdn` set and requires exact set equality with `docs/documentation-inventory.md`; no drifting count is policy input |
| External links | Every merged Markdown HTTP(S) occurrence must match `docs/external-link-registry.md`; this is offline coverage, never an online-link claim |
| Merged #6 coverage | `docs/starter_features.md`, `docs/config_identity.md`, `docs/generated_data_tutorial.md`, `docs/id_space.md`, and support/API tables document all four default-off flags, dependencies, typed content/mechanics, QoL, matrices, budgets, save/legal boundaries |
| Merged #18 coverage | `docs/localization.md`, `docs/save_format.md`, `docs/config_identity.md`, architecture/support/API tables document stable IDs/catalogs, en/qps-ploc authoring, config/defines, prefs/epoch-2 precedence/migration, selector/settings/reset, budgets and matrices |
| Gate truth | `scripts/upstream_port/verify.py` remains exactly 10 ordered gates. The standalone docs workflow step is the eleventh issues #7/#17 closure gate. Master's localization host step remains required workflow-only coverage; localization runtime checks remain inside the linker gates. |
| Future #9 boundary | Only current issue-resolution governance and an unfilled migration template exist; no release automation/tag/changelog/artifact/updater claim is made |

### Current integration validation evidence

All results below were reproduced in this integration worktree; counts are
point-in-time output, not policy constants:

- `python3 -m unittest discover -s scripts/docs_check_tests -v` -> 182 tests,
  `OK`.
- `python3 scripts/check_docs.py --check --check-examples` -> 72 recognized
  Markdown files, 0 findings; all three safe help examples passed. This made
  no network requests.
- `GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover -s
  tools/gba-playtest/tests -v` -> 407 tests, `OK (skipped=11)`.
- `python3 -m unittest discover -s scripts/generated_data/tests -v` -> 633
  tests, `OK`; `make generated-data-check` -> 13 tables / 722 records, no
  table/manifest/consumer-census/ID-space drift.
- `python3 -m unittest discover -s tests/upstream_port -v` -> 146 tests,
  `OK`, including live workflow argv/order and both standalone-step locks.
- `python3 -m unittest discover -s scripts/modernize/tests -v` -> 530 tests,
  `OK (skipped=1)`. Because temporary files were required to remain inside
  this worktree, the first run exposed two Git-parent-discovery assertions;
  the final run set `GIT_CEILING_DIRECTORIES` at the in-worktree scratch root
  and passed without writing to `/tmp` or changing tests.
- `python3 -m unittest discover -s scripts/localization/tests -p
  'test_*.py' -v` -> 82 tests, `OK`.
- Targeted defaults: `test_build_default_lane.py` -> 15 tests, `OK`;
  `test_quickstart.py` -> 15 tests, `OK`.
- `python3 -m scripts.upstream_port verify --dry-run --jobs 2` -> exactly 10
  ordered `SKIPPED(dry-run)` entries, with the issue #6 starter-content args
  on gates 9-10. The workflow-only docs check remains the eleventh issues
  #7/#17 closure gate; the localization host step is separately preserved.
- Safe Make probes resolved the live object-print targets, localization
  generation target, and compile-only `apcs-gnu` cohort; the linked
  `apcs-gnu` ELF probe failed with the documented AAPCS-only guard.


## Scope recap

Issue #7 asks that this repository's documentation stop being a
one-time, ad-hoc rewrite and instead become an **authoritative,
100%-inventoried, drift-resistant governance system**: every Markdown
file accounted for, every internal link/anchor verified, every external
link classified, stale command/path references caught before merge, and
CI-enforced so regressions cannot land silently.

## Checklist -> evidence mapping

| Checklist item | Evidence | Status |
| --- | --- | --- |
| Modern-framework-first top-level docs (README/CONTRIBUTING) | [`README.md`](../README.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md) (rewritten to lead with the modern `arm-none-eabi`/AAPCS release lane, archival agbcc lane as an explicit side lane) | Candidate current-scope |
| Architecture map for new contributors | [`docs/architecture.md`](../docs/architecture.md) | Candidate current-scope |
| Supported host/toolchain/target matrix | [`docs/framework-support.md`](../docs/framework-support.md) | Candidate current-scope |
| Document generated data schemas and authoring workflows | [`docs/generated_data.md`](../docs/generated_data.md) (schema/validation/generation design reference, issue #5) and [`docs/generated_data_tutorial.md`](../docs/generated_data_tutorial.md) (contributor authoring walkthrough); JSON sources under `src/data/*.json` + `scripts/generated_data/*/schema.py`; `make generated-data-validate`/`generated-data-generate`/`generated-data-check` | Candidate current-scope |
| Publish public APIs, hooks, debug tooling, tests, and compatibility policy | [`docs/README.md`](../docs/README.md#public-api-index-source-of-truth-by-subsystem) (Public API index entry-point table); [`docs/debugtools.md`](../docs/debugtools.md) (debug-tools subsystem, issue #11) plus `include/expansion_debugtools.h` (hook/registration API) and its own [`Host tests`](../docs/debugtools.md#host-tests) section; [`docs/project-governance.md`](../docs/project-governance.md#support-and-compatibility-policy) (Support and compatibility policy) | Candidate current-scope |
| Bridge guide for decomp-base/agbcc contributors | [`docs/migration-from-decomp.md`](../docs/migration-from-decomp.md) | Candidate current-scope |
| Archival decomp workflow preserved, clearly scoped | [`docs/archival-decomp.md`](../docs/archival-decomp.md) | Candidate current-scope |
| Governance entry point (security/copyright/credits/compatibility) | [`docs/project-governance.md`](../docs/project-governance.md) | Candidate current-scope |
| Version-migration scaffolding for future releases | [`docs/release-migration-template.md`](../docs/release-migration-template.md) | Template (intentionally unfilled) |
| Full documentation index / learning paths | [`docs/README.md`](../docs/README.md) | Candidate current-scope |
| **100% Markdown inventory, exact coverage, no drift** | [`docs/documentation-inventory.md`](../docs/documentation-inventory.md), enforced by [`scripts/check_docs.py`](../scripts/check_docs.py) | Candidate current-scope, CI-enforced |
| Deterministic internal link/anchor verification | `scripts/check_docs.py`'s `resolve_internal_link`/`compute_heading_slugs` (GitHub-slug-compatible, stdlib-only) + [`scripts/docs_check_tests/test_check_docs.py`](../scripts/docs_check_tests/test_check_docs.py) | Candidate current-scope, CI-enforced |
| External-link registry (no network re-check, but no unregistered/misclassified URL) | [`docs/external-link-registry.md`](../docs/external-link-registry.md) | Candidate current-scope, CI-enforced |
| Stale command/path denylist + Makefile-target existence check | `scripts/check_docs.py`'s `STALE_PHRASE_RULES` + `parse_make_targets`/`make_target_exists` (static Makefile parse, recipe never executed) | Candidate current-scope, CI-enforced |
| Safe, executable doc examples | `scripts/check_docs.py --check-examples` (quickstart/upstream-port/check-docs `--help`, zero-ROM/zero-network) | Candidate current-scope, CI-enforced |
| Fast-fail CI wiring before expensive build/tools steps | `.github/workflows/build.yml`'s "Check documentation" step (added after the artifact guard, before dependency install/build) | Candidate current-scope |
| Stale AI-agent-instruction pointer fixed | [`.github/copilot-instructions.md`](../.github/copilot-instructions.md) **and** [`CLAUDE.md`](../CLAUDE.md) (both: decomp tutorial pointer corrected to `docs/archival-decomp.md`; build-command framing corrected to lead with the modern `make`/`make all` default, archival `make legacy`/`make fireemblem8.gba` kept as an explicit, separate lane) | Candidate current-scope |

## Acceptance criteria -> evidence mapping

The Acceptance criteria section of issue #7 (verbatim, via `gh issue view 7
--json body`) is mapped below to the final, merged evidence this repository
actually contains today -- not a paraphrase and not a self-invented
substitute:

| Acceptance criterion (verbatim, issue #7) | Evidence & anchors | Validation command(s) / result |
| --- | --- | --- |
| "A new contributor can install, configure, author content, build, test, and debug using repository documentation alone." | [`docs/README.md`](../docs/README.md#learning-paths) chains [`docs/quickstart.md`](../docs/quickstart.md) (install/configure/build) -> [`docs/architecture.md`](../docs/architecture.md) (orient) -> [`docs/generated_data_tutorial.md`](../docs/generated_data_tutorial.md) (author content) -> [`CONTRIBUTING.md`](../CONTRIBUTING.md) (test: fast checks / full gates) -> [`docs/debugtools.md`](../docs/debugtools.md) (debug) | `scripts/quickstart.sh --help` is one of the three commands `--check-examples` actually executes; see the last row for the reproduced result |
| "Documentation clearly separates supported expansion workflows from archival decomp workflows." | [`docs/migration-from-decomp.md`](../docs/migration-from-decomp.md) (bridge guide) and [`docs/archival-decomp.md`](../docs/archival-decomp.md), listed by [`docs/README.md`](../docs/README.md#full-document-list-and-status) as "Current, archival scope"; the split is governed by [`docs/issue-resolution-policy.md`](../docs/issue-resolution-policy.md#supported-modern-path-vs-archival-decomp-path) | The STALE_PHRASE_RULES denylist in `scripts/check_docs.py` rejects the pre-rewrite claim that the decomp tutorial lives in `CONTRIBUTING.md` (moved to `docs/archival-decomp.md`); see the last row for the reproduced 0-finding result |
| "Public APIs and compatibility guarantees are explicit." | [`docs/README.md`](../docs/README.md#public-api-index-source-of-truth-by-subsystem) (Public API index table); [`docs/project-governance.md`](../docs/project-governance.md#support-and-compatibility-policy); [`docs/architecture.md`](../docs/architecture.md#public-extension-boundaries); [`docs/framework-support.md`](../docs/framework-support.md#merged-framework-contracts) | `python3 scripts/check_docs.py` resolves every internal anchor cited in this row (fail-closed on any broken anchor); see the last row for the reproduced result |
| "Documentation commands/examples are CI-tested where practical." | the "Check documentation (issues #7/#17)" step in `.github/workflows/build.yml`; [`scripts/check_docs.py`](../scripts/check_docs.py) `--check --check-examples`; [`scripts/docs_check_tests/`](../scripts/docs_check_tests/) | Reproduced directly in this worktree: `python3 -m unittest discover -s scripts/docs_check_tests -v` -> `Ran 174 tests ... OK`; `python3 scripts/check_docs.py --check --check-examples` -> `check_docs: OK -- 65 Markdown file(s) checked, 0 findings.` plus `example[quickstart-help]: ok`, `example[upstream-port-help]: ok`, `example[check-docs-help]: ok` (point-in-time counts -- re-run both commands against the commit under review rather than trusting the numbers frozen here) |

## What this explicitly does not claim

- **Not a GitHub issue-closure decision.** Per
  [`docs/issue-resolution-policy.md`](../docs/issue-resolution-policy.md#issue-closure-evidence),
  issue closure is a human decision recorded in the linked PR/issue
  thread -- this report is evidence for that decision, not the decision
  itself.
- **Update (issues #7/#17 integration merge): issues #10, #11, and #13 are
  now merged into `master` with final, supported public interfaces**,
  superseding the original (pre-merge) framing of this bullet below.
  [`docs/architecture.md`](../docs/architecture.md#public-extension-boundaries)
  and [`docs/framework-support.md`](../docs/framework-support.md#merged-framework-contracts)
  now document each interface's supported surface and narrow, explicit
  non-goals (not an open/deferred scope); this documentation-foundation
  work does not itself implement or close those issues -- it documents
  what the separately-merged code already does. In particular:
  - **Issue #10** (typed IDs / extensible content-ID contracts/limits) --
    the DEFAULT/ACTIVE contract is documented in
    [`docs/id_space.md`](../docs/id_space.md); see
    [`reports/issue10_closure.md`](issue10_closure.md) for the closure evidence
    and its own explicit non-goals (no class/chapter/unit/character ID
    widening; no save-migration tooling built yet).
  - **Issue #11** (debug-tools extension/config/safety interface) --
    the full registration API, hub entry points, five bounded tools, and
    diagnostics are documented in
    [`docs/debugtools.md`](../docs/debugtools.md); its own "Remaining #11
    scope" section (not this report) is authoritative for the few
    remaining narrow non-goals.
  - **Issue #13** (regression-scenario library/host matrix/verification
    policy) -- `tools/gba-playtest` now provides the full deterministic
    scenario suite and host-only/normal run-mode policy; see
    [`reports/gba_playtest_issue13_closure.md`](gba_playtest_issue13_closure.md).
- **Not a claim that every historical/archival document was re-verified
  against `master`.** `docs/documentation-inventory.md`'s `historical`
  status entries are explicitly point-in-time and are not re-verified by
  this work.

## Validation run for this report

See [`reports/issue17_documentation_audit.md`](issue17_documentation_audit.md)
for the full command-by-command verification evidence (doc unittests,
`scripts/check_docs.py --check --check-examples`, CI YAML structural
audit, and the other commands in this task's verification set); this
report does not duplicate that command log.
