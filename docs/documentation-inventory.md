# Documentation inventory

This is the machine-checked, exact-coverage registry of **every** file
with a recognized Markdown extension, tracked (or untracked-but-not-
ignored, in a dev worktree) in this repository (see
[`docs/README.md`](README.md) for the human-oriented narrative
index/learning-paths view of the same set). The recognized extension set
is small, explicit, and documented: `.md`, `.markdown`, `.mdown`, `.mkd`, `.mkdn`
(matched case-insensitively -- see
[`scripts/check_docs.py`](../scripts/check_docs.py)'s
`RECOGNIZED_MARKDOWN_EXTENSIONS`); an unrecognized extension (`.txt`,
`.mdx`, ...) is never swept in just because it looks Markdown-adjacent.
`scripts/check_docs.py` parses the delimited block below and fails closed
if:

- any Git-tracked or untracked-but-not-ignored file whose extension is one
  of the recognized Markdown extensions above (discovered from the full
  `git ls-files --cached --others --exclude-standard` listing filtered by
  extension in Python -- not a `*.md`-only pathspec glob, which would
  silently miss any other recognized extension) is missing an entry here,
  or
- any entry here references a recognized-Markdown-extension path that
  doesn't exist/isn't tracked, or
- any entry has an empty owner/scope, or a `status` outside the controlled
  enum below.

Each line is `- path | owner | status | scope` (exactly four
`|`-delimited fields). This is a deliberately small, bespoke,
line-oriented format -- not YAML/JSON and not parsed by any third-party
Markdown library, so it stays stdlib-parseable and diff-friendly.

## Status enum

