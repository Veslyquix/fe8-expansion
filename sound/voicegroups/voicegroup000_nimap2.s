	@ GENERATED FILE -- do not edit by hand.
	@ Regenerate with: python3 scripts/sound/gen_nimap2.py --upstream <dir>
	@
	@ NIMAP2 instrument map: replaces vanilla voicegroup000's 128
	@ placeholder square waves with a General-MIDI-shaped map, so custom
	@ songs arranged against GM instrument numbers sound as intended.
	@ Trailing comment on each line is the GM program number.

	.include "asm/macros/music_voice.inc"

	.section .rodata

	.align 2
	@********************** Voicegroup **********************@

	.global voicegroup000
voicegroup000:
	voice_directsound 60, 0, DirectSoundData_h_piano_g3_13k8b_ss, 255, 250, 0, 204	@ 0
	voice_directsound 60, 0, DirectSoundData_h_piano_c5_13k8b_ss, 255, 250, 0, 204	@ 1
	voice_directsound 60, 0, DirectSoundData_k_strpizz_c2_13k_ss, 255, 249, 0, 165	@ 2
	voice_square_1 0, 2, 0, 0, 15, 0	@ 3
	voice_directsound 60, 0, DirectSoundData_k_epiano_g4_13k, 255, 253, 0, 204	@ 4
	voice_square_1 0, 2, 0, 0, 15, 0	@ 5
	voice_directsound 60, 0, DirectSoundData_k_harpsi_c3_13k_s, 255, 249, 0, 165	@ 6
	voice_directsound 60, 0, DirectSoundData_k_harpsi_c3_13k_s, 255, 245, 150, 150	@ 7
	voice_directsound 60, 0, DirectSoundData_k_celesta_c5_13k_ss, 255, 0, 255, 165	@ 8
	voice_square_1 0, 2, 0, 0, 15, 0	@ 9
	voice_directsound 60, 0, DirectSoundData_k_mbox_c5_13k_s, 255, 226, 255, 226	@ 10
	voice_directsound 60, 0, DirectSoundData_k_celesta_c5_13k_ss, 255, 235, 0, 204	@ 11
	voice_square_1 0, 2, 0, 0, 15, 0	@ 12
	voice_directsound 60, 0, DirectSoundData_k_marimba2_c4_13k_ss, 255, 0, 255, 165	@ 13
	voice_directsound 60, 0, DirectSoundData_k_tubular_c4_13k_s, 255, 250, 0, 204	@ 14
	voice_directsound 60, 0, DirectSoundData_h_dulcimer_g3_13k8b_ss, 255, 0, 255, 165	@ 15
	voice_directsound 60, 0, DirectSoundData_k_pipeorgan_c5_13k_s, 255, 0, 255, 165	@ 16
	voice_square_1 0, 2, 0, 0, 15, 0	@ 17
	voice_directsound 60, 0, DirectSoundData_h_organ2_c5_13k8b_ss, 255, 0, 255, 149	@ 18
	voice_directsound 60, 0, DirectSoundData_k_pipeorgan_c4_13k_s, 255, 0, 255, 165	@ 19
	voice_directsound 60, 0, DirectSoundData_k_pipeorgan_c5_13k_s, 255, 0, 255, 165	@ 20
	voice_directsound 60, 0, DirectSoundData_h_acd_g3_13k8b_ss, 64, 0, 255, 127	@ 21
	voice_square_1 0, 2, 0, 0, 15, 0	@ 22
	voice_directsound 60, 0, DirectSoundData_h_organ_c5_13k8b_ss, 64, 0, 255, 200	@ 23
	voice_directsound 60, 0, DirectSoundData_h_pizz_c4_13k8b_ss, 255, 250, 0, 198	@ 24
	voice_square_1 0, 2, 0, 0, 15, 0	@ 25
	voice_square_1 0, 2, 0, 0, 15, 0	@ 26
	voice_square_1 0, 2, 0, 0, 15, 0	@ 27
	voice_directsound 60, 0, DirectSoundData_k_distgtr2_mute_c3_13k_s, 255, 250, 200, 150	@ 28
	voice_directsound 60, 0, DirectSoundData_k_sitar_c4_13k_ss, 255, 250, 0, 165	@ 29
	voice_directsound 60, 0, DirectSoundData_k_distgtr2_c3_13k_ss, 255, 0, 255, 165	@ 30
	voice_directsound 60, 0, DirectSoundData_h_guiter_scrape1_13k_e, 255, 0, 255, 204	@ 31
	voice_directsound 60, 0, DirectSoundData_k_tuba_c3_13k_ss, 255, 0, 255, 165	@ 32
	voice_directsound 60, 0, DirectSoundData_k_finbass2_c3_13k_s, 100, 0, 255, 200	@ 33
	voice_directsound 60, 0, DirectSoundData_k_finbass2_c3_13k_s, 255, 250, 200, 165	@ 34
	voice_directsound 60, 0, DirectSoundData_k_tuba_c3_13k_ss, 80, 255, 0, 200	@ 35
	voice_directsound 60, 0, DirectSoundData_k_slap_c2_13k_ss, 255, 251, 100, 165	@ 36
	voice_square_1 0, 2, 0, 0, 15, 0	@ 37
	voice_directsound 60, 0, DirectSoundData_k_synbass1_c2_13k_ss, 255, 235, 80, 165	@ 38
	voice_directsound 60, 0, DirectSoundData_k_fbass_c3_13k_s, 255, 246, 128, 165	@ 39
	voice_directsound 60, 0, DirectSoundData_k_strings_13k_c4, 200, 0, 255, 150	@ 40
	voice_directsound 60, 0, DirectSoundData_k_strings_13k_c5, 255, 0, 255, 89	@ 41
	voice_directsound 60, 0, DirectSoundData_k_strings7_c6_13k_ss, 255, 0, 255, 165	@ 42
	voice_square_1 0, 2, 0, 0, 15, 0	@ 43
	voice_directsound 60, 0, DirectSoundData_k_harp_c4_13k_s, 255, 242, 0, 165	@ 44
	voice_directsound 60, 0, DirectSoundData_h_pizz_c4_13k8b_ss, 128, 0, 255, 178	@ 45
	voice_directsound 60, 0, DirectSoundData_k_harp_c4_13k_s, 255, 242, 0, 220	@ 46
	voice_directsound 60, 0, DirectSoundData_k_timpani3_g3_13k_s, 255, 250, 0, 204	@ 47
	voice_directsound 60, 0, DirectSoundData_k_strings5_c4_13k, 150, 0, 255, 165	@ 48
	voice_directsound 60, 0, DirectSoundData_k_strings_13k_c4, 50, 255, 0, 220	@ 49
	voice_directsound 60, 0, DirectSoundData_k_strings5_c2_13k, 100, 0, 255, 150	@ 50
	voice_directsound 60, 0, DirectSoundData_k_strings5_c3_13k, 200, 0, 255, 150	@ 51
	voice_directsound 60, 0, DirectSoundData_k_voice1_c4_13k_ss, 255, 0, 255, 178	@ 52
	voice_square_1 0, 2, 0, 0, 15, 0	@ 53
	voice_directsound 60, 0, DirectSoundData_k_voice1_c5_13k_ss, 50, 0, 255, 200	@ 54
	voice_square_1 0, 2, 0, 0, 15, 0	@ 55
	voice_directsound 60, 0, DirectSoundData_brass4_c4_e3l_10k8b, 255, 0, 255, 165	@ 56
	voice_directsound 60, 0, DirectSoundData_k_brasstrm_c4_13k, 255, 0, 255, 165	@ 57
	voice_directsound 60, 0, DirectSoundData_k_horn5_c4_13k_ss, 100, 0, 255, 200	@ 58
	voice_directsound 60, 0, DirectSoundData_h_tp_mute_c5_13k8b_ss, 200, 0, 255, 150	@ 59
	voice_directsound 60, 0, DirectSoundData_k_horn2_c4_13k_ss, 120, 0, 255, 150	@ 60
	voice_directsound 60, 0, DirectSoundData_k_brass2_c4_13k, 200, 0, 255, 165	@ 61
	voice_directsound 60, 0, DirectSoundData_k_brass3_c3_13k, 255, 0, 255, 150	@ 62
	voice_directsound 60, 0, DirectSoundData_k_brass_c3_13k, 255, 0, 255, 165	@ 63
	voice_directsound 60, 0, DirectSoundData_k_enghorn_c4_13k_s, 200, 0, 255, 150	@ 64
	voice_directsound 60, 0, DirectSoundData_k_brasstrp_c4_13k, 150, 0, 255, 200	@ 65
	voice_directsound 60, 0, DirectSoundData_k_brass_c4_13k, 200, 0, 255, 150	@ 66
	voice_directsound 60, 0, DirectSoundData_k_oboe_c4_13k_ss, 128, 0, 255, 165	@ 67
	voice_directsound 60, 0, DirectSoundData_k_oboe_c5_13k_s, 255, 0, 255, 89	@ 68
	voice_directsound 60, 0, DirectSoundData_k_oboe_c4_13k_s, 255, 0, 255, 89	@ 69
	voice_directsound 60, 0, DirectSoundData_k_bassoon_c3_13k_ss, 255, 0, 255, 178	@ 70
	voice_directsound 60, 0, DirectSoundData_k_clarinet_c5_13k_ss, 255, 0, 255, 165	@ 71
	voice_square_1 0, 2, 0, 0, 15, 0	@ 72
	voice_directsound 60, 0, DirectSoundData_k_flute_c6_13k_s, 255, 0, 255, 165	@ 73
	voice_directsound 60, 0, DirectSoundData_k_flute_c5_13k_ss, 255, 0, 255, 165	@ 74
	voice_directsound 60, 0, DirectSoundData_k_pflute_c5_13k_ss, 255, 0, 255, 150	@ 75
	voice_directsound 60, 0, DirectSoundData_k_pflute_c5_13k_ss, 50, 255, 0, 210	@ 76
	voice_directsound 60, 0, DirectSoundData_k_piccolo_c5_13k_ss, 255, 0, 255, 150	@ 77
	voice_directsound 60, 0, DirectSoundData_k_enghorn_c4_13k_s, 50, 0, 255, 220	@ 78
	voice_directsound 60, 0, DirectSoundData_h_rec_c5_13k8b_ss, 255, 0, 255, 188	@ 79
	voice_directsound 60, 0, DirectSoundData_h_square_c5_13k8b_ss, 255, 0, 255, 127	@ 80
	voice_directsound 60, 0, DirectSoundData_dr_solo2_c2_e3l_10k, 255, 0, 255, 0	@ 81
	voice_square_1 0, 2, 0, 0, 15, 0	@ 82
	voice_square_1 0, 2, 0, 0, 15, 0	@ 83
	voice_square_1 0, 2, 0, 0, 15, 0	@ 84
	voice_directsound 60, 0, DirectSoundData_k_voice1_c5_13k_ss, 255, 0, 255, 165	@ 85
	voice_directsound 60, 0, DirectSoundData_k_brasstrm2_c4_13k, 150, 0, 255, 150	@ 86
	voice_square_1 0, 2, 0, 0, 15, 0	@ 87
	voice_directsound 60, 0, DirectSoundData_k_brass_c3_13k, 8, 255, 0, 224	@ 88
	voice_directsound 60, 0, DirectSoundData_k_voice1_c5_13k_ss, 10, 255, 0, 224	@ 89
	voice_directsound 60, 0, DirectSoundData_h_tp_mute_c5_13k8b_ss, 255, 0, 255, 165	@ 90
	voice_directsound 60, 0, DirectSoundData_k_voice1_c4_13k_ss, 8, 255, 0, 224	@ 91
	voice_directsound 60, 0, DirectSoundData_k_epiano_g4_13k, 9, 255, 0, 224	@ 92
	voice_directsound 60, 0, DirectSoundData_k_brass2_c4_13k, 8, 255, 0, 224	@ 93
	voice_directsound 60, 0, DirectSoundData_k_brightness_c5_13k_ss, 5, 255, 0, 234	@ 94
	voice_directsound 60, 0, DirectSoundData_h_square_c5_13k8b_ss, 8, 255, 40, 224	@ 95
	voice_square_1 0, 2, 0, 0, 15, 0	@ 96
	voice_square_1 0, 2, 0, 0, 15, 0	@ 97
	voice_directsound 60, 0, DirectSoundData_k_horn5_c4_13k_ss, 44, 0, 255, 200	@ 98
	voice_directsound 60, 0, DirectSoundData_h_dulcimer_g3_13k8b_ss, 50, 255, 150, 200	@ 99
	voice_directsound 60, 0, DirectSoundData_k_brightness_c5_13k_ss, 255, 252, 40, 220	@ 100
	voice_directsound 60, 0, DirectSoundData_k_brassorc_c4_13k, 100, 0, 255, 165	@ 101
	voice_directsound 60, 0, DirectSoundData_k_brass_c4_13k, 50, 0, 255, 200	@ 102
	voice_directsound 60, 0, DirectSoundData_k_distgtr4_c3_13k, 255, 0, 255, 204	@ 103
	voice_directsound 60, 0, DirectSoundData_k_brass3_c4_13k, 255, 0, 255, 165	@ 104
	voice_directsound 60, 0, DirectSoundData_k_synstrings1_c4_13k, 255, 0, 255, 178	@ 105
	voice_directsound 60, 0, DirectSoundData_k_strings5_c5_13k_ss, 85, 0, 255, 149	@ 106
	voice_directsound 60, 0, DirectSoundData_k_strings7_c5_13k_ss, 255, 0, 255, 165	@ 107
	voice_directsound 60, 0, DirectSoundData_k_strings5_c5_13k, 255, 0, 255, 165	@ 108
	voice_directsound 60, 0, DirectSoundData_k_strings5_c5c4_13k, 50, 0, 255, 200	@ 109
	voice_directsound 60, 0, DirectSoundData_k_strings5_c5c4_13k, 255, 0, 255, 165	@ 110
	voice_directsound 60, 0, DirectSoundData_h_pr_hyuun1_02_13k8b, 255, 0, 255, 0	@ 111
	voice_directsound 60, 0, DirectSoundData_25, 255, 252, 0, 234	@ 112
	voice_square_1 0, 2, 0, 0, 15, 0	@ 113
	voice_square_1 0, 2, 0, 0, 15, 0	@ 114
	voice_square_1 0, 2, 0, 0, 15, 0	@ 115
	voice_directsound 60, 0, DirectSoundData_26, 255, 253, 0, 200	@ 116
	voice_directsound 60, 0, DirectSoundData_32, 255, 0, 255, 150	@ 117
	voice_directsound 60, 0, DirectSoundData_8, 150, 0, 255, 165	@ 118
	voice_directsound 60, 0, DirectSoundData_9, 255, 0, 255, 165	@ 119
	voice_square_1 0, 2, 0, 0, 15, 0	@ 120
	voice_keysplit_all voicegroup084	@ 121
	voice_keysplit_all voicegroup083	@ 122
	voice_keysplit_all voicegroup079	@ 123
	voice_keysplit_all voicegroup080	@ 124
	voice_directsound 60, 0, DirectSoundData_y_se_wind_1_l_13k8b, 150, 0, 255, 150	@ 125
	voice_directsound 60, 0, DirectSoundData_kansei1_e5l_13k8b, 255, 0, 255, 0	@ 126
	voice_keysplit_all voicegroup083	@ 127
