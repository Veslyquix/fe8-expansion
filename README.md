# Fire Emblem 8 Expansion

[![Build CI](https://github.com/laqieer/fireemblem8-expansion/actions/workflows/build.yml/badge.svg)](https://github.com/laqieer/fireemblem8-expansion/actions/workflows/build.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)

A **Fire Emblem: The Sacred Stones (GBA) expansion framework**, built and
released with a modern `arm-none-eabi` GCC/AAPCS toolchain. The expansion
ROM is built from source and is **not** required to be byte-identical to
the original game. The original agbcc-based decompilation build is kept as
an explicit, unbroken **archival** side lane for decomp-matching work — see
[`docs/archival-decomp.md`](docs/archival-decomp.md).

📚 **[Full documentation index](docs/README.md)** — start there for
architecture, support matrix, governance, and migration guides. The
**[project wiki](https://github.com/laqieer/fireemblem8-expansion/wiki)**
is a concise navigation portal to those authoritative repository docs.

## Quick start

From the repo root, on Ubuntu/WSL, Arch Linux, or macOS/Homebrew, run:

```bash
./scripts/quickstart.sh [--rom /path/to/baserom.gba] [--legacy] [--refresh-agbcc]
```

By default this installs the modern toolchain and libmGBA playtest backend
(**no agbcc of any kind**), then builds and boot-verifies the **supported
modern AAPCS release ROM**
(`build/expansion-modern/release/aapcs/fireemblem8.gba`). Pass `--legacy`
to build the archival agbcc-based `fireemblem8.gba` instead. The build does
**not** require the original ROM — a `baserom.gba` is only used by
`asmdiff.sh` for disassembly comparison.

See [`docs/quickstart.md`](docs/quickstart.md) for full flags and
troubleshooting, and [`docs/framework-support.md`](docs/framework-support.md)
for the exact supported-host/toolchain/target matrix.


Then configure the build in `config.mk` or with `make` overrides. The default
is English-only with all starter features off; see
[`docs/config_identity.md`](docs/config_identity.md),
[`docs/starter_features.md`](docs/starter_features.md), and
[`docs/localization.md`](docs/localization.md) before enabling optional
content or locales.

## Default build behavior

A bare `make` (or `make all`) deterministically builds and boot-verifies
the modern release AAPCS ROM — it never requires, builds, or resolves to a
`tools/agbcc` executable or library:

```bash
make                # equivalent to: make all
```

Equivalently, and explicitly:

```bash
make expansion-modern-toolchain-check
make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs -j$(nproc)
```

To clean build artifacts: `make clean` (or `make clean_fast` to skip the
slow battle-animation compression outputs).

## Contributor journeys

| I want to... | Go to |
| --- | --- |
| Author game content (characters, classes, items, chapters) | [`docs/generated_data_tutorial.md`](docs/generated_data_tutorial.md) |
| Enable/extend the typed starter-content and mechanics examples | [`docs/starter_features.md`](docs/starter_features.md) |
| Author expansion UI text or locale catalogs | [`docs/localization.md`](docs/localization.md) |
| Write/modify C runtime code under the modern framework | [`docs/architecture.md`](docs/architecture.md), [`docs/quickstart.md`](docs/quickstart.md) |
| Debug a build or investigate runtime behavior | [`docs/debugtools.md`](docs/debugtools.md), `tools/gba-playtest/README.md` |
| Port/track a change from the canonical upstream decomp | [`docs/upstream-porting.md`](docs/upstream-porting.md) |
| Do byte-for-byte decomp-matching against the original ROM | [`docs/archival-decomp.md`](docs/archival-decomp.md) |

Full contribution workflow (preparation, fast checks, full gates, PR
provenance): [`CONTRIBUTING.md`](CONTRIBUTING.md).


The repository-only path is therefore: quickstart -> configure -> author
JSON/content and locale catalogs -> build -> run host and ROM gates -> debug
with the bounded debug-tools and libmGBA scenario harness. The project wiki is
optional navigation; no wiki is required for that path.

## Support, compatibility, and governance

- **What's supported**: [`docs/framework-support.md`](docs/framework-support.md)
- **Architecture overview**: [`docs/architecture.md`](docs/architecture.md)
- **Contribution/security/copyright governance**: [`docs/project-governance.md`](docs/project-governance.md)
- **Issue closure and review policy**: [`docs/issue-resolution-policy.md`](docs/issue-resolution-policy.md)

## Used by

Projects powered by this repository:

* [**fe-maps**](https://github.com/laqieer/fe-maps) ([site](https://laqieer.github.io/fe-maps/)) — browsable ROM/RAM data maps extracted from this repo's ELF with `readelf`/`nm -l`.
* [**FE_GBA_Function_Library**](https://github.com/laqieer/FE_GBA_Function_Library) ([site](https://laqieer.github.io/FE_GBA_Function_Library/)) — cross-game function documentation using `nm -l` for signatures and `source:line` links.
* [**FE-Clib-Decomp**](https://github.com/laqieer/FE-Clib-Decomp) — ROM-hacking linker scripts, `lyn` reference assembly, and Event Assembler defines generated from this repo's ELF.

## Historical upstream `[historical upstream]`

These track the original decompilation project this expansion is derived
from. They are provenance/credits context, not authoritative for this
repository — see [`docs/project-governance.md`](docs/project-governance.md#credits-and-downstream-context).

[![Code](https://decomp.dev/laqieer/fireemblem8u/us.svg?mode=shield&measure=matched_code_percent&label=Code)](https://decomp.dev/laqieer/fireemblem8u/us)
[![Data](https://decomp.dev/laqieer/fireemblem8u/us.svg?mode=shield&measure=matched_data_percent&label=Data)](https://decomp.dev/laqieer/fireemblem8u/us)
[![Functions](https://decomp.dev/laqieer/fireemblem8u/us.svg?mode=shield&measure=matched_functions_percent&label=Functions)](https://decomp.dev/laqieer/fireemblem8u/us)

[Upstream wiki](https://github.com/laqieer/fireemblem8u/wiki) · [FE Decomp Portal](https://laqieer.github.io/fe-decomp-portal/) · [decomp.dev](https://decomp.dev/laqieer/fireemblem8u/us)
