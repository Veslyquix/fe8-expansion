# Documentation index

This is the authoritative entry point for this repository's documentation.
The project's default, supported path is a **modern `arm-none-eabi`
GCC/AAPCS release framework**; the original agbcc-based decompilation
workflow is preserved as an explicit, clearly separated **archival** lane.
See [`../README.md`](../README.md) for the top-level project overview.

## Start here

| If you want to... | Read |
| --- | --- |
| Build the project for the first time | [`quickstart.md`](quickstart.md) |
| Understand what's actually supported (hosts, toolchains, targets) | [`framework-support.md`](framework-support.md) |
| Get the architecture map before diving into source | [`architecture.md`](architecture.md) |
| Author game content (characters/classes/items/etc.) | [`generated_data_tutorial.md`](generated_data_tutorial.md) |
| Enable/extend starter content, mechanics, or Threat Range QoL | [`starter_features.md`](starter_features.md) |
| Author expansion-localized UI text/locales | [`localization.md`](localization.md) |
| Contribute code/docs and know the review process | [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`project-governance.md`](project-governance.md) |
| Come from the old decomp-base/agbcc workflow | [`migration-from-decomp.md`](migration-from-decomp.md) |
| Do byte-for-byte decomp-matching work | [`archival-decomp.md`](archival-decomp.md) |
| Write a future version-to-version migration guide | [`release-migration-template.md`](release-migration-template.md) |

## Learning paths

**New contributor, modern framework (most people):**
1. [`quickstart.md`](quickstart.md) — install and boot-verify a build.
2. [`config_identity.md`](config_identity.md) — configure identity, debug/release, starter flags, and locales.
3. [`architecture.md`](architecture.md) — orient yourself.
4. [`generated_data_tutorial.md`](generated_data_tutorial.md) and
   [`localization.md`](localization.md) — author typed content and expansion UI text.
