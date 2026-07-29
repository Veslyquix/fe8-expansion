# Project governance

This is the entry point for contribution governance, security reporting,
copyright/provenance boundaries, credits, and the support/compatibility
policy. It links to the deeper, single-source-of-truth documents rather
than duplicating them.

## Contribution governance

The single authoritative governance document for issue closure, review
enforcement, and the baseline/fingerprint review process is
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md). In summary:

- Issue closure is a **human decision**, recorded as plain-prose evidence
  in the linked PR/issue (frozen scope, every validation command actually
  run and its result, runtime/playtest evidence when behavior can be
  affected). There is intentionally no machine-readable evidence schema.
- `.github/CODEOWNERS` requests `@laqieer` as reviewer for baseline/
  fingerprint and artifact-governance paths, but **does not by itself
  require or block anything** — only repository branch protection/rulesets
  do that.
- `python3 scripts/artifact_guard.py --revision HEAD` is a structural
  Git-object checker (rejects ROM/ELF/save/savestate/patch/generated
  compressed-asset files and specific root outputs). It is **not** a legal
  or copyright clearance — see "Copyright and provenance" below.
- Use the [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
  checklist shape for every PR.

## Security reporting

This repository does not currently ship a `SECURITY.md`. Do not invent a
contact address or process that isn't backed by a real, checked-in file or
platform feature. **Never disclose a sensitive vulnerability's details in
a public issue, pull request, or pull request review comment** -- every
one of those is world-readable on GitHub by default; "avoid a public
issue" is not satisfied by using a PR comment instead, since that is
equally public. Until a `SECURITY.md` is added:

- If GitHub's private vulnerability reporting is enabled for this
  repository, use it (repository → Security tab → "Report a vulnerability").
  Availability depends on the repository's platform configuration and is
  not guaranteed by this document -- check the Security tab yourself
  rather than assuming it is enabled.
- If it is not enabled (or you cannot tell), do not post sensitive
  vulnerability details anywhere public in this repository. Instead, open
  a minimal, non-sensitive request asking the maintainer (`@laqieer`, the
  sole `CODEOWNERS` entry) to establish or point you to a private
  reporting channel, and withhold the actual sensitive details until a
  private channel is confirmed available.

This document does not create, and must not be read as creating, a
guaranteed private-disclosure email address, contact method, or SLA.

## Copyright and provenance

- **This repository does not currently have a `LICENSE` file.** Do not
  assume, state, or imply any specific license for this codebase in other
  docs; if you need a licensing determination, raise it as its own issue
  rather than relying on silence here.
- `scripts/artifact_guard.py` passing is a **structural-compatibility
  allowance only** — it does not confirm that any tracked asset (including
  `graphics/`, `preview/`, `sound/` source-asset classes it narrowly
  permits) is legally cleared, appropriately licensed, or authorized for
  redistribution. See
  [`docs/issue-resolution-policy.md`](issue-resolution-policy.md#legal-and-copyright-boundary)
  for the exact allow/deny list.
- Wave 0 (the current governance baseline) makes **no** decision about a
  distributable "source release" manifest/allowlist; that is tracked
  separately as issue #9 and is out of scope for this document.
- **Do not commit ROM/GBA files, ELF files, saves/SRAM, savestates,
  patches, or generated compressed asset outputs (`.lz`/`.4bpp`/`.8bpp`/
  `.gbapal`) or root build outputs (`fireemblem8.map`,
  `fireemblem8_relocs.map`, `objects.lst`, `build/`).** These are exactly
  what `scripts/artifact_guard.py` rejects.

## Credits and downstream context

Projects that consume this repository's ELF/decomp output:

- [**fe-maps**](https://github.com/laqieer/fe-maps) ([site](https://laqieer.github.io/fe-maps/)) — browsable ROM/RAM data maps extracted with `readelf`/`nm -l`.
- [**FE_GBA_Function_Library**](https://github.com/laqieer/FE_GBA_Function_Library) ([site](https://laqieer.github.io/FE_GBA_Function_Library/)) — cross-game function documentation.
- [**FE-Clib-Decomp**](https://github.com/laqieer/FE-Clib-Decomp) — ROM-hacking linker scripts and Event Assembler defines generated from this repo's ELF.

`[historical upstream]` references — kept for provenance, not authoritative
for this repository:

- [Wiki](https://github.com/laqieer/fireemblem8u/wiki)
- [FE Decomp Portal](https://laqieer.github.io/fe-decomp-portal/)
- [decomp.dev match tracker](https://decomp.dev/laqieer/fireemblem8u/us)

## Support and compatibility policy

- The **supported modern path** (`arm-none-eabi` GCC/AAPCS,
  `expansion-modern-*` targets) is what CI builds and boot-verifies. See
  [`docs/framework-support.md`](framework-support.md) for the exact
  host/toolchain/target matrix.
- The **archival agbcc path** (`make legacy`) is preserved, unbroken, but
  explicitly not the default/supported release lane. See
  [`docs/archival-decomp.md`](archival-decomp.md).
- Compatibility expectations (ABI, struct layout, legacy constraints,
  save-format epoch) differ between the two paths — say which path a
  change targets in issue/PR evidence, per
  [`docs/issue-resolution-policy.md`](issue-resolution-policy.md#supported-modern-path-vs-archival-decomp-path).
- Version-to-version migration guidance (once a versioned release exists)
  follows [`docs/release-migration-template.md`](release-migration-template.md).

## Merged vs. active integration slots

Issues **#10** (typed IDs / extensible-ID contracts), **#11** (debug-tools
extension surface), and **#13** (regression/host-matrix policy) are now
merged with final, supported public interfaces — narrow, explicit
non-goals remain per closure report, not open governance questions.
Issues **#6**, **#9**, and **#18** remain open/active; any governance
statement about "supported public API" scope for those areas is deferred
to their own follow-up documentation updates — see
[`docs/architecture.md`](architecture.md#public-extension-boundaries--merged-101113-vs-active-6918).
