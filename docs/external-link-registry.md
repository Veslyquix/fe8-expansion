# External link registry

Every external (`http`/`https`) URL occurrence in every Markdown file in
this repository -- including inside inline code spans, but not fenced
code blocks -- must be covered by a rule below, matched by
[`scripts/check_docs.py`](../scripts/check_docs.py). This is **syntax and
ownership/status registry coverage only**; it never performs a network
request. A URL is "covered" when its host (for a `host:` rule) or its full
string (for a `prefix:` rule) matches; the checker also enforces that
every `github.com/laqieer/fireemblem8u*` / `decomp.dev/laqieer/fireemblem8u*`
occurrence specifically matches a rule whose status is
`historical-upstream` (never `authoritative-self`) -- this repository's
own docs are authoritative; the upstream wiki/tracker are provenance
context, not a mirrored source of truth (see
[`docs/project-governance.md`](project-governance.md#credits-and-downstream-context)).

Each line is `- pattern | owner | status | notes` where `pattern` is
either `host:<exact netloc>` or `prefix:<literal URL prefix, checked with
str.startswith>`. Rules are matched in file order; keep the more specific
`prefix:` rules for a host above any catch-all `host:` rule for the same
host if a broader host-level entry is also listed for it. Deliberately a
small, bespoke, line-oriented, stdlib-parseable format -- not YAML/JSON
and not a third-party Markdown/link-checker library.

## Status enum

| Status | Meaning |
| --- | --- |
| `authoritative-self` | This repository's own GitHub project surface (Actions, issues, badges). |
| `historical-upstream` | The upstream fireemblem8u decomp project (wiki/tracker/blob links) -- provenance, not mirrored truth. |
| `downstream-reference` | Projects/sites that consume this repo, kept for credits/context. |
| `third-party-reference` | External tools/docs/services this project merely links to. |

The issue #6/#18 Markdown merged into the current tree is covered by the
same exact occurrence scan; it introduces no new unclassified host/prefix.
This statement reflects offline syntax/registry coverage only, never an online
availability check.

## Coverage note on prefix rule count

`docs/tsa_audit.md` alone contributes several hundred pinned
`github.com/laqieer/fireemblem8u/blob/<sha>/...` asset links; one
`prefix:` rule covers all of them (and any future ones under the same
repo) instead of one registry line per pinned link.

## Rules

<!-- EXTERNAL-LINK-REGISTRY:BEGIN -->
- prefix:https://github.com/laqieer/fireemblem8u | laqieer | historical-upstream | Canonical upstream decomp repo: wiki, blob/tree/commit links (incl. docs/tsa_audit.md's ~500 pinned-commit asset links), .git clone URL. Wiki is provenance, not a mirrored source of truth for this repo -- see docs/project-governance.md.
- prefix:https://decomp.dev/laqieer/fireemblem8u | laqieer | historical-upstream | decomp.dev match-percentage tracker + badges for the upstream decomp project.
- prefix:https://github.com/laqieer/fireemblem8-expansion | laqieer | authoritative-self | This repository's own GitHub Actions/badge/issue links and project-wiki navigation portal.
- prefix:https://github.com/laqieer/fe-maps | laqieer | downstream-reference | Downstream project consuming this repo's ELF for browsable ROM/RAM maps.
- prefix:https://github.com/laqieer/FE_GBA_Function_Library | laqieer | downstream-reference | Downstream cross-game function-documentation project.
- prefix:https://github.com/laqieer/FE-Clib-Decomp | laqieer | downstream-reference | Downstream ROM-hacking linker-script/Event-Assembler-define project.
- host:laqieer.github.io | laqieer | downstream-reference | GitHub Pages sites for downstream/portal projects (fe-maps, FE_GBA_Function_Library, fe-decomp-portal).
- prefix:https://github.com/laqieer/decomp-permuter-arm | laqieer | third-party-reference | laqieer's ARM fork of the decomp-permuter tool, linked as an external tool reference.
- prefix:https://github.com/StanHash/mgfembp | laqieer | third-party-reference | Upstream source of the mgfembp submodule.
- prefix:https://github.com/adobe-fonts/source-han-sans | laqieer | third-party-reference | Authoritative Adobe Source Han Sans project referenced by the vendored Noto CJK copyright notice.
- prefix:http://www.adobe.com/ | laqieer | third-party-reference | Exact HTTP URL retained only because it appears verbatim in the embedded Noto CJK copyright notice; the contextual Source Han Sans project uses the separate HTTPS rule above.
- prefix:https://github.com/pret/ | laqieer | third-party-reference | pret project tools/references (agbcc, pokeemerald, pokeruby INSTALL.md docs).
- prefix:https://github.com/SBird1337/cexplore | laqieer | third-party-reference | Compiler Explorer fork source, linked as a tool reference.
- prefix:https://github.com/TwitchPlaysPokemon/pret3 | laqieer | third-party-reference | External datadump & funchash tool reference.
- prefix:https://github.com/bminor/binutils-gdb | laqieer | third-party-reference | Pinned binutils changelog reference for a specific troubleshooting note.
- host:github.com | laqieer | third-party-reference | Bare github.com references (e.g. 'register a GitHub account') not covered by a more specific rule above.
- host:help.github.com | laqieer | third-party-reference | GitHub Help.
- host:cexplore.karathan.at | laqieer | third-party-reference | Compiler Explorer instance used for archival decomp work.
- host:developer.arm.com | laqieer | third-party-reference | ARM GNU Embedded Toolchain download page.
- host:devkitpro.org | laqieer | third-party-reference | devkitPro toolchain install docs.
- host:egghead.io | laqieer | third-party-reference | First-PR tutorial series linked from CONTRIBUTING.md.
- host:feuniverse.us | laqieer | third-party-reference | FEUniverse forum reference (online decompiler discussion).
- host:gcc.gnu.org | laqieer | third-party-reference | Upstream GCC documentation/feature pages.
- host:ghidra-sre.org | laqieer | third-party-reference | Ghidra tool homepage.
- host:www.libpng.org | laqieer | third-party-reference | libpng project homepage (build dependency).
- host:makeapullrequest.com | laqieer | third-party-reference | PR-badge link target.
- host:img.shields.io | laqieer | third-party-reference | Badge image service used by README.md.
- host:marketplace.visualstudio.com | laqieer | third-party-reference | VS Code Makefile Tools extension listing.
- host:retdec.com | laqieer | third-party-reference | RetDec decompiler homepage.
- host:tasvideos.org | laqieer | third-party-reference | Published TAS movie metadata and downloadable input-log reference used by the diagnostic replay lane.
- host:www.hex-rays.com | laqieer | third-party-reference | IDA Pro product page.
<!-- EXTERNAL-LINK-REGISTRY:END -->
