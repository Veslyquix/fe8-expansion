	@ GENERATED FILE -- do not edit by hand.
	@ Regenerate with: python3 scripts/sound/gen_nimap2.py --upstream <dir>
	@
	@ NIMAP2 drumfix: voicegroup081 with 7 percussion
	@ entries replaced so GM drum-track note numbers land on real
	@ percussion samples instead of vanilla's gaps/placeholders.

	.include "asm/macros/music_voice.inc"

	.section .rodata

	.align 2
	@********************** Voicegroup **********************@

	.global voicegroup081
voicegroup081:
	voice_directsound_no_resample 60, 79, DirectSoundData_32, 255, 0, 255, 165	@08222B30
	voice_directsound_no_resample 60, 84, DirectSoundData_33, 255, 149, 167, 204	@08222B3C
	voice_directsound_no_resample 60, 44, DirectSoundData_7, 255, 0, 255, 204	@08222B48
	voice_directsound_no_resample 60, 44, DirectSoundData_34, 255, 0, 255, 204	@08222B54
	voice_directsound 60, 44, DirectSoundData_8, 255, 0, 255, 165	@08222B60
	voice_directsound 60, 84, DirectSoundData_9, 255, 0, 255, 165	@08222B6C
	voice_directsound_no_resample 60, 79, DirectSoundData_10, 255, 0, 255, 204	@08222B78
	voice_directsound_no_resample 60, 54, DirectSoundData_11, 255, 0, 255, 204	@08222B84
	voice_directsound_no_resample 60, 79, DirectSoundData_12, 255, 0, 255, 204	@08222B90
	voice_directsound_no_resample 60, 84, DirectSoundData_k_roomcc_c4_13k_ss, 255, 0, 255, 204	@08222B9C
	voice_directsound_no_resample 60, 34, DirectSoundData_13, 255, 0, 255, 204	@08222BA8
	voice_directsound_no_resample 60, 64, DirectSoundData_34, 255, 0, 255, 204	@ drumfix
	voice_directsound_no_resample 60, 94, DirectSoundData_h_dr_bongo_h_13k8b_ss, 255, 0, 255, 204	@08222BC0
	voice_directsound_no_resample 60, 94, DirectSoundData_h_dr_bongo_l_13k8b_ss, 255, 0, 255, 204	@08222BCC
	voice_directsound_no_resample 60, 39, DirectSoundData_14, 255, 0, 255, 204	@08222BD8
	voice_directsound_no_resample 60, 39, DirectSoundData_15, 255, 0, 255, 204	@08222BE4
	voice_directsound_no_resample 60, 34, DirectSoundData_16, 255, 0, 255, 204	@08222BF0
	voice_directsound_no_resample 60, 64, DirectSoundData_h_dr_bongo_h_13k8b_ss, 255, 0, 255, 204	@ drumfix
	voice_directsound_no_resample 60, 94, DirectSoundData_h_dr_bongo_l_13k8b_ss, 255, 0, 255, 204	@ drumfix
	voice_directsound_no_resample 60, 36, DirectSoundData_h_agogo_h_13k8b_ss, 255, 0, 255, 204	@08222C14
	voice_directsound_no_resample 60, 36, DirectSoundData_17, 255, 0, 255, 204	@08222C20
	voice_directsound_no_resample 60, 12, DirectSoundData_30, 255, 0, 255, 204	@ drumfix
	voice_directsound_no_resample 60, 24, DirectSoundData_30, 255, 0, 255, 204	@ drumfix
	voice_square_1 0, 2, 0, 0, 15, 0	@08222C44
	voice_square_1 0, 2, 0, 0, 15, 0	@08222C50
	voice_directsound_no_resample 60, 84, DirectSoundData_18, 255, 0, 255, 204	@08222C5C
	voice_directsound_no_resample 60, 84, DirectSoundData_19, 255, 0, 255, 204	@08222C68
	voice_directsound_no_resample 60, 89, DirectSoundData_20, 255, 0, 255, 204	@08222C74
	voice_directsound_no_resample 60, 87, DirectSoundData_21, 255, 0, 255, 204	@08222C80
	voice_directsound_no_resample 60, 92, DirectSoundData_h_wblock_l_13k8b_ss, 255, 0, 255, 204	@08222C8C
	@ pan byte 0x80 has no music_voice.inc macro form
	.byte 8, 60, 0, 0x80
	.4byte DirectSoundData_18
	.byte 255, 0, 255, 204	@ drumfix
	voice_directsound_no_resample 60, 89, DirectSoundData_19, 255, 0, 255, 204	@ drumfix
	voice_directsound_no_resample 60, 34, DirectSoundData_22, 255, 0, 255, 204	@08222CB0
	voice_directsound_no_resample 60, 34, DirectSoundData_23, 255, 242, 0, 204	@08222CBC
	voice_directsound_no_resample 60, 34, DirectSoundData_24, 255, 0, 255, 204	@08222CC8
	voice_directsound_no_resample 60, 99, DirectSoundData_25, 255, 0, 255, 204	@08222CD4
	voice_directsound_no_resample 60, 64, DirectSoundData_0, 255, 0, 255, 204	@08222CE0
	voice_directsound_no_resample 60, 64, DirectSoundData_h_sidestick_13k8b_ss, 255, 0, 255, 204	@08222CEC
	voice_directsound_no_resample 60, 64, DirectSoundData_k_roomsd_c4_13k_ss, 255, 0, 255, 204	@08222CF8
	voice_directsound_no_resample 60, 44, DirectSoundData_1, 255, 0, 255, 204	@08222D04
	voice_square_1 0, 2, 0, 0, 15, 0	@08222D10
	voice_directsound_no_resample 60, 34, DirectSoundData_2, 255, 0, 255, 226	@08222D1C
	voice_directsound_no_resample 60, 89, DirectSoundData_3, 255, 0, 255, 204	@08222D28
	voice_square_1 0, 2, 0, 0, 15, 0	@08222D34
	voice_square_1 0, 2, 0, 0, 15, 0	@08222D40
	voice_directsound_no_resample 60, 59, DirectSoundData_4, 255, 0, 255, 204	@08222D4C
	voice_directsound_no_resample 60, 89, DirectSoundData_5, 255, 0, 255, 204	@08222D58
	voice_square_1 0, 2, 0, 0, 15, 0	@08222D64
