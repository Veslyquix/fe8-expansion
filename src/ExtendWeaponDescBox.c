#include "gbafe.h"
#include "expansion_config.h"

#if FE8_EXTEND_DESC_BOX

#include "helpbox.h"
#include "proc.h"
#include "gba/macro.h"
#include "bm.h"
#include "bmtrade.h"
#include "mu.h"
#include "face.h"

/* Modern-build port of a FEBuilder-style ROM patch ("ExtendWeaponDescBox")
 * that extends the item/weapon help box from 3 to 5 lines by adding extra
 * text handles and the VRAM banks that back them, plus the shop/prep/
 * supply/trade VRAM-bank selection and layout fixes the extra lines depend
 * on.
 *
 * Every hook below is a direct C port verified against the vanilla FE8U ROM
 * disassembly at the address it replaced, rather than transcribed
 * asm-to-C blind, since the original patch's own renamed helper functions
 * (e.g. "InitVramRow") are themselves just the original author's guesses at
 * already-decompiled vanilla function names -- see reference/fe8u_symbols.txt
 * for the address/symbol table this was cross-checked against. */

/* Proc script tables not owned by this file; not yet given `extern`
 * declarations in their own headers. */
extern struct ProcCmd ProcScr_SaveMenu[];
extern struct ProcCmd gProcScr_SaveMenuPostChapter[];
extern struct ProcCmd ProcScr_bmview[];
extern struct ProcCmd gProcScr_PrepWMShopSell[];

/* If any of these procs are active, ClearHelpBoxText's extra (4th/5th line)
 * VRAM banks are never (re)allocated -- these screens' own VRAM layout is
 * incompatible with the extra banks used here. */
static const struct ProcCmd* const sExtraDescVramNeverProcs[] = {
    ProcScr_SaveMenu,
    gProcScr_SaveMenuPostChapter,
    ProcScr_bmview,
    gProcScr_ChapterStatusScreen,
    gProcScr_DrawUnitInfoBgSprites,
    gProcScr_DrawPrepFundsSprite,
    NULL,
};

/* If this proc is active, the extra VRAM banks are always (re)allocated,
 * bypassing every other check below (the WM shop sell screen's overlapping
 * VRAM usage is otherwise mistaken for one of the pair-exception cases). */
static const struct ProcCmd* const sExtraDescVramAlwaysProcs[] = {
    gProcScr_PrepWMShopSell,
    NULL,
};

struct ExtraDescVramProcPair
{
    const struct ProcCmd* a;
    const struct ProcCmd* b;
};

/* If BOTH procs in any pair here are simultaneously active, the extra VRAM
 * banks are not (re)allocated -- that specific screen combination already
 * uses that VRAM for something else. */
static const struct ExtraDescVramProcPair sExtraDescVramNeverBothProcs[] = {
    { ProcScr_PrepUnitScreen, ProcScr_SlidingWallBg },
    { NULL, NULL },
};

/* FE8U = 0x0808A126 (inside ClearHelpBoxText, replacing its 3
 * SpriteText_DrawBackground(&gHelpBoxSt.text[N]) calls). */
