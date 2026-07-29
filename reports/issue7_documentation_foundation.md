# Issue #7 closure evidence -- documentation foundation

**Status: candidate closure-mapping evidence for reviewer/verifier. GitHub
issue #7's state is not asserted or changed by this document, and no CI
run URL or merged state is claimed here.** This report maps issue #7's
own scope checklist to concrete, current-scope files, code, and tests in
this repository, and calls out exactly what remains open (issues #10,
#11, #13 follow-up work) rather than claiming full closure.

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

## What this explicitly does not claim

- **Not a GitHub issue-closure decision.** Per
  [`docs/issue-resolution-policy.md`](../docs/issue-resolution-policy.md#issue-closure-evidence),
  issue closure is a human decision recorded in the linked PR/issue
  thread -- this report is evidence for that decision, not the decision
  itself.
- **Update (issues #7/#17 integration merge): issues #10, #11, and #13 are
  now merged into `master` with final, supported public interfaces**,
  superseding the original (pre-merge) framing of this bullet below.
  [`docs/architecture.md`](../docs/architecture.md#public-extension-boundaries--merged-101113-vs-active-6918)
  and [`docs/framework-support.md`](../docs/framework-support.md#merged-framework-contracts-issues-10-11-13)
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
