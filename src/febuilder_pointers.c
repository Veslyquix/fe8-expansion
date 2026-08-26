#include "global.h"

#if FE8_FEBUILDER_POINTERS

#include "febuilder_pointers.h"
#include "bmunit.h"
#include "bmitem.h"
#include "face.h"
#include "chapterdata.h"
#include "soundroom.h"
#include "proc.h"
#include "bmsave.h"
#include "constants/items.h"
#include "constants/terrains.h"

/* Symbols with real external linkage that no header reachable from
 * global.h declares. Only their ADDRESS is taken below, so an opaque
 * byte-array type is sufficient and avoids duplicating (or conflicting
 * with) whatever richer type their defining translation unit uses. */
extern const u8 AiEscapePts_None[];
extern const u8 CreditsCG_EndingCredits_0[];
extern const u8 EventScrWM_Prologue_Beginning[];
extern const u8 EventScr_EirikaModeGameEnd[];
extern const u8 EventScr_EphraimModeGameEnd[];
extern const u8 EventScr_SkirmishCommonBeginning[];
extern const u8 EventScr_SkirmishCommonEnd[];
extern const u8 Events_WM_Beginning[];
extern const u8 Events_WM_ChapterIntro[];
extern const u8 GfxSet_WmNationMap[];
extern const u8 Img_Banimmisc_0[];
extern const u8 Img_EfxLeftItemBox[];
extern const u8 Img_EfxLeftNameBox[];
extern const u8 Img_EfxRightItemBox[];
extern const u8 Img_EfxRightNameBox[];
extern const u8 Img_PrepItemListSpinningArrow[];
extern const u8 Init[];
extern const u8 ItemList_WM_BorderMulan_Armory[];
extern const u8 ItemList_WM_BorderMulan_SecretShop[];
extern const u8 ItemList_WM_BorderMulan_Vendor[];
extern const u8 MenuAlwaysEnabled[];
extern const u8 MenuAlwaysNotShown[];
extern const u8 MenuDef_RouteSplit[];
extern const u8 Menu_PromoSubConfirm[];
extern const u8 MuSoundScr_Foot[];
extern const u8 ObjectType1[];
extern const u8 ObjectType2[];
extern const u8 ObjectType3[];
extern const u8 ObjectType4[];
extern const u8 Pal_LimitViewBlue[];
extern const u8 Pal_LimitViewGreen[];
extern const u8 Pal_LimitViewRed[];
extern const u8 Pal_MenuScrollBar[];
extern const u8 Pal_SpinningArrow[];
extern const u8 SupportData_Eirika[];
extern const u8 TileConfiguration1[];
extern const u8 TileConfiguration2[];
extern const u8 TileConfiguration3[];
extern const u8 TileConfiguration4[];
extern const u8 WmMonsterGenerateRatesIdx_EirikaMode[];
extern const u8 WmMonsterGenerateRatesIdx_EphraimMode[];
extern const u8 WmMonsterGenerateRates_EirikaMode[];
extern const u8 WmMonsterGenerateRates_EphraimMode[];
extern const u8 WmMonsterGenerateRates_XmapEirika[];
extern const u8 WmMonsterGenerateRates_XmapEphraim[];
extern const u8 banim_data[];
extern const u8 battle_terrain_table[];
extern const u8 chap_title_data[];
extern const u8 character_battle_animation_palette_table[];
extern const u8 gAffinityBonuses[];
extern const u8 gAiCombatScoreCoefficientTable[];
extern const u8 gAiItemConfigTable[];
extern const u8 gAiState[];
extern const u8 gAiStealPriorityItemList[];
extern const u8 gArenaState[];
extern const u8 gBanimBossBGMs[];
extern const u8 gBanimLinkArenaFlag[];
extern const u8 gBanimmisc_0[];
extern const u8 gBanimmisc_1[];
extern const u8 gBanimmisc_2[];
extern const u8 gBanimmisc_3[];
extern const u8 gBanimmisc_5[];
extern const u8 gBanimmisc_6[];
extern const u8 gBattleBGDataTable[];
extern const u8 gCGDataTable[];
extern const u8 gCharacterEndingDefeatLut[];
extern const u8 gCharacterEndingTitleLut[];
extern const u8 gCharacterEndingsByRoute[];
extern const u8 gCharacterEndings_Ephraim[];
extern const u8 gClassList_BowArena[];
extern const u8 gClassList_MagicArena[];
extern const u8 gClassList_MeleeArena[];
extern const u8 gClassReelData[];
extern const u8 gDebugClearMenuDef[];
extern const u8 gDebugClearMenuItems[];
extern const u8 gEkrSpellAnimLut[];
extern const u8 gEndingCredits_0[];
extern const u8 gGameOptions[];
extern const u8 gGameOptionsUiOrder[];
extern const u8 gGuideTable[];
extern const u8 gHelpInfo_CbpHp[];
extern const u8 gHelpInfo_MbpHp[];
extern const u8 gHelpInfo_Ss0Pow[];
extern const u8 gHelpInfo_Ss1Item0[];
extern const u8 gHelpInfo_Ss2Rank0[];
extern const u8 gItemSubMenuItems[];
extern const u8 gLinkArenaBanList[];
extern const u8 gMapMenuItems[];
extern const u8 gMenuDef_PromoSel[];
extern const u8 gMenu_WMGeneralMenu[];
extern const u8 gMenu_WMNodeMenu[];
extern const u8 gMonsterClassWeights[];
extern const u8 gMonsterItemTable[];
extern const u8 gMonsterItemWeightsTable[];
extern const u8 gMonsterItemsByClassIndex[];
extern const u8 gOpSubtitleGfxLut[];
extern const u8 gOpinfo_1[];
extern const u8 gPal_SupportScreenBanner[];
extern const u8 gPaletteBuffer[];
extern const u8 gPrepShopInventory[];
extern const u8 gProcScr_GameControl[];
extern const u8 gProcScr_SoundRoomUi[];
extern const u8 gProc_MapTask[];
extern const u8 gRedAiEscapePoints[];
extern const u8 gSongTable[];
extern const u8 gSoundSt[];
extern const u8 gSpellAssocData[];
extern const u8 gTSA_BattleForecastStandard[];
extern const u8 gTextIds_GuideCategoriesChapter[];
extern const u8 gTextIds_GuideCategoriesTopic[];
extern const u8 gUnitActionMenuItems[];
extern const u8 gUnitListScreenFields[];
extern const u8 gUnused_BmsaveLib_0[];
extern const u8 gWMMonsterSpawnLocations[];
extern const u8 gWMNodeData[];
extern const u8 gWMNodeIconData[];
extern const u8 gWMPathData[];
extern const u8 gWMSongTable[];
extern const u8 gWorldmapGmap_0[];
extern const u8 gWorldmapGmap_1[];
extern const u8 gWorldmapGmap_2[];
extern const u8 gWorldmapGmap_3[];
extern const u8 gWorldmapMapmu_2[];
extern const u8 gpAi1Table[];
extern const u8 gpAi2Table[];
extern const u8 item_icon_palette[];
extern const u8 item_icon_tiles[];
extern const u8 sActiveMsg[];
extern const u8 sAiSpecialItemFuncLut[];
extern const u8 sAiStaffFuncLut[];
extern const u8 sHelpInfo_ChapterStatus_TurnCount[];
extern const u8 sMsgString[];
extern const u8 sPage0TextInfo[];
extern const u8 sPage1TextInfo[];
extern const u8 unit_icon_move_table[];
extern const u8 unit_icon_pal_after_action[];
extern const u8 unit_icon_pal_enemy[];
extern const u8 unit_icon_pal_npc[];
extern const u8 unit_icon_wait_table[];

