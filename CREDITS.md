# Credits

Generally sourced from the community
[Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) asset repository.

## Battle Animations (`NEW_ANIMS`)

| Class | Pack | Credits |
| --- | --- | --- |
| `CLASS_SOLDIER` | [Soldier-Custom] FE10-Style [M] by Flasuban | Flasuban sprited the base version of the FE10 Soldier. Slow/Angled is Flasuban's first version. Fast/Straight is a revision based off the vanilla GBA Soldier movements, made to look more like the GBA timings, animated by Nuramon. Sword animation is based on the Fast/Straight animation done by Nuramon, animated by Craigrandall55. Lance (Echoes Lance) variant by UltraFenix. |
| `CLASS_BRIGAND` | [Brigand-Reskin] Fully-Clothed [M] by Flasuban | Made by Flasuban. |
| `CLASS_FIGHTER` | [Fighter-Variant] FE9 Repal [M] by Glenwing | Original FE9 Fighter by MK404. Repalette by Glenwing. |
| `CLASS_KNIGHT` | [Knight-Variant] Generic [M] by SALVAGED | Animations by SALVAGED. Axe (Magic Axe) variant by Itanc. |
| `CLASS_MERCENARY` | [Mercenary-Reskin] Armored SALVAGED Style [M] | Animation by Alusq, Maiser6. Recolor/Repalette by RRSKAI. Head from Team SALVAGE's Mercenary. Reskin by UltraFenix. |
| *(unused -- see below)* | [Archer-Reskin] FE5-Style [M] by Pushwall | Animation by Pushwall. |
| `CLASS_CAVALIER` | [Cavalier-Variant] [M] Generic by SALVAGED v2 | Cavalier custom by SALVAGED. Upgraded version of the original SALVAGED cavalier; no female equivalent currently exists. |
| `CLASS_PEGASUS_KNIGHT` | [Peg T1 Base] [F] Repal v2 + Weapons by Flasuban | Sword/Lance/Axe/Handaxe/Unarmed/Repalette by Flasuban. Unarmed palette fix by UltraFenix. Magic by UltraFenix, using Light Mage by Leo_link and L95 as a base. UltraFenix fixed a pixel mistake in all animations. |
| `CLASS_ARCHER` | [Archer-Variant] Der's Improved [M] | Original animation by IS. Archer Variant by Flasuban and DerTheVaporeon. |
| `CLASS_ARCHER_F` | [Archer-Variant] Der's Improved [F] | Original animation by IS. Archer Variant by Flasuban and DerTheVaporeon. |
| `CLASS_MAGE` | [Mage-Custom] Gaiden-Style Frame Fix [F] by Gamma | HyperGammaSpaces, Teraspark, Obsidian_Daddy, Devisian_Nights. Frame fixes (misplaced eye) by Raulster/Alice. |
| `CLASS_MAGE_F` | [Mage-Custom] Gaiden-Style Ponytail [F] by Gamma | HyperGammaSpaces, Teraspark, Obsidian_Daddy, Devisian_Nights. Frame fixes (misplaced eye) and ponytail by Raulster/Alice. |
| `CLASS_LYN_LORD` | [FE7 Lyn-Reskin] T1 Long Hair [F] | Frames by Blazt. Formatted by Seliost1. |
| `CLASS_NOMAD`, `CLASS_NOMAD_F` | [Nomad-Base] [M]/[F] Vanilla Repal | Repalette by Pikmin1211 and Maiser6. |
| `CLASS_NOMAD_TROOPER` | [Nomad Trooper Reskin][M] FE6 Style by Levin64 | FE6 Nomad Trooper improved by Levin64. |
| `CLASS_NOMAD_TROOPER_F` | [Nomad Trooper Reskin] [F] FE6 Style by Levin64 | FE6 Nomad Trooper improved by Levin64. Female variant reskin by Fuyu. |

Pushwall's FE5-style Archer (the animation `CLASS_ARCHER` used before) is
still imported as an available `banim_data[]` entry (see
`scripts/banim_packs.json`) but is no longer assigned to any class.

## Map Sprites

| Class | Credits |
| --- | --- |
| `CLASS_LYN_LORD` | Merpin |
| `CLASS_NOMAD`, `CLASS_NOMAD_F` | IS, MeatOfJustice, UltraFenix |
| `CLASS_NOMAD_TROOPER`, `CLASS_NOMAD_TROOPER_F` | IS |

## Map Tilesets (`NEW_TILESETS`)

