#ifndef GUARD_EXPANSION_ITEMTEST_H
#define GUARD_EXPANSION_ITEMTEST_H

/*
 * Issue #10 -- opt-in runtime probe for the expanded item ID space.
 *
 * This is a TEST HARNESS, not a feature: every value it records is
 * produced by an unmodified production call (GetItemData, the event
 * engine's own EV_CMD_GIVEITEM decoder, DrawItemMenuLine/
 * DrawItemStatScreenLine, WriteGameSave/ReadGameSave,
 * WriteSuspendSave/ReadSuspendSave, WriteMultiArenaSaveTeam/
 * ReadMultiArenaSaveTeam). Nothing here re-implements, mirrors or models
 * item lookup, event decoding, UI drawing or save packing; the file only
 * sequences those production calls and copies their observable results
 * into gItemExpansionProbe for a headless playtest run to assert.
 *
 * Gate: FE8_EXPANSION_ITEMTEST_ENABLED. It is deliberately INDEPENDENT of
 * FE8_EXPANSION_DEBUG/NDEBUG (unlike FE8_EXPANSION_DEBUGTOOLS_ENABLED), so
 * the very same probe runs in a real modern debug ROM and a real modern
 * release ROM. It defaults to 0: an ordinary build -- legacy agbcc,
 * modern debug, modern release, at the default cap or at an expanded cap
 * -- compiles this translation unit to an empty object, links no probe
 * data, and reaches no hook. Enable it with
 * `make ... FE8_EXPANSION_ITEMTEST=1 FE8_ITEM_ID_CAP=0xCE`.
 *
 * See docs/id_space.md ("Runtime probe") and
 * tools/gba-playtest/run_item_expansion_checks.py.
 */

#include "id_space.h"

#ifndef FE8_EXPANSION_ITEMTEST_ENABLED
#define FE8_EXPANSION_ITEMTEST_ENABLED 0
#endif

#if FE8_EXPANSION_ITEMTEST_ENABLED
#if ITEM_ID_CONFIGURED_CAP < ITEM_ID_EXPANSION_FIRST
#error "FE8_EXPANSION_ITEMTEST_ENABLED requires an expanded item cap (build with FE8_ITEM_ID_CAP=0xCE or higher)"
#endif

/* Written into gItemExpansionProbe.magic only after every stage below has
 * run to completion, so a partial/hung run can never look like a pass. */
#define ITEM_EXPANSION_PROBE_MAGIC 0x49584345 /* ASCII "IXCE" */

enum ItemExpansionTestStage
{
    ITEMTEST_STAGE_ITEMDATA   = 1 << 0, /* GetItemData + item accessors */
    ITEMTEST_STAGE_EVENT      = 1 << 1, /* EV_CMD_GIVEITEM -> unit inventory */
    ITEMTEST_STAGE_UI         = 1 << 2, /* item menu line + stat screen line */
    ITEMTEST_STAGE_MULTIARENA = 1 << 3, /* link/arena team representation */
    ITEMTEST_STAGE_GAMESAVE   = 1 << 4, /* WriteGameSave -> ReadGameSave */
    ITEMTEST_STAGE_SUSPEND    = 1 << 5, /* WriteSuspendSave -> ReadSuspendSave */
    ITEMTEST_STAGE_CONTENT    = 1 << 6  /* issue #6 content mechanic apply */
};

#define ITEMTEST_STAGE_ALL \
    (ITEMTEST_STAGE_ITEMDATA | ITEMTEST_STAGE_EVENT | ITEMTEST_STAGE_UI | \
     ITEMTEST_STAGE_MULTIARENA | ITEMTEST_STAGE_GAMESAVE | ITEMTEST_STAGE_SUSPEND | \
     ITEMTEST_STAGE_CONTENT)

/* Sentinel for "no such registry index / no such inventory slot", so a
 * missing entry is an explicit recorded value instead of an ambiguous 0. */
#define ITEMTEST_INDEX_NONE 0xFFFFFFFF

/* Every field is a u32 so a playtest probe can read any of them with one
 * naturally aligned 4-byte read, and so the host-side runner can resolve
 * each address as `gItemExpansionProbe + 4 * index` from the linked ELF's
 * symbol table (no hardcoded EWRAM address, no committed frame oracle). */
