    .INCLUDE "macro.inc"

	.SYNTAX unified
	.ifndef FE8_OVERFLOW_SAFETY_CHECKS
	.equ FE8_OVERFLOW_SAFETY_CHECKS, 0
	.endif

	THUMB_FUNC_START ClearOAMBuffer
ClearOAMBuffer: @ 0x080D7498
	.if FE8_OVERFLOW_SAFETY_CHECKS
	ldr r3, =ClearOAMBufferSafe
	bx r3
	.else
	bx pc
	nop
	.ARM
	b ClearOam
	.endif

	THUMB_FUNC_END ClearOAMBuffer

	THUMB_FUNC_START CallARM_FillTileRect
CallARM_FillTileRect: @ 0x080D74A0
	bx pc
	nop
	.ARM
	b TmApplyTsa

	THUMB_FUNC_END CallARM_FillTileRect

	THUMB_FUNC_START TileMap_FillRect
TileMap_FillRect: @ 0x080D74A8
	bx pc
	nop
	.ARM
	b TmFillRect

	THUMB_FUNC_END TileMap_FillRect

	THUMB_FUNC_START CALLARM_ColorFadeTick
CALLARM_ColorFadeTick: @ 0x080D74B0
	bx pc
	nop
	.ARM
	b ColorFadeTick

	THUMB_FUNC_END CALLARM_ColorFadeTick

	THUMB_FUNC_START TileMap_CopyRect
TileMap_CopyRect: @ 0x080D74B8
	bx pc
	nop
	.ARM
	b TmCopyRect

	THUMB_FUNC_END TileMap_CopyRect

	THUMB_FUNC_START ComputeChecksum32
ComputeChecksum32: @ 0x080D74C0
	bx pc
    nop
	.ARM
	b Checksum32

	THUMB_FUNC_END ComputeChecksum32

	.align 2, 0
