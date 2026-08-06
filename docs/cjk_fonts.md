# Deterministic CJK font assets

This directory contract supplies Sprint 3 with reviewable Japanese and
Simplified Chinese glyph bitmaps without changing the renderer or the normal
build. Bare `make` does not invoke FEBuilderGBA, .NET, a GUI, the network, or a
system font lookup.

## Inventory contract

Run:

```bash
python3 -m scripts.fonttools.cjk generate-inventory
python3 -m scripts.fonttools.cjk check
```

The inventory reads the committed normalized sources:

- `texts/locales/ja/indexed.txt`;
- `texts/locales/zh-Hans/indexed.txt`;
- unique records in `texts/locales/zh-Hans/raw.json`;
- active `texts/expansion` catalog strings, resolved through the English
  fallback catalog when a locale catalog is absent.

`[CTRL:HHHH]` controls and `{N}` expansion placeholders are not glyphs.
Visible text is normalized with NFC only. ASCII remains in the existing
runtime fonts. The source contains one non-ASCII spacing scalar, U+3000
IDEOGRAPHIC SPACE; FEBuilder schema v1 rejects whitespace, so U+3000 is
reported separately and Sprint 3 must give it an explicit advance rather than
performing a bitmap lookup.

Current deterministic counts:

| Locale | Source non-ASCII | Bitmap scalars per style | Styles |
| --- | ---: | ---: | --- |
| `ja` | 1,849 | 1,848 | System/item, Talk/text |
| `zh-Hans` | 2,460 | 2,460 | System/item, Talk/text |
| union | 3,332 | 3,331 | U+3000 is the one spacing scalar |

The sorted corpora are in `fonts/cjk/corpora/`; human-readable scalar maps are
in `fonts/cjk/maps/`; counts, input hashes, output hashes, token rules, and
contributions are in `fonts/cjk/inventory.json`.

## Licensed font inputs

The repository vendors unmodified, region-appropriate Noto CJK 2.004 Regular
SubsetOTF files from upstream commit
`f8d157532fbfaeda587e826d4cd5b21a49186f7c`:

| Locale | File | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `ja` | `NotoSansJP-Regular.otf` | 4,533,028 | `dff723ba59d57d136764a04b9b2d03205544f7cd785a711442d6d2d085ac5073` |
| `zh-Hans` | `NotoSansSC-Regular.otf` | 8,331,336 | `faa6c9df652116dde789d351359f3d7e5d2285a2b2a1f04a2d7244df706d5ea9` |

Both are licensed under OFL-1.1. The exact upstream license is vendored as
`fonts/cjk/licenses/Noto-CJK-OFL-1.1.txt` with SHA-256
`6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2`.
See `fonts/cjk/font-sources.json` and
`fonts/cjk/THIRD_PARTY_NOTICES.md`.

Normal work is offline. If a vendored input must be restored, the explicit
network bootstrap uses immutable URLs and refuses a hash mismatch:

```bash
python3 -m scripts.fonttools.cjk bootstrap-fonts
```

## FEBuilderGBA maintainer gate

`fonts/cjk/febuilder-manifest.json` is strict schema v1 with four
`main-16x16` jobs:

- `ja-system`: item style, 12 px;
- `ja-talk`: text style, 11 px;
- `zh-hans-system`: item style, 12 px;
- `zh-hans-talk`: text style, 11 px.

Each job uses the complete locale bitmap corpus and a deterministic dense
temporary `moji` mapping. Runtime lookup does not use that mapping; it uses the
generated Unicode tables described below.

Build FEBuilderGBA CLI issue #2034 from a trusted checkout, then set
`FEBUILDER_CLI`. For a framework-dependent build this may contain both the
`dotnet` executable and CLI DLL:

```bash
make -f cjk_fonts.mk cjk-fonts-febuilder-all \
  FEBUILDER_CLI="/path/to/dotnet /path/to/FEBuilderGBA.CLI.dll"
```

The explicit maintainer sequence is:

1. dry-run provenance and capacity planning;
2. generate the manifest jobs and their derived corpus row count;
3. validate with the immutable external generation report;
4. non-rasterizing byte-for-byte roundtrip;
5. record the generation report and gate evidence after all commands exit zero;
6. create a deterministic temporary archive under `build/tmp/cjk-fonts/`,
   import it twice to prove deterministic compact output, and check the assets.

The committed run used FEBuilderGBA commit
`c1700532b27c579511585ca63e2d63222b9ea646` and .NET SDK 10.0.302.
Machine-readable evidence is in
`fonts/cjk/reports/febuilder-gates.json`; the full immutable oracle is
`fonts/cjk/reports/febuilder-generation-report.json`. FEBuilder package
directories and archives are temporary maintainer artifacts under
`build/tmp/cjk-fonts/`; neither loose PNG package trees nor ZIP archives are
committed. Delete that ignored directory at any time and rerun the command
above to reproduce the gate.

## Sprint 3 aggregate asset contract

For each `locale.style`, `graphics/fonts/cjk/` contains:

- `*.codepoints.u32le`: sorted unique little-endian `uint32` Unicode scalars;
- `*.widths.u8`: one unsigned width byte per scalar, range 1 through 16;
- `*.glyphs.2bpp`: one 64-byte 16x16 bitmap per scalar, row-major, four
  low-bit-first 2bpp pixels per byte.

Binary-search the codepoint table. The matching index selects one width byte
and one fixed-stride bitmap. `graphics/fonts/cjk/manifest.json` pins every
asset hash and all package/report provenance.

The four locale/style payloads total **594,504 bytes**, or **594,504 bytes**
when every blob is independently aligned to four bytes. This budget includes
the bitmap, width, and Unicode index data, but not future linker/table
wrappers.

## Verification

Normal stdlib-only verification:

```bash
python3 -m scripts.fonttools.cjk check
python3 -m unittest discover -s scripts/fonttools/cjk/tests -p 'test_*.py' -v
```

These checks regenerate the inventory, derive expected job/row counts from the
manifest and corpora, verify the recorded FEBuilder gates and report hashes,
require nonzero 64-byte glyphs, validate widths and exact catalog/game scalar
coverage, compare every aggregate hash, and reject ZIP files or ZIP magic in
the committed font domain. They do not invoke FEBuilderGBA or download
anything. The explicit maintainer gate above performs the temporary package
generation, validation, roundtrip, and deterministic import.
