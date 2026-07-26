# Contributing to Fire Emblem 8 Expansion

This project's default, supported contribution path is the **modern
`arm-none-eabi` GCC/AAPCS framework**. The original agbcc-based
decompilation workflow is preserved as an explicit **archival** lane — see
the "Archival/decomp contributions" section at the end of this document
and [`docs/archival-decomp.md`](docs/archival-decomp.md) for its full
guide.

For architecture context before you dive in, see
[`docs/architecture.md`](docs/architecture.md) and the
[full documentation index](docs/README.md).

## 1. Preparation

1. Register an account on [GitHub](https://github.com/) if you don't have one.
2. Fork and clone the repository, then fetch submodules:
   ```bash
   git submodule update --init --recursive
   ```
3. Run the quickstart to get a working modern build:
   ```bash
   ./scripts/quickstart.sh
   ```
   See [`docs/quickstart.md`](docs/quickstart.md) for flags and
   troubleshooting, and [`docs/framework-support.md`](docs/framework-support.md)
   for supported hosts/toolchains.

## 2. Choose your change type

| Change type | Where | Primary commands |
| --- | --- | --- |
| **Content authoring** (characters, classes, items, supports, Chapter 2 slice) | `src/data/*.json` | `make generated-data-validate`, `make generated-data-generate`, `make generated-data-test` — see [`docs/generated_data_tutorial.md`](docs/generated_data_tutorial.md) |
| **C/runtime code** (modern framework) | `src/`, `include/` | `make expansion-modern-toolchain-check`, `make expansion-modern-cohort` (or `-all`), `make expansion-modern-elf`, `make expansion-modern-rom`, `make expansion-modern-boot-check` — see [`docs/quickstart.md`](docs/quickstart.md) |
| **Docs** | `README.md`, `CONTRIBUTING.md`, `docs/*.md` | Verify every relative link resolves and every referenced command actually exists |
| **Upstream-port tracking** | `config/upstream-port-state.json` (via CLI only) | `python3 -m scripts.upstream_port scan/drift/report/update-state/verify` — see [`docs/upstream-porting.md`](docs/upstream-porting.md) |
| **Archival/decomp matching** | `asm/`, `src/` (agbcc-matched) | `make legacy` — see [`docs/archival-decomp.md`](docs/archival-decomp.md) |

## 3. Fast checks (no ROM, run these first)

```bash
python3 scripts/artifact_guard.py --revision HEAD
make generated-data-validate
python3 -m unittest discover -s scripts/artifact_guard_tests -p 'test_*.py'
python3 -m unittest discover -s scripts/modernize/tests -v          # modern build/config/save-format host tests
python3 -m unittest discover -s tools/gba-playtest/tests -v         # only if your change touches runtime/playtest behavior
python3 -m scripts.upstream_port scan                               # only if your change touches upstream-port tracking
```

`scripts/modernize/tests` and `tools/gba-playtest/tests` assume
`./build_tools.sh` and `git submodule update --init --recursive` have
already been run (quickstart does both); a small number of their host
tests are environment-dependent (missing built tool binaries, or a
libmGBA backend without `pkg-config` metadata) and fail actionably rather
than silently in an incomplete environment — see each test's own
diagnostic.

## 4. Full gates (ROM/libmGBA build, run before opening a PR)

```bash
make generated-data-check
make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs
make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs
```

Run the relevant subset for your change type; run all of them for anything
that touches shared runtime, linker, or generated-data code. If your change
can affect boot, save, or gameplay behavior, also capture
`tools/gba-playtest` scenario evidence (scenario, environment, command,
result) — see [`docs/issue-resolution-policy.md`](docs/issue-resolution-policy.md#issue-closure-evidence).

## 5. PR provenance and review

This repository's Wave 0 governance baseline is the single authoritative
source for what a PR/issue must record before closure:
[`docs/issue-resolution-policy.md`](docs/issue-resolution-policy.md). In
short:

- Issue closure is a human decision backed by plain-prose evidence in the
  PR/issue thread (frozen scope, every command run and its result,
  runtime/playtest evidence when relevant) — not a machine-readable schema.
- Use [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)'s
  checklist shape.
- `reports/baseline/`, `tools/gba-playtest/fingerprints/`, and
  `scripts/shiftcheck/tas/fingerprint.lua` are reviewed oracles — explain
  *why* in your PR description if you touch them.
- `python3 scripts/artifact_guard.py --revision HEAD` rejects tracked
  ROM/ELF/save/savestate/patch/generated-compressed-asset files; it is a
  structural check, **not** a legal/copyright clearance — see
  [`docs/project-governance.md`](docs/project-governance.md#copyright-and-provenance).

**Working on your first Pull Request?** Learn how from this *free* series:
[How to Contribute to an Open Source Project on GitHub](https://egghead.io/series/how-to-contribute-to-an-open-source-project-on-github).

## Archival/decomp contributions

If your change is byte-for-byte decomp-matching work against the original
ROM (not the supported modern framework), use the archival agbcc lane:

```bash
make legacy -j$(nproc)
```

The full decompiling tutorial, rules, setup steps, and related
asset-extraction references live in
[`docs/archival-decomp.md`](docs/archival-decomp.md) — that document is
explicitly marked unsupported for expansion releases; do not treat it as
guidance for the default framework path.