/* FEBuilderGBA's ROMFE8U.cs hardcodes, for each field, the vanilla ROM
 * address of a POINTER CELL -- an inline literal-pool word holding the
 * real table address -- which FEBuilder dereferences to find the table.
 * A recompiled ROM has no such literal pool at a stable address, so this
 * array supplies the equivalent: each 'slot' entry below IS a pointer
 * cell, and scripts/gen_custom_pointer_txt.py writes that cell's own ROM
 * offset into fireemblem8.custom_pointer.txt for FEBuilder to dereference.
 *
 * Entry kinds (see tools/febuilder_pointers/field_order.txt, which pairs
 * each field name with its kind, in this exact order):
 *   slot   -- FEBuilder wants a pointer cell; it gets this entry's address
 *   direct -- FEBuilder wants the data address itself; it gets this value
 *   scalar -- a size/count/id constant; it gets this value verbatim
 *
 * Mapping was derived by dereferencing each vanilla pointer cell in
 * baserom.gba, resolving the target through reference/fe8u_symbols.txt to
 * a vanilla symbol name, and confirming that same symbol exists here.
 * Scalars use sizeof()/offsetof()/real constants rather than copied
 * vanilla literals, so they track this repo's actual layout. */
CONST_DATA u32 gFebuilderPointers[] = {
    (u32)&(gMsgHuffmanTableRoot), // mask_point_base_pointer [slot]
    (u32)&(gMsgHuffmanTable), // mask_pointer [slot]
    (u32)&(gMsgTable), // text_pointer [slot]
    (u32)&(gMsgTable), // text_recover_address [direct]
    (u32)&(gCharacterData), // unit_pointer [slot]
    (u32)(sizeof(struct CharacterData)), // unit_datasize [scalar]
    (u32)&gClassData - sizeof(struct ClassData), // class_pointer [slot]
    (u32)(sizeof(struct ClassData)), // class_datasize [scalar]
    (u32)&(gConvoBackgroundData), // bg_pointer [slot]
    (u32)&portrait_data - sizeof(struct FaceData), // portrait_pointer [slot]
    (u32)(sizeof(struct FaceData)), // portrait_datasize [scalar]
    (u32)&(item_icon_tiles), // icon_pointer [slot]
    (u32)&(item_icon_tiles), // icon_orignal_address [direct]
    (u32)&(item_icon_palette), // icon_palette_pointer [slot]
    (u32)&(unit_icon_wait_table), // unit_wait_icon_pointer [slot]
    (u32)&(gPal_MapSprite), // unit_icon_palette_address [direct]
    (u32)&(unit_icon_pal_enemy), // unit_icon_enemey_palette_address [direct]
    (u32)&(unit_icon_pal_npc), // unit_icon_npc_palette_address [direct]
    (u32)&(unit_icon_pal_after_action), // unit_icon_gray_palette_address [direct]
    (u32)&(gPal_MapSpriteArena), // unit_icon_four_palette_address [direct]
    (u32)&(gPal_LightRune), // unit_icon_lightrune_palette_address [direct]
    (u32)&(gPal_MapSpriteSepia), // unit_icon_sepia_palette_address [direct]
    (u32)&(unit_icon_move_table), // unit_move_icon_pointer [slot]
    (u32)&(gChapterDataTable), // map_setting_pointer [slot]
    (u32)(sizeof(struct ROMChapterData)), // map_setting_datasize [scalar]
    (u32)(offsetof(struct ROMChapterData, mapEventDataId)), // map_setting_event_plist_pos [scalar]
    (u32)(offsetof(struct ROMChapterData, gmapEventId)), // map_setting_worldmap_plist_pos [scalar]
    (u32)(offsetof(struct ROMChapterData, goalWindowTextId)), // map_setting_clear_conditon_text_pos [scalar]
    (u32)(offsetof(struct ROMChapterData, chapTitleTextId)), // map_setting_name_text_pos [scalar]
    (u32)&(gChapterDataAssetTable), // map_config_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_obj_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_pal_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_tileanime1_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_tileanime2_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_map_pointer_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_mapchange_pointer [slot]
    (u32)&(gChapterDataAssetTable), // map_event_pointer [slot]
    (u32)&(Init), // map_worldmapevent_pointer [direct]
    (u32)&(banim_data), // image_battle_animelist_pointer [slot]
    (u32)&(SupportData_Eirika), // support_unit_pointer [slot]
    (u32)&(gSupportTalkList), // support_talk_pointer [slot]
    (u32)&(gAnimCharaPalIt), // unit_palette_color_pointer [slot]
    (u32)&(gAnimCharaPalConfig), // unit_palette_class_pointer [slot]
    (u32)&(gAffinityBonuses), // support_attribute_pointer [slot]
    (u32)&(TerrainTable_HealAmount), // terrain_recovery_pointer [slot]
    (u32)&(TerrainTable_HealsStatus), // terrain_bad_status_recovery_pointer [slot]
    (u32)&(TerrainTable_MovCost_BerserkerNormal), // terrain_show_infomation_pointer [slot]
    (u32)&(TerrainMoveCost_Ballista), // ballista_movcost_pointer [slot]
    (u32)&(gPromoJidLut), // ccbranch_pointer [slot]
    (u32)&gPromoJidLut + 1, // ccbranch2_pointer [slot]
    (u32)&(Init), // class_alphaname_pointer [direct]
    (u32)&(gTerrains_0), // map_terrain_name_pointer [slot]
    (u32)&(chap_title_data), // image_chapter_title_pointer [slot]
    (u32)&(Pal_MenuScrollBar), // image_chapter_title_palette [direct]
    (u32)&(character_battle_animation_palette_table), // image_unit_palette_pointer [slot]
    (u32)&(gItemData), // item_pointer [slot]
    (u32)(sizeof(struct ItemData)), // item_datasize [scalar]
    (u32)&(gSpellAssocData), // item_effect_pointer [slot]
    (u32)&(gSongTable), // sound_table_pointer [slot]
    (u32)&(gSoundRoomTable), // sound_room_pointer [slot]
    (u32)(sizeof(struct SoundRoomEnt)), // sound_room_datasize [scalar]
    (u32)&(Init), // sound_room_cg_pointer [direct]
    (u32)&(gBattleTalkList), // event_ballte_talk_pointer [slot]
    (u32)&(Init), // event_ballte_talk2_pointer [direct]
    (u32)&(gDefeatTalkList), // event_haiku_pointer [slot]
    (u32)&(Init), // event_haiku_tutorial_1_pointer [direct]
    (u32)&(Init), // event_haiku_tutorial_2_pointer [direct]
    (u32)&(gForceDeploymentList), // event_force_sortie_pointer [slot]
    (u32)&(Init), // event_tutorial_pointer [direct]
    (u32)&(gRedAiEscapePoints), // map_exit_point_pointer [slot]
    (u32)&(AiEscapePts_None), // map_exit_point_blank [direct]
    (u32)&(gBanimBossBGMs), // sound_boss_bgm_pointer [slot]
    (u32)&(MuSoundScr_Foot), // sound_foot_steps_data_pointer [slot]
    (u32)&(gWorldmapMapmu_2), // worldmap_scroll_somedata_pointer [slot]
    (u32)&(gWMNodeData), // worldmap_point_pointer [slot]
    (u32)&(gWMSongTable), // worldmap_bgm_pointer [slot]
    (u32)&(gWMNodeIconData), // worldmap_icon_data_pointer [slot]
    (u32)&(Events_WM_Beginning), // worldmap_event_on_stageclear_pointer [slot]
    (u32)&(Events_WM_ChapterIntro), // worldmap_event_on_stageselect_pointer [slot]
    (u32)&(GfxSet_WmNationMap), // worldmap_county_border_pointer [slot]
    (u32)&(Pal_WmHighLightNationMap), // worldmap_county_border_palette_pointer [slot]
    (u32)&(gPrepShopInventory), // item_shop_hensei_pointer [slot]
    (u32)&(gCharacterEndingDefeatLut), // ed_1_pointer [slot]
    (u32)&(gCharacterEndingTitleLut), // ed_2_pointer [slot]
    (u32)&(gCharacterEndingsByRoute), // ed_3a_pointer [direct]
    (u32)&(gCharacterEndings_Ephraim), // ed_3b_pointer [slot]
    (u32)&(Init), // ed_3c_pointer [direct]
    (u32)(ITEM_HEROCREST), // cc_item_hero_crest_itemid [scalar]
    (u32)(ITEM_KNIGHTCREST), // cc_item_knight_crest_itemid [scalar]
    (u32)(ITEM_ORIONSBOLT), // cc_item_orion_bolt_itemid [scalar]
    (u32)(ITEM_ELYSIANWHIP), // cc_elysian_whip_itemid [scalar]
    (u32)(ITEM_GUIDINGRING), // cc_guiding_ring_itemid [scalar]
    (u32)(ITEM_HEAVENSEAL), // cc_fallen_contract_itemid [scalar]
    (u32)(ITEM_MASTERSEAL), // cc_master_seal_itemid [scalar]
    (u32)(ITEM_OCEANSEAL), // cc_ocean_seal_itemid [scalar]
    (u32)(ITEM_LUNARBRACE), // cc_moon_bracelet_itemid [scalar]
    (u32)(ITEM_SOLARBRACE), // cc_sun_bracelet_itemid [scalar]
    (u32)&(gItemUseJidList_HeroCrest), // cc_item_hero_crest_pointer [slot]
    (u32)&(gItemUseJidList_KnightCrest), // cc_item_knight_crest_pointer [slot]
    (u32)&(gItemUseJidList_OrionsBolt), // cc_item_orion_bolt_pointer [slot]
    (u32)&(gItemUseJidList_ElysianWhip), // cc_elysian_whip_pointer [slot]
    (u32)&(gItemUseJidList_GuidRing), // cc_guiding_ring_pointer [slot]
    (u32)&(gItemUseJidList_HeavenSeal), // cc_fallen_contract_pointer [slot]
    (u32)&(gItemUseJidList_MasterSeal), // cc_master_seal_pointer [slot]
    (u32)&(gItemUseJidList_OceanSeal), // cc_ocean_seal_pointer [slot]
    (u32)&(gItemUseJidList_LunarBrace), // cc_moon_bracelet_pointer [slot]
    (u32)&(gItemUseJidList_SolarBrace), // cc_sun_bracelet_pointer [slot]
    (u32)&(gClassReelData), // op_class_demo_pointer [slot]
    (u32)&(gOpinfo_1), // op_class_font_pointer [slot]
    (u32)&(gPal_SupportScreenBanner), // op_class_font_palette_pointer [slot]
    (u32)&(TextGlyphs_Special), // status_font_pointer [slot]
    (u32)&(gEndingCredits_0), // ed_staffroll_image_pointer [direct]
    (u32)&(Pal_StaffReelEnt_EndingFin), // ed_staffroll_palette_pointer [slot]
    (u32)&(gOpSubtitleGfxLut), // op_prologue_image_pointer [slot]
    (u32)&(Pal_StaffReelEnt_EndingFin), // op_prologue_palette_color_pointer [slot]
    (u32)&(gClassList_MeleeArena), // arena_class_near_weapon_pointer [slot]
    (u32)&(gClassList_BowArena), // arena_class_far_weapon_pointer [slot]
    (u32)&(gClassList_MagicArena), // arena_class_magic_weapon_pointer [slot]
    (u32)&(gLinkArenaBanList), // link_arena_deny_unit_pointer [slot]
    (u32)&(gWMPathData), // worldmap_road_pointer [slot]
    (u32)&(gDebugClearMenuDef), // menu_definiton_pointer [slot]
    (u32)&(Menu_PromoSubConfirm), // menu_promotion_pointer [slot]
    (u32)&(gMenuDef_PromoSel), // menu_promotion_branch_pointer [slot]
    (u32)&(MenuDef_RouteSplit), // menu_definiton_split_pointer [slot]
    (u32)&(gMenu_WMGeneralMenu), // menu_definiton_worldmap_pointer [slot]
    (u32)&(gMenu_WMNodeMenu), // menu_definiton_worldmap_shop_pointer [slot]
    (u32)&(gUnitActionMenuItems), // menu_unit_pointer [slot]
    (u32)&(gMapMenuItems), // menu_game_pointer [slot]
    (u32)&(gDebugClearMenuItems), // menu_debug1_pointer [slot]
    (u32)&(gItemSubMenuItems), // menu_item_pointer [slot]
    (u32)&(MenuAlwaysEnabled), // MenuCommand_UsabilityAlways [direct]
    (u32)&(MenuAlwaysNotShown), // MenuCommand_UsabilityNever [direct]
    (u32)&(gHelpInfo_Ss0Pow), // status_rmenu_unit_pointer [slot]
    (u32)&(gHelpInfo_Ss1Item0), // status_rmenu_game_pointer [slot]
    (u32)&(gHelpInfo_Ss2Rank0), // status_rmenu3_pointer [slot]
    (u32)&(gHelpInfo_MbpHp), // status_rmenu4_pointer [slot]
    (u32)&(gHelpInfo_CbpHp), // status_rmenu5_pointer [slot]
    (u32)&(sHelpInfo_ChapterStatus_TurnCount), // status_rmenu6_pointer [direct]
    (u32)&(sPage0TextInfo), // status_param1_pointer [slot]
    (u32)&(sPage1TextInfo), // status_param2_pointer [slot]
    (u32)&(Init), // status_param3w_pointer [direct]
    (u32)&(Init), // status_param3m_pointer [direct]
    (u32)&(gUiFrameImage), // systemmenu_common_image_pointer [slot]
    (u32)&(gUiFramePaletteA), // systemmenu_common_palette_pointer [slot]
    (u32)&(gTSA_GoalBox_OneLine), // systemmenu_goal_tsa_pointer [slot]
    (u32)&(gTSA_TerrainBox), // systemmenu_terrain_tsa_pointer [slot]
    (u32)&(gUiFrameImage), // systemmenu_name_image_pointer [slot]
    (u32)&(gTSA_MinimugBox), // systemmenu_name_tsa_pointer [slot]
    (u32)&(gUiFramePaletteA), // systemmenu_name_palette_pointer [slot]
    (u32)&(gUiFrameImage), // systemmenu_battlepreview_image_pointer [slot]
    (u32)&(gTSA_BattleForecastStandard), // systemmenu_battlepreview_tsa_pointer [slot]
    (u32)&(gUiFramePaletteA), // systemmenu_battlepreview_palette_pointer [slot]
    (u32)&(Pal_LimitViewBlue), // systemarea_move_gradation_palette_pointer [slot]
    (u32)&(Pal_LimitViewRed), // systemarea_attack_gradation_palette_pointer [slot]
    (u32)&(Pal_LimitViewGreen), // systemarea_staff_gradation_palette_pointer [slot]
    (u32)&(gGfx_StatusText), // systemmenu_badstatus_image_pointer [slot]
    (u32)&(Pal_HelpBox), // systemmenu_badstatus_palette_pointer [slot]
    (u32)&(Init), // systemmenu_badstatus_old_image_pointer [direct]
    (u32)&(Init), // systemmenu_badstatus_old_palette_pointer [direct]
    (u32)&(gCGDataTable), // bigcg_pointer [slot]
    (u32)&(CreditsCG_EndingCredits_0), // end_cg_address [direct]
    (u32)&(gWorldmapGmap_0), // worldmap_big_image_pointer [slot]
    (u32)&(gWorldmapGmap_2), // worldmap_big_palette_pointer [slot]
    (u32)&(gWorldmapGmap_1), // worldmap_big_dpalette_pointer [slot]
    (u32)&(gWorldmapGmap_3), // worldmap_big_palettemap_pointer [slot]
    (u32)&(Img_EventGmap), // worldmap_event_image_pointer [slot]
    (u32)&(Pal_EventGmap), // worldmap_event_palette_pointer [slot]
    (u32)&(Tsa_EventGmap), // worldmap_event_tsa_pointer [slot]
    (u32)&(Img_WorldmapMinimap), // worldmap_mini_image_pointer [slot]
    (u32)&(Pal_WorldmapMinimap), // worldmap_mini_palette_pointer [slot]
    (u32)&(gWorldmapGmap_4), // worldmap_icon_palette_pointer [slot]
    (u32)&(Img_GmapNodes), // worldmap_icon1_pointer [slot]
    (u32)&(Img_GmapCastleNodes), // worldmap_icon2_pointer [slot]
    (u32)&(Img_GmapPath), // worldmap_road_tile_pointer [slot]
    (u32)&(gGfx_MiscUiGraphics), // system_icon_pointer [slot]
    (u32)&(gPal_MiscUiGraphics), // system_icon_palette_pointer [slot]
    (u32)&(Img_PrepItemListSpinningArrow), // system_weapon_icon_pointer [slot]
    (u32)&(Pal_SpinningArrow), // system_weapon_icon_palette_pointer [slot]
    (u32)&(Img_ConfigUiIcons), // system_music_icon_pointer [slot]
    (u32)&(Pal_ConfigUiSprites), // system_music_icon_palette_pointer [slot]
    (u32)&(TextGlyphs_System), // font_item_address [direct]
    (u32)&(TextGlyphs_Talk), // font_serif_address [direct]
    (u32)&(gMonsterClassWeights), // monster_probability_pointer [slot]
    (u32)&(gMonsterItemTable), // monster_item_item_pointer [slot]
    (u32)&(gMonsterItemWeightsTable), // monster_item_probability_pointer [slot]
    (u32)&(gMonsterItemsByClassIndex), // monster_item_table_pointer [slot]
    (u32)&(gWMMonsterSpawnLocations), // monster_wmap_base_point_pointer [slot]
    (u32)&(WmMonsterGenerateRatesIdx_EirikaMode), // monster_wmap_stage_1_pointer [slot]
    (u32)&(WmMonsterGenerateRatesIdx_EphraimMode), // monster_wmap_stage_2_pointer [slot]
    (u32)&(WmMonsterGenerateRates_EirikaMode), // monster_wmap_probability_1_pointer [slot]
    (u32)&(WmMonsterGenerateRates_EphraimMode), // monster_wmap_probability_2_pointer [slot]
    (u32)&(WmMonsterGenerateRates_XmapEirika), // monster_wmap_probability_after_1_pointer [slot]
    (u32)&(WmMonsterGenerateRates_XmapEphraim), // monster_wmap_probability_after_2_pointer [slot]
    (u32)&(EventScr_SkirmishCommonBeginning), // worldmap_skirmish_startevent_pointer [slot]
    (u32)&(EventScr_SkirmishCommonEnd), // worldmap_skirmish_endevent_pointer [slot]
    (u32)&(gBattleBGDataTable), // battle_bg_pointer [slot]
    (u32)&(battle_terrain_table), // battle_terrain_pointer [slot]
    (u32)&(Init), // senseki_comment_pointer [direct]
    (u32)&(Init), // unit_custom_battle_anime_pointer [direct]
    (u32)&(gEkrSpellAnimLut), // magic_effect_pointer [slot]
    (u32)&(gImg_PathArrow), // system_move_allowicon_pointer [slot]
    (u32)&(gPal_PathArrow), // system_move_allowicon_palette_pointer [slot]
    (u32)&(Tsa_CommGameBgScreenInShop), // system_tsa_16color_304x240_pointer [slot]
    (u32)&(EventScrWM_Prologue_Beginning), // oping_event_pointer [slot]
    (u32)&(EventScr_EirikaModeGameEnd), // ending1_event_pointer [slot]
    (u32)&(EventScr_EphraimModeGameEnd), // ending2_event_pointer [slot]
    (u32)&(gUnitLookup), // RAMSlotTable_address [direct]
    (u32)&(gUnitArrayBlue), // workmemory_player_units_address [direct]
    (u32)&(gUnitArrayRed), // workmemory_enemy_units_address [direct]
    (u32)&(gUnitArrayGreen), // workmemory_npc_units_address [direct]
    (u32)(sizeof(struct PlaySt)), // workmemory_chapterdata_size [scalar]
    (u32)&(gBattleActor), // workmemory_battle_actor_address [direct]
    (u32)&(gBattleTarget), // workmemory_battle_target_address [direct]
    (u32)&(gArenaState), // workmemory_arena_data_address [direct]
    (u32)&(gAiState), // workmemory_ai_data_address [direct]
    (u32)&(gActionData), // workmemory_action_data_address [direct]
    (u32)&(gBanimLinkArenaFlag), // workmemory_battlesome_data_address [direct]
    (u32)&(gBattleHitArray), // workmemory_battleround_data_address [direct]
    (u32)&(sActiveMsg), // workmemory_last_string_address [direct]
    (u32)&(sMsgString), // workmemory_text_buffer_address [direct]
    (u32)&(gUnused_BmsaveLib_0), // workmemory_bwl_address [direct]
    (u32)&(gChapterStats), // workmemory_clear_turn_address [direct]
    (u32)(WIN_ARRAY_NUM), // workmemory_clear_turn_count [scalar]
    (u32)&(gProcTreeRootArray), // workmemory_procs_forest_address [direct]
    (u32)&(gSoundSt), // workmemory_bgm_address [direct]
    (u32)(offsetof(struct Proc, unk34)), // workmemory_reference_procs_event_address_offset [scalar]
    (u32)&(gPaletteBuffer), // workmemory_palette_address [direct]
    (u32)&(gProc_MapTask), // procs_maptask_pointer [slot]
    (u32)&(gProcScr_SoundRoomUi), // procs_soundroomUI_pointer [slot]
    (u32)&(gProcScr_GameControl), // procs_game_main_address [direct]
    (u32)&(gSummonConfig), // summon_unit_pointer [slot]
    (u32)&(gUnitDefSumDK), // summons_demon_king_pointer [slot]
    (u32)&(gBanimmisc_0), // battle_screen_TSA1_pointer [slot]
    (u32)&(gBanimmisc_1), // battle_screen_TSA2_pointer [slot]
    (u32)&(gBanimmisc_2), // battle_screen_TSA3_pointer [slot]
    (u32)&(gBanimmisc_3), // battle_screen_TSA4_pointer [slot]
    (u32)&(gBanimmisc_5), // battle_screen_TSA5_pointer [slot]
    (u32)&(gBanimmisc_6), // battle_screen_palette_pointer [slot]
    (u32)&(Img_Banimmisc_0), // battle_screen_image1_pointer [slot]
    (u32)&(Img_EfxLeftNameBox), // battle_screen_image2_pointer [slot]
    (u32)&(Img_EfxLeftItemBox), // battle_screen_image3_pointer [slot]
    (u32)&(Img_EfxRightNameBox), // battle_screen_image4_pointer [slot]
    (u32)&(Img_EfxRightItemBox), // battle_screen_image5_pointer [slot]
    (u32)&(gpAi1Table), // ai1_pointer [direct]
    (u32)&(gpAi2Table), // ai2_pointer [direct]
    (u32)&(gAiCombatScoreCoefficientTable), // ai3_pointer [slot]
    (u32)&(gAiStealPriorityItemList), // ai_steal_item_pointer [slot]
    (u32)&(sAiStaffFuncLut), // ai_preform_staff_pointer [slot]
    (u32)&(sAiSpecialItemFuncLut), // ai_preform_item_pointer [slot]
    (u32)&(gAiItemConfigTable), // ai_map_setting_pointer [slot]
    (u32)&(Init), // item_promotion2_array_pointer [direct]
    (u32)&(Init), // item_promotion2_array_switch2_address [direct]
    (u32)&(gEventLoCmdTable), // event_function_pointer_table_pointer [slot]
    (u32)&(gEventHiCmdTable), // event_function_pointer_table2_pointer [slot]
    (u32)&(gEkrSpellAnimLut), // item_effect_pointer_table_pointer [slot]
    (u32)&(gGuideTable), // dic_main_pointer [slot]
    (u32)&(gTextIds_GuideCategoriesChapter), // dic_chaptor_pointer [slot]
    (u32)&(gTextIds_GuideCategoriesTopic), // dic_title_pointer [slot]
    (u32)(ITEM_GOLD), // item_gold_id [scalar]
    (u32)&(BanimTerrainGroundDefault), // lookup_table_battle_terrain_00_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset01), // lookup_table_battle_terrain_01_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset02), // lookup_table_battle_terrain_02_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset03), // lookup_table_battle_terrain_03_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset04), // lookup_table_battle_terrain_04_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset05), // lookup_table_battle_terrain_05_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset06), // lookup_table_battle_terrain_06_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset07), // lookup_table_battle_terrain_07_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset08), // lookup_table_battle_terrain_08_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset09), // lookup_table_battle_terrain_09_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset0A), // lookup_table_battle_terrain_10_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset0B), // lookup_table_battle_terrain_11_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset0C), // lookup_table_battle_terrain_12_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset0D), // lookup_table_battle_terrain_13_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset0E), // lookup_table_battle_terrain_14_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset0F), // lookup_table_battle_terrain_15_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset10), // lookup_table_battle_terrain_16_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset11), // lookup_table_battle_terrain_17_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset12), // lookup_table_battle_terrain_18_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset13), // lookup_table_battle_terrain_19_pointer [slot]
    (u32)&(BanimTerrainGround_Tileset14), // lookup_table_battle_terrain_20_pointer [slot]
    (u32)&(gBanimBGLutDefault), // lookup_table_battle_bg_00_pointer [slot]
    (u32)&(gBanimBGLut01), // lookup_table_battle_bg_01_pointer [slot]
    (u32)&(gBanimBGLut02), // lookup_table_battle_bg_02_pointer [slot]
    (u32)&(gBanimBGLut03), // lookup_table_battle_bg_03_pointer [slot]
    (u32)&(gBanimBGLut04), // lookup_table_battle_bg_04_pointer [slot]
    (u32)&(gBanimBGLut05), // lookup_table_battle_bg_05_pointer [slot]
    (u32)&(gBanimBGLut06), // lookup_table_battle_bg_06_pointer [slot]
    (u32)&(gBanimBGLut07), // lookup_table_battle_bg_07_pointer [slot]
    (u32)&(gBanimBGLut08), // lookup_table_battle_bg_08_pointer [slot]
    (u32)&(gBanimBGLut09), // lookup_table_battle_bg_09_pointer [slot]
    (u32)&(gBanimBGLut0A), // lookup_table_battle_bg_10_pointer [slot]
    (u32)&(gBanimBGLut0B), // lookup_table_battle_bg_11_pointer [slot]
    (u32)&(gBanimBGLut0C), // lookup_table_battle_bg_12_pointer [slot]
    (u32)&(gBanimBGLut0D), // lookup_table_battle_bg_13_pointer [slot]
    (u32)&(gBanimBGLut0E), // lookup_table_battle_bg_14_pointer [slot]
    (u32)&(gBanimBGLut0F), // lookup_table_battle_bg_15_pointer [slot]
    (u32)&(gBanimBGLut10), // lookup_table_battle_bg_16_pointer [slot]
    (u32)&(gBanimBGLut11), // lookup_table_battle_bg_17_pointer [slot]
    (u32)&(gBanimBGLut12), // lookup_table_battle_bg_18_pointer [slot]
    (u32)&(gBanimBGLut13), // lookup_table_battle_bg_19_pointer [slot]
    (u32)&(gBanimBGLut14), // lookup_table_battle_bg_20_pointer [slot]
    (u32)(TERRAIN_COUNT), // map_terrain_type_count [scalar]
    (u32)&(MenuAlwaysEnabled), // menu_J12_always_address [direct]
    (u32)&(MenuAlwaysNotShown), // menu_J12_hide_address [direct]
    (u32)&(gGameOptions), // status_game_option_pointer [slot]
    (u32)&(gGameOptionsUiOrder), // status_game_option_order_pointer [slot]
    (u32)&(Init), // status_game_option_order2_pointer [direct]
    (u32)&(gUnitListScreenFields), // status_units_menu_pointer [slot]
    (u32)&(Init), // tactician_affinity_pointer [direct]
    (u32)&(Init), // event_final_serif_pointer [direct]
    (u32)&(gBuildDateTime), // builddate_address [direct]
    (u32)&(TileConfiguration1), // vanilla_field_config_address [direct]
    (u32)&(ObjectType1), // vanilla_field_image_address [direct]
    (u32)&(TileConfiguration2), // vanilla_village_config_address [direct]
    (u32)&(ObjectType2), // vanilla_village_image_address [direct]
    (u32)&(TileConfiguration3), // vanilla_casle_config_address [direct]
    (u32)&(ObjectType3), // vanilla_casle_image_address [direct]
    (u32)&(TileConfiguration4), // vanilla_plain_config_address [direct]
    (u32)&(ObjectType4), // vanilla_plain_image_address [direct]
    (u32)&(ItemList_WM_BorderMulan_Armory), // worldmap_node_armory_empty_address [direct]
    (u32)&(ItemList_WM_BorderMulan_Vendor), // worldmap_node_vendor_empty_address [direct]
    (u32)&(ItemList_WM_BorderMulan_SecretShop), // worldmap_node_secret_empty_address [direct]
};

#endif