| Chapter | Tileset | Credits |
| --- | --- | --- |
| Prologue | FE8 - Fields - Remaster - Super Fields (Object Palette: FE7 Darker Green) | Made by WAve, RandomWizard and Beast. |




## Custom Campaign Portraits (`CUSTOM_CAMPAIGN`)

| Character | Portrait | Artist |
| --- | --- | --- |
| Hannah | `{Nickt} Hannah.png` | Nickt |
| Francis | `{Nickt} Francis.png` | Nickt |
| Frederick | `{Nickt} Frederick.png` | Nickt |
| Fox | `{Nickt} Fox.png` | Nickt |
| Liz | `Flyer Girl Liz[F2E].png` | RandomWizard (tagged **F2E**, "Free to Edit") |
| Ishkode | `{Eden} Ishkode.png` | Eden |
| Wakwi | `{Eden} Wakwi.png` | Eden |
| Kargan (replaces O'Neill) | `{Eden} Kargan[F2E].png` | Eden |
| Asin (replaces Moulder) | `{Eden} Asin.png` | Eden |

Hannah and Francis are no longer used by `src/portrait_data.c` (replaced by
Wakwi and Ishkode respectively) but remain credited/linked, not removed.


## CO Screen Graphics (`CO_POWERS`)

| Asset | File | Artist |
| --- | --- | --- |
| CO info screen backdrop | `graphics/bg/bg_CoStatusScreen.png` | PatrickHoang |

## Conversation Backgrounds (`MULTIPALETTE_BG`)

Public-domain paintings, converted to the 192-colour multipalette format
(`scripts/convo_bg_to_source.py`) as test/demo backgrounds for that mode.

| Asset | File | Artist |
| --- | --- | --- |
| Hillside | `graphics/convo_bg/AlexanderLawrieHillside.png` | Alexander Lawrie |
| Mountains at Dusk | `graphics/convo_bg/GustaveDoreStreaminMountainsatDusk.png` | Gustave Doré |
| River Forest Landscape | `graphics/convo_bg/tobias-everet-spence-river-forest-landscape.png` | Tobias Everet Spence |
| A Tornado in the Wilderness | `graphics/convo_bg/sep_a-tornado-in-the-wilderness-1835_Thomas_Cole.png` | Thomas Cole |
| Aquaduct | `graphics/convo_bg/sep_Aquaduct_Thomas_Cole.png` | Thomas Cole |
| Aurora Borealis | `graphics/convo_bg/sep_aurora-borealis-Frederic_Edwin_Church.png` | Frederic Edwin Church |
| Distant View of Niagara Falls | `graphics/convo_bg/sep_distant-view-of-niagara-falls-1830_Thomas_Cole.png` | Thomas Cole |
| Expulsion from the Garden of Eden | `graphics/convo_bg/sep_expulsion-from-the-garden-of-eden-1828_Thomas_Cole.png` | Thomas Cole |
| Expulsion, Moon and Firelight | `graphics/convo_bg/sep_expulsion-moon-and-firelight_thomas_cole.png` | Thomas Cole |
| Interior of the Colosseum, Rome | `graphics/convo_bg/sep_interior-of-the-colosseum-rome-1832_Thomas_Cole.png` | Thomas Cole |
| Lake with Dead Trees | `graphics/convo_bg/sep_lake-with-dead-trees-catskill-Thomas_Cole.png` | Thomas Cole |
| Mount Aetna from Taormina | `graphics/convo_bg/sep_mount-aetna-from-taormina-1843_Thomas_Cole.png` | Thomas Cole |
| Mountain Sunrise | `graphics/convo_bg/sep_mountain-sunrise-Thomas_Cole.png` | Thomas Cole |
| Parthenon | `graphics/convo_bg/sep_parthenon-Frederic_Edwin_Church.png` | Frederic Edwin Church |
| Romantic Landscape with Ruined Tower | `graphics/convo_bg/sep_romantic-landscape-with-ruined-tower_Thomas_Cole.png` | Thomas Cole |
| The Arabian Desert | `graphics/convo_bg/sep_the-arabian-desert-Frederic_Edwin_Church.png` | Frederic Edwin Church |
| The Cascatelli, Tivoli | `graphics/convo_bg/sep_the-cascatelli-tivoli_Thomas_Cole.png` | Thomas Cole |
| The Garden of Eden | `graphics/convo_bg/sep_the-garden-of-eden_Thomas_Cole.png` | Thomas Cole |
| The Notch of the White Mountains | `graphics/convo_bg/sep_the-notch-of-the-white-mountains-crawford-notch-Thomas_Cole.png` | Thomas Cole |
| The Past | `graphics/convo_bg/sep_the-past-thomas_cole.png` | Thomas Cole |
| The Subsiding of the Waters of the Deluge | `graphics/convo_bg/sep_the-subsiding-of-the-waters-of-the-deluge_Thomas_Cole.png` | Thomas Cole |
| Scene from The Last of the Mohicans | `graphics/convo_bg/sep_thomas-cole-scene-from-the-last-of-the-mohicans.png` | Thomas Cole |
| Twilight Mount | `graphics/convo_bg/sep_TwilightMount_Frederic_Edwin_Church.png` | Frederic Edwin Church |
| White Mountain Landscape, Mount Washington | `graphics/convo_bg/sep_white-mountain-landscape-mount-washington-Martin_Johnson_Heade.png` | Martin Johnson Heade |

## Custom BGM (`NIMAP2`)

Sound data sourced from the [Fire Emblem: Sacred Rewritten
Randomizer](https://github.com/Vesly-FE/SRR) BGM pack (`bgm/`). Re-expressed as
decomp voicegroup/song assembly by `scripts/sound/gen_nimap2.py` and
`scripts/sound/import_bgm.py`; see [docs/custom_bgm.md](docs/custom_bgm.md).

### Instrument maps

| Component | Credits |
| --- | --- |
| NIMAP2 native instrument map (`voicegroup000`) | Community FE-hacking patch, distributed with the SRR BGM pack. No individual attribution is recorded upstream. |
| Percussion drumfix (`voicegroup079`/`080`/`081`/`083`/`084`) | As above. The pack's companion FE7 16-track/12-sound fix is credited upstream to Agro/Brendor; the FE8 drumfix data itself carries no separate attribution. |

### Songs

| Song ID | Track | Arranger |
| --- | --- | --- |
| `SONG_BGM_GS_VENUS_LIGHTHOUSE` | Golden Sun — Venus Lighthouse | AReliableChair |
| `SONG_BGM_POKEMON_GS_GOLDENROD_CITY` | Pokémon Gold/Silver — Goldenrod City | AReliableChair |

Original compositions remain the property of their respective rights holders
(Camelot/Nintendo for *Golden Sun*; Game Freak/Nintendo for *Pokémon
Gold/Silver*); only the GBA arrangements are credited above.

## Ported Code Patches

| Patch | Author |
| --- | --- |
| `DEBUGGER` | Vesly |
| `PURCHASE_GENERICS` | Vesly |
| `MAPGEN` | Vesly |
| `CREDITS` | Vesly |
| `DANGER_BONES` | Vesly |
| `SELECT_VIEW_GROWTHS` | Vesly |
| `BATTLE_STATS_NO_ANIMS` | Tequila, Vesly, Alusq |
| `DRAW_MAP_ANIMS` | Vesly, Viktor Hahn |
| `BATTLE_ANIMATION_NUMBERS` | Huichelaar |
| `MULTIPALETTE_BG` | Huichelaar |
| `MMB` | Zane |
| `EXTEND_DESC_BOX` | Vesly |
| `DISPLAY_OBTAINABLE_ITEM` | Mkol, Huichelaar, Vesly |
| `HP_BARS` | circleseverywhere, Tequila, hypergammaspaces, Alusq |
| `ALPHA_SPRITE_ARROW` | JesterWizard |
| `SHOW_HEAL_AMOUNT` | Tequila |
| `DEBUFFS` | Vesly |
| `GROUP_AI` | Vesly, PhantomSentine |
| `PROMOTE_COMMAND` | Vesly |
| `TURN_AUTOSAVE` | Vesly |
| `TEXT_CHAPTER_NAMES` | circleseverywhere, hypergammaspaces |
| `ANIMS_FAST_FORWARD` | Vesly |
| `MODE_SELECT` | Eebit, JesterWizard. The `CO_POWERS` CO select screen (`src/coSelect.c`) is derived from the same hack. |
| `NIMAP2` | Community BGM patch (see "Custom BGM" above); repo integration by Vesly |
| `RAND_BGM` / `CONTINUE_BGM_BATTLE` | Ported from the SRR (Skill Randomizer / Randomizer) FE randomizer project's BGM-randomization logic; repo integration by Vesly. See [`docs/random_bgm.md`](docs/random_bgm.md). |




