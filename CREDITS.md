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


## Batch2 Imported Classes (`FE8_NEW_ANIMS`)

Battle animations imported from the batch2 FE-Repo/FEBuilder animation folders under `C:\devkitPro\feex\banims\batch2`. Folder names retain the upstream artist tags and are registered in `scripts/banim_packs.json`.

### Batch2 Class Cards

```text
Class Card Credits
==================

Cards copied from C:\Users\David\Desktop\Repo\Class Cards
Destination file name in each animation folder: Class Card.png

Copied cards:
- [Axe-Custom] Swashbuckler [F] by Yellowtoad: Infantry - (Axe) Brigs, Pirates, Zerkers\Swashbuckler (F) Axe {Nuramon, ZoramineFae, Yellowtoad}.png
- [Axe-Custom] Swashbuckler [M] by Yellowtoad: Infantry - (Axe) Brigs, Pirates, Zerkers\Swashbuckler (M) Axe {Nuramon, ZoramineFae, Yellowtoad}.png
- [Berserker-Custom] Leo's Berserker [M] by Leo_Link: Infantry - (Axe) Brigs, Pirates, Zerkers\Berserker (M) Axe {IS}.png
- [CavalryCustom]_[U]_Updated_Grand_Mahout_by_Orihara_Saki_DatonDemand: Mounted - Dismounted, Monsters, Misc\Mahout {7743}.png
- [Custom_Halb]_[M]_Halberdier_+Axes_by_TBA: Infantry - (Lnc) Soldiers, Halberdiers\Halberdier (M) Lance {TBA}.png
- [Custom_Magi]_[F]_War_Cleric_by_SkidMarc25: Magi - Special\War Cleric (F) {Der}.png
- [Custom_Magi]_[F]_Witch_Nuibaba_by_Nuramon: Magi - Special\Witch {Aruka, Yggdra}.png
- [Custom_Magi]_[U]_Angel_by_Atey: Magi - Special\Angel (F) {N426}.png
- [DevisianCustom]_[M]_Occultist_v2_by_Devisian_Nights: Magi - Special\Occultist (M) Magic {Valak}.png.png
- [FE7 Lyn-Variant] T1 Blader Myrmidon V2 Ponytail [F] by Leo_Link: Infantry - (Swd) Myrms and Swordmasters\Myrmidon (F) Sword {L95}.png
- [FE7_HectorVariant]_[U]_T2_Harbinger_by_Nuramon - Copy: Lords - Vanilla and Custom\Harbinger (M) Magic {flasuban}.png
- [FE7_HectorVariant]_[U]_T2_Harbinger_by_Nuramon: Lords - Vanilla and Custom\Harbinger (M) Magic {flasuban}.png
- [FE8_EphraimCustom]_[M]_T2_Heavy_Infantry_by_Nuramon: Lords - Vanilla and Custom\Heavy Infantry (M) {SamirPlayz}.png
- [GeneralReskin]_[U]_Baron_+Weapons: Infantry - Knights, Generals, Armors\Baron (U) Lance {SamirPlayz}.png
- [GeneralReskin]_[U]_ShieldGeneral_v2_+Cape: Infantry - Knights, Generals, Armors\General Shield (U) Cape Lance {Topazlight,SamirPlayz,}.png
- [ManaketeCustom]_[U]_Black_Dragon_FE10Style_by_Nuramon: Monsters - Dragons and Special\Dragon (U) Magic {L95}.png
- [MonsterCustom]_[U]_Living_Armor_by_Sphealnuke: Monsters - Dragons and Special\Living Armor (U) {Sphealnuke}.png
- [MonsterCustom]_[U]_Wild_Fellbeast_by_Nuramon: Monsters - Dragons and Special\Wyvern Wild {Faeriefruit}.png
- [RogueVariant]_[F]_Samurai__Iaijutsu_Rogue: Infantry - (Swd) Thieves, Rogues, Assassins\Samurai (F) {VelvetKitsune, L95, Pushwall, Nuramon}.png
- [Sword Custom] Master Ninja [M] by Pikmin and Der: Infantry - (Swd) Thieves, Rogues, Assassins\Master Ninja (M) {Der}.png
- [Sword Custom] Ninja - Hooded [U] by Pikmin and Der: Infantry - (Swd) Thieves, Rogues, Assassins\Ninja {Der}.png
- [Sword FE15 Custom] Myrmidon [F] by Nuramon: Infantry - (Swd) Myrms and Swordmasters\Myrmidon (F) Sword {L95}.png
- [Sword FE15 Custom] Myrmidon [M] by Nuramon: Infantry - (Swd) Myrms and Swordmasters\Myrmidon (M) Sword {IS}.png
- [Sword_Custom]_[M]_Thug_by_MonkeyBard: Infantry - (Swd) Thieves, Rogues, Assassins\Thug (M) Sword {Rasdel}.png
- [Sword_FE16_Custom]_[U]_Dread_Fighter_by_Nuramon: Infantry - (Swd) Myrms and Swordmasters\[T2][SWD] Dread Fighter (U) {Nuramon}.png
- [T3_Custom]_[U]_Moloch_Sorcerer_by_Huichelaar: Magi - Dark-Type\Moloch Sorcerer (U) T3 Style {Huichelaar}.png
- [Tactician]_[U]_Tactician_by_SALVAGED: Magi - Special\Tactician (U) Magic {SALVAGED}.png
- [Trickster]_F_Trickster_V_2_Ponytail: Infantry - (Swd) Thieves, Rogues, Assassins\Trickster (F) Sword T2 {Jj09, Scraiza, Sword of HaE,SableMage}.png
- [Trickster]_M_Trickster_V_2_by_Leo_Link: Infantry - (Swd) Thieves, Rogues, Assassins\Trickster (M) Sword T2 {Jj09, Scraiza, Sword of HaE}.png
- [VillagerCustom]_F_Villager_v2_by_Nuramon: Bards, Dancers, Suppliers, Misc\Villager (U) Updated {Ghast, HyperGammaSpaces}.png
- [VillagerCustom]_M_Villager_v2_by_Nuramon: Bards, Dancers, Suppliers, Misc\Villager (U) Updated {Ghast, HyperGammaSpaces}.png
- [ZephielReskin]_[U]_Legion_King_by_Huichelaar: Infantry - Knights, Generals, Armors\King (U) T2 Style v2 {Huichelaar, Seal, Der, Mobile21}.png
- AxeCustom__%5BM__Oni_Chieftain_Repalette_by_Dora_Drago: Infantry - (Axe) Brigs, Pirates, Zerkers\Oni Chieftain (M) Axe {Dora Drago}.png
- BardBase__%5BM__Elffin_Fancy_%2BMagic: Bards, Dancers, Suppliers, Misc\Fancy Bard (M) +Lyre {MeatOfJustice}.png
- BrigandStyle_____Mounted_Marauder_by_TytheBub: Mounted - Cavs, Paladins, Rangers\Marauder (M) Axe {NoelWoodsoul}.png
- Custom_Drag_____Dragoon_Repal_by_Pikmin: Infantry - (Lnc) Soldiers, Halberdiers\Halberdier (M) Dragoon v2 Lance {Pikmin, Uncredited}.png
- Custom_Lance__%5BM__Lancer_by_SALVAGED: Infantry - (Lnc) Soldiers, Halberdiers\Lancer (M) Lance {SALVAGED}.png
- Custom_Lance__%5BM__Militia_Deserter_by_Alusq: Infantry - (Lnc) Soldiers, Halberdiers\Militia (M) Deserter Lance {Rasdel}.png
- EphraimVariant_____T1_Lancer_Fix_by_MemaeMemai: Infantry - (Lnc) Soldiers, Halberdiers\Halb-Lancer (M) {Jj09}.png
- HectorReskin__%5BM__T1_Waleed's_Gladiator_Repal_v2_%2BSword: Infantry - (Axe) Brigs, Pirates, Zerkers\Gladiator (M) Sword {L95, Pushwall}.png
- horn_brigand: Infantry - (Axe) Brigs, Pirates, Zerkers\Brigand (M) Axe {IS}.png
- horn_soldier: Infantry - (Lnc) Soldiers, Halberdiers\Soldier (M) FE10-Style Lance {flasuban}.png
- HunterM__%5BM__Hunter_by_MeatOfJustice: Infantry - (Bow) Archers and Hunters\Hunter (M) {Spud}.png
- MiscSupplierAnna_____Repalled_%2B_Weapons_by_JonoTheRed_DatonDemand: Bards, Dancers, Suppliers, Misc\Supplier (M) Potion {N426}.png
- MonsterCustom_____Mimic_Chest_by_Seal: Bards, Dancers, Suppliers, Misc\Chest Mimic {LaurentLacroix}.png
- MonsterCustom_____Mosquito_by_Dutch_Introvert: Monsters - Dragons and Special\Mosquito (U) {Odd Dutch}.png
- MonsterCustom_____Phantom_by_TBA: Monsters - Dragons and Special\Phantom (U) Axe {IS}.png
- MonsterCustom_____Slime_by_Yellowtoad: Monsters - Dragons and Special\Slime (U) {Yellowtoad}.png
- SniperReskin_____Adventurer_by_ltranc: Infantry - (Bow) Snipers and Ballistae\Adventurer (M) {Cygnus}.png

- [Custom_DM_[M]_Arcanist_by_Nuramon: Magi - Dark-Type\Dark Mage (M) {Jj09}.png (fallback dark mage card for Arcanist)
- [Custom_Magi]_[F]_Miko_V_2_by_RedBean: Infantry - (Bow) Snipers and Ballistae\Sniper (F) Long Hair Bow {flasuban, L95}.png
- [CustomLord]_[F]_Halberd_Brighid_by_Sphealnuke: Infantry - (Lnc) Soldiers, Halberdiers\Halberdier (F) Lance {TBA, Yellowtoad}.png
- [DevisianCustom]_[M]_Arcanist_by_Devisian_Nights: Magi - Dark-Type\Dark Mage (M) {Jj09}.png (fallback dark mage card for Arcanist)
- [DevisianCustom]_[M]_Magician_v2_by_Devisian_Nights: Magi - Nature-Type\Mage (M) Hatless Magic {RobertFPY}.png (fallback mage card for Magician)
- [MonsterCustom]_[M]_Djinn_by_Alexsplode: Monsters - Dragons and Special\Fire Imp {Alexsplode}.png (fallback fire-imp monster card for Djinn)
- [Sword_Custom]_[F]_Katarina_Fencer_by_GabrielKnight: Infantry - (Swd) Myrms and Swordmasters\Myrmidon (F) Sword {L95}.png
- [SwordmasterVariant]_[F]_Fir_by_Redbean: Infantry - (Swd) Myrms and Swordmasters\Swordmaster (F) Sword {L95}.png
- [SwordmasterVariant]_[M]_Trueblade_by_Dinar87: Infantry - (Swd) Myrms and Swordmasters\Swordmaster (M) Sword {IS}.png
- [T3_Custom]_[M]_Red_Mage_by_Mycahel: Magi - Nature-Type\Mage (M) Fire Magic {L95}.png (fallback fire mage card for Red Mage)
- Crossbow__%5BM__Mechanist_by_Sphealnuke: Infantry - (Bow) Archers and Hunters\Cowboy (M) Crossbow {MeatofJustice}.png (fallback for Mechanist/crossbow)
- Custom_Lance_____Sentinel_by_Nuramon: Infantry - (Lnc) Soldiers, Halberdiers\Halberdier (M) Lance {TBA}.png
- Monster_Custom_____Sandworm_by_Stephano: Monsters - Dragons and Special\Slime (U) {Yellowtoad}.png (fallback monster card for Sandworm)
- MonsterCustom_____Cursed_Sword_by_SALVAGED: Monsters - Dragons and Special\Cursed Sword {Der}.png
- MonsterCustom_____Magical_Tomes_by_N426: Monsters - Dragons and Special\Cursed Tome {N426}.png
- MonsterCustom_____Warbird_by_Alexsplode: Monsters - Dragons and Special\Harpy (U) {Sphealnuke}.png (fallback flying monster card for Warbird)
No suitable card found / not copied:
```

