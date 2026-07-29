# Changelog

All notable changes to this project are documented here. This project is
currently pre-1.0 (see `config.mk`'s `EXPANSION_VERSION_*` and
[`docs/public_api_policy.md`](docs/public_api_policy.md) for exactly what
that means for SemVer/compatibility).

The `## [Unreleased]` section below is rendered **deterministically** from
machine-readable fragments in [`changelog_fragments/`](changelog_fragments/) by
`python3 -m scripts.release_rehearsal.changelog render` (or `write` to update this
file in place); see [`docs/release_process.md`](docs/release_process.md).
Do not hand-edit the text between the two HTML comment markers below --
`make release-check` fails actionably if it drifts from the fragments.

## [Unreleased]

<!-- release-rehearsal:unreleased:begin -->
### Internal

- Add a read-only release/publication rehearsal system (policy, changelog fragments, release manifest, migration registry, source-release guard/provenance, deterministic archive rehearsal, and a read-only CI workflow); publication remains mechanically BLOCKED pending human license/provenance approval. (#9)
- Remediate all ten independent-verifier findings against the read-only release/publication rehearsal system: exact per-member source allowlist and provenance coverage, expanded hard-deny rules with an audited map/hex exception list, immutable Git-blob-bound archive rehearsal, a truthful four-state rebuild rehearsal, additional manifest consistency validators, a machine-distinct exit/status contract, a dynamically-rendered CI job summary, a hardened workflow guard, and fixed broken docs links; publication remains mechanically BLOCKED throughout. (#9)
<!-- release-rehearsal:unreleased:end -->

## [0.1.0] - baseline

The framework's semantic version and GBA ROM identity fields were
established in `config.mk` (issue #8) before this changelog/fragment
system existed; no fragment history is recorded for it. See
`docs/config_identity.md`.