struct ItemExpansionProbe
{
    /* 00 */ u32 magic;              /* ITEM_EXPANSION_PROBE_MAGIC when done */
    /* 04 */ u32 stagesCompleted;    /* bitmask of enum ItemExpansionTestStage */
    /* 08 */ u32 configuredCap;      /* ITEM_ID_CONFIGURED_CAP as compiled */

    /* Stage 1 -- runtime item record, straight from GetItemData(). */
    /* 0C */ u32 dataNumber;
    /* 10 */ u32 dataNameTextId;
    /* 14 */ u32 dataDescTextId;
    /* 18 */ u32 dataIconId;
    /* 1C */ u32 dataWeaponType;
    /* 20 */ u32 dataMaxUses;
    /* 24 */ u32 dataAttributes;
    /* 28 */ u32 madeItem;           /* MakeNewItem(ITEM_EXPANSION_CE) */
    /* 2C */ u32 lookupIndex;        /* GetItemIndex() of that made item */
    /* 30 */ u32 lookupUses;         /* GetItemUses() of that made item */
    /* 34 */ u32 legacyDataNumber;   /* GetItemData(ITEM_UNK_CD)->number */

    /* Stage 2 -- production event engine EV_CMD_GIVEITEM decoder. */
    /* 38 */ u32 eventUnitPid;       /* pid of the unit the event targeted */
    /* 3C */ u32 eventItemSlot;      /* inventory slot the expansion item landed in */
    /* 40 */ u32 eventItem;          /* raw items[] halfword (uses<<8 | id) */
    /* 44 */ u32 eventLegacyItem;    /* raw items[] halfword for the 0xCD item */

    /* Stage 3 -- production item UI draw path. */
    /* 48 */ u32 uiNamePtr;          /* GetItemName(ITEM_EXPANSION_CE) */
    /* 4C */ u32 uiIconId;           /* GetItemIconId() as the UI itself read it */
    /* 50 */ u32 uiMenuIconTile;     /* tilemap entry DrawIcon() wrote */
    /* 54 */ u32 uiMenuUsesTile;     /* tilemap entry the uses number wrote */
    /* 58 */ u32 uiMenuNameTile;     /* tilemap entry PutText() wrote */
    /* 5C */ u32 uiStatIconTile;     /* stat-screen line icon tilemap entry */
    /* 60 */ u32 uiStatSlashTile;    /* stat-screen line "/" tilemap entry */
    /* 64 */ u32 uiDescId;           /* GetItemDescId(ITEM_EXPANSION_CE) */

    /* Stage 4 -- MultiArena/link team representation roundtrip. */
    /* 68 */ u32 arenaItem;
    /* 6C */ u32 arenaLegacyItem;
    /* 70 */ u32 arenaEmptySlot;     /* an untouched ITEM_NONE slot */

    /* Stage 5 -- production game-save unit pack/unpack roundtrip. */
    /* 74 */ u32 gameSaveItem;
    /* 78 */ u32 gameSaveLegacyItem;
    /* 7C */ u32 gameSaveEmptySlot;

    /* Stage 6 -- production suspend-save unit encode/decode roundtrip. */
    /* 80 */ u32 suspendItem;
    /* 84 */ u32 suspendLegacyItem;
    /* 88 */ u32 suspendEmptySlot;

    /* Harness diagnostics -- not part of the item contract, but they turn
     * "the probe never finished" into an actionable stage/timing report. */
    /* 8C */ u32 bootPrepared;      /* the boot hook ran */
    /* 90 */ u32 phaseWaitFrames;   /* frames until the first stable Player Phase */
    /* 94 */ u32 phaseTimedOut;     /* 1 if that wait hit its fail-safe instead */
    /* 98 */ u32 eventWaitFrames;   /* frames the production event took to finish */
    /* 9C */ u32 lastChapterIndex;  /* gPlaySt.chapterIndex, sampled while waiting */
    /* A0 */ u32 lastFaction;       /* gPlaySt.faction, sampled while waiting */
    /* A4 */ u32 mapMainSeen;       /* the map's own gProc_BMapMain was found */
    /* A8 */ u32 playerPhaseSeen;   /* gProcScr_PlayerPhase was found */
    /* AC */ u32 procStateBits;     /* which known procs were live while waiting */
    /* B0 */ u32 procStateNow;      /* the same bits, for the current frame only */
    /* B4 */ u32 wmLocation;        /* gGMData.units[0].location */
    /* B8 */ u32 wmCurrentNode;     /* gGMData.current_node */
    /* BC */ u32 gameSavePackedField; /* the packed record's own 14-bit item field */
    /* C0 */ u32 suspendPackedField;  /* same, for the suspend record */

