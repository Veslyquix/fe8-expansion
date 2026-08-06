OUTPUT_ARCH(arm)

MEMORY
{
    rom   : ORIGIN = 0x08000000, LENGTH = __rom_size
    iwram : ORIGIN = 0x03000000, LENGTH = 32K
    ewram : ORIGIN = 0x02000000, LENGTH = 256K
}

__text_start  = ORIGIN(rom);
__ewram_start = ORIGIN(ewram);
__iwram_start = ORIGIN(iwram);
__iwram_top   = ORIGIN(iwram) + LENGTH(iwram);
__sp_irq      = __iwram_top - 0x060;
__sp_usr      = __sp_irq - 0x1A0;
/*
 * crt0 initializes the downward-growing system/user stack at __sp_usr.
 * The historical fixed IWRAM layout ended at 0x030067A8, leaving 0x1658
 * bytes below that pointer. The modern CJK scratch ends at 0x03006CA8,
 * leaving 0x1158. Preserve a 0x1000-byte user-stack floor while retaining
 * 0x158 bytes of current static-growth headroom.
 */
__iwram_static_limit = __sp_usr - 0x1000;
__irq_flags   = 0x03007ff8;

ENTRY(Init)

gNumMusicPlayers = 9;
gMaxLines = 0;

SECTIONS
{
    ewram_overlay_0 __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(SORT_BY_NAME(ewram_overlay_0.unitlist.*))
        *(ewram_overlay_0)

        . = 0x01F148;
        PROVIDE(gUnk_SoundRoom_0 = .);
        . += 0x54;
        PROVIDE(gSoundRoomVolumeGraphBuffer = .);
        . += 0x62;

        __ewram_overlay_0_end = .;
    } > ewram AT> ewram
    __ewram_overlay_0_size = __ewram_overlay_0_end - __ewram_start;

    ewram_overlay_gameending __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_gameending)
        __ewram_overlay_gameending_end = .;
    } > ewram AT> ewram
    __ewram_overlay_gameending_size = __ewram_overlay_gameending_end - __ewram_start;

    ewram_overlay_bmstart __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_bmstart)
        __ewram_overlay_bmstart_end = .;
    } > ewram AT> ewram
    __ewram_overlay_bmstart_size = __ewram_overlay_bmstart_end - __ewram_start;

    ewram_overlay_gamestartsave __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_gamestartsave)
        __ewram_overlay_gamestartsave_end = .;
    } > ewram AT> ewram
    __ewram_overlay_gamestartsave_size = __ewram_overlay_gamestartsave_end - __ewram_start;

    ewram_overlay_gamestart __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_gamestart)

        . = 0x002038; PROVIDE(gUnk_0 = .);
        . = 0x007838; PROVIDE(gUnk_1 = .);
        . = 0x0078D8; PROVIDE(gUnk_2 = .);
        . = 0x00A2D8; PROVIDE(gUnk_4 = .);
        . = 0x00A300; PROVIDE(gUnk_5 = .);
        . = 0x00C300; PROVIDE(gUnk_7 = .);
        . = 0x00CB00; PROVIDE(gUnk_8 = .);
        . = 0x01CDD4; PROVIDE(gUnk_OpSubtitle_0 = .);
        . = 0x01DB00; PROVIDE(gUnk_Opinfo_0 = .);
        . = 0x01DB28; PROVIDE(gUnk_OpInfo_0 = .);
        . = 0x01FB28; PROVIDE(gUnk_OpInfo_1 = .);
        . += 0x30;

        __ewram_overlay_gamestart_end = .;
    } > ewram AT> ewram
    __ewram_overlay_gamestart_size = __ewram_overlay_gamestart_end - __ewram_start;

    ewram_overlay_banim __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_banim)
        __ewram_overlay_banim_end = .;
    } > ewram AT> ewram
    __ewram_overlay_banim_size = __ewram_overlay_banim_end - __ewram_start;

    ewram_overlay_sio __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_sio)

        . = 0x000000; PROVIDE(gUnk_Sio_0 = .);
        . = 0x000C60; PROVIDE(Font_Sio_0 = .);
        . = 0x000C78; PROVIDE(gUnk_Sio_1 = .);
        . = 0x000F00; PROVIDE(gUnk_Sio_2 = .);
        . = 0x001180; PROVIDE(gUnk_Sio_3 = .);
        . = 0x001184; PROVIDE(gUnk_Sio_4 = .);
        . = 0x001188; PROVIDE(gUnk_Sio_5 = .);
        . += 0x4;

        __ewram_overlay_sio_end = .;
    } > ewram AT> ewram
    __ewram_overlay_sio_size = __ewram_overlay_sio_end - __ewram_start;

    ewram_overlay_worldmap __ewram_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_overlay_worldmap)

        . = 0x0087A0; PROVIDE(gUnk_3 = .);
        . = 0x00AF00; PROVIDE(gUnk_6 = .);
        . = 0x019D00; PROVIDE(gUnk_9 = .);
        . = 0x01AFC0; PROVIDE(gFont_0 = .);
        . = 0x01AFF0; PROVIDE(gUnk_10 = .);
        . = 0x01B0D8; PROVIDE(gUnk_11 = .);
        . = 0x01B100; PROVIDE(gUnk_12 = .);
        . = 0x01B104; PROVIDE(gUnk_13 = .);
        . = 0x01B1E4; PROVIDE(gUnk_14 = .);
        . = 0x01B3A4; PROVIDE(gUnk_15 = .);
        . = 0x01B430; PROVIDE(gUnk_16 = .);
        . = 0x01B458; PROVIDE(gUnk_17 = .);
        . = 0x01B718; PROVIDE(gUnk_18 = .);
        . = 0x01B71C; PROVIDE(gUnk_19 = .);
        . = 0x01B758; PROVIDE(gUnk_20 = .);
        . = 0x01B7DA; PROVIDE(gUnk_21 = .);
        . = 0x01B864; PROVIDE(gUnk_22 = .);
        . = 0x01B930; PROVIDE(gUnk_23 = .);
        . = 0x01B958; PROVIDE(gUnk_24 = .);
        . = 0x01BBD8; PROVIDE(gUnk_25 = .);
        . = 0x01BE30; PROVIDE(gWmHblankStatus = .);
        . = 0x01BE32; PROVIDE(gUnk_26 = .);
        . = 0x01C5B4; PROVIDE(gUnk_27 = .);
        . = 0x01C5C0; PROVIDE(gUnk_28 = .);
        . = 0x01C5CC; PROVIDE(gUnk_29 = .);
        . = 0x01C5CF; PROVIDE(gUnk_30 = .);
        . = 0x01C5D0; PROVIDE(gUnk_31 = .);
        . = 0x01C5D1; PROVIDE(gUnk_32 = .);
        . = 0x01C5D4; PROVIDE(gUnk_33 = .);
        . += 0x800;

        __ewram_overlay_worldmap_end = .;
    } > ewram AT> ewram
    __ewram_overlay_worldmap_size = __ewram_overlay_worldmap_end - __ewram_start;

    __ewram_overlay_peak_size = MAX(
        MAX(
            MAX(__ewram_overlay_0_size, __ewram_overlay_gameending_size),
            MAX(__ewram_overlay_bmstart_size, __ewram_overlay_gamestartsave_size)
        ),
        MAX(
            MAX(__ewram_overlay_gamestart_size, __ewram_overlay_banim_size),
            MAX(__ewram_overlay_sio_size, __ewram_overlay_worldmap_size)
        )
    );
    __ewram_persistent_start =
        __ewram_start + ((__ewram_overlay_peak_size + 3) & ~3);

    ewram_data __ewram_persistent_start (NOLOAD) : ALIGN(4)
    {
        *(ewram_data)

        /* Linker-defined EWRAM scratch symbols with no owning object. */
        . = ALIGN(4);
        PROVIDE(gGenericBuffer = .); . += 0x2000;
        PROVIDE(gOpAnimSt = .); . += 0x100;
        *(ewram_data.ui_frame_scratch_end)

        . = ALIGN(4);
        PROVIDE(gLinkArenaSt = .); . += 0x54;
        PROVIDE(gUnk_Sio_6 = .); . += 0x10;
        PROVIDE(gUnk_Sio_7 = .); . += 0x28;
        PROVIDE(Texts_0 = .); . += 0x10;
        PROVIDE(gUnk_Sio_8 = .); . += 0x5;
        PROVIDE(gUnk_Sio_9 = .); . += 0x4B;
        PROVIDE(gSioSaveConfig = .); . += 0x4;
        PROVIDE(Texts_1 = .); . += 0x8;
        PROVIDE(gUnk_Sio_10 = .); . += 0x48;
        PROVIDE(Font_0 = .); . += 0x18;
        PROVIDE(gLinkArenaTeamList = .); . += 0xC8;
        PROVIDE(gSioResultRankings = .); . += 0x4;
        PROVIDE(gUnk_Sio_11 = .); . += 0xC4;
        PROVIDE(gSioTexts = .); . += 0x10;
        PROVIDE(Text_0 = .); . += 0x8;
        PROVIDE(gUnk_Sio_12 = .); . += 0x4;
        PROVIDE(gUnk_Sio_13 = .); . += 0x4;
        PROVIDE(gKeyInputSequenceBuffer = .); . += 0x20;
        PROVIDE(gKeyInputSequenceTimer = .); . += 0x4;
        PROVIDE(gUnk_Sio_14 = .); . += 0x3C;
        PROVIDE(gUnk_Sio_15 = .); . += 0x4;
        PROVIDE(gUnk_Sio_16 = .); . += 0x4;
        PROVIDE(gUnk_Sio_17 = .); . += 0x1;
        PROVIDE(gUnk_Sio_18 = .); . += 0x5;
        PROVIDE(gUnk_Sio_19 = .); . += 0x5;
        PROVIDE(gUnk_Sio_20 = .); . += 0x15;
        PROVIDE(gUnk_Sio_21 = .); . += 0x28;
        PROVIDE(gUnk_Sio_22 = .); . += 0x4;

        . = ALIGN(4);
        PROVIDE(gLoadUnitBuffer = .);
        PROVIDE(end = .);
    } > ewram AT> ewram

    IWRAM __iwram_start (NOLOAD) : ALIGN(4)
    {
        INCLUDE "linker/iwram.ld"
    } > iwram
    __iwram_static_end = ADDR(IWRAM) + SIZEOF(IWRAM);

    .bss (NOLOAD) : ALIGN(4)
    {
        *(.bss .bss.* COMMON)
    } > ewram
    __ewram_used_end = .;

    ROM __text_start : ALIGN(4)
    {
        /* === PINNED: startup + ARM (never shift) === */
        KEEP(*src/rom_header.o(.text))
        KEEP(*src/crt0.o(.text))
        *asm/arm.o(.text)

        /* === SHIFT PADDING: inserts __text_shift bytes here === */
        . = ALIGN(4);
        __shift_start = .;
        . += __text_shift;
        __shift_end = .;

        /* === FLOATING: moves by shift amount === */
        EXCLUDE_FILE (*src/rom_header.o *src/crt0.o *asm/arm.o *asm/arm_call.o)
            *(.text .text.* .glue_7 .glue_7t)
        *asm/arm_call.o(.text)
        *(.vfp11_veneer .v4_bx .iplt)

        . = ALIGN(4);
        *(.rodata .rodata.* .rodata.str1.* .rodata.cst*)

        . = ALIGN(4);
        /* Outside the section list so the exclusion covers .data and .data.*. */
        EXCLUDE_FILE (
            *banim_data.o
            banim/data_banim.o
            *banim_terrain_data.o
            *data_banim_terrain.o
            *banim_pal_chara.o
            *data_banim_pal.o
            *data_FE0000.o
            *data_FFF000.o
        ) *(.data .data.*)
        *(.igot.plt)
        __floating_end = .;

        /* === PINNED: banim regions (never shift) === */
        FILL(0xFF);
        . = 0xC00000;
        *banim_data.o(.data)
        *banim_data.o(.data.banim_array_len)
        *banim_data.o(.data.banim_array)

        FILL(0x00);
        . = 0xC02000;
        banim/data_banim.o(.data)

        FILL(0xFF);
        . = 0xEE0000;
        *banim_terrain_data.o(.data)
        *banim_terrain_data.o(.data.banim_terrain_head)
        *banim_terrain_data.o(.data.banim_terrain_ptr_table)

        FILL(0x00);
        . = 0xEE0C00;
        *data_banim_terrain.o(.data)

        FILL(0xFF);
        _banim_pal_start = 0xEF8000;
        . = _banim_pal_start;
        *banim_pal_chara.o(.data)
        *banim_pal_chara.o(.data.banim_pal_head)
        *banim_pal_chara.o(.data.banim_pal_ptr_table)

        FILL(0x00);
        . = _banim_pal_start + 0x1000;
        *data_banim_pal.o(.data)
        _banim_pal_end = .;
        _banim_pal_size = . - _banim_pal_start;

        FILL(0xFF);
        . = 0xFE0000;
        *data_FE0000.o(.data)
        . = 0xFFF000;
        *data_FFF000.o(.data)
    } > rom = 0xFF

    /* === UPPER ROM: locale bank (32 MiB profiles only) === */
    __locale_bank_start = 0x09000000;
    .locale_data __locale_bank_start : ALIGN(4)
    {
        *(.locale_data .locale_data.*)
        . = ALIGN(4);
    } > rom = 0xFF
    __locale_bank_end = __locale_bank_start + SIZEOF(.locale_data);
    __locale_bank_size = SIZEOF(.locale_data);
    ASSERT(__locale_bank_size == 0 || __rom_size == 0x02000000,
        "Locale data requires MODERN_ROM_SIZE=32M")
    ASSERT(__locale_bank_end <= 0x0A000000,
        "Locale data exceeds the 32 MiB ROM boundary")
    /* === END UPPER ROM LOCALE BANK === */

    ASSERT(SIZEOF(ROM) <= __rom_size, "ROM content exceeds configured ROM size")
    ASSERT(SIZEOF(IWRAM) <= 32K, "IWRAM overflow")
    ASSERT(__iwram_static_end <= __sp_usr,
        "IWRAM data overlaps the reserved user/IRQ stacks")
    ASSERT(__iwram_static_end < __sp_usr,
        "IWRAM data leaves no user stack")
    ASSERT(__iwram_static_end <= __iwram_static_limit,
        "IWRAM data leaves less than 0x1000 bytes for the user stack")
    ASSERT(__ewram_used_end <= ORIGIN(ewram) + LENGTH(ewram), "EWRAM overflow")
    ASSERT(gOpAnimSt - gGenericBuffer == 0x2000,
        "gGenericBuffer must immediately precede gOpAnimSt")
    ASSERT(gFadeComponentStep - gOpAnimSt == 0x100,
        "gFadeComponentStep must terminate the buffered UI-frame scratch region")
    ASSERT(gMainCallback < gGenericBuffer || gMainCallback >= gFadeComponentStep,
        "gMainCallback overlaps the buffered UI-frame scratch region")
    ASSERT(ADDR(ewram_data) >= __ewram_start + __ewram_overlay_peak_size,
        "Persistent EWRAM overlaps an overlay")
    ASSERT(__floating_end <= 0x08C00000, "Floating ROM content overlaps pinned banim region at 0x08C00000")
    ASSERT(SIZEOF(ewram_overlay_0) <= 256K, "ewram_overlay_0 exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_gameending) <= 256K, "ewram_overlay_gameending exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_bmstart) <= 256K, "ewram_overlay_bmstart exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_gamestartsave) <= 256K, "ewram_overlay_gamestartsave exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_gamestart) <= 256K, "ewram_overlay_gamestart exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_banim) <= 256K, "ewram_overlay_banim exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_sio) <= 256K, "ewram_overlay_sio exceeds EWRAM")
    ASSERT(SIZEOF(ewram_overlay_worldmap) <= 256K, "ewram_overlay_worldmap exceeds EWRAM")

    .stab             0 : { *(.stab) }
    .stabstr          0 : { *(.stabstr) }
    .stab.excl        0 : { *(.stab.excl) }
    .stab.exclstr     0 : { *(.stab.exclstr) }
    .stab.index       0 : { *(.stab.index) }
    .stab.indexstr    0 : { *(.stab.indexstr) }
    .comment          0 : { *(.comment) }
    .gnu.build.attributes 0 : { *(.gnu.build.attributes .gnu.build.attributes.*) }
    .rel.dyn          0 : { *(.rel.iplt .rel.dyn) }

    .debug            0 : { *(.debug) }
    .line             0 : { *(.line) }
    .debug_srcinfo    0 : { *(.debug_srcinfo) }
    .debug_sfnames    0 : { *(.debug_sfnames) }
    .debug_aranges    0 : { *(.debug_aranges) }
    .debug_pubnames   0 : { *(.debug_pubnames) }
    .debug_info       0 : { *(.debug_info .gnu.linkonce.wi.*) }
    .debug_abbrev     0 : { *(.debug_abbrev) }
    .debug_line       0 : { *(.debug_line .debug_line.* .debug_line_end) }
    .debug_frame      0 : { *(.debug_frame) }
    .debug_str        0 : { *(.debug_str) }
    .debug_str_offsets 0 : { *(.debug_str_offsets) }
    .debug_line_str   0 : { *(.debug_line_str) }
    .debug_addr       0 : { *(.debug_addr) }
    .debug_loc        0 : { *(.debug_loc) }
    .debug_loclists   0 : { *(.debug_loclists) }
    .debug_macinfo    0 : { *(.debug_macinfo) }
    .debug_macro      0 : { *(.debug_macro) }
    .debug_names      0 : { *(.debug_names) }
    .debug_pubtypes   0 : { *(.debug_pubtypes) }
    .debug_ranges     0 : { *(.debug_ranges) }
    .debug_rnglists   0 : { *(.debug_rnglists) }
    .debug_sup        0 : { *(.debug_sup) }
    .debug_weaknames  0 : { *(.debug_weaknames) }
    .debug_funcnames  0 : { *(.debug_funcnames) }
    .debug_typenames  0 : { *(.debug_typenames) }
    .debug_varnames   0 : { *(.debug_varnames) }

    .ARM.attributes     0 : { KEEP(*(.ARM.attributes)) KEEP(*(.gnu.attributes)) }
    .note.gnu.arm.ident 0 : { KEEP(*(.note.gnu.arm.ident)) }

    /DISCARD/ :
    {
        *(.eh_frame)
        *(.eh_frame_hdr)
        *(.ARM.extab .ARM.extab.*)
        *(.ARM.exidx .ARM.exidx.*)
        *(.gnu.warning.*)
        *(.init_array .init_array.*)
        *(.fini_array .fini_array.*)
        *(.note.GNU-stack)
        *(.note.gnu.property)
        *(.gnu.hash)
        *(.interp)
        *(.dynsym)
        *(.dynstr)
        *(.dynamic)
        *(.hash)
        *(.got .got.plt)
        *(.plt .plt.*)
    }
}