| Status | Meaning |
| --- | --- |
| `current` | Authoritative, actively maintained, expected to reflect `master`. |
| `historical` | Archival / point-in-time; not re-verified against `master`. |
| `generated` | Machine-generated report/inventory -- never hand-edit its content (only this registry's metadata *about* it). |
| `subsystem-reference` | Deep reference scoped to one subsystem/tool, not part of the top-level learning path. |
| `deprecated` | Superseded; kept only for compatibility/history. |
| `evidence` | Issue/closure *candidate* evidence report -- explicitly not a closure claim. |
| `template` | Intentionally unfilled scaffolding. |

## Entries

<!-- DOCS-INVENTORY:BEGIN -->
- README.md | laqieer | current | Top-level project overview, quick start, and doc-index pointer
- CONTRIBUTING.md | laqieer | current | Contribution workflow: prep, fast checks, full gates, PR provenance
- CLAUDE.md | laqieer | current | Claude Code agent guidance for this repository
- .github/copilot-instructions.md | laqieer | current | GitHub Copilot agent guidance for this repository
- .github/PULL_REQUEST_TEMPLATE.md | laqieer | template | PR checklist template shape referenced by CONTRIBUTING.md
- CHANGELOG.md | laqieer | current | Human-readable changelog; its Unreleased section is rendered deterministically from changelog_fragments/*.json (issue #9)
- changelog_fragments/README.md | laqieer | current | Machine changelog-fragment schema, authoring, and validation/render/write contract (issue #9)
- docs/README.md | laqieer | current | Documentation index: learning paths and full document list/status
- docs/documentation-inventory.md | laqieer | current | This file: exact-coverage Markdown inventory consumed by scripts/check_docs.py
- docs/external-link-registry.md | laqieer | current | External-URL host/prefix ownership+status registry consumed by scripts/check_docs.py
- docs/architecture.md | laqieer | current | Concise architecture map + later-integration-slot pointers
- docs/framework-support.md | laqieer | current | Supported hosts/toolchains/targets/outputs matrix
- docs/project-governance.md | laqieer | current | Contribution/security/copyright/credits/compatibility governance entry point
- docs/quickstart.md | laqieer | current | Setup guide: modern default build + archival --legacy path
- docs/migration-from-decomp.md | laqieer | current | Bridge guide: old decomp-base/agbcc workflow -> modern framework
- docs/archival-decomp.md | laqieer | current | Archival-lane decomp-matching workflow, setup, and asset-extraction references
- docs/release-migration-template.md | laqieer | template | Unfilled scaffolding for a future version-to-version migration guide
- docs/config_identity.md | laqieer | current | Config surface + ROM identity fingerprint reference (issue #8)
- docs/save_format.md | laqieer | current | Save format + compatibility gate reference (issue #2)
- docs/id_space.md | laqieer | current | Extensible ID space DEFAULT vs ACTIVE contract reference (issue #10)
- docs/debugtools.md | laqieer | current | Debug-tools full closure reference: action registry, hotkey hub, five bounded tools, diagnostics, safety/release gating, non-goals (issue #11)
- docs/generated_data.md | laqieer | current | Full generated-data platform design/reference (issue #5)
- docs/generated_data_tutorial.md | laqieer | current | Contributor-facing generated-data authoring walkthrough
- docs/starter_features.md | laqieer | current | Four default-off starter flags, typed mechanics/content API, QoL, and runtime matrices (issue #6)
- docs/localization.md | laqieer | current | Stable locale/message IDs, catalog authoring, prefs/UI, budgets, and runtime matrices (issue #18)
- docs/upstream-porting.md | laqieer | current | Canonical upstream-port tracking tooling reference (issue #12)
- docs/issue-resolution-policy.md | laqieer | current | Wave 0 issue closure / review / legal-boundary governance baseline
- docs/release_process.md | laqieer | current | Authoritative release-rehearsal/publication-eligibility process contract (issue #9)
- docs/public_api_policy.md | laqieer | current | Public API/SemVer scope and branch/tag conventions for this pre-1.0 project (issue #9)
- docs/migration_registry.md | laqieer | current | EXPANSION_SAVE_COMPAT_EPOCH transition registry: mechanical-vs-manual migrations (issue #9)
- docs/release_closure_candidate.md | laqieer | evidence | Issue #9 closure-candidate evidence report; not a closure claim or publication approval
- docs/dump_extraction_plan.md | laqieer | historical | Now-completed dump/ raw-blob-to-source extraction workflow
- docs/lz_suffix_diagnostic.md | laqieer | historical | Point-in-time hidden-asset LZ diagnostic technique
- docs/tsa_audit.md | laqieer | historical | Point-in-time tilemap (TSA) data audit snapshot
- docs/banim_asset_extraction.md | laqieer | historical | Battle-animation asset extraction workflow record
- docs/Banim_AnimScr_Decompilation_Report.md | laqieer | historical | Battle-animation script decompilation report
- docs/Banim_TSA_Preservation_Report.md | laqieer | historical | Battle-animation TSA preservation report
- githooks/README.md | laqieer | subsystem-reference | Local git-hook build/shiftability gates
- preview/README.md | laqieer | subsystem-reference | TSA preview-image generation, preview-only, not part of the ROM build
- reports/baseline/README.md | laqieer | subsystem-reference | baseline.json machine-readable matching-build evidence contract
- reports/modernize/inventory.md | laqieer | generated | Auto-generated modern-compiler blocker inventory (scripts/modernize/audit.py)
- reports/blob_extraction_classification.md | laqieer | generated | Auto-generated blob extraction classification (scripts/classify_blob.py)
- reports/detailed_dump_analysis.md | laqieer | historical | Resolved point-in-time analysis of former dump/ binary files
- reports/dump_conversion_report.md | laqieer | historical | Point-in-time dump/ .incbin-to-source conversion tracking report
- reports/dump_incbin_resources.md | laqieer | historical | Point-in-time dump/ .incbin resource extraction count/listing
- reports/dump_resources_list.md | laqieer | historical | Point-in-time per-symbol dump/ resource classification table
- reports/generated_data_manifest.md | laqieer | generated | Auto-generated generated-data platform table/record manifest
- reports/generated_data_bundle_inventory.md | laqieer | generated | Auto-generated chapterbundle table inventory
- reports/generated_data_characters_inventory.md | laqieer | generated | Auto-generated characters table inventory
- reports/generated_data_classes_inventory.md | laqieer | generated | Auto-generated classes table inventory
- reports/generated_data_eventlists_inventory.md | laqieer | generated | Auto-generated eventlists table inventory
- reports/generated_data_eventscripts_inventory.md | laqieer | generated | Auto-generated eventscripts table inventory
- reports/generated_data_items_inventory.md | laqieer | generated | Auto-generated items table inventory
- reports/generated_data_movecost_inventory.md | laqieer | generated | Auto-generated movecost table inventory
- reports/generated_data_shops_inventory.md | laqieer | generated | Auto-generated shops table inventory
- reports/generated_data_supports_inventory.md | laqieer | generated | Auto-generated supports table inventory
- reports/generated_data_terrainstats_inventory.md | laqieer | generated | Auto-generated terrainstats table inventory
- reports/generated_data_traps_inventory.md | laqieer | generated | Auto-generated traps table inventory
- reports/generated_data_units_inventory.md | laqieer | generated | Auto-generated units table inventory
- reports/generated_data_weapontriangle_inventory.md | laqieer | generated | Auto-generated weapontriangle table inventory
- reports/id_space_audit.md | laqieer | generated | Auto-generated DEFAULT ID-space contract audit (issue #10)
- reports/generated_data_issue5_closure.md | laqieer | evidence | Candidate closure evidence mapping for issue #5, not a closure claim
- reports/issue10_closure.md | laqieer | evidence | Candidate closure-mapping evidence for issue #10, not a closure claim
- reports/debugtools_issue11_closure.md | laqieer | evidence | Candidate closure-mapping evidence for issue #11, not a closure claim
- reports/gba_playtest_issue13_closure.md | laqieer | evidence | Candidate closure-mapping evidence for issue #13, not a closure claim
- reports/issue7_documentation_foundation.md | laqieer | evidence | Candidate closure-mapping evidence for issue #7, not a closure claim
- reports/issue17_documentation_audit.md | laqieer | evidence | Candidate closure-mapping evidence for issue #17, not a closure claim
- reports/issue6_closure.md | laqieer | evidence | Historical issue #6 Sprint 2 candidate closure evidence; current contract is docs/starter_features.md
- reports/issue6_foundation_evidence.md | laqieer | evidence | Historical issue #6 Sprint 1 foundation/runtime evidence
- reports/issue18_idspace_active_cap_dag_closure.md | laqieer | evidence | Issue #18 active-cap dependency-DAG remediation evidence
- reports/issue18_localization_closure.md | laqieer | evidence | Historical issue #18 sprint evidence and superseding addenda
- reports/itemexpansion_gate_order_race_diagnosis.md | laqieer | evidence | Point-in-time item-expansion gate-order race diagnosis
- scripts/symdoc.md | laqieer | subsystem-reference | Symbol-renaming tooling reference
- scripts/linker_report/README.md | laqieer | subsystem-reference | Deterministic linker .map memory-budget report tooling
- scripts/modernize/README.md | laqieer | subsystem-reference | Modern-compiler blocker audit tooling reference
- scripts/shiftcheck/README.md | laqieer | subsystem-reference | ROM shiftability-harness reference
- scripts/shiftcheck/tas/README.md | laqieer | subsystem-reference | Full-game TAS shiftability validation reference
- tools/gba-playtest/README.md | laqieer | subsystem-reference | Headless libmGBA playtest fingerprint tooling reference
<!-- DOCS-INVENTORY:END -->

## Notes

- `owner` is maintainer/DRI (directly-responsible-individual) routing
  metadata: the person accountable for this file's content and who to
  route questions/reviews to. It records human responsibility, **not**
  automated GitHub review enforcement, and it is **not** a claim of
  per-file solo authorship.
- This `owner` field is independent of `.github/CODEOWNERS`. Only paths
  that `.github/CODEOWNERS` explicitly lists get any automatic
  reviewer-request behavior from GitHub; as of this writing that file
  lists a small, specific set of protected baseline/fingerprint and
  artifact-governance paths (see that file directly for the current
  list), not every path in this inventory. A file's `owner` here does
  not imply -- and must never be read as implying -- that the same path
  is also matched by a `.github/CODEOWNERS` rule.
- Adding a new Markdown file anywhere in this repository requires adding
  an entry here in the same change, or `scripts/check_docs.py --check`
  fails. Deleting a Markdown file requires removing its entry.
- This inventory does not record line counts, byte counts, or any other
  value that drifts on every unrelated edit -- only the path/owner/status/
  scope quadruple, which is stable unless the file's actual role changes.