### Batch2 Map Sprites

```text
Map Sprite Credits
==================

Preferred source: C:\Users\David\Desktop\SRR_FEGBA\gfx\MapSprites
Fallback source: C:\Users\David\Desktop\Repo\Map Sprites
Destination file names in each animation folder: SMS.png and MMS.png

Copied map sprites:
- [Axe-Custom] Swashbuckler [F] by Yellowtoad: Repo/Map Sprites: Infantry - (Axe) Brigs, Pirates, Zerkers\Swashbuckler (F) Axe {Yellowtoad}-stand.png + Infantry - (Axe) Brigs, Pirates, Zerkers\Swashbuckler (F) Axe {Yellowtoad}-walk.png
- [Axe-Custom] Swashbuckler [M] by Yellowtoad: Repo/Map Sprites: Infantry - (Axe) Brigs, Pirates, Zerkers\Swashbuckler (M) Axe {Yellowtoad}-stand.png + Infantry - (Axe) Brigs, Pirates, Zerkers\Swashbuckler (M) Axe {Yellowtoad}-walk.png
- [Berserker-Custom] Leo's Berserker [M] by Leo_Link: Repo/Map Sprites: Infantry - (Axe) Brigs, Pirates, Zerkers\Berserker (M) Axe {IS}-stand.png + Infantry - (Axe) Brigs, Pirates, Zerkers\Berserker (M) Axe {IS}-walk.png
- [CavalryCustom]_[U]_Updated_Grand_Mahout_by_Orihara_Saki_DatonDemand: SRR_FEGBA/gfx/MapSprites: SMS/GrandMahout_CamusZekeSirius_SHYUTERz_Orihara_Datstand.png + MMS/GrandMahout_CamusZekeSirius_SHYUTERz_Orihara_Datwalk.png
- [Custom_DM_[M]_Arcanist_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/Arcanist_U_Unfinished_Norikinsstand.png + MMS/Arcanist_U_Unfinished_Norikinswalk.png
- [Custom_Halb]_[M]_Halberdier_+Axes_by_TBA: SRR_FEGBA/gfx/MapSprites: SMS/Halberdier_M_2_0_TBAstand.png + MMS/Halberdier_M_2_0_TBAwalk.png
- [Custom_Magi]_[F]_Miko_V_2_by_RedBean: SRR_FEGBA/gfx/MapSprites: SMS/Miko_Diviner_F_Orochi_Sphealnukestand.png + MMS/Miko_Diviner_F_Orochi_Sphealnukewalk.png
- [Custom_Magi]_[F]_War_Cleric_by_SkidMarc25: SRR_FEGBA/gfx/MapSprites: SMS/WarCleric_F_Staff_SkidMarc25stand.png + MMS/WarCleric_F_Staff_SkidMarc25walk.png
- [Custom_Magi]_[F]_Witch_Nuibaba_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/Witch_F_Aruka_Kenpuhustand.png + MMS/Witch_F_Aruka_Kenpuhuwalk.png
- [Custom_Magi]_[U]_Angel_by_Atey: SRR_FEGBA/gfx/MapSprites: SMS/Angel_F_Unknownstand.png + MMS/Angel_F_Unknownwalk.png
- [CustomLord]_[F]_Halberd_Brighid_by_Sphealnuke: SRR_FEGBA/gfx/MapSprites: SMS/Brighid_Hector_Axe_Shin19stand.png + MMS/Brighid_Hector_Axe_Shin19walk.png
- [DevisianCustom]_[M]_Arcanist_by_Devisian_Nights: SRR_FEGBA/gfx/MapSprites: SMS/Arcanist_U_Unfinished_Norikinsstand.png + MMS/Arcanist_U_Unfinished_Norikinswalk.png
- [DevisianCustom]_[M]_Magician_v2_by_Devisian_Nights: SRR_FEGBA/gfx/MapSprites: SMS/Magician_Eliwood_16x16_TyTheBubstand.png + MMS/Magician_EliwoodTyTheBubwalk.png
- [DevisianCustom]_[M]_Occultist_v2_by_Devisian_Nights: SRR_FEGBA/gfx/MapSprites: SMS/Shaman_M_Occultist_Devisian_Nights_Pikminstand.png + MMS/Shaman_M_Occultist_Devisian_Nights_Pikminwalk.png
- [FE7 Lyn-Variant] T1 Blader Myrmidon V2 Ponytail [F] by Leo_Link: SRR_FEGBA/gfx/MapSprites: SMS/Blade_Lord_F_Lyn_Sword_ISstand.png + MMS/Blade_Lord_F_Lyn_Sword_ISwalk.png (fallback Lyn blade-lord pair)
- [FE7_HectorVariant]_[U]_T2_Harbinger_by_Nuramon - Copy: SRR_FEGBA/gfx/MapSprites: SMS/Great_Lord_M_HectorHarbinger_SD9Kstand.png + MMS/Great_Lord_M_HectorHarbinger_SD9Kwalk.png
- [FE7_HectorVariant]_[U]_T2_Harbinger_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/Great_Lord_M_HectorHarbinger_SD9Kstand.png + MMS/Great_Lord_M_HectorHarbinger_SD9Kwalk.png
- [FE8_EphraimCustom]_[M]_T2_Heavy_Infantry_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/HeavyInfantry_Ephraim_Snewpingstand.png + MMS/HeavyInfantry_EphraimSnewpingwalk.png
- [GeneralReskin]_[U]_Baron_+Weapons: SRR_FEGBA/gfx/MapSprites: SMS/Baron_U_Lance_Topazlight_Nuramon_Its_Just_Jaystand.png + MMS/Baron_U_Cape_Nuramon_Jay_Rynwalk.png
- [GeneralReskin]_[U]_ShieldGeneral_v2_+Cape: Repo/Map Sprites: Infantry - Knights, Generals, Armors\Baron (U) +Cape and Shield Lance Centurion Helm {Nuramon, Jay, Ryn}-stand.png + Infantry - Knights, Generals, Armors\Baron (U) +Cape and Shield Lance Centurion Helm {Nuramon, Jay, Ryn}-walk.png
- [ManaketeCustom]_[U]_Black_Dragon_FE10Style_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/BlackDragon_U_Magic_L95stand.png + MMS/BlackDragon_U_Magic_L95walk.png
- [MonsterCustom]_[M]_Djinn_by_Alexsplode: SRR_FEGBA/gfx/MapSprites: SMS/Djinn_M_Alexsplodestand.png + MMS/Djinn_M_Alexsplodewalk.png
- [MonsterCustom]_[U]_Living_Armor_by_Sphealnuke: SRR_FEGBA/gfx/MapSprites: SMS/LivingArmor_Red_Flame_Sphealnuke_topazlightstand.png + MMS/LivingArmor_Red_Flame_Sphealnuke_topazlightwalk.png
- [MonsterCustom]_[U]_Wild_Fellbeast_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/Fellbeast_Wyvern_Wild_U_16x16_Faeriefruitstand.png + MMS/Fellbeast_Wyvern_Wild_U_Faeriefruitwalk.png
- [RogueVariant]_[F]_Samurai__Iaijutsu_Rogue: Repo/Map Sprites: Infantry - (Swd) Thieves, Rogues, Assassins\Samurai (Iaijutsu - Rouge) (F) Sword {GabrielKnight}-stand.png + Infantry - (Swd) Thieves, Rogues, Assassins\Samurai (Iaijutsu - Rouge) (F) Sword {GabrielKnight}-walk.png
- [Sword Custom] Ninja - Hooded [U] by Pikmin and Der: SRR_FEGBA/gfx/MapSprites: SMS/Ninja_Derstand.png + MMS/Ninja_Derwalk.png
- [Sword FE15 Custom] Myrmidon [F] by Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/FE15Myrmidon_U_Sword_Nuramonstand.png + MMS/FE15Myrmidon_U_Sword_Nuramonwalk.png
- [Sword FE15 Custom] Myrmidon [M] by Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/FE15Myrmidon_U_Sword_Nuramonstand.png + MMS/FE15Myrmidon_U_Sword_Nuramonwalk.png
- [Sword_Custom]_[F]_Katarina_Fencer_by_GabrielKnight: SRR_FEGBA/gfx/MapSprites: SMS/Fencer_Blade_LordAnnoyingAnonstand.png + MMS/Fencer_Blade_LordAnnoyingAnonwalk.png
- [Sword_Custom]_[M]_Thug_by_MonkeyBard: Repo/Map Sprites: Infantry - (Swd) Thieves, Rogues, Assassins\Thug (M) Sword {Rasdel}-stand.png + Infantry - (Swd) Thieves, Rogues, Assassins\Thug (M) Sword {Rasdel}-walk.png
- [Sword_FE16_Custom]_[U]_Dread_Fighter_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/Dread_Fighter_M_Nuramonstand.png + MMS/Dread_Fighter_M_Nuramonwalk.png
- [SwordmasterVariant]_[F]_Fir_by_Redbean: Repo/Map Sprites: Infantry - (Swd) Myrms and Swordmasters\Swordmaster (F) {IS}-stand.png + Infantry - (Swd) Myrms and Swordmasters\Swordmaster (F) {IS}-walk.png
- [SwordmasterVariant]_[M]_Trueblade_by_Dinar87: Repo/Map Sprites: Infantry - (Swd) Myrms and Swordmasters\Trueblade (M) {Seliost1}-stand.png + Infantry - (Swd) Myrms and Swordmasters\Trueblade (M) {Seliost1}-walk.png
- [T3_Custom]_[M]_Red_Mage_by_Mycahel: SRR_FEGBA/gfx/MapSprites: SMS/RedMage2_Sage_Hat_TopazlightUnknownstand.png + MMS/RedMage2_Sage_Hat_TopazlightUnknownwalk.png
- [T3_Custom]_[U]_Moloch_Sorcerer_by_Huichelaar: Repo/Map Sprites: Magi - Dark-Type\Moloch Sorcerer (U) {Huichelaar}-stand.png + Magi - Dark-Type\Moloch Sorcerer (U) {Huichelaar}-walk.png
- [Tactician]_[U]_Tactician_by_SALVAGED: SRR_FEGBA/gfx/MapSprites: SMS/Tactician_U_SALVAGEDstand.png + MMS/Tactician_U_SALVAGEDwalk.png
- [Trickster]_F_Trickster_V_2_Ponytail: Repo/Map Sprites: Infantry - (Swd) Thieves, Rogues, Assassins\Trickster (F) {StreetHero, Sable Mage}-stand.png + Infantry - (Swd) Thieves, Rogues, Assassins\Trickster (F) {StreetHero, Sable Mage}-walk.png
- [Trickster]_M_Trickster_V_2_by_Leo_Link: Repo/Map Sprites: Infantry - (Swd) Thieves, Rogues, Assassins\Trickster (M) {StreetHero}-stand.png + Infantry - (Swd) Thieves, Rogues, Assassins\Trickster (M) {StreetHero}-walk.png
- [VillagerCustom]_F_Villager_v2_by_Nuramon: Repo/Map Sprites: Infantry - (Swd) Mercenaries and Heroes\Villager (F) v2 Sword {HyperGammaSpaces}-stand.png + Infantry - (Swd) Mercenaries and Heroes\Villager (F) v2 Sword {HyperGammaSpaces}-walk.png
- [VillagerCustom]_M_Villager_v2_by_Nuramon: Repo/Map Sprites: Infantry - (Swd) Mercenaries and Heroes\Villager (M) v2 Sword {HyperGammaSpaces}-stand.png + Infantry - (Swd) Mercenaries and Heroes\Villager (M) v2 Sword {HyperGammaSpaces}-walk.png
- [ZephielReskin]_[U]_Legion_King_by_Huichelaar: SRR_FEGBA/gfx/MapSprites: SMS/LegionKing_Lance_EN_L95_Pikmin_Der_Huichelaarstand.png + MMS/LegionKing_Lance_EN_L95_Pikmin_Der_Huichelaarwalk.png
- AxeCustom__%5BM__Oni_Chieftain_Repalette_by_Dora_Drago: Repo/Map Sprites: Infantry - (Axe) Brigs, Pirates, Zerkers\Berserker (M) Oni Chieftain {Dora Drago}-stand.png + Infantry - (Axe) Brigs, Pirates, Zerkers\Berserker (M) Oni Chieftain {Dora Drago}-walk.png
- BardBase__%5BM__Elffin_Fancy_%2BMagic: SRR_FEGBA/gfx/MapSprites: SMS/Bard_M_Elffin_ISstand.png + MMS/Bard_M_Elffin_ISwalk.png
- BrigandStyle_____Mounted_Marauder_by_TytheBub: SRR_FEGBA/gfx/MapSprites: SMS/Marauder_M_Basic_Axe_Blademasterstand.png + MMS/Marauder_M_Basic_Axe_Blademasterwalk.png
- Crossbow__%5BM__Mechanist_by_Sphealnuke: Repo/Map Sprites: Infantry - (Bow) Archers and Hunters\Cowboy (M) Crossbow {MeatofJustice}-stand.png + Infantry - (Bow) Archers and Hunters\Cowboy (M) Crossbow {MeatofJustice}-walk.png (fallback for Mechanist/crossbow)
- Custom_Drag_____Dragoon_Repal_by_Pikmin: SRR_FEGBA/gfx/MapSprites: SMS/Dragoon_M_v2_Lance_Pikmin_Unknownstand.png + MMS/Dragoon_M_v2_Lance_Pikmin_Unknownwalk.png
- Custom_Lance_____Sentinel_by_Nuramon: SRR_FEGBA/gfx/MapSprites: SMS/Sentinel_Halberdier_Aruka_Kenpuhustand.png + MMS/Sentinel_Halberdier_Aruka_Kenpuhuwalk.png
- Custom_Lance__%5BM__Lancer_by_SALVAGED: SRR_FEGBA/gfx/MapSprites: SMS/Lancer_M_Brown_Hair_SALVAGEDstand.png + MMS/Lancer_M_Brown_Hair_SALVAGEDwalk.png
- Custom_Lance__%5BM__Militia_Deserter_by_Alusq: SRR_FEGBA/gfx/MapSprites: SMS/Militia_M_Deserter_Lance_Alusqstand.png + MMS/Militia_M_Deserter_Lance_Alusqwalk.png
- EphraimVariant_____T1_Lancer_Fix_by_MemaeMemai: SRR_FEGBA/gfx/MapSprites: SMS/Lancer_M_Brown_Hair_SALVAGEDstand.png + MMS/Lancer_M_Brown_Hair_SALVAGEDwalk.png (fallback lancer pair)
- HectorReskin__%5BM__T1_Waleed's_Gladiator_Repal_v2_%2BSword: SRR_FEGBA/gfx/MapSprites: SMS/Gladiator_M_Sword_Pikmin_L95_Pushwallstand.png + MMS/Gladiator_M_Sword_Pikmin_L95_Pushwallwalk.png
- horn_brigand: Repo/Map Sprites: Infantry - (Axe) Brigs, Pirates, Zerkers\Brigand (M) Axe {IS}-stand.png + Infantry - (Axe) Brigs, Pirates, Zerkers\Brigand (M) Axe {IS}-walk.png
- horn_soldier: Repo/Map Sprites: Infantry - (Lnc) Soldiers, Halberdiers\Soldier (M) FE10-Style Lance {flasuban}-stand.png + Infantry - (Lnc) Soldiers, Halberdiers\Soldier (M) FE10-Style Lance {flasuban}-walk.png
- HunterM__%5BM__Hunter_by_MeatOfJustice: SRR_FEGBA/gfx/MapSprites: SMS/Hunter_M_MeatOfJusticestyle_knabepicerstand.png + MMS/Hunter_M_MeatOfJusticestyle_knabepicerwalk.png
- MiscSupplierAnna_____Repalled_%2B_Weapons_by_JonoTheRed_DatonDemand: SRR_FEGBA/gfx/MapSprites: SMS/Supplier_v2_Anna_F_Unarmed_N426_Erukolindostand.png + MMS/Supplier_v2_Anna_F_Unarmed_N426_Erukolindowalk.png
- Monster_Custom_____Sandworm_by_Stephano: SRR_FEGBA/gfx/MapSprites: SMS/Sandworm_Norikins_stand.png + MMS/Sandworm_Norikins_move.png
- MonsterCustom_____Cursed_Sword_by_SALVAGED: SRR_FEGBA/gfx/MapSprites: SMS/Cursed_Sword_U_Derstand.png + MMS/Cursed_Sword_U_Derwalk.png
- MonsterCustom_____Magical_Tomes_by_N426: SRR_FEGBA/gfx/MapSprites: SMS/Tome_U_Anima_N426stand.png + MMS/Tome_U_Anima_N426walk.png
- MonsterCustom_____Mimic_Chest_by_Seal: Repo/Map Sprites: Monsters - Dragons and Special\Mimic (U) {Seal}-stand.png + Monsters - Dragons and Special\Mimic (U) {Seal}-walk.png
- MonsterCustom_____Mosquito_by_Dutch_Introvert: SRR_FEGBA/gfx/MapSprites: SMS/Mosquito_U_Dutch_Introvertstand.png + MMS/Mosquito_U_Dutch_Introvertwalk.png
- MonsterCustom_____Phantom_by_TBA: SRR_FEGBA/gfx/MapSprites: SMS/Phantom_U_IS_Pushwallstand.png + MMS/Phantom_U_ISwalk.png
- MonsterCustom_____Slime_by_Yellowtoad: SRR_FEGBA/gfx/MapSprites: SMS/Slime_U_Yellowtoadstand.png + MMS/Slime_U_Yellowtoadwalk.png
- MonsterCustom_____Warbird_by_Alexsplode: SRR_FEGBA/gfx/MapSprites: SMS/Warbird_F_Unknown_Alexsplodestand.png + MMS/Warbird_F_Unknown_Alexsplodewalk.png

- [Sword Custom] Master Ninja [M] by Pikmin and Der: SRR_FEGBA/gfx/MapSprites: SMS/Ninja_Derstand.png + MMS/Ninja_Derwalk.png (fallback ninja pair for Master Ninja)
- SniperReskin_____Adventurer_by_ltranc: Repo/Map Sprites: Infantry - (Bow) Snipers and Ballistae\Sniper (M) {IS}-stand.png + Infantry - (Bow) Snipers and Ballistae\Sniper (M) {IS}-walk.png (fallback sniper pair for Adventurer)
No suitable map sprite found / not copied:
```

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