    /* Issue #6 bundled content example (see
     * include/expansion_starter_content.h). Recorded through the PUBLIC
     * config/registry API only -- no numeric literal, no pointer.
     *
     * The first block is boot-stage state (no map needed), so a modern
     * release ROM records it too; the second block is the map-dependent
     * apply, recorded by ITEMTEST_STAGE_CONTENT. */
    /* C4 */ u32 contentEnabled;      /* ExpansionStarterContentIsEnabled() */
    /* C8 */ u32 contentItemId;       /* ExpansionStarterContentItemId() (typed) */
    /* CC */ u32 contentMechanicsCount;  /* ExpansionMechanicsCount() after install */
    /* D0 */ u32 contentMechanicIndex;   /* registry index of the content mechanic */
    /* D4 */ u32 contentSampleIndex;     /* registry index of the content-free sample */
    /* D8 */ u32 contentRegisterOk;      /* successful public registrations */
    /* DC */ u32 contentRegisterErr;     /* rejected public registrations */
    /* E0 */ u32 contentLastResult;      /* last enum ExpansionMechanicsResult */

    /* E4 */ u32 contentBearerPid;          /* unit that carries the content item */
    /* E8 */ u32 contentBearerItemSlot;     /* GetUnitItemSlot() of that item */
    /* EC */ u32 contentBearerAvoidDelta;   /* battleAvoidRate change on one apply */
    /* F0 */ u32 contentBearerDefenseDelta; /* battleDefense change on one apply */
    /* F4 */ u32 contentControlPid;         /* unit that does NOT carry it */
    /* F8 */ u32 contentControlItemSlot;    /* ITEMTEST_INDEX_NONE for the control */
    /* FC */ u32 contentControlAvoidDelta;
    /*100 */ u32 contentControlDefenseDelta;
    /*104 */ u32 contentApplyCount;         /* seam applies this stage performed */
    /*108 */ u32 contentSampleTriggerCount; /* sample bonuses granted this stage */
};

extern struct ItemExpansionProbe gItemExpansionProbe;

/* Hook 1 -- Title_IDLE (src/titlescreen.c). Returns 1 exactly once, on
 * the first title-screen idle frame, so the ROM performs the ordinary
 * "start the game" transition with no keypress at all. Mirrors the shape
 * of the debug hub's own pending-request detection, but is gated on this
 * test config, so it works identically in a release ROM. */
int ItemExpansionTest_RequestsTitleStart(void);

/* Hook 2 -- GameControl_PostIntro (src/gamecontrol.c). Returns 1 exactly
 * once, and only for the title-start above. */
int ItemExpansionTest_ConsumeChapterBootRequest(void);

/* Hook 2's body: the ordinary new-game bootstrap production sequence
 * (InitPlayConfig/ResetPermanentFlags/ResetChapterFlags/InitUnits/
 * GmDataInit -- exactly the calls GameControl_InitTutorialGame and the
 * debug launcher's Chapter 2 boot already use), plus starting the probe
 * proc. The caller performs the ordinary Proc_Goto(LGAMECTRL_EXEC_BM)
 * transition itself. */
void ItemExpansionTest_PrepareChapterBoot(void);

/* One-shot bootstrap-suppression window, mirroring the debug launcher's
 * own DebugTools_IsBootstrapSuppressionActive() (see docs/debugtools.md):
 * the automatic per-phase suspend write must not fire in the middle of a
 * scripted deterministic boot -- it is documented there to stall the rest
 * of the chapter's progression. Active from the boot hook until the probe
 * proc has seen a stable Player Phase and settled; always 0 afterwards, so
 * this build's own later WriteSuspendSave/ReadSuspendSave stage exercises
 * the completely ordinary production path. */
int ItemExpansionTest_IsBootSuppressionActive(void);

#endif /* FE8_EXPANSION_ITEMTEST_ENABLED */

#endif /* GUARD_EXPANSION_ITEMTEST_H */