void InitItemDescVram(void)
{
    u32 vramAddr;
    int i;

    SpriteText_DrawBackground(&gHelpBoxSt.text[0]);

    /* gHelpBoxSt.oam2_base already encodes which OBJ char-base tile bank
     * this help box's sprites are using (see PutSpriteExt/oam2 callers);
     * the low 10 bits are the tile index, and each tile is 0x20 bytes. */
    vramAddr = 0x6010000 + ((gHelpBoxSt.oam2_base & 0x3FF) << 5);

    SpriteText_DrawBackground(&gHelpBoxSt.text[1]);
    SpriteText_DrawBackground(&gHelpBoxSt.text[2]);

    for (i = 0; sExtraDescVramAlwaysProcs[i] != NULL; i++)
    {
        if (Proc_Find(sExtraDescVramAlwaysProcs[i]))
            goto AllocateExtra;
    }

    for (i = 0; sExtraDescVramNeverProcs[i] != NULL; i++)
    {
        if (Proc_Find(sExtraDescVramNeverProcs[i]))
            return;
    }

    for (i = 0; sExtraDescVramNeverBothProcs[i].a != NULL; i++)
    {
        if (Proc_Find(sExtraDescVramNeverBothProcs[i].a) &&
            Proc_Find(sExtraDescVramNeverBothProcs[i].b))
        {
            return;
        }
    }

AllocateExtra:
    /* Clear the 4th and 5th text lines' char-tile VRAM (0xD8 words = 0x360
     * bytes each, fixed-source fill of 0x44444444 -- an empty/blank tile
     * pattern, matching the vanilla SpriteText_DrawBackground clears
     * above). */
    CpuFastFill(0x44444444, (void*)(vramAddr + 0x1800), 0x360);
    CpuFastFill(0x44444444, (void*)(vramAddr + 0x1C00), 0x360);
    CpuFastFill(0x44444444, (void*)(vramAddr + 0x2000), 0x360);
    CpuFastFill(0x44444444, (void*)(vramAddr + 0x2400), 0x360);
}

/* FE8U = 0x0808A064 (inside HelpBoxIntroDrawTexts, replacing its
 * otherProc->font/texts[0..2] assignments). Extends the scrolling-text
 * proc's text handles from 3 to 5, wiring the two new gHelpBoxSt.text[]
 * slots this file's extended HELP_BOX_TEXT_COUNT adds. */
void InitProcTextHandles(struct HelpBoxScrollProc* otherProc)
{
    struct Text* text4 = &gHelpBoxSt.text[3];
    struct Text* text5 = &gHelpBoxSt.text[4];

    otherProc->font = &gHelpBoxSt.font;
    otherProc->texts[0] = &gHelpBoxSt.text[0];
    otherProc->texts[1] = &gHelpBoxSt.text[1];
    otherProc->texts[2] = &gHelpBoxSt.text[2];

    /* The other 3 slots' cursor/color state is (re)initialized by the
     * InitSpriteText() calls in LoadHelpBoxGfx; these 2 new slots have no
     * such call site, so only their cursor is reset here instead (matching
     * the original patch's own behavior -- not re-initialized when
     * scrolling up/down/etc, only x is). */
    text4->x = 0;
    otherProc->texts[3] = text4;
    Text_SetColor(text4, 6);

    text5->x = 0;
    otherProc->texts[4] = text5;
    Text_SetColor(text5, 6);
}

/* The map trade menu's own VRAM layout collides with the extended
 * description box's larger footprint, so its moving-unit sprite's OAM tile
 * bank and face slot get rearranged around the trade menu's
 * LockGame/ClearDisplay proc-script entries. */
static void UpdateTradeMenuMuTileBase(u16 newTileIndex)
{
    struct MuProc* mu = (struct MuProc*)Proc_Find(ProcScr_Mu);

    if (mu != NULL)
    {
        mu->sprite_anim->tileBase = (mu->sprite_anim->tileBase & ~0x3FF) | newTileIndex;
        mu->sprite_anim->gfxNeedsUpdate = 1;
    }
}

/* FE8U = 0x0859BB1C proc-script index 0 (replaces PROC_CALL(LockGame)). */
void TradeMenu_LockGameOverride(void)
{
    static CONST_DATA struct FaceVramEntry sTradeMenuGfxData[FACE_SLOT_COUNT] = {
        { 0x6000, 6 },
        { 0x7000, 7 },
    };

    SetupFaceGfxData(sTradeMenuGfxData);
    UpdateTradeMenuMuTileBase(0x8F << 2);
    LockGame();
}

/* FE8U = 0x0859BB1C proc-script index 19 (replaces
 * PROC_CALL(TradeMenu_ClearDisplay)). */
void TradeMenu_ClearDisplayOverride(struct TradeMenuProc* proc)
{
    SetupFaceGfxData(NULL);
    UpdateTradeMenuMuTileBase(0xE0 << 2);
    TradeMenu_ClearDisplay(proc);
}

#endif /* FE8_EXTEND_DESC_BOX */