5. [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — run host checks, both ROM gates, and record PR evidence.
6. [`debugtools.md`](debugtools.md) and
   [`../tools/gba-playtest/README.md`](../tools/gba-playtest/README.md) — debug bounded runtime behavior.

**Coming from the old decomp-first workflow:**
1. [`migration-from-decomp.md`](migration-from-decomp.md) — what changed and why.
2. [`archival-decomp.md`](archival-decomp.md) — if your goal is still byte-for-byte matching, this is unchanged and still supported *for that purpose*.

**Maintaining framework identity, saves, typed IDs, or debug tooling:**
1. [`config_identity.md`](config_identity.md)
2. [`save_format.md`](save_format.md)
3. [`id_space.md`](id_space.md) — typed IDs / DEFAULT vs ACTIVE contract (issue #10)
4. [`debugtools.md`](debugtools.md)

**Tracking or applying upstream decomp changes:**
1. [`upstream-porting.md`](upstream-porting.md)

## Public API index (source of truth by subsystem)

Concrete entry points a downstream contributor actually calls/includes/
extends -- each row links the reference doc, not aspirational; issue
numbers mark merged (closed) contracts only:

| Subsystem | Public entry points | Reference |
| --- | --- | --- |
| Generated data authoring | JSON sources under `src/data/*.json` + table schemas in `scripts/generated_data/*/schema.py`; `make generated-data-check`/`generated-data-active-heal-check` | [`generated_data.md`](generated_data.md), [`generated_data_tutorial.md`](generated_data_tutorial.md) |
| Typed IDs / caps (issue #10) | `include/id_space.h` (DEFAULT), `build/generated/data/id_space_active.h` (ACTIVE), `FE8_ITEM_ID_CAP` | [`id_space.md`](id_space.md), [`../reports/id_space_audit.md`](../reports/id_space_audit.md) |
| Config / ROM identity | `struct ExpansionMetadata` (`include/expansion_metadata.h`), `EXPANSION_SAVE_COMPAT_EPOCH` | [`config_identity.md`](config_identity.md), [`save_format.md`](save_format.md) |
| Debug-tools extension (issue #11) | Action-registration API (`include/expansion_debugtools.h`), `FE8_EXPANSION_DEBUGTOOLS_ENABLED` | [`debugtools.md`](debugtools.md) |
| Starter features (issue #6) | Four default-off flags; `include/expansion_mechanics.h`; `include/expansion_starter_content.h`; danger-overlay menu | [`starter_features.md`](starter_features.md) |
| Localization (issue #18) | `ExpansionLocaleId`/`ExpansionMsgId`, `texts/expansion/`, prefs + selector/settings APIs | [`localization.md`](localization.md), [`save_format.md`](save_format.md) |
| Runtime test harness (issue #13) | JSON scenario format + fingerprints, `GBA_PLAYTEST_HOST_ONLY` | [`../tools/gba-playtest/README.md`](../tools/gba-playtest/README.md) |
| Upstream-port review tooling | `python3 -m scripts.upstream_port {scan,drift,verify,update-state}` | [`upstream-porting.md`](upstream-porting.md) |
| Proc/runtime core | `include/proc.h` (`struct Proc`, `struct ProcCmd[]`) | [`architecture.md`](architecture.md) |

Not a public API today: issue #9's future versioned-release/downstream-
upgrade tooling. The repository currently has no release automation, tags/
changelog contract, versioned artifact pipeline, or downstream updater; the
migration template is scaffolding only.

## Documentation governance

This document is the human-oriented narrative index. The **machine-checked,
exact-coverage registry** of every Markdown file in this repository (owner,
status, scope) is [`documentation-inventory.md`](documentation-inventory.md);
external URLs used across all docs are classified in
[`external-link-registry.md`](external-link-registry.md). Both are enforced
by [`scripts/check_docs.py`](../scripts/check_docs.py) (stdlib-only,
zero-network) in CI -- see its own `--help` and
[`scripts/docs_check_tests/`](../scripts/docs_check_tests/) for the checker
and its test suite. Candidate closure-mapping evidence for the documentation
governance work itself lives in
[`reports/issue7_documentation_foundation.md`](../reports/issue7_documentation_foundation.md)
and
[`reports/issue17_documentation_audit.md`](../reports/issue17_documentation_audit.md)
-- neither claims a GitHub issue is closed; see
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md#issue-closure-evidence).

## Full document list and status

| Document | Status | Scope |
| --- | --- | --- |
| [`quickstart.md`](quickstart.md) | Current | One-command setup, modern default + archival `--legacy` path |
| [`framework-support.md`](framework-support.md) | Current | Supported hosts/toolchains/targets/outputs |
| [`architecture.md`](architecture.md) | Current | Concise architecture map + later integration slots |
| [`project-governance.md`](project-governance.md) | Current | Contribution/security/copyright/credits/compatibility policy |
| [`migration-from-decomp.md`](migration-from-decomp.md) | Current | Decomp-base/agbcc → modern framework bridge |
| [`release-migration-template.md`](release-migration-template.md) | Template | Fill in for a real future version migration |
| [`archival-decomp.md`](archival-decomp.md) | Current, archival scope | Unsupported-for-releases decomp-matching workflow |
| [`config_identity.md`](config_identity.md) | Current | Config surface + ROM identity fingerprint (issue #8) |
| [`save_format.md`](save_format.md) | Current | Save format + compatibility gate (issue #2) |
| [`id_space.md`](id_space.md) | Current | Typed-ID DEFAULT vs ACTIVE contract, cap switching (issue #10) |
| [`debugtools.md`](debugtools.md) | Current | Debug-tools subsystem, merged (issue #11); see its "Remaining #11 scope" for the few narrow non-goals |
| [`generated_data.md`](generated_data.md) | Current, reference | Full generated-data design reference (issue #5) |
| [`generated_data_tutorial.md`](generated_data_tutorial.md) | Current, tutorial | Contributor-facing generated-data walkthrough |
| [`starter_features.md`](starter_features.md) | Current | Four opt-in flags, typed mechanics/content API, QoL and matrices (issue #6) |
| [`localization.md`](localization.md) | Current | Stable locale/message IDs, authoring, prefs/UI, budgets and matrices (issue #18) |
| [`documentation-inventory.md`](documentation-inventory.md) | Current | Exact recognized-Markdown inventory |
| [`external-link-registry.md`](external-link-registry.md) | Current | Offline URL ownership/status coverage |
| [`upstream-porting.md`](upstream-porting.md) | Current | Canonical upstream drift tooling (issue #12) |
| [`issue-resolution-policy.md`](issue-resolution-policy.md) | Current, authoritative | Issue closure / review / legal-boundary governance |
| [`dump_extraction_plan.md`](dump_extraction_plan.md) | Archival | Raw-blob-to-source extraction workflow |
| [`lz_suffix_diagnostic.md`](lz_suffix_diagnostic.md) | Archival | Hidden-asset diagnostic technique |
| [`tsa_audit.md`](tsa_audit.md) | Archival, point-in-time | Tilemap data audit snapshot |
| [`banim_asset_extraction.md`](banim_asset_extraction.md) | Archival | Battle-animation asset extraction |
| [`Banim_AnimScr_Decompilation_Report.md`](Banim_AnimScr_Decompilation_Report.md) | Archival | Battle-animation script decompilation report |
| [`Banim_TSA_Preservation_Report.md`](Banim_TSA_Preservation_Report.md) | Archival | Battle-animation TSA preservation report |

"Current" means actively maintained and expected to reflect `master`.
"Archival" means it documents a point-in-time or archival-lane-only
workflow and is not re-verified against the modern framework. "Template"
means it is intentionally unfilled scaffolding.

## Merged contracts and future release slot

Issues **#6**, **#10**, **#11**, **#13**, and **#18** have implementation
merged into the current source tree; this statement does not assert or change
their GitHub issue state. Their supported surfaces and explicit non-goals are
summarized in [`architecture.md`](architecture.md#public-extension-boundaries)
and [`framework-support.md`](framework-support.md#merged-framework-contracts).

Issue **#9** remains future work. Only the current issue-resolution policy and
an explicitly unfilled migration template exist; do not infer release
automation or a current release process from either.
