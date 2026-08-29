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
| `CLASS_ARCHER` | [Archer-Reskin] FE5-Style [M] by Pushwall | Animation by Pushwall. |
| `CLASS_CAVALIER` | [Cavalier-Variant] [M] Generic by SALVAGED v2 | Cavalier custom by SALVAGED. Upgraded version of the original SALVAGED cavalier; no female equivalent currently exists. |
| `CLASS_PEGASUS_KNIGHT` | [Peg T1 Base] [F] Repal v2 + Weapons by Flasuban | Sword/Lance/Axe/Handaxe/Unarmed/Repalette by Flasuban. Unarmed palette fix by UltraFenix. Magic by UltraFenix, using Light Mage by Leo_link and L95 as a base. UltraFenix fixed a pixel mistake in all animations. |

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
| `DEBUFFS` | Vesly |
| `GROUP_AI` | Vesly, PhantomSentine |
| `PROMOTE_COMMAND` | Vesly |
| `TURN_AUTOSAVE` | Vesly |
| `TEXT_CHAPTER_NAMES` | circleseverywhere, hypergammaspaces |
| `ANIMS_FAST_FORWARD` | Vesly |
| `NIMAP2` | Community BGM patch (see "Custom BGM" above); repo integration by Vesly |




