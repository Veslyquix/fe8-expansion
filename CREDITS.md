# Credits

Third-party art/animation assets used by this expansion, and the artists who
made them. This document is started with the battle-animation set pulled in
for `NEW_ANIMS` and `NEW_TILESETS` (see below); add further sections as more external
content (portraits, map sprites, tilesets, etc.) is integrated.

All entries below are sourced from the community
[Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) asset repository
and are tagged **F2U/F2E** ("Free to Use / Free to Edit") by their authors.

## Battle Animations (`NEW_ANIMS`)

| Class | Pack | Credits |
| --- | --- | --- |
| `CLASS_SOLDIER` | [Soldier-Custom] FE10-Style [M] by Flasuban | Flasuban sprited the base version of the FE10 Soldier. Slow/Angled is Flasuban's first version. Fast/Straight is a revision based off the vanilla GBA Soldier movements, made to look more like the GBA timings, animated by Nuramon. Sword animation is based on the Fast/Straight animation done by Nuramon, animated by Craigrandall55. Lance (Echoes Lance) variant by UltraFenix. |
| `CLASS_BRIGAND` | [Brigand-Reskin] Fully-Clothed [M] by Flasuban | Made by Flasuban. |
| `CLASS_FIGHTER` | [Fighter-Variant] FE9 Repal [M] by Glenwing | Original FE9 Fighter by MK404. Repalette by Glenwing. |
| `CLASS_KNIGHT` | [Knight-Variant] Generic [M] by SALVAGED | Animations by SALVAGED. Axe (Magic Axe) variant by Itanc. |
| `CLASS_MERCENARY` | [Mercenary-Reskin] Armored SALVAGED Style [M] | Animation by Alusq, Maiser6. Recolor/Repalette by RRSKAI. Head from Team SALVAGE's Mercenary. Reskin by UltraFenix. |
| `CLASS_ARCHER` | [Archer-Reskin] FE5-Style [M] by Pushwall | Animation by Pushwall. |
| `CLASS_CAVALIER` | [Cavalier-Variant] [M] Generic by SALVAGED v2 | Cavalier custom by SALVAGED. Upgraded version of the original SALVAGED cavalier; no female equivalent currently exists. |
| `CLASS_PEGASUS_KNIGHT` | [Peg T1 Base] [F] Repal v2 + Weapons by Flasuban | Sword/Lance/Axe/Handaxe/Unarmed/Repalette by Flasuban. Unarmed palette fix by UltraFenix. Magic by UltraFenix, using Light Mage by Leo_link and L95 as a base. UltraFenix fixed a pixel mistake in all animations. |

## Map Tilesets (`NEW_TILESETS`)

| Chapter | Tileset | Credits |
| --- | --- | --- |
| Prologue | FE8 - Fields - Remaster - Super Fields (Object Palette: FE7 Darker Green) | Made by WAve, RandomWizard and Beast. |

Enable with `NEW_TILESETS=1` (compiles as `FE8_NEW_TILESETS`). The pack ships
several alternate object palettes; this build uses "FE7 Darker Green". To swap
palette, re-run the converter against a different `2. ... Object Palette (X).png`
from the same pack -- the tile graphics and mapchip config are shared, only the
160-colour palette differs.

Converted by `scripts/tileset_to_source.py`, which turns the FEBuilder export
(an indexed "Object Palette" PNG plus a `.mapchip_config`) into the three
sources this repo builds from -- `graphics/map/SuperFields{ObjectType.png,
MapPalette.pal,TileConfiguration.S}`. Regenerate with:

```bash
python3 scripts/tileset_to_source.py --name SuperFields \
    --palette-png "<pack>/2. ... Object Palette (FE7 Darker Green).png" \
    --mapchip-config "<pack>/1. ....mapchip_config"
```

Graphics, palette and tile config are swapped together in
`gChapterDataAssetTable` (`src/data/data_8B363C.c`): a tile config's indices and
palette rows are only meaningful against its own sheet, so mixing them with the
vanilla tileset would render garbage.

## How these are built

Enable with `NEW_ANIMS=1` (see `config.mk`; compiles as `FE8_NEW_ANIMS`).
Default is off, and with it off the ROM keeps the stock animations exactly.

The packs above are compiled to Event Assembler `.event` installers by
AA.exe (Klokinator's `FE-Repo` toolchain, run on Windows), then converted to
this repo's banim sources by `scripts/banim_event_to_source.py`, which emits:

* `banim/banim_new<class>_<weapon>_script.s` — the frame/AnimScr stream,
  **uncompressed**; `linker_script_banim.txt` applies `>lz` so the engine's
  single runtime `LZ77UnCompWram` lands on correctly-compressed data.
* `banim/banim_new<class>_<weapon>_{oam.bin.lz,modes.bin}` and
  `graphics/banim/banim_new<class>_<weapon>{.agbpal.lz,_sheet_N.4bpp.lz}`.

Wiring lives in `src/banim_data.c` (slots `0xC9`–`0xE7`),
`src/data_banimconf.c` (the per-class `AnimConf_*` tables) and
`src/opinfo.c` (`gClassReelData`, read ahead of `pBattleAnimDef` by the
class-reel/unit-preview surfaces). Regenerate with:

```bash
python3 scripts/banim_event_to_source.py
```

Four things are easy to get wrong here and are handled by the converter:
`.index` in `struct BattleAnimDef` is **one-based** (`GetBattleAnimationId`
returns `idx - 1`); `_modes.bin` must be padded to the vanilla 96-byte
footprint; AA.exe's frame data arrives already LZ77-compressed and must not
be compressed twice; and ranged axes match on **exact item id**
(`wtype < 0x100`) rather than weapon type.
