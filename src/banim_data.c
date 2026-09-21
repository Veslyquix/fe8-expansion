#include "banim_data.h"
__attribute__((section(".data.banim_array")))
struct BattleAnim banim_data[] = {
	{"lorm_sp1", &banim_lorm_sp1_modes_bin, &banim_lorm_sp1_motion_o, &banim_lorm_sp1_oam_r_bin, &banim_lorm_sp1_oam_l_bin, &banim_lorm_sp1_agbpal}, // 0x0
	{"lorm_sp1", &banim_lorm_sp1_2_modes_bin, &banim_lorm_sp1_2_motion_o, &banim_lorm_sp1_2_oam_r_bin, &banim_lorm_sp1_2_oam_l_bin, &banim_lorm_sp1_2_agbpal}, // 0x1
	{"lorf_sw1", &banim_lorf_sw1_modes_bin, &banim_lorf_sw1_motion_o, &banim_lorf_sw1_oam_r_bin, &banim_lorf_sw1_oam_l_bin, &banim_lorf_sw1_agbpal}, // 0x2
	{"lorf_sw1", &banim_lorf_sw1_2_modes_bin, &banim_lorf_sw1_2_motion_o, &banim_lorf_sw1_2_oam_r_bin, &banim_lorf_sw1_2_oam_l_bin, &banim_lorf_sw1_2_agbpal}, // 0x3
	{"lomm_sp1", &banim_lomm_sp1_modes_bin, &banim_lomm_sp1_motion_o, &banim_lomm_sp1_oam_r_bin, &banim_lomm_sp1_oam_l_bin, &banim_lomm_sp1_agbpal}, // 0x4
	{"lorf_sw1", &banim_lorf_sw1_3_modes_bin, &banim_lorf_sw1_3_motion_o, &banim_lorf_sw1_3_oam_r_bin, &banim_lorf_sw1_3_oam_l_bin, &banim_lorf_sw1_3_agbpal}, // 0x5
	{"lomm_sp1", &banim_lomm_sp1_2_modes_bin, &banim_lomm_sp1_2_motion_o, &banim_lomm_sp1_2_oam_r_bin, &banim_lomm_sp1_2_oam_l_bin, &banim_lomm_sp1_2_agbpal}, // 0x6
	{"lomf_sw1", &banim_lomf_sw1_modes_bin, &banim_lomf_sw1_motion_o, &banim_lomf_sw1_oam_r_bin, &banim_lomf_sw1_oam_l_bin, &banim_lomf_sw1_agbpal}, // 0x7
	{"lorf_sw1", &banim_lorf_sw1_4_modes_bin, &banim_lorf_sw1_4_motion_o, &banim_lorf_sw1_4_oam_r_bin, &banim_lorf_sw1_4_oam_l_bin, &banim_lorf_sw1_4_agbpal}, // 0x8
	{"lomf_sw1", &banim_lomf_sw1_2_modes_bin, &banim_lomf_sw1_2_motion_o, &banim_lomf_sw1_2_oam_r_bin, &banim_lomf_sw1_2_oam_l_bin, &banim_lomf_sw1_2_agbpal}, // 0x9
	{"merm_sw1", &banim_merm_sw1_modes_bin, &banim_merm_sw1_motion_o, &banim_merm_sw1_oam_r_bin, &banim_merm_sw1_oam_l_bin, &banim_merm_sw1_agbpal}, // 0xA
	{"merm_sw1", &banim_merm_sw1_2_modes_bin, &banim_merm_sw1_2_motion_o, &banim_merm_sw1_2_oam_r_bin, &banim_merm_sw1_2_oam_l_bin, &banim_merm_sw1_2_agbpal}, // 0xB
	{"bram_sw1", &banim_bram_sw1_modes_bin, &banim_bram_sw1_motion_o, &banim_bram_sw1_oam_r_bin, &banim_bram_sw1_oam_l_bin, &banim_bram_sw1_agbpal}, // 0xC
	{"bram_sw1", &banim_bram_sw1_2_modes_bin, &banim_bram_sw1_2_motion_o, &banim_bram_sw1_2_oam_r_bin, &banim_bram_sw1_2_oam_l_bin, &banim_bram_sw1_2_agbpal}, // 0xD
	{"bram_sw1", &banim_bram_sw1_3_modes_bin, &banim_bram_sw1_3_motion_o, &banim_bram_sw1_3_oam_r_bin, &banim_bram_sw1_3_oam_l_bin, &banim_bram_sw1_3_agbpal}, // 0xE
	{"bram_sw1", &banim_bram_sw1_4_modes_bin, &banim_bram_sw1_4_motion_o, &banim_bram_sw1_4_oam_r_bin, &banim_bram_sw1_4_oam_l_bin, &banim_bram_sw1_4_agbpal}, // 0xF
	{"myrm_sw1", &banim_myrm_sw1_modes_bin, &banim_myrm_sw1_motion_o, &banim_myrm_sw1_oam_r_bin, &banim_myrm_sw1_oam_l_bin, &banim_myrm_sw1_agbpal}, // 0x10
	{"myrm_sw1", &banim_myrm_sw1_2_modes_bin, &banim_myrm_sw1_2_motion_o, &banim_myrm_sw1_2_oam_r_bin, &banim_myrm_sw1_2_oam_l_bin, &banim_myrm_sw1_2_agbpal}, // 0x11
	{"myrf_sw1", &banim_myrf_sw1_modes_bin, &banim_myrf_sw1_motion_o, &banim_myrf_sw1_oam_r_bin, &banim_myrf_sw1_oam_l_bin, &banim_myrf_sw1_agbpal}, // 0x12
	{"myrf_sw1", &banim_myrf_sw1_2_modes_bin, &banim_myrf_sw1_2_motion_o, &banim_myrf_sw1_2_oam_r_bin, &banim_myrf_sw1_2_oam_l_bin, &banim_myrf_sw1_2_agbpal}, // 0x13
	{"swmm_sw1", &banim_swmm_sw1_modes_bin, &banim_swmm_sw1_motion_o, &banim_swmm_sw1_oam_r_bin, &banim_swmm_sw1_oam_l_bin, &banim_swmm_sw1_agbpal}, // 0x14
	{"swmm_sw1", &banim_swmm_sw1_2_modes_bin, &banim_swmm_sw1_2_motion_o, &banim_swmm_sw1_2_oam_r_bin, &banim_swmm_sw1_2_oam_l_bin, &banim_swmm_sw1_2_agbpal}, // 0x15
	{"swmf_sw1", &banim_swmf_sw1_modes_bin, &banim_swmf_sw1_motion_o, &banim_swmf_sw1_oam_r_bin, &banim_swmf_sw1_oam_l_bin, &banim_swmf_sw1_agbpal}, // 0x16
	{"swmf_sw1", &banim_swmf_sw1_2_modes_bin, &banim_swmf_sw1_2_motion_o, &banim_swmf_sw1_2_oam_r_bin, &banim_swmf_sw1_2_oam_l_bin, &banim_swmf_sw1_2_agbpal}, // 0x17
	{"figm_ax1", &banim_figm_ax1_modes_bin, &banim_figm_ax1_motion_o, &banim_figm_ax1_oam_r_bin, &banim_figm_ax1_oam_l_bin, &banim_figm_ax1_agbpal}, // 0x18
	{"figm_ax1", &banim_figm_ax1_2_modes_bin, &banim_figm_ax1_2_motion_o, &banim_figm_ax1_2_oam_r_bin, &banim_figm_ax1_2_oam_l_bin, &banim_figm_ax1_2_agbpal}, // 0x19
	{"figm_ax1", &banim_figm_ax1_3_modes_bin, &banim_figm_ax1_3_motion_o, &banim_figm_ax1_3_oam_r_bin, &banim_figm_ax1_3_oam_l_bin, &banim_figm_ax1_3_agbpal}, // 0x1A
	{"warm_ax1", &banim_warm_ax1_modes_bin, &banim_warm_ax1_motion_o, &banim_warm_ax1_oam_r_bin, &banim_warm_ax1_oam_l_bin, &banim_warm_ax1_agbpal}, // 0x1B
	{"warm_ax1", &banim_warm_ax1_2_modes_bin, &banim_warm_ax1_2_motion_o, &banim_warm_ax1_2_oam_r_bin, &banim_warm_ax1_2_oam_l_bin, &banim_warm_ax1_2_agbpal}, // 0x1C
	{"warm_ar1", &banim_warm_ar1_modes_bin, &banim_warm_ar1_motion_o, &banim_warm_ar1_oam_r_bin, &banim_warm_ar1_oam_l_bin, &banim_warm_ar1_agbpal}, // 0x1D
	{"warm_ax1", &banim_warm_ax1_3_modes_bin, &banim_warm_ax1_3_motion_o, &banim_warm_ax1_3_oam_r_bin, &banim_warm_ax1_3_oam_l_bin, &banim_warm_ax1_3_agbpal}, // 0x1E
	{"banm_ax1", &banim_banm_ax1_modes_bin, &banim_banm_ax1_motion_o, &banim_banm_ax1_oam_r_bin, &banim_banm_ax1_oam_l_bin, &banim_banm_ax1_agbpal}, // 0x1F
	{"banm_ax1", &banim_banm_ax1_2_modes_bin, &banim_banm_ax1_2_motion_o, &banim_banm_ax1_2_oam_r_bin, &banim_banm_ax1_2_oam_l_bin, &banim_banm_ax1_2_agbpal}, // 0x20
	{"banm_ax1", &banim_banm_ax1_3_modes_bin, &banim_banm_ax1_3_motion_o, &banim_banm_ax1_3_oam_r_bin, &banim_banm_ax1_3_oam_l_bin, &banim_banm_ax1_3_agbpal}, // 0x21
	{"brsm_ax1", &banim_brsm_ax1_modes_bin, &banim_brsm_ax1_motion_o, &banim_brsm_ax1_oam_r_bin, &banim_brsm_ax1_oam_l_bin, &banim_brsm_ax1_agbpal}, // 0x22
	{"brsm_ax1", &banim_brsm_ax1_2_modes_bin, &banim_brsm_ax1_2_motion_o, &banim_brsm_ax1_2_oam_r_bin, &banim_brsm_ax1_2_oam_l_bin, &banim_brsm_ax1_2_agbpal}, // 0x23
	{"brsm_ax1", &banim_brsm_ax1_3_modes_bin, &banim_brsm_ax1_3_motion_o, &banim_brsm_ax1_3_oam_r_bin, &banim_brsm_ax1_3_oam_l_bin, &banim_brsm_ax1_3_agbpal}, // 0x24
	{"arcm_ar1", &banim_arcm_ar1_modes_bin, &banim_arcm_ar1_motion_o, &banim_arcm_ar1_oam_r_bin, &banim_arcm_ar1_oam_l_bin, &banim_arcm_ar1_agbpal}, // 0x25
	{"arcm_ar1", &banim_arcm_ar1_2_modes_bin, &banim_arcm_ar1_2_motion_o, &banim_arcm_ar1_2_oam_r_bin, &banim_arcm_ar1_2_oam_l_bin, &banim_arcm_ar1_2_agbpal}, // 0x26
	{"arcf_ar1", &banim_arcf_ar1_modes_bin, &banim_arcf_ar1_motion_o, &banim_arcf_ar1_oam_r_bin, &banim_arcf_ar1_oam_l_bin, &banim_arcf_ar1_agbpal}, // 0x27
	{"arcf_ar1", &banim_arcf_ar1_2_modes_bin, &banim_arcf_ar1_2_motion_o, &banim_arcf_ar1_2_oam_r_bin, &banim_arcf_ar1_2_oam_l_bin, &banim_arcf_ar1_2_agbpal}, // 0x28
	{"snim_ar1", &banim_snim_ar1_modes_bin, &banim_snim_ar1_motion_o, &banim_snim_ar1_oam_r_bin, &banim_snim_ar1_oam_l_bin, &banim_snim_ar1_agbpal}, // 0x29
	{"snim_ar1", &banim_snim_ar1_2_modes_bin, &banim_snim_ar1_2_motion_o, &banim_snim_ar1_2_oam_r_bin, &banim_snim_ar1_2_oam_l_bin, &banim_snim_ar1_2_agbpal}, // 0x2A
	{"snif_ar1", &banim_snif_ar1_modes_bin, &banim_snif_ar1_motion_o, &banim_snif_ar1_oam_r_bin, &banim_snif_ar1_oam_l_bin, &banim_snif_ar1_agbpal}, // 0x2B
	{"snif_ar1", &banim_snif_ar1_2_modes_bin, &banim_snif_ar1_2_motion_o, &banim_snif_ar1_2_oam_r_bin, &banim_snif_ar1_2_oam_l_bin, &banim_snif_ar1_2_agbpal}, // 0x2C
	{"form_sw1", &banim_form_sw1_modes_bin, &banim_form_sw1_motion_o, &banim_form_sw1_oam_r_bin, &banim_form_sw1_oam_l_bin, &banim_form_sw1_agbpal}, // 0x2D
	{"form_ar1", &banim_form_ar1_modes_bin, &banim_form_ar1_motion_o, &banim_form_ar1_oam_r_bin, &banim_form_ar1_oam_l_bin, &banim_form_ar1_agbpal}, // 0x2E
	{"form_sw1", &banim_form_sw1_2_modes_bin, &banim_form_sw1_2_motion_o, &banim_form_sw1_2_oam_r_bin, &banim_form_sw1_2_oam_l_bin, &banim_form_sw1_2_agbpal}, // 0x2F
	{"forf_sw1", &banim_forf_sw1_modes_bin, &banim_forf_sw1_motion_o, &banim_forf_sw1_oam_r_bin, &banim_forf_sw1_oam_l_bin, &banim_forf_sw1_agbpal}, // 0x30
	{"forf_ar1", &banim_forf_ar1_modes_bin, &banim_forf_ar1_motion_o, &banim_forf_ar1_oam_r_bin, &banim_forf_ar1_oam_l_bin, &banim_forf_ar1_agbpal}, // 0x31
	{"forf_sw1", &banim_forf_sw1_2_modes_bin, &banim_forf_sw1_2_motion_o, &banim_forf_sw1_2_oam_r_bin, &banim_forf_sw1_2_oam_l_bin, &banim_forf_sw1_2_agbpal}, // 0x32
	{"sokm_sp1", &banim_sokm_sp1_modes_bin, &banim_sokm_sp1_motion_o, &banim_sokm_sp1_oam_r_bin, &banim_sokm_sp1_oam_l_bin, &banim_sokm_sp1_agbpal}, // 0x33
	{"sokm_sp1", &banim_sokm_sp1_2_modes_bin, &banim_sokm_sp1_2_motion_o, &banim_sokm_sp1_2_oam_r_bin, &banim_sokm_sp1_2_oam_l_bin, &banim_sokm_sp1_2_agbpal}, // 0x34
	{"sokm_sp1", &banim_sokm_sp1_3_modes_bin, &banim_sokm_sp1_3_motion_o, &banim_sokm_sp1_3_oam_r_bin, &banim_sokm_sp1_3_oam_l_bin, &banim_sokm_sp1_3_agbpal}, // 0x35
	{"sokf_sp1", &banim_sokf_sp1_modes_bin, &banim_sokf_sp1_motion_o, &banim_sokf_sp1_oam_r_bin, &banim_sokf_sp1_oam_l_bin, &banim_sokf_sp1_agbpal}, // 0x36
	{"sokf_sp1", &banim_sokf_sp1_2_modes_bin, &banim_sokf_sp1_2_motion_o, &banim_sokf_sp1_2_oam_r_bin, &banim_sokf_sp1_2_oam_l_bin, &banim_sokf_sp1_2_agbpal}, // 0x37
	{"sokf_sp1", &banim_sokf_sp1_3_modes_bin, &banim_sokf_sp1_3_motion_o, &banim_sokf_sp1_3_oam_r_bin, &banim_sokf_sp1_3_oam_l_bin, &banim_sokf_sp1_3_agbpal}, // 0x38
	{"pakm_sw1", &banim_pakm_sw1_modes_bin, &banim_pakm_sw1_motion_o, &banim_pakm_sw1_oam_r_bin, &banim_pakm_sw1_oam_l_bin, &banim_pakm_sw1_agbpal}, // 0x39
	{"pakm_sw1", &banim_pakm_sw1_2_modes_bin, &banim_pakm_sw1_2_motion_o, &banim_pakm_sw1_2_oam_r_bin, &banim_pakm_sw1_2_oam_l_bin, &banim_pakm_sw1_2_agbpal}, // 0x3A
	{"pakm_sw1", &banim_pakm_sw1_3_modes_bin, &banim_pakm_sw1_3_motion_o, &banim_pakm_sw1_3_oam_r_bin, &banim_pakm_sw1_3_oam_l_bin, &banim_pakm_sw1_3_agbpal}, // 0x3B
	{"paif_sw1", &banim_paif_sw1_modes_bin, &banim_paif_sw1_motion_o, &banim_paif_sw1_oam_r_bin, &banim_paif_sw1_oam_l_bin, &banim_paif_sw1_agbpal}, // 0x3C
	{"paif_sw1", &banim_paif_sw1_2_modes_bin, &banim_paif_sw1_2_motion_o, &banim_paif_sw1_2_oam_r_bin, &banim_paif_sw1_2_oam_l_bin, &banim_paif_sw1_2_agbpal}, // 0x3D
	{"paif_sw1", &banim_paif_sw1_3_modes_bin, &banim_paif_sw1_3_motion_o, &banim_paif_sw1_3_oam_r_bin, &banim_paif_sw1_3_oam_l_bin, &banim_paif_sw1_3_agbpal}, // 0x3E
	{"armm_sp1", &banim_armm_sp1_modes_bin, &banim_armm_sp1_motion_o, &banim_armm_sp1_oam_r_bin, &banim_armm_sp1_oam_l_bin, &banim_armm_sp1_agbpal}, // 0x3F
	{"armm_sp1", &banim_armm_sp1_2_modes_bin, &banim_armm_sp1_2_motion_o, &banim_armm_sp1_2_oam_r_bin, &banim_armm_sp1_2_oam_l_bin, &banim_armm_sp1_2_agbpal}, // 0x40
	{"armm_sp1", &banim_armm_sp1_3_modes_bin, &banim_armm_sp1_3_motion_o, &banim_armm_sp1_3_oam_r_bin, &banim_armm_sp1_3_oam_l_bin, &banim_armm_sp1_3_agbpal}, // 0x41
	{"armm_sp1", &banim_armm_sp1_4_modes_bin, &banim_armm_sp1_4_motion_o, &banim_armm_sp1_4_oam_r_bin, &banim_armm_sp1_4_oam_l_bin, &banim_armm_sp1_4_agbpal}, // 0x42
	{"genm_sw1", &banim_genm_sw1_modes_bin, &banim_genm_sw1_motion_o, &banim_genm_sw1_oam_r_bin, &banim_genm_sw1_oam_l_bin, &banim_genm_sw1_agbpal}, // 0x43
	{"genm_al1", &banim_genm_al1_modes_bin, &banim_genm_al1_motion_o, &banim_genm_al1_oam_r_bin, &banim_genm_al1_oam_l_bin, &banim_genm_al1_agbpal}, // 0x44
	{"genm_al1", &banim_genm_al1_2_modes_bin, &banim_genm_al1_2_motion_o, &banim_genm_al1_2_oam_r_bin, &banim_genm_al1_2_oam_l_bin, &banim_genm_al1_2_agbpal}, // 0x45
	{"genm_al1", &banim_genm_al1_3_modes_bin, &banim_genm_al1_3_motion_o, &banim_genm_al1_3_oam_r_bin, &banim_genm_al1_3_oam_l_bin, &banim_genm_al1_3_agbpal}, // 0x46
	{"genm_al1", &banim_genm_al1_4_modes_bin, &banim_genm_al1_4_motion_o, &banim_genm_al1_4_oam_r_bin, &banim_genm_al1_4_oam_l_bin, &banim_genm_al1_4_agbpal}, // 0x47
	{"genm_sw1", &banim_genm_sw1_2_modes_bin, &banim_genm_sw1_2_motion_o, &banim_genm_sw1_2_oam_r_bin, &banim_genm_sw1_2_oam_l_bin, &banim_genm_sw1_2_agbpal}, // 0x48
	{"genm_al1", &banim_genm_al1_5_modes_bin, &banim_genm_al1_5_motion_o, &banim_genm_al1_5_oam_r_bin, &banim_genm_al1_5_oam_l_bin, &banim_genm_al1_5_agbpal}, // 0x49
	{"genm_al1", &banim_genm_al1_6_modes_bin, &banim_genm_al1_6_motion_o, &banim_genm_al1_6_oam_r_bin, &banim_genm_al1_6_oam_l_bin, &banim_genm_al1_6_agbpal}, // 0x4A
	{"genm_al1", &banim_genm_al1_7_modes_bin, &banim_genm_al1_7_motion_o, &banim_genm_al1_7_oam_r_bin, &banim_genm_al1_7_oam_l_bin, &banim_genm_al1_7_agbpal}, // 0x4B
	{"genm_al1", &banim_genm_al1_8_modes_bin, &banim_genm_al1_8_motion_o, &banim_genm_al1_8_oam_r_bin, &banim_genm_al1_8_oam_l_bin, &banim_genm_al1_8_agbpal}, // 0x4C
	{"grkm_sw1", &banim_grkm_sw1_modes_bin, &banim_grkm_sw1_motion_o, &banim_grkm_sw1_oam_r_bin, &banim_grkm_sw1_oam_l_bin, &banim_grkm_sw1_agbpal}, // 0x4D
	{"grkm_sp1", &banim_grkm_sp1_modes_bin, &banim_grkm_sp1_motion_o, &banim_grkm_sp1_oam_r_bin, &banim_grkm_sp1_oam_l_bin, &banim_grkm_sp1_agbpal}, // 0x4E
	{"grkm_ax1", &banim_grkm_ax1_modes_bin, &banim_grkm_ax1_motion_o, &banim_grkm_ax1_oam_r_bin, &banim_grkm_ax1_oam_l_bin, &banim_grkm_ax1_agbpal}, // 0x4F
	{"grkm_ax1", &banim_grkm_ax1_2_modes_bin, &banim_grkm_ax1_2_motion_o, &banim_grkm_ax1_2_oam_r_bin, &banim_grkm_ax1_2_oam_l_bin, &banim_grkm_ax1_2_agbpal}, // 0x50
	{"grkm_sw1", &banim_grkm_sw1_2_modes_bin, &banim_grkm_sw1_2_motion_o, &banim_grkm_sw1_2_oam_r_bin, &banim_grkm_sw1_2_oam_l_bin, &banim_grkm_sw1_2_agbpal}, // 0x51
	{"grkm_sw1", &banim_grkm_sw1_3_modes_bin, &banim_grkm_sw1_3_motion_o, &banim_grkm_sw1_3_oam_r_bin, &banim_grkm_sw1_3_oam_l_bin, &banim_grkm_sw1_3_agbpal}, // 0x52
	{"grkm_sp1", &banim_grkm_sp1_2_modes_bin, &banim_grkm_sp1_2_motion_o, &banim_grkm_sp1_2_oam_r_bin, &banim_grkm_sp1_2_oam_l_bin, &banim_grkm_sp1_2_agbpal}, // 0x53
	{"grkm_ax1", &banim_grkm_ax1_3_modes_bin, &banim_grkm_ax1_3_motion_o, &banim_grkm_ax1_3_oam_r_bin, &banim_grkm_ax1_3_oam_l_bin, &banim_grkm_ax1_3_agbpal}, // 0x54
	{"grkm_ax1", &banim_grkm_ax1_4_modes_bin, &banim_grkm_ax1_4_motion_o, &banim_grkm_ax1_4_oam_r_bin, &banim_grkm_ax1_4_oam_l_bin, &banim_grkm_ax1_4_agbpal}, // 0x55
	{"grkm_sw1", &banim_grkm_sw1_4_modes_bin, &banim_grkm_sw1_4_motion_o, &banim_grkm_sw1_4_oam_r_bin, &banim_grkm_sw1_4_oam_l_bin, &banim_grkm_sw1_4_agbpal}, // 0x56
	{"drkm_sp1", &banim_drkm_sp1_modes_bin, &banim_drkm_sp1_motion_o, &banim_drkm_sp1_oam_r_bin, &banim_drkm_sp1_oam_l_bin, &banim_drkm_sp1_agbpal}, // 0x57
	{"drkm_sp1", &banim_drkm_sp1_2_modes_bin, &banim_drkm_sp1_2_motion_o, &banim_drkm_sp1_2_oam_r_bin, &banim_drkm_sp1_2_oam_l_bin, &banim_drkm_sp1_2_agbpal}, // 0x58
	{"drkm_sp1", &banim_drkm_sp1_3_modes_bin, &banim_drkm_sp1_3_motion_o, &banim_drkm_sp1_3_oam_r_bin, &banim_drkm_sp1_3_oam_l_bin, &banim_drkm_sp1_3_agbpal}, // 0x59
	{"drkm_sp1", &banim_drkm_sp1_4_modes_bin, &banim_drkm_sp1_4_motion_o, &banim_drkm_sp1_4_oam_r_bin, &banim_drkm_sp1_4_oam_l_bin, &banim_drkm_sp1_4_agbpal}, // 0x5A
	{"drmm_sp1", &banim_drmm_sp1_modes_bin, &banim_drmm_sp1_motion_o, &banim_drmm_sp1_oam_r_bin, &banim_drmm_sp1_oam_l_bin, &banim_drmm_sp1_agbpal}, // 0x5B
	{"drmm_sp1", &banim_drmm_sp1_2_modes_bin, &banim_drmm_sp1_2_motion_o, &banim_drmm_sp1_2_oam_r_bin, &banim_drmm_sp1_2_oam_l_bin, &banim_drmm_sp1_2_agbpal}, // 0x5C
	{"drmm_sp1", &banim_drmm_sp1_3_modes_bin, &banim_drmm_sp1_3_motion_o, &banim_drmm_sp1_3_oam_r_bin, &banim_drmm_sp1_3_oam_l_bin, &banim_drmm_sp1_3_agbpal}, // 0x5D
	{"drmm_sp1", &banim_drmm_sp1_4_modes_bin, &banim_drmm_sp1_4_motion_o, &banim_drmm_sp1_4_oam_r_bin, &banim_drmm_sp1_4_oam_l_bin, &banim_drmm_sp1_4_agbpal}, // 0x5E
	{"drmm_sp1", &banim_drmm_sp1_5_modes_bin, &banim_drmm_sp1_5_motion_o, &banim_drmm_sp1_5_oam_r_bin, &banim_drmm_sp1_5_oam_l_bin, &banim_drmm_sp1_5_agbpal}, // 0x5F
	{"drmm_sp1", &banim_drmm_sp1_6_modes_bin, &banim_drmm_sp1_6_motion_o, &banim_drmm_sp1_6_oam_r_bin, &banim_drmm_sp1_6_oam_l_bin, &banim_drmm_sp1_6_agbpal}, // 0x60
	{"wykm_sp1", &banim_wykm_sp1_modes_bin, &banim_wykm_sp1_motion_o, &banim_wykm_sp1_oam_r_bin, &banim_wykm_sp1_oam_l_bin, &banim_wykm_sp1_agbpal}, // 0x61
	{"wykm_sp1", &banim_wykm_sp1_2_modes_bin, &banim_wykm_sp1_2_motion_o, &banim_wykm_sp1_2_oam_r_bin, &banim_wykm_sp1_2_oam_l_bin, &banim_wykm_sp1_2_agbpal}, // 0x62
	{"wykm_sp1", &banim_wykm_sp1_3_modes_bin, &banim_wykm_sp1_3_motion_o, &banim_wykm_sp1_3_oam_r_bin, &banim_wykm_sp1_3_oam_l_bin, &banim_wykm_sp1_3_agbpal}, // 0x63
	{"wykm_sp1", &banim_wykm_sp1_4_modes_bin, &banim_wykm_sp1_4_motion_o, &banim_wykm_sp1_4_oam_r_bin, &banim_wykm_sp1_4_oam_l_bin, &banim_wykm_sp1_4_agbpal}, // 0x64
	{"pekf_sp1", &banim_pekf_sp1_modes_bin, &banim_pekf_sp1_motion_o, &banim_pekf_sp1_oam_r_bin, &banim_pekf_sp1_oam_l_bin, &banim_pekf_sp1_agbpal}, // 0x65
	{"pekf_sp1", &banim_pekf_sp1_2_modes_bin, &banim_pekf_sp1_2_motion_o, &banim_pekf_sp1_2_oam_r_bin, &banim_pekf_sp1_2_oam_l_bin, &banim_pekf_sp1_2_agbpal}, // 0x66
	{"fakf_sp1", &banim_fakf_sp1_modes_bin, &banim_fakf_sp1_motion_o, &banim_fakf_sp1_oam_r_bin, &banim_fakf_sp1_oam_l_bin, &banim_fakf_sp1_agbpal}, // 0x67
	{"fakf_sp1", &banim_fakf_sp1_2_modes_bin, &banim_fakf_sp1_2_motion_o, &banim_fakf_sp1_2_oam_r_bin, &banim_fakf_sp1_2_oam_l_bin, &banim_fakf_sp1_2_agbpal}, // 0x68
	{"fakf_sp1", &banim_fakf_sp1_3_modes_bin, &banim_fakf_sp1_3_motion_o, &banim_fakf_sp1_3_oam_r_bin, &banim_fakf_sp1_3_oam_l_bin, &banim_fakf_sp1_3_agbpal}, // 0x69
	{"magm_mg1", &banim_magm_mg1_modes_bin, &banim_magm_mg1_motion_o, &banim_magm_mg1_oam_r_bin, &banim_magm_mg1_oam_l_bin, &banim_magm_mg1_agbpal}, // 0x6A
	{"magf_mg1", &banim_magf_mg1_modes_bin, &banim_magf_mg1_motion_o, &banim_magf_mg1_oam_r_bin, &banim_magf_mg1_oam_l_bin, &banim_magf_mg1_agbpal}, // 0x6B
	{"sagm_mg1", &banim_sagm_mg1_modes_bin, &banim_sagm_mg1_motion_o, &banim_sagm_mg1_oam_r_bin, &banim_sagm_mg1_oam_l_bin, &banim_sagm_mg1_agbpal}, // 0x6C
	{"sagm_mg1", &banim_sagm_mg1_2_modes_bin, &banim_sagm_mg1_2_motion_o, &banim_sagm_mg1_2_oam_r_bin, &banim_sagm_mg1_2_oam_l_bin, &banim_sagm_mg1_2_agbpal}, // 0x6D
	{"sagf_mg1", &banim_sagf_mg1_modes_bin, &banim_sagf_mg1_motion_o, &banim_sagf_mg1_oam_r_bin, &banim_sagf_mg1_oam_l_bin, &banim_sagf_mg1_agbpal}, // 0x6E
	{"sagf_mg1", &banim_sagf_mg1_2_modes_bin, &banim_sagf_mg1_2_motion_o, &banim_sagf_mg1_2_oam_r_bin, &banim_sagf_mg1_2_oam_l_bin, &banim_sagf_mg1_2_agbpal}, // 0x6F
	{"mgkm_mg1", &banim_mgkm_mg1_modes_bin, &banim_mgkm_mg1_motion_o, &banim_mgkm_mg1_oam_r_bin, &banim_mgkm_mg1_oam_l_bin, &banim_mgkm_mg1_agbpal}, // 0x70
	{"mgkm_mg1", &banim_mgkm_mg1_2_modes_bin, &banim_mgkm_mg1_2_motion_o, &banim_mgkm_mg1_2_oam_r_bin, &banim_mgkm_mg1_2_oam_l_bin, &banim_mgkm_mg1_2_agbpal}, // 0x71
	{"mgkf_mg1", &banim_mgkf_mg1_modes_bin, &banim_mgkf_mg1_motion_o, &banim_mgkf_mg1_oam_r_bin, &banim_mgkf_mg1_oam_l_bin, &banim_mgkf_mg1_agbpal}, // 0x72
	{"mgkf_mg1", &banim_mgkf_mg1_2_modes_bin, &banim_mgkf_mg1_2_motion_o, &banim_mgkf_mg1_2_oam_r_bin, &banim_mgkf_mg1_2_oam_l_bin, &banim_mgkf_mg1_2_agbpal}, // 0x73
	{"sham_mg1", &banim_sham_mg1_modes_bin, &banim_sham_mg1_motion_o, &banim_sham_mg1_oam_r_bin, &banim_sham_mg1_oam_l_bin, &banim_sham_mg1_agbpal}, // 0x74
	{"shaf_mg1", &banim_shaf_mg1_modes_bin, &banim_shaf_mg1_motion_o, &banim_shaf_mg1_oam_r_bin, &banim_shaf_mg1_oam_l_bin, &banim_shaf_mg1_agbpal}, // 0x75
	{"drum_mg1", &banim_drum_mg1_modes_bin, &banim_drum_mg1_motion_o, &banim_drum_mg1_oam_r_bin, &banim_drum_mg1_oam_l_bin, &banim_drum_mg1_agbpal}, // 0x76
	{"drum_mg1", &banim_drum_mg1_2_modes_bin, &banim_drum_mg1_2_motion_o, &banim_drum_mg1_2_oam_r_bin, &banim_drum_mg1_2_oam_l_bin, &banim_drum_mg1_2_agbpal}, // 0x77
	{"druf_mg1", &banim_druf_mg1_modes_bin, &banim_druf_mg1_motion_o, &banim_druf_mg1_oam_r_bin, &banim_druf_mg1_oam_l_bin, &banim_druf_mg1_agbpal}, // 0x78
	{"druf_mg1", &banim_druf_mg1_2_modes_bin, &banim_druf_mg1_2_motion_o, &banim_druf_mg1_2_oam_r_bin, &banim_druf_mg1_2_oam_l_bin, &banim_druf_mg1_2_agbpal}, // 0x79
	{"smnm_ro1", &banim_smnm_ro1_modes_bin, &banim_smnm_ro1_motion_o, &banim_smnm_ro1_oam_r_bin, &banim_smnm_ro1_oam_l_bin, &banim_smnm_ro1_agbpal}, // 0x7A
	{"smnm_ro1", &banim_smnm_ro1_2_modes_bin, &banim_smnm_ro1_2_motion_o, &banim_smnm_ro1_2_oam_r_bin, &banim_smnm_ro1_2_oam_l_bin, &banim_smnm_ro1_2_agbpal}, // 0x7B
	{"monm_mg1", &banim_monm_mg1_modes_bin, &banim_monm_mg1_motion_o, &banim_monm_mg1_oam_r_bin, &banim_monm_mg1_oam_l_bin, &banim_monm_mg1_agbpal}, // 0x7C
	{"prim_ro1", &banim_prim_ro1_modes_bin, &banim_prim_ro1_motion_o, &banim_prim_ro1_oam_r_bin, &banim_prim_ro1_oam_l_bin, &banim_prim_ro1_agbpal}, // 0x7D
	{"prim_ro1", &banim_prim_ro1_2_modes_bin, &banim_prim_ro1_2_motion_o, &banim_prim_ro1_2_oam_r_bin, &banim_prim_ro1_2_oam_l_bin, &banim_prim_ro1_2_agbpal}, // 0x7E
	{"prif_ro1", &banim_prif_ro1_modes_bin, &banim_prif_ro1_motion_o, &banim_prif_ro1_oam_r_bin, &banim_prif_ro1_oam_l_bin, &banim_prif_ro1_agbpal}, // 0x7F
	{"bism_mg1", &banim_bism_mg1_modes_bin, &banim_bism_mg1_motion_o, &banim_bism_mg1_oam_r_bin, &banim_bism_mg1_oam_l_bin, &banim_bism_mg1_agbpal}, // 0x80
	{"bism_mg1", &banim_bism_mg1_2_modes_bin, &banim_bism_mg1_2_motion_o, &banim_bism_mg1_2_oam_r_bin, &banim_bism_mg1_2_oam_l_bin, &banim_bism_mg1_2_agbpal}, // 0x81
	{"bisf_mg1", &banim_bisf_mg1_modes_bin, &banim_bisf_mg1_motion_o, &banim_bisf_mg1_oam_r_bin, &banim_bisf_mg1_oam_l_bin, &banim_bisf_mg1_agbpal}, // 0x82
	{"bisf_mg1", &banim_bisf_mg1_2_modes_bin, &banim_bisf_mg1_2_motion_o, &banim_bisf_mg1_2_oam_r_bin, &banim_bisf_mg1_2_oam_l_bin, &banim_bisf_mg1_2_agbpal}, // 0x83
	{"trof_ro1", &banim_trof_ro1_modes_bin, &banim_trof_ro1_motion_o, &banim_trof_ro1_oam_r_bin, &banim_trof_ro1_oam_l_bin, &banim_trof_ro1_agbpal}, // 0x84
	{"trof_ro1", &banim_trof_ro1_2_modes_bin, &banim_trof_ro1_2_motion_o, &banim_trof_ro1_2_oam_r_bin, &banim_trof_ro1_2_oam_l_bin, &banim_trof_ro1_2_agbpal}, // 0x85
	{"valf_mg1", &banim_valf_mg1_modes_bin, &banim_valf_mg1_motion_o, &banim_valf_mg1_oam_r_bin, &banim_valf_mg1_oam_l_bin, &banim_valf_mg1_agbpal}, // 0x86
	{"valf_mg1", &banim_valf_mg1_2_modes_bin, &banim_valf_mg1_2_motion_o, &banim_valf_mg1_2_oam_r_bin, &banim_valf_mg1_2_oam_l_bin, &banim_valf_mg1_2_agbpal}, // 0x87
	{"thim_sw1", &banim_thim_sw1_modes_bin, &banim_thim_sw1_motion_o, &banim_thim_sw1_oam_r_bin, &banim_thim_sw1_oam_l_bin, &banim_thim_sw1_agbpal}, // 0x88
	{"thim_sw1", &banim_thim_sw1_2_modes_bin, &banim_thim_sw1_2_motion_o, &banim_thim_sw1_2_oam_r_bin, &banim_thim_sw1_2_oam_l_bin, &banim_thim_sw1_2_agbpal}, // 0x89
	{"asnm_sw1", &banim_asnm_sw1_modes_bin, &banim_asnm_sw1_motion_o, &banim_asnm_sw1_oam_r_bin, &banim_asnm_sw1_oam_l_bin, &banim_asnm_sw1_agbpal}, // 0x8A
	{"asnm_sw1", &banim_asnm_sw1_2_modes_bin, &banim_asnm_sw1_2_motion_o, &banim_asnm_sw1_2_oam_r_bin, &banim_asnm_sw1_2_oam_l_bin, &banim_asnm_sw1_2_agbpal}, // 0x8B
	{"asnm_sw1", &banim_asnm_sw1_3_modes_bin, &banim_asnm_sw1_3_motion_o, &banim_asnm_sw1_3_oam_r_bin, &banim_asnm_sw1_3_oam_l_bin, &banim_asnm_sw1_3_agbpal}, // 0x8C
	{"asnm_sw1", &banim_asnm_sw1_4_modes_bin, &banim_asnm_sw1_4_motion_o, &banim_asnm_sw1_4_oam_r_bin, &banim_asnm_sw1_4_oam_l_bin, &banim_asnm_sw1_4_agbpal}, // 0x8D
	{"rogm_sw1", &banim_rogm_sw1_modes_bin, &banim_rogm_sw1_motion_o, &banim_rogm_sw1_oam_r_bin, &banim_rogm_sw1_oam_l_bin, &banim_rogm_sw1_agbpal}, // 0x8E
	{"rogm_sw1", &banim_rogm_sw1_2_modes_bin, &banim_rogm_sw1_2_motion_o, &banim_rogm_sw1_2_oam_r_bin, &banim_rogm_sw1_2_oam_l_bin, &banim_rogm_sw1_2_agbpal}, // 0x8F
	{"danf_da1", &banim_danf_da1_modes_bin, &banim_danf_da1_motion_o, &banim_danf_da1_oam_r_bin, &banim_danf_da1_oam_l_bin, &banim_danf_da1_agbpal}, // 0x90
	{"pbfm_ax1", &banim_pbfm_ax1_modes_bin, &banim_pbfm_ax1_motion_o, &banim_pbfm_ax1_oam_r_bin, &banim_pbfm_ax1_oam_l_bin, &banim_pbfm_ax1_agbpal}, // 0x91
	{"pbfm_ax1", &banim_pbfm_ax1_2_modes_bin, &banim_pbfm_ax1_2_motion_o, &banim_pbfm_ax1_2_oam_r_bin, &banim_pbfm_ax1_2_oam_l_bin, &banim_pbfm_ax1_2_agbpal}, // 0x92
	{"pbfm_ax1", &banim_pbfm_ax1_3_modes_bin, &banim_pbfm_ax1_3_motion_o, &banim_pbfm_ax1_3_oam_r_bin, &banim_pbfm_ax1_3_oam_l_bin, &banim_pbfm_ax1_3_agbpal}, // 0x93
	{"pbmm_mg1", &banim_pbmm_mg1_modes_bin, &banim_pbmm_mg1_motion_o, &banim_pbmm_mg1_oam_r_bin, &banim_pbmm_mg1_oam_l_bin, &banim_pbmm_mg1_agbpal}, // 0x94
	{"pbrf_sp1", &banim_pbrf_sp1_modes_bin, &banim_pbrf_sp1_motion_o, &banim_pbrf_sp1_oam_r_bin, &banim_pbrf_sp1_oam_l_bin, &banim_pbrf_sp1_agbpal}, // 0x95
	{"pbrf_sp1", &banim_pbrf_sp1_2_modes_bin, &banim_pbrf_sp1_2_motion_o, &banim_pbrf_sp1_2_oam_r_bin, &banim_pbrf_sp1_2_oam_l_bin, &banim_pbrf_sp1_2_agbpal}, // 0x96
	{"solm_sp1", &banim_solm_sp1_modes_bin, &banim_solm_sp1_motion_o, &banim_solm_sp1_oam_r_bin, &banim_solm_sp1_oam_l_bin, &banim_solm_sp1_agbpal}, // 0x97
	{"solm_sp1", &banim_solm_sp1_2_modes_bin, &banim_solm_sp1_2_motion_o, &banim_solm_sp1_2_oam_r_bin, &banim_solm_sp1_2_oam_l_bin, &banim_solm_sp1_2_agbpal}, // 0x98
	{"pirm_ax1", &banim_pirm_ax1_modes_bin, &banim_pirm_ax1_motion_o, &banim_pirm_ax1_oam_r_bin, &banim_pirm_ax1_oam_l_bin, &banim_pirm_ax1_agbpal}, // 0x99
	{"pirm_ax1", &banim_pirm_ax1_2_modes_bin, &banim_pirm_ax1_2_motion_o, &banim_pirm_ax1_2_oam_r_bin, &banim_pirm_ax1_2_oam_l_bin, &banim_pirm_ax1_2_agbpal}, // 0x9A
	{"pirm_ax1", &banim_pirm_ax1_3_modes_bin, &banim_pirm_ax1_3_motion_o, &banim_pirm_ax1_3_oam_r_bin, &banim_pirm_ax1_3_oam_l_bin, &banim_pirm_ax1_3_agbpal}, // 0x9B
	{"necm_mg1", &banim_necm_mg1_modes_bin, &banim_necm_mg1_motion_o, &banim_necm_mg1_oam_r_bin, &banim_necm_mg1_oam_l_bin, &banim_necm_mg1_agbpal}, // 0x9C
	{"necm_ro1", &banim_necm_ro1_modes_bin, &banim_necm_ro1_motion_o, &banim_necm_ro1_oam_r_bin, &banim_necm_ro1_oam_l_bin, &banim_necm_ro1_agbpal}, // 0x9D
	{"stam_ar1", &banim_stam_ar1_modes_bin, &banim_stam_ar1_motion_o, &banim_stam_ar1_oam_r_bin, &banim_stam_ar1_oam_l_bin, &banim_stam_ar1_agbpal}, // 0x9E
	{"zom_at1", &banim_zom_at1_modes_bin, &banim_zom_at1_motion_o, &banim_zom_at1_oam_r_bin, &banim_zom_at1_oam_l_bin, &banim_zom_at1_agbpal}, // 0x9F
	{"zom_at1", &banim_zom_at1_2_modes_bin, &banim_zom_at1_2_motion_o, &banim_zom_at1_2_oam_r_bin, &banim_zom_at1_2_oam_l_bin, &banim_zom_at1_2_agbpal}, // 0xA0
	{"sks_sw1", &banim_sks_sw1_modes_bin, &banim_sks_sw1_motion_o, &banim_sks_sw1_oam_r_bin, &banim_sks_sw1_oam_l_bin, &banim_sks_sw1_agbpal}, // 0xA1
	{"sks_sp1", &banim_sks_sp1_modes_bin, &banim_sks_sp1_motion_o, &banim_sks_sp1_oam_r_bin, &banim_sks_sp1_oam_l_bin, &banim_sks_sp1_agbpal}, // 0xA2
	{"sks_sw1", &banim_sks_sw1_2_modes_bin, &banim_sks_sw1_2_motion_o, &banim_sks_sw1_2_oam_r_bin, &banim_sks_sw1_2_oam_l_bin, &banim_sks_sw1_2_agbpal}, // 0xA3
	{"ska_ar1", &banim_ska_ar1_modes_bin, &banim_ska_ar1_motion_o, &banim_ska_ar1_oam_r_bin, &banim_ska_ar1_oam_l_bin, &banim_ska_ar1_agbpal}, // 0xA4
	{"sks_sw1", &banim_sks_sw1_3_modes_bin, &banim_sks_sw1_3_motion_o, &banim_sks_sw1_3_oam_r_bin, &banim_sks_sw1_3_oam_l_bin, &banim_sks_sw1_3_agbpal}, // 0xA5
	{"sks_sw1", &banim_sks_sw1_4_modes_bin, &banim_sks_sw1_4_motion_o, &banim_sks_sw1_4_oam_r_bin, &banim_sks_sw1_4_oam_l_bin, &banim_sks_sw1_4_agbpal}, // 0xA6
	{"sks_sp1", &banim_sks_sp1_2_modes_bin, &banim_sks_sp1_2_motion_o, &banim_sks_sp1_2_oam_r_bin, &banim_sks_sp1_2_oam_l_bin, &banim_sks_sp1_2_agbpal}, // 0xA7
	{"sks_sw1", &banim_sks_sw1_5_modes_bin, &banim_sks_sw1_5_motion_o, &banim_sks_sw1_5_oam_r_bin, &banim_sks_sw1_5_oam_l_bin, &banim_sks_sw1_5_agbpal}, // 0xA8
	{"ska_ar1", &banim_ska_ar1_2_modes_bin, &banim_ska_ar1_2_motion_o, &banim_ska_ar1_2_oam_r_bin, &banim_ska_ar1_2_oam_l_bin, &banim_ska_ar1_2_agbpal}, // 0xA9
	{"sks_sw1", &banim_sks_sw1_6_modes_bin, &banim_sks_sw1_6_motion_o, &banim_sks_sw1_6_oam_r_bin, &banim_sks_sw1_6_oam_l_bin, &banim_sks_sw1_6_agbpal}, // 0xAA
	{"bae_at1", &banim_bae_at1_modes_bin, &banim_bae_at1_motion_o, &banim_bae_at1_oam_r_bin, &banim_bae_at1_oam_l_bin, &banim_bae_at1_agbpal}, // 0xAB
	{"bae_at1", &banim_bae_at1_2_modes_bin, &banim_bae_at1_2_motion_o, &banim_bae_at1_2_oam_r_bin, &banim_bae_at1_2_oam_l_bin, &banim_bae_at1_2_agbpal}, // 0xAC
	{"cyc_ax1", &banim_cyc_ax1_modes_bin, &banim_cyc_ax1_motion_o, &banim_cyc_ax1_oam_r_bin, &banim_cyc_ax1_oam_l_bin, &banim_cyc_ax1_agbpal}, // 0xAD
	{"cyc_ax1", &banim_cyc_ax1_2_modes_bin, &banim_cyc_ax1_2_motion_o, &banim_cyc_ax1_2_oam_r_bin, &banim_cyc_ax1_2_oam_l_bin, &banim_cyc_ax1_2_agbpal}, // 0xAE
	{"cyc_ax1", &banim_cyc_ax1_3_modes_bin, &banim_cyc_ax1_3_motion_o, &banim_cyc_ax1_3_oam_r_bin, &banim_cyc_ax1_3_oam_l_bin, &banim_cyc_ax1_3_agbpal}, // 0xAF
	{"mdg_at1", &banim_mdg_at1_modes_bin, &banim_mdg_at1_motion_o, &banim_mdg_at1_oam_r_bin, &banim_mdg_at1_oam_l_bin, &banim_mdg_at1_agbpal}, // 0xB0
	{"cer_at1", &banim_cer_at1_modes_bin, &banim_cer_at1_motion_o, &banim_cer_at1_oam_r_bin, &banim_cer_at1_oam_l_bin, &banim_cer_at1_agbpal}, // 0xB1
	{"mcd_ax1", &banim_mcd_ax1_modes_bin, &banim_mcd_ax1_motion_o, &banim_mcd_ax1_oam_r_bin, &banim_mcd_ax1_oam_l_bin, &banim_mcd_ax1_agbpal}, // 0xB2
	{"mcd_ax1", &banim_mcd_ax1_2_modes_bin, &banim_mcd_ax1_2_motion_o, &banim_mcd_ax1_2_oam_r_bin, &banim_mcd_ax1_2_oam_l_bin, &banim_mcd_ax1_2_agbpal}, // 0xB3
	{"mcd_ax1", &banim_mcd_ax1_3_modes_bin, &banim_mcd_ax1_3_motion_o, &banim_mcd_ax1_3_oam_r_bin, &banim_mcd_ax1_3_oam_l_bin, &banim_mcd_ax1_3_agbpal}, // 0xB4
	{"mcd_ax1", &banim_mcd_ax1_4_modes_bin, &banim_mcd_ax1_4_motion_o, &banim_mcd_ax1_4_oam_r_bin, &banim_mcd_ax1_4_oam_l_bin, &banim_mcd_ax1_4_agbpal}, // 0xB5
	{"mcd_ax1", &banim_mcd_ax1_5_modes_bin, &banim_mcd_ax1_5_motion_o, &banim_mcd_ax1_5_oam_r_bin, &banim_mcd_ax1_5_oam_l_bin, &banim_mcd_ax1_5_agbpal}, // 0xB6
	{"mcd_ar1", &banim_mcd_ar1_modes_bin, &banim_mcd_ar1_motion_o, &banim_mcd_ar1_oam_r_bin, &banim_mcd_ar1_oam_l_bin, &banim_mcd_ar1_agbpal}, // 0xB7
	{"mcd_ax1", &banim_mcd_ax1_6_modes_bin, &banim_mcd_ax1_6_motion_o, &banim_mcd_ax1_6_oam_r_bin, &banim_mcd_ax1_6_oam_l_bin, &banim_mcd_ax1_6_agbpal}, // 0xB8
	{"bgl_mg1", &banim_bgl_mg1_modes_bin, &banim_bgl_mg1_motion_o, &banim_bgl_mg1_oam_r_bin, &banim_bgl_mg1_oam_l_bin, &banim_bgl_mg1_agbpal}, // 0xB9
	{"bgl_mg1", &banim_bgl_mg1_2_modes_bin, &banim_bgl_mg1_2_motion_o, &banim_bgl_mg1_2_oam_r_bin, &banim_bgl_mg1_2_oam_l_bin, &banim_bgl_mg1_2_agbpal}, // 0xBA
	{"gog_mg1", &banim_gog_mg1_modes_bin, &banim_gog_mg1_motion_o, &banim_gog_mg1_oam_r_bin, &banim_gog_mg1_oam_l_bin, &banim_gog_mg1_agbpal}, // 0xBB
	{"gar_sp1", &banim_gar_sp1_modes_bin, &banim_gar_sp1_motion_o, &banim_gar_sp1_oam_r_bin, &banim_gar_sp1_oam_l_bin, &banim_gar_sp1_agbpal}, // 0xBC
	{"gar_sp1", &banim_gar_sp1_2_modes_bin, &banim_gar_sp1_2_motion_o, &banim_gar_sp1_2_oam_r_bin, &banim_gar_sp1_2_oam_l_bin, &banim_gar_sp1_2_agbpal}, // 0xBD
	{"gar_sp1", &banim_gar_sp1_3_modes_bin, &banim_gar_sp1_3_motion_o, &banim_gar_sp1_3_oam_r_bin, &banim_gar_sp1_3_oam_l_bin, &banim_gar_sp1_3_agbpal}, // 0xBE
	{"gar_sp1", &banim_gar_sp1_4_modes_bin, &banim_gar_sp1_4_motion_o, &banim_gar_sp1_4_oam_r_bin, &banim_gar_sp1_4_oam_l_bin, &banim_gar_sp1_4_agbpal}, // 0xBF
	{"drz_mg1", &banim_drz_mg1_modes_bin, &banim_drz_mg1_motion_o, &banim_drz_mg1_oam_r_bin, &banim_drz_mg1_oam_l_bin, &banim_drz_mg1_agbpal}, // 0xC0
	{"bos_at1", &banim_bos_at1_modes_bin, &banim_bos_at1_motion_o, &banim_bos_at1_oam_r_bin, &banim_bos_at1_oam_l_bin, &banim_bos_at1_agbpal}, // 0xC1
	{"bos_at1", &banim_bos_at1_2_modes_bin, &banim_bos_at1_2_motion_o, &banim_bos_at1_2_oam_r_bin, &banim_bos_at1_2_oam_l_bin, &banim_bos_at1_2_agbpal}, // 0xC2
	{"fifd_mg1", &banim_fifd_mg1_modes_bin, &banim_fifd_mg1_motion_o, &banim_fifd_mg1_oam_r_bin, &banim_fifd_mg1_oam_l_bin, &banim_fifd_mg1_agbpal}, // 0xC3
	{"fifd_he1", &banim_fifd_he1_modes_bin, &banim_fifd_he1_motion_o, &banim_fifd_he1_oam_r_bin, &banim_fifd_he1_oam_l_bin, &banim_fifd_he1_agbpal}, // 0xC4
	{"fifd_hk1", &banim_fifd_hk1_modes_bin, &banim_fifd_hk1_motion_o, &banim_fifd_hk1_oam_r_bin, &banim_fifd_hk1_oam_l_bin, &banim_fifd_hk1_agbpal}, // 0xC5
	{"mf_mi1", &banim_mf_mi1_modes_bin, &banim_mf_mi1_motion_o, &banim_mf_mi1_oam_r_bin, &banim_mf_mi1_oam_l_bin, &banim_mf_mi1_agbpal}, // 0xC6
	{"prif_ro1", &banim_prif_ro1_2_modes_bin, &banim_prif_ro1_2_motion_o, &banim_prif_ro1_2_oam_r_bin, &banim_prif_ro1_2_oam_l_bin, &banim_prif_ro1_2_agbpal}, // 0xC7
	{"fifd_mg1", &banim_fifd_mg1_2_modes_bin, &banim_fifd_mg1_2_motion_o, &banim_fifd_mg1_2_oam_r_bin, &banim_fifd_mg1_2_oam_l_bin, &banim_fifd_mg1_2_agbpal}, // 0xC8
	// FE8_NEW_ANIMS custom battle animations (FE-Repo packs, see CREDITS.md).
	// Compiled from the checked-in source at banim/src/ by tools/aaa/AAA.py
	// and generated by scripts/banim_event_to_source.py -- do not edit by hand.
    {"newsldsw1", &banim_newsoldier_sword_modes_bin, &banim_newsoldier_sword_script_o, &banim_newsoldier_sword_oam_bin, &banim_newsoldier_sword_oam_bin, &banim_newsoldier_sword_agbpal}, // 0xC9 soldier sword
    {"newsldln1", &banim_newsoldier_lance_modes_bin, &banim_newsoldier_lance_script_o, &banim_newsoldier_lance_oam_bin, &banim_newsoldier_lance_oam_bin, &banim_newsoldier_lance_agbpal}, // 0xCA soldier lance
    {"newsldun1", &banim_newsoldier_unarmed_modes_bin, &banim_newsoldier_unarmed_script_o, &banim_newsoldier_unarmed_oam_bin, &banim_newsoldier_unarmed_oam_bin, &banim_newsoldier_unarmed_agbpal}, // 0xCB soldier unarmed
    {"newbrgax1", &banim_newbrigand_axe_modes_bin, &banim_newbrigand_axe_script_o, &banim_newbrigand_axe_oam_bin, &banim_newbrigand_axe_oam_bin, &banim_newbrigand_axe_agbpal}, // 0xCC brigand axe
    {"newbrghx1", &banim_newbrigand_handaxe_modes_bin, &banim_newbrigand_handaxe_script_o, &banim_newbrigand_handaxe_oam_bin, &banim_newbrigand_handaxe_oam_bin, &banim_newbrigand_handaxe_agbpal}, // 0xCD brigand handaxe
    {"newbrgun1", &banim_newbrigand_unarmed_modes_bin, &banim_newbrigand_unarmed_script_o, &banim_newbrigand_unarmed_oam_bin, &banim_newbrigand_unarmed_oam_bin, &banim_newbrigand_unarmed_agbpal}, // 0xCE brigand unarmed
    {"newfigax1", &banim_newfighter_axe_modes_bin, &banim_newfighter_axe_script_o, &banim_newfighter_axe_oam_bin, &banim_newfighter_axe_oam_bin, &banim_newfighter_axe_agbpal}, // 0xCF fighter axe
    {"newfighx1", &banim_newfighter_handaxe_modes_bin, &banim_newfighter_handaxe_script_o, &banim_newfighter_handaxe_oam_bin, &banim_newfighter_handaxe_oam_bin, &banim_newfighter_handaxe_agbpal}, // 0xD0 fighter handaxe
    {"newfigun1", &banim_newfighter_unarmed_modes_bin, &banim_newfighter_unarmed_script_o, &banim_newfighter_unarmed_oam_bin, &banim_newfighter_unarmed_oam_bin, &banim_newfighter_unarmed_agbpal}, // 0xD1 fighter unarmed
    {"newkntsw1", &banim_newknight_sword_modes_bin, &banim_newknight_sword_script_o, &banim_newknight_sword_oam_bin, &banim_newknight_sword_oam_bin, &banim_newknight_sword_agbpal}, // 0xD2 knight sword
    {"newkntln1", &banim_newknight_lance_modes_bin, &banim_newknight_lance_script_o, &banim_newknight_lance_oam_bin, &banim_newknight_lance_oam_bin, &banim_newknight_lance_agbpal}, // 0xD3 knight lance
    {"newkntax1", &banim_newknight_axe_modes_bin, &banim_newknight_axe_script_o, &banim_newknight_axe_oam_bin, &banim_newknight_axe_oam_bin, &banim_newknight_axe_agbpal}, // 0xD4 knight axe
    {"newknthx1", &banim_newknight_handaxe_modes_bin, &banim_newknight_handaxe_script_o, &banim_newknight_handaxe_oam_bin, &banim_newknight_handaxe_oam_bin, &banim_newknight_handaxe_agbpal}, // 0xD5 knight handaxe
    {"newkntbw1", &banim_newknight_bow_modes_bin, &banim_newknight_bow_script_o, &banim_newknight_bow_oam_bin, &banim_newknight_bow_oam_bin, &banim_newknight_bow_agbpal}, // 0xD6 knight bow
    {"newkntun1", &banim_newknight_unarmed_modes_bin, &banim_newknight_unarmed_script_o, &banim_newknight_unarmed_oam_bin, &banim_newknight_unarmed_oam_bin, &banim_newknight_unarmed_agbpal}, // 0xD7 knight unarmed
    {"newmrcsw1", &banim_newmerc_sword_modes_bin, &banim_newmerc_sword_script_o, &banim_newmerc_sword_oam_bin, &banim_newmerc_sword_oam_bin, &banim_newmerc_sword_agbpal}, // 0xD8 merc sword
    {"newmrcun1", &banim_newmerc_unarmed_modes_bin, &banim_newmerc_unarmed_script_o, &banim_newmerc_unarmed_oam_bin, &banim_newmerc_unarmed_oam_bin, &banim_newmerc_unarmed_agbpal}, // 0xD9 merc unarmed
    {"newarcbw1", &banim_newarcher_bow_modes_bin, &banim_newarcher_bow_script_o, &banim_newarcher_bow_oam_bin, &banim_newarcher_bow_oam_bin, &banim_newarcher_bow_agbpal}, // 0xDA archer bow
    {"newarcun1", &banim_newarcher_unarmed_modes_bin, &banim_newarcher_unarmed_script_o, &banim_newarcher_unarmed_oam_bin, &banim_newarcher_unarmed_oam_bin, &banim_newarcher_unarmed_agbpal}, // 0xDB archer unarmed
    {"newcavsw1", &banim_newcavalier_sword_modes_bin, &banim_newcavalier_sword_script_o, &banim_newcavalier_sword_oam_bin, &banim_newcavalier_sword_oam_bin, &banim_newcavalier_sword_agbpal}, // 0xDC cavalier sword
    {"newcavln1", &banim_newcavalier_lance_modes_bin, &banim_newcavalier_lance_script_o, &banim_newcavalier_lance_oam_bin, &banim_newcavalier_lance_oam_bin, &banim_newcavalier_lance_agbpal}, // 0xDD cavalier lance
    {"newcavax1", &banim_newcavalier_axe_modes_bin, &banim_newcavalier_axe_script_o, &banim_newcavalier_axe_oam_bin, &banim_newcavalier_axe_oam_bin, &banim_newcavalier_axe_agbpal}, // 0xDE cavalier axe
    {"newcavhx1", &banim_newcavalier_handaxe_modes_bin, &banim_newcavalier_handaxe_script_o, &banim_newcavalier_handaxe_oam_bin, &banim_newcavalier_handaxe_oam_bin, &banim_newcavalier_handaxe_agbpal}, // 0xDF cavalier handaxe
    {"newcavbw1", &banim_newcavalier_bow_modes_bin, &banim_newcavalier_bow_script_o, &banim_newcavalier_bow_oam_bin, &banim_newcavalier_bow_oam_bin, &banim_newcavalier_bow_agbpal}, // 0xE0 cavalier bow
    {"newcavun1", &banim_newcavalier_unarmed_modes_bin, &banim_newcavalier_unarmed_script_o, &banim_newcavalier_unarmed_oam_bin, &banim_newcavalier_unarmed_oam_bin, &banim_newcavalier_unarmed_agbpal}, // 0xE1 cavalier unarmed
    {"newpegsw1", &banim_newpegasus_sword_modes_bin, &banim_newpegasus_sword_script_o, &banim_newpegasus_sword_oam_bin, &banim_newpegasus_sword_oam_bin, &banim_newpegasus_sword_agbpal}, // 0xE2 pegasus sword
    {"newpegln1", &banim_newpegasus_lance_modes_bin, &banim_newpegasus_lance_script_o, &banim_newpegasus_lance_oam_bin, &banim_newpegasus_lance_oam_bin, &banim_newpegasus_lance_agbpal}, // 0xE3 pegasus lance
    {"newpegax1", &banim_newpegasus_axe_modes_bin, &banim_newpegasus_axe_script_o, &banim_newpegasus_axe_oam_bin, &banim_newpegasus_axe_oam_bin, &banim_newpegasus_axe_agbpal}, // 0xE4 pegasus axe
    {"newpeghx1", &banim_newpegasus_handaxe_modes_bin, &banim_newpegasus_handaxe_script_o, &banim_newpegasus_handaxe_oam_bin, &banim_newpegasus_handaxe_oam_bin, &banim_newpegasus_handaxe_agbpal}, // 0xE5 pegasus handaxe
    {"newpegmg1", &banim_newpegasus_magic_modes_bin, &banim_newpegasus_magic_script_o, &banim_newpegasus_magic_oam_bin, &banim_newpegasus_magic_oam_bin, &banim_newpegasus_magic_agbpal}, // 0xE6 pegasus magic
    {"newpegun1", &banim_newpegasus_unarmed_modes_bin, &banim_newpegasus_unarmed_script_o, &banim_newpegasus_unarmed_oam_bin, &banim_newpegasus_unarmed_oam_bin, &banim_newpegasus_unarmed_agbpal}, // 0xE7 pegasus unarmed
    {"newdambw1", &banim_newderarcm_bow_modes_bin, &banim_newderarcm_bow_script_o, &banim_newderarcm_bow_oam_bin, &banim_newderarcm_bow_oam_bin, &banim_newderarcm_bow_agbpal}, // 0xE8 derarcm bow
    {"newdamun1", &banim_newderarcm_unarmed_modes_bin, &banim_newderarcm_unarmed_script_o, &banim_newderarcm_unarmed_oam_bin, &banim_newderarcm_unarmed_oam_bin, &banim_newderarcm_unarmed_agbpal}, // 0xE9 derarcm unarmed
    {"newdafbw1", &banim_newderarcf_bow_modes_bin, &banim_newderarcf_bow_script_o, &banim_newderarcf_bow_oam_bin, &banim_newderarcf_bow_oam_bin, &banim_newderarcf_bow_agbpal}, // 0xEA derarcf bow
    {"newdafun1", &banim_newderarcf_unarmed_modes_bin, &banim_newderarcf_unarmed_script_o, &banim_newderarcf_unarmed_oam_bin, &banim_newderarcf_unarmed_oam_bin, &banim_newderarcf_unarmed_agbpal}, // 0xEB derarcf unarmed
    {"newgmfmg1", &banim_newgaidenmage_framefix_magic_modes_bin, &banim_newgaidenmage_framefix_magic_script_o, &banim_newgaidenmage_framefix_magic_oam_bin, &banim_newgaidenmage_framefix_magic_oam_bin, &banim_newgaidenmage_framefix_magic_agbpal}, // 0xEC gaidenmage_framefix magic
    {"newgmpmg1", &banim_newgaidenmage_ponytail_magic_modes_bin, &banim_newgaidenmage_ponytail_magic_script_o, &banim_newgaidenmage_ponytail_magic_oam_bin, &banim_newgaidenmage_ponytail_magic_oam_bin, &banim_newgaidenmage_ponytail_magic_agbpal}, // 0xED gaidenmage_ponytail magic
    {"newlynsw1", &banim_newlynlord_sword_modes_bin, &banim_newlynlord_sword_script_o, &banim_newlynlord_sword_oam_bin, &banim_newlynlord_sword_oam_bin, &banim_newlynlord_sword_agbpal}, // 0xEE lynlord sword
    {"newnombw1", &banim_newnomadm_bow_modes_bin, &banim_newnomadm_bow_script_o, &banim_newnomadm_bow_oam_bin, &banim_newnomadm_bow_oam_bin, &banim_newnomadm_bow_agbpal}, // 0xEF nomadm bow
    {"newnomun1", &banim_newnomadm_unarmed_modes_bin, &banim_newnomadm_unarmed_script_o, &banim_newnomadm_unarmed_oam_bin, &banim_newnomadm_unarmed_oam_bin, &banim_newnomadm_unarmed_agbpal}, // 0xF0 nomadm unarmed
    {"newnofbw1", &banim_newnomadf_bow_modes_bin, &banim_newnomadf_bow_script_o, &banim_newnomadf_bow_oam_bin, &banim_newnomadf_bow_oam_bin, &banim_newnomadf_bow_agbpal}, // 0xF1 nomadf bow
    {"newnofun1", &banim_newnomadf_unarmed_modes_bin, &banim_newnomadf_unarmed_script_o, &banim_newnomadf_unarmed_oam_bin, &banim_newnomadf_unarmed_oam_bin, &banim_newnomadf_unarmed_agbpal}, // 0xF2 nomadf unarmed
    {"newntmsw1", &banim_newnomtrpm_sword_modes_bin, &banim_newnomtrpm_sword_script_o, &banim_newnomtrpm_sword_oam_bin, &banim_newnomtrpm_sword_oam_bin, &banim_newnomtrpm_sword_agbpal}, // 0xF3 nomtrpm sword
    {"newntmbw1", &banim_newnomtrpm_bow_modes_bin, &banim_newnomtrpm_bow_script_o, &banim_newnomtrpm_bow_oam_bin, &banim_newnomtrpm_bow_oam_bin, &banim_newnomtrpm_bow_agbpal}, // 0xF4 nomtrpm bow
    {"newntmun1", &banim_newnomtrpm_unarmed_modes_bin, &banim_newnomtrpm_unarmed_script_o, &banim_newnomtrpm_unarmed_oam_bin, &banim_newnomtrpm_unarmed_oam_bin, &banim_newnomtrpm_unarmed_agbpal}, // 0xF5 nomtrpm unarmed
    {"newntfsw1", &banim_newnomtrpf_sword_modes_bin, &banim_newnomtrpf_sword_script_o, &banim_newnomtrpf_sword_oam_bin, &banim_newnomtrpf_sword_oam_bin, &banim_newnomtrpf_sword_agbpal}, // 0xF6 nomtrpf sword
    {"newntfbw1", &banim_newnomtrpf_bow_modes_bin, &banim_newnomtrpf_bow_script_o, &banim_newnomtrpf_bow_oam_bin, &banim_newnomtrpf_bow_oam_bin, &banim_newnomtrpf_bow_agbpal}, // 0xF7 nomtrpf bow
    {"newntfun1", &banim_newnomtrpf_unarmed_modes_bin, &banim_newnomtrpf_unarmed_script_o, &banim_newnomtrpf_unarmed_oam_bin, &banim_newnomtrpf_unarmed_oam_bin, &banim_newnomtrpf_unarmed_agbpal}, // 0xF8 nomtrpf unarmed
    {"newswbfsw1", &banim_newswbf_sword_modes_bin, &banim_newswbf_sword_script_o, &banim_newswbf_sword_oam_bin, &banim_newswbf_sword_oam_bin, &banim_newswbf_sword_agbpal}, // 0xF9 swbf sword
    {"newswbfax1", &banim_newswbf_axe_modes_bin, &banim_newswbf_axe_script_o, &banim_newswbf_axe_oam_bin, &banim_newswbf_axe_oam_bin, &banim_newswbf_axe_agbpal}, // 0xFA swbf axe
    {"newswbfhx1", &banim_newswbf_handaxe_modes_bin, &banim_newswbf_handaxe_script_o, &banim_newswbf_handaxe_oam_bin, &banim_newswbf_handaxe_oam_bin, &banim_newswbf_handaxe_agbpal}, // 0xFB swbf handaxe
    {"newswbfst1", &banim_newswbf_staff_modes_bin, &banim_newswbf_staff_script_o, &banim_newswbf_staff_oam_bin, &banim_newswbf_staff_oam_bin, &banim_newswbf_staff_agbpal}, // 0xFC swbf staff
    {"newswbfmg1", &banim_newswbf_magic_modes_bin, &banim_newswbf_magic_script_o, &banim_newswbf_magic_oam_bin, &banim_newswbf_magic_oam_bin, &banim_newswbf_magic_agbpal}, // 0xFD swbf magic
    {"newswbmsw1", &banim_newswbm_sword_modes_bin, &banim_newswbm_sword_script_o, &banim_newswbm_sword_oam_bin, &banim_newswbm_sword_oam_bin, &banim_newswbm_sword_agbpal}, // 0xFE swbm sword
    {"newswbmax1", &banim_newswbm_axe_modes_bin, &banim_newswbm_axe_script_o, &banim_newswbm_axe_oam_bin, &banim_newswbm_axe_oam_bin, &banim_newswbm_axe_agbpal}, // 0xFF swbm axe
    {"newswbmhx1", &banim_newswbm_handaxe_modes_bin, &banim_newswbm_handaxe_script_o, &banim_newswbm_handaxe_oam_bin, &banim_newswbm_handaxe_oam_bin, &banim_newswbm_handaxe_agbpal}, // 0x100 swbm handaxe
    {"newswbmst1", &banim_newswbm_staff_modes_bin, &banim_newswbm_staff_script_o, &banim_newswbm_staff_oam_bin, &banim_newswbm_staff_oam_bin, &banim_newswbm_staff_agbpal}, // 0x101 swbm staff
    {"newswbmmg1", &banim_newswbm_magic_modes_bin, &banim_newswbm_magic_script_o, &banim_newswbm_magic_oam_bin, &banim_newswbm_magic_oam_bin, &banim_newswbm_magic_agbpal}, // 0x102 swbm magic
    {"newleobax1", &banim_newleob_axe_modes_bin, &banim_newleob_axe_script_o, &banim_newleob_axe_oam_bin, &banim_newleob_axe_oam_bin, &banim_newleob_axe_agbpal}, // 0x103 leob axe
    {"newleobhx1", &banim_newleob_handaxe_modes_bin, &banim_newleob_handaxe_script_o, &banim_newleob_handaxe_oam_bin, &banim_newleob_handaxe_oam_bin, &banim_newleob_handaxe_agbpal}, // 0x104 leob handaxe
    {"newleobun1", &banim_newleob_unarmed_modes_bin, &banim_newleob_unarmed_script_o, &banim_newleob_unarmed_oam_bin, &banim_newleob_unarmed_oam_bin, &banim_newleob_unarmed_agbpal}, // 0x105 leob unarmed
    {"newgmahln1", &banim_newgmah_lance_modes_bin, &banim_newgmah_lance_script_o, &banim_newgmah_lance_oam_bin, &banim_newgmah_lance_oam_bin, &banim_newgmah_lance_agbpal}, // 0x106 gmah lance
    {"newgmahbw1", &banim_newgmah_bow_modes_bin, &banim_newgmah_bow_script_o, &banim_newgmah_bow_oam_bin, &banim_newgmah_bow_oam_bin, &banim_newgmah_bow_agbpal}, // 0x107 gmah bow
    {"newgmahmo1", &banim_newgmah_monster_modes_bin, &banim_newgmah_monster_script_o, &banim_newgmah_monster_oam_bin, &banim_newgmah_monster_oam_bin, &banim_newgmah_monster_agbpal}, // 0x108 gmah monster
    {"newarcnst1", &banim_newarcn_staff_modes_bin, &banim_newarcn_staff_script_o, &banim_newarcn_staff_oam_bin, &banim_newarcn_staff_oam_bin, &banim_newarcn_staff_agbpal}, // 0x109 arcn staff
    {"newarcnmg1", &banim_newarcn_magic_modes_bin, &banim_newarcn_magic_script_o, &banim_newarcn_magic_oam_bin, &banim_newarcn_magic_oam_bin, &banim_newarcn_magic_agbpal}, // 0x10A arcn magic
    {"newhalbln1", &banim_newhalb_lance_modes_bin, &banim_newhalb_lance_script_o, &banim_newhalb_lance_oam_bin, &banim_newhalb_lance_oam_bin, &banim_newhalb_lance_agbpal}, // 0x10B halb lance
    {"newhalbax1", &banim_newhalb_axe_modes_bin, &banim_newhalb_axe_script_o, &banim_newhalb_axe_oam_bin, &banim_newhalb_axe_oam_bin, &banim_newhalb_axe_agbpal}, // 0x10C halb axe
    {"newhalbhx1", &banim_newhalb_handaxe_modes_bin, &banim_newhalb_handaxe_script_o, &banim_newhalb_handaxe_oam_bin, &banim_newhalb_handaxe_oam_bin, &banim_newhalb_handaxe_agbpal}, // 0x10D halb handaxe
    {"newhalbun1", &banim_newhalb_unarmed_modes_bin, &banim_newhalb_unarmed_script_o, &banim_newhalb_unarmed_oam_bin, &banim_newhalb_unarmed_oam_bin, &banim_newhalb_unarmed_agbpal}, // 0x10E halb unarmed
    {"newmikoln1", &banim_newmiko_lance_modes_bin, &banim_newmiko_lance_script_o, &banim_newmiko_lance_oam_bin, &banim_newmiko_lance_oam_bin, &banim_newmiko_lance_agbpal}, // 0x10F miko lance
    {"newmikobw1", &banim_newmiko_bow_modes_bin, &banim_newmiko_bow_script_o, &banim_newmiko_bow_oam_bin, &banim_newmiko_bow_oam_bin, &banim_newmiko_bow_agbpal}, // 0x110 miko bow
    {"newmikost1", &banim_newmiko_staff_modes_bin, &banim_newmiko_staff_script_o, &banim_newmiko_staff_oam_bin, &banim_newmiko_staff_oam_bin, &banim_newmiko_staff_agbpal}, // 0x111 miko staff
    {"newmikomg1", &banim_newmiko_magic_modes_bin, &banim_newmiko_magic_script_o, &banim_newmiko_magic_oam_bin, &banim_newmiko_magic_oam_bin, &banim_newmiko_magic_agbpal}, // 0x112 miko magic
    {"newmikoun1", &banim_newmiko_unarmed_modes_bin, &banim_newmiko_unarmed_script_o, &banim_newmiko_unarmed_oam_bin, &banim_newmiko_unarmed_oam_bin, &banim_newmiko_unarmed_agbpal}, // 0x113 miko unarmed
    {"newwclax1", &banim_newwcl_axe_modes_bin, &banim_newwcl_axe_script_o, &banim_newwcl_axe_oam_bin, &banim_newwcl_axe_oam_bin, &banim_newwcl_axe_agbpal}, // 0x114 wcl axe
    {"newwclhx1", &banim_newwcl_handaxe_modes_bin, &banim_newwcl_handaxe_script_o, &banim_newwcl_handaxe_oam_bin, &banim_newwcl_handaxe_oam_bin, &banim_newwcl_handaxe_agbpal}, // 0x115 wcl handaxe
    {"newwclmg1", &banim_newwcl_magic_modes_bin, &banim_newwcl_magic_script_o, &banim_newwcl_magic_oam_bin, &banim_newwcl_magic_oam_bin, &banim_newwcl_magic_agbpal}, // 0x116 wcl magic
    {"newwtchst1", &banim_newwtch_staff_modes_bin, &banim_newwtch_staff_script_o, &banim_newwtch_staff_oam_bin, &banim_newwtch_staff_oam_bin, &banim_newwtch_staff_agbpal}, // 0x117 wtch staff
    {"newwtchmg1", &banim_newwtch_magic_modes_bin, &banim_newwtch_magic_script_o, &banim_newwtch_magic_oam_bin, &banim_newwtch_magic_oam_bin, &banim_newwtch_magic_agbpal}, // 0x118 wtch magic
    {"newanglmg1", &banim_newangl_magic_modes_bin, &banim_newangl_magic_script_o, &banim_newangl_magic_oam_bin, &banim_newangl_magic_oam_bin, &banim_newangl_magic_agbpal}, // 0x119 angl magic
    {"newbrghax1", &banim_newbrgh_axe_modes_bin, &banim_newbrgh_axe_script_o, &banim_newbrgh_axe_oam_bin, &banim_newbrgh_axe_oam_bin, &banim_newbrgh_axe_agbpal}, // 0x11A brgh axe
    {"newbrghhx1", &banim_newbrgh_handaxe_modes_bin, &banim_newbrgh_handaxe_script_o, &banim_newbrgh_handaxe_oam_bin, &banim_newbrgh_handaxe_oam_bin, &banim_newbrgh_handaxe_agbpal}, // 0x11B brgh handaxe
    {"newbrghun1", &banim_newbrgh_unarmed_modes_bin, &banim_newbrgh_unarmed_script_o, &banim_newbrgh_unarmed_oam_bin, &banim_newbrgh_unarmed_oam_bin, &banim_newbrgh_unarmed_agbpal}, // 0x11C brgh unarmed
    {"newarcdmg1", &banim_newarcd_magic_modes_bin, &banim_newarcd_magic_script_o, &banim_newarcd_magic_oam_bin, &banim_newarcd_magic_oam_bin, &banim_newarcd_magic_agbpal}, // 0x11D arcd magic
    {"newmagcmg1", &banim_newmagc_magic_modes_bin, &banim_newmagc_magic_script_o, &banim_newmagc_magic_oam_bin, &banim_newmagc_magic_oam_bin, &banim_newmagc_magic_agbpal}, // 0x11E magc magic
    {"newmagcun1", &banim_newmagc_unarmed_modes_bin, &banim_newmagc_unarmed_script_o, &banim_newmagc_unarmed_oam_bin, &banim_newmagc_unarmed_oam_bin, &banim_newmagc_unarmed_agbpal}, // 0x11F magc unarmed
    {"newocltmg1", &banim_newoclt_magic_modes_bin, &banim_newoclt_magic_script_o, &banim_newoclt_magic_oam_bin, &banim_newoclt_magic_oam_bin, &banim_newoclt_magic_agbpal}, // 0x120 oclt magic
    {"newbldrsw1", &banim_newbldr_sword_modes_bin, &banim_newbldr_sword_script_o, &banim_newbldr_sword_oam_bin, &banim_newbldr_sword_oam_bin, &banim_newbldr_sword_agbpal}, // 0x121 bldr sword
    {"newbldrun1", &banim_newbldr_unarmed_modes_bin, &banim_newbldr_unarmed_script_o, &banim_newbldr_unarmed_oam_bin, &banim_newbldr_unarmed_oam_bin, &banim_newbldr_unarmed_agbpal}, // 0x122 bldr unarmed
    {"newhrbgsw1", &banim_newhrbg_sword_modes_bin, &banim_newhrbg_sword_script_o, &banim_newhrbg_sword_oam_bin, &banim_newhrbg_sword_oam_bin, &banim_newhrbg_sword_agbpal}, // 0x123 hrbg sword
    {"newhrbgln1", &banim_newhrbg_lance_modes_bin, &banim_newhrbg_lance_script_o, &banim_newhrbg_lance_oam_bin, &banim_newhrbg_lance_oam_bin, &banim_newhrbg_lance_agbpal}, // 0x124 hrbg lance
    {"newhrbgax1", &banim_newhrbg_axe_modes_bin, &banim_newhrbg_axe_script_o, &banim_newhrbg_axe_oam_bin, &banim_newhrbg_axe_oam_bin, &banim_newhrbg_axe_agbpal}, // 0x125 hrbg axe
    {"newhrbghx1", &banim_newhrbg_handaxe_modes_bin, &banim_newhrbg_handaxe_script_o, &banim_newhrbg_handaxe_oam_bin, &banim_newhrbg_handaxe_oam_bin, &banim_newhrbg_handaxe_agbpal}, // 0x126 hrbg handaxe
    {"newhrbgst1", &banim_newhrbg_staff_modes_bin, &banim_newhrbg_staff_script_o, &banim_newhrbg_staff_oam_bin, &banim_newhrbg_staff_oam_bin, &banim_newhrbg_staff_agbpal}, // 0x127 hrbg staff
    {"newhrbgmg1", &banim_newhrbg_magic_modes_bin, &banim_newhrbg_magic_script_o, &banim_newhrbg_magic_oam_bin, &banim_newhrbg_magic_oam_bin, &banim_newhrbg_magic_agbpal}, // 0x128 hrbg magic
    {"newhrbgun1", &banim_newhrbg_unarmed_modes_bin, &banim_newhrbg_unarmed_script_o, &banim_newhrbg_unarmed_oam_bin, &banim_newhrbg_unarmed_oam_bin, &banim_newhrbg_unarmed_agbpal}, // 0x129 hrbg unarmed
    {"newhvinsw1", &banim_newhvin_sword_modes_bin, &banim_newhvin_sword_script_o, &banim_newhvin_sword_oam_bin, &banim_newhvin_sword_oam_bin, &banim_newhvin_sword_agbpal}, // 0x12A hvin sword
    {"newhvinln1", &banim_newhvin_lance_modes_bin, &banim_newhvin_lance_script_o, &banim_newhvin_lance_oam_bin, &banim_newhvin_lance_oam_bin, &banim_newhvin_lance_agbpal}, // 0x12B hvin lance
    {"newhvinax1", &banim_newhvin_axe_modes_bin, &banim_newhvin_axe_script_o, &banim_newhvin_axe_oam_bin, &banim_newhvin_axe_oam_bin, &banim_newhvin_axe_agbpal}, // 0x12C hvin axe
    {"newhvinhx1", &banim_newhvin_handaxe_modes_bin, &banim_newhvin_handaxe_script_o, &banim_newhvin_handaxe_oam_bin, &banim_newhvin_handaxe_oam_bin, &banim_newhvin_handaxe_agbpal}, // 0x12D hvin handaxe
    {"newhvinun1", &banim_newhvin_unarmed_modes_bin, &banim_newhvin_unarmed_script_o, &banim_newhvin_unarmed_oam_bin, &banim_newhvin_unarmed_oam_bin, &banim_newhvin_unarmed_agbpal}, // 0x12E hvin unarmed
    {"newbarosw1", &banim_newbaro_sword_modes_bin, &banim_newbaro_sword_script_o, &banim_newbaro_sword_oam_bin, &banim_newbaro_sword_oam_bin, &banim_newbaro_sword_agbpal}, // 0x12F baro sword
    {"newbaroln1", &banim_newbaro_lance_modes_bin, &banim_newbaro_lance_script_o, &banim_newbaro_lance_oam_bin, &banim_newbaro_lance_oam_bin, &banim_newbaro_lance_agbpal}, // 0x130 baro lance
    {"newbaroax1", &banim_newbaro_axe_modes_bin, &banim_newbaro_axe_script_o, &banim_newbaro_axe_oam_bin, &banim_newbaro_axe_oam_bin, &banim_newbaro_axe_agbpal}, // 0x131 baro axe
    {"newbarohx1", &banim_newbaro_handaxe_modes_bin, &banim_newbaro_handaxe_script_o, &banim_newbaro_handaxe_oam_bin, &banim_newbaro_handaxe_oam_bin, &banim_newbaro_handaxe_agbpal}, // 0x132 baro handaxe
    {"newbarobw1", &banim_newbaro_bow_modes_bin, &banim_newbaro_bow_script_o, &banim_newbaro_bow_oam_bin, &banim_newbaro_bow_oam_bin, &banim_newbaro_bow_agbpal}, // 0x133 baro bow
    {"newbarost1", &banim_newbaro_staff_modes_bin, &banim_newbaro_staff_script_o, &banim_newbaro_staff_oam_bin, &banim_newbaro_staff_oam_bin, &banim_newbaro_staff_agbpal}, // 0x134 baro staff
    {"newbaromg1", &banim_newbaro_magic_modes_bin, &banim_newbaro_magic_script_o, &banim_newbaro_magic_oam_bin, &banim_newbaro_magic_oam_bin, &banim_newbaro_magic_agbpal}, // 0x135 baro magic
    {"newshgnsw1", &banim_newshgn_sword_modes_bin, &banim_newshgn_sword_script_o, &banim_newshgn_sword_oam_bin, &banim_newshgn_sword_oam_bin, &banim_newshgn_sword_agbpal}, // 0x136 shgn sword
    {"newshgnln1", &banim_newshgn_lance_modes_bin, &banim_newshgn_lance_script_o, &banim_newshgn_lance_oam_bin, &banim_newshgn_lance_oam_bin, &banim_newshgn_lance_agbpal}, // 0x137 shgn lance
    {"newshgnax1", &banim_newshgn_axe_modes_bin, &banim_newshgn_axe_script_o, &banim_newshgn_axe_oam_bin, &banim_newshgn_axe_oam_bin, &banim_newshgn_axe_agbpal}, // 0x138 shgn axe
    {"newshgnhx1", &banim_newshgn_handaxe_modes_bin, &banim_newshgn_handaxe_script_o, &banim_newshgn_handaxe_oam_bin, &banim_newshgn_handaxe_oam_bin, &banim_newshgn_handaxe_agbpal}, // 0x139 shgn handaxe
    {"newshgnmg1", &banim_newshgn_magic_modes_bin, &banim_newshgn_magic_script_o, &banim_newshgn_magic_oam_bin, &banim_newshgn_magic_oam_bin, &banim_newshgn_magic_agbpal}, // 0x13A shgn magic
    {"newshgnun1", &banim_newshgn_unarmed_modes_bin, &banim_newshgn_unarmed_script_o, &banim_newshgn_unarmed_oam_bin, &banim_newshgn_unarmed_oam_bin, &banim_newshgn_unarmed_agbpal}, // 0x13B shgn unarmed
    {"newbdrgun1", &banim_newbdrg_unarmed_modes_bin, &banim_newbdrg_unarmed_script_o, &banim_newbdrg_unarmed_oam_bin, &banim_newbdrg_unarmed_oam_bin, &banim_newbdrg_unarmed_agbpal}, // 0x13C bdrg unarmed
    {"newbdrgdr1", &banim_newbdrg_dragonstone_modes_bin, &banim_newbdrg_dragonstone_script_o, &banim_newbdrg_dragonstone_oam_bin, &banim_newbdrg_dragonstone_oam_bin, &banim_newbdrg_dragonstone_agbpal}, // 0x13D bdrg dragonstone
    {"newdjinsw1", &banim_newdjin_sword_modes_bin, &banim_newdjin_sword_script_o, &banim_newdjin_sword_oam_bin, &banim_newdjin_sword_oam_bin, &banim_newdjin_sword_agbpal}, // 0x13E djin sword
    {"newdjinmg1", &banim_newdjin_magic_modes_bin, &banim_newdjin_magic_script_o, &banim_newdjin_magic_oam_bin, &banim_newdjin_magic_oam_bin, &banim_newdjin_magic_agbpal}, // 0x13F djin magic
    {"newdjinsu1", &banim_newdjin_supply_modes_bin, &banim_newdjin_supply_script_o, &banim_newdjin_supply_oam_bin, &banim_newdjin_supply_oam_bin, &banim_newdjin_supply_agbpal}, // 0x140 djin supply
    {"newlarmsw1", &banim_newlarm_sword_modes_bin, &banim_newlarm_sword_script_o, &banim_newlarm_sword_oam_bin, &banim_newlarm_sword_oam_bin, &banim_newlarm_sword_agbpal}, // 0x141 larm sword
    {"newlarmax1", &banim_newlarm_axe_modes_bin, &banim_newlarm_axe_script_o, &banim_newlarm_axe_oam_bin, &banim_newlarm_axe_oam_bin, &banim_newlarm_axe_agbpal}, // 0x142 larm axe
    {"newlarmhx1", &banim_newlarm_handaxe_modes_bin, &banim_newlarm_handaxe_script_o, &banim_newlarm_handaxe_oam_bin, &banim_newlarm_handaxe_oam_bin, &banim_newlarm_handaxe_agbpal}, // 0x143 larm handaxe
    {"newlarmun1", &banim_newlarm_unarmed_modes_bin, &banim_newlarm_unarmed_script_o, &banim_newlarm_unarmed_oam_bin, &banim_newlarm_unarmed_oam_bin, &banim_newlarm_unarmed_agbpal}, // 0x144 larm unarmed
    {"newfellmg1", &banim_newfell_magic_modes_bin, &banim_newfell_magic_script_o, &banim_newfell_magic_oam_bin, &banim_newfell_magic_oam_bin, &banim_newfell_magic_agbpal}, // 0x145 fell magic
    {"newfellmo1", &banim_newfell_monster_modes_bin, &banim_newfell_monster_script_o, &banim_newfell_monster_oam_bin, &banim_newfell_monster_oam_bin, &banim_newfell_monster_agbpal}, // 0x146 fell monster
    {"newsamfsw1", &banim_newsamf_sword_modes_bin, &banim_newsamf_sword_script_o, &banim_newsamf_sword_oam_bin, &banim_newsamf_sword_oam_bin, &banim_newsamf_sword_agbpal}, // 0x147 samf sword
    {"newsamfun1", &banim_newsamf_unarmed_modes_bin, &banim_newsamf_unarmed_script_o, &banim_newsamf_unarmed_oam_bin, &banim_newsamf_unarmed_oam_bin, &banim_newsamf_unarmed_agbpal}, // 0x148 samf unarmed
    {"newmnjasw1", &banim_newmnja_sword_modes_bin, &banim_newmnja_sword_script_o, &banim_newmnja_sword_oam_bin, &banim_newmnja_sword_oam_bin, &banim_newmnja_sword_agbpal}, // 0x149 mnja sword
    {"newmnjaun1", &banim_newmnja_unarmed_modes_bin, &banim_newmnja_unarmed_script_o, &banim_newmnja_unarmed_oam_bin, &banim_newmnja_unarmed_oam_bin, &banim_newmnja_unarmed_agbpal}, // 0x14A mnja unarmed
    {"newhnjasw1", &banim_newhnja_sword_modes_bin, &banim_newhnja_sword_script_o, &banim_newhnja_sword_oam_bin, &banim_newhnja_sword_oam_bin, &banim_newhnja_sword_agbpal}, // 0x14B hnja sword
    {"newhnjaun1", &banim_newhnja_unarmed_modes_bin, &banim_newhnja_unarmed_script_o, &banim_newhnja_unarmed_oam_bin, &banim_newhnja_unarmed_oam_bin, &banim_newhnja_unarmed_agbpal}, // 0x14C hnja unarmed
    {"newmyffsw1", &banim_newmyff_sword_modes_bin, &banim_newmyff_sword_script_o, &banim_newmyff_sword_oam_bin, &banim_newmyff_sword_oam_bin, &banim_newmyff_sword_agbpal}, // 0x14D myff sword
    {"newmyffun1", &banim_newmyff_unarmed_modes_bin, &banim_newmyff_unarmed_script_o, &banim_newmyff_unarmed_oam_bin, &banim_newmyff_unarmed_oam_bin, &banim_newmyff_unarmed_agbpal}, // 0x14E myff unarmed
    {"newmyfmsw1", &banim_newmyfm_sword_modes_bin, &banim_newmyfm_sword_script_o, &banim_newmyfm_sword_oam_bin, &banim_newmyfm_sword_oam_bin, &banim_newmyfm_sword_agbpal}, // 0x14F myfm sword
    {"newmyfmun1", &banim_newmyfm_unarmed_modes_bin, &banim_newmyfm_unarmed_script_o, &banim_newmyfm_unarmed_oam_bin, &banim_newmyfm_unarmed_oam_bin, &banim_newmyfm_unarmed_agbpal}, // 0x150 myfm unarmed
    {"newkatasw1", &banim_newkata_sword_modes_bin, &banim_newkata_sword_script_o, &banim_newkata_sword_oam_bin, &banim_newkata_sword_oam_bin, &banim_newkata_sword_agbpal}, // 0x151 kata sword
    {"newkataun1", &banim_newkata_unarmed_modes_bin, &banim_newkata_unarmed_script_o, &banim_newkata_unarmed_oam_bin, &banim_newkata_unarmed_oam_bin, &banim_newkata_unarmed_agbpal}, // 0x152 kata unarmed
    {"newthugsw1", &banim_newthug_sword_modes_bin, &banim_newthug_sword_script_o, &banim_newthug_sword_oam_bin, &banim_newthug_sword_oam_bin, &banim_newthug_sword_agbpal}, // 0x153 thug sword
    {"newthugun1", &banim_newthug_unarmed_modes_bin, &banim_newthug_unarmed_script_o, &banim_newthug_unarmed_oam_bin, &banim_newthug_unarmed_oam_bin, &banim_newthug_unarmed_agbpal}, // 0x154 thug unarmed
    {"newdrdfsw1", &banim_newdrdf_sword_modes_bin, &banim_newdrdf_sword_script_o, &banim_newdrdf_sword_oam_bin, &banim_newdrdf_sword_oam_bin, &banim_newdrdf_sword_agbpal}, // 0x155 drdf sword
    {"newdrdfmg1", &banim_newdrdf_magic_modes_bin, &banim_newdrdf_magic_script_o, &banim_newdrdf_magic_oam_bin, &banim_newdrdf_magic_oam_bin, &banim_newdrdf_magic_agbpal}, // 0x156 drdf magic
    {"newdrdfun1", &banim_newdrdf_unarmed_modes_bin, &banim_newdrdf_unarmed_script_o, &banim_newdrdf_unarmed_oam_bin, &banim_newdrdf_unarmed_oam_bin, &banim_newdrdf_unarmed_agbpal}, // 0x157 drdf unarmed
    {"newfirssw1", &banim_newfirs_sword_modes_bin, &banim_newfirs_sword_script_o, &banim_newfirs_sword_oam_bin, &banim_newfirs_sword_oam_bin, &banim_newfirs_sword_agbpal}, // 0x158 firs sword
    {"newfirsln1", &banim_newfirs_lance_modes_bin, &banim_newfirs_lance_script_o, &banim_newfirs_lance_oam_bin, &banim_newfirs_lance_oam_bin, &banim_newfirs_lance_agbpal}, // 0x159 firs lance
    {"newfirsun1", &banim_newfirs_unarmed_modes_bin, &banim_newfirs_unarmed_script_o, &banim_newfirs_unarmed_oam_bin, &banim_newfirs_unarmed_oam_bin, &banim_newfirs_unarmed_agbpal}, // 0x15A firs unarmed
    {"newtrubsw1", &banim_newtrub_sword_modes_bin, &banim_newtrub_sword_script_o, &banim_newtrub_sword_oam_bin, &banim_newtrub_sword_oam_bin, &banim_newtrub_sword_agbpal}, // 0x15B trub sword
    {"newtrubun1", &banim_newtrub_unarmed_modes_bin, &banim_newtrub_unarmed_script_o, &banim_newtrub_unarmed_oam_bin, &banim_newtrub_unarmed_oam_bin, &banim_newtrub_unarmed_agbpal}, // 0x15C trub unarmed
    {"newredmsw1", &banim_newredm_sword_modes_bin, &banim_newredm_sword_script_o, &banim_newredm_sword_oam_bin, &banim_newredm_sword_oam_bin, &banim_newredm_sword_agbpal}, // 0x15D redm sword
    {"newredmst1", &banim_newredm_staff_modes_bin, &banim_newredm_staff_script_o, &banim_newredm_staff_oam_bin, &banim_newredm_staff_oam_bin, &banim_newredm_staff_agbpal}, // 0x15E redm staff
    {"newredmmg1", &banim_newredm_magic_modes_bin, &banim_newredm_magic_script_o, &banim_newredm_magic_oam_bin, &banim_newredm_magic_oam_bin, &banim_newredm_magic_agbpal}, // 0x15F redm magic
    {"newmololn1", &banim_newmolo_lance_modes_bin, &banim_newmolo_lance_script_o, &banim_newmolo_lance_oam_bin, &banim_newmolo_lance_oam_bin, &banim_newmolo_lance_agbpal}, // 0x160 molo lance
    {"newmolost1", &banim_newmolo_staff_modes_bin, &banim_newmolo_staff_script_o, &banim_newmolo_staff_oam_bin, &banim_newmolo_staff_oam_bin, &banim_newmolo_staff_agbpal}, // 0x161 molo staff
    {"newmolomg1", &banim_newmolo_magic_modes_bin, &banim_newmolo_magic_script_o, &banim_newmolo_magic_oam_bin, &banim_newmolo_magic_oam_bin, &banim_newmolo_magic_agbpal}, // 0x162 molo magic
    {"newmoloun1", &banim_newmolo_unarmed_modes_bin, &banim_newmolo_unarmed_script_o, &banim_newmolo_unarmed_oam_bin, &banim_newmolo_unarmed_oam_bin, &banim_newmolo_unarmed_agbpal}, // 0x163 molo unarmed
    {"newtactmg1", &banim_newtact_magic_modes_bin, &banim_newtact_magic_script_o, &banim_newtact_magic_oam_bin, &banim_newtact_magic_oam_bin, &banim_newtact_magic_agbpal}, // 0x164 tact magic
    {"newtrifsw1", &banim_newtrif_sword_modes_bin, &banim_newtrif_sword_script_o, &banim_newtrif_sword_oam_bin, &banim_newtrif_sword_oam_bin, &banim_newtrif_sword_agbpal}, // 0x165 trif sword
    {"newtrifbw1", &banim_newtrif_bow_modes_bin, &banim_newtrif_bow_script_o, &banim_newtrif_bow_oam_bin, &banim_newtrif_bow_oam_bin, &banim_newtrif_bow_agbpal}, // 0x166 trif bow
    {"newtrifst1", &banim_newtrif_staff_modes_bin, &banim_newtrif_staff_script_o, &banim_newtrif_staff_oam_bin, &banim_newtrif_staff_oam_bin, &banim_newtrif_staff_agbpal}, // 0x167 trif staff
    {"newtrifmg1", &banim_newtrif_magic_modes_bin, &banim_newtrif_magic_script_o, &banim_newtrif_magic_oam_bin, &banim_newtrif_magic_oam_bin, &banim_newtrif_magic_agbpal}, // 0x168 trif magic
    {"newtrimsw1", &banim_newtrim_sword_modes_bin, &banim_newtrim_sword_script_o, &banim_newtrim_sword_oam_bin, &banim_newtrim_sword_oam_bin, &banim_newtrim_sword_agbpal}, // 0x169 trim sword
    {"newtrimbw1", &banim_newtrim_bow_modes_bin, &banim_newtrim_bow_script_o, &banim_newtrim_bow_oam_bin, &banim_newtrim_bow_oam_bin, &banim_newtrim_bow_agbpal}, // 0x16A trim bow
    {"newtrimst1", &banim_newtrim_staff_modes_bin, &banim_newtrim_staff_script_o, &banim_newtrim_staff_oam_bin, &banim_newtrim_staff_oam_bin, &banim_newtrim_staff_agbpal}, // 0x16B trim staff
    {"newtrimmg1", &banim_newtrim_magic_modes_bin, &banim_newtrim_magic_script_o, &banim_newtrim_magic_oam_bin, &banim_newtrim_magic_oam_bin, &banim_newtrim_magic_agbpal}, // 0x16C trim magic
    {"newvilfsw1", &banim_newvilf_sword_modes_bin, &banim_newvilf_sword_script_o, &banim_newvilf_sword_oam_bin, &banim_newvilf_sword_oam_bin, &banim_newvilf_sword_agbpal}, // 0x16D vilf sword
    {"newvilfun1", &banim_newvilf_unarmed_modes_bin, &banim_newvilf_unarmed_script_o, &banim_newvilf_unarmed_oam_bin, &banim_newvilf_unarmed_oam_bin, &banim_newvilf_unarmed_agbpal}, // 0x16E vilf unarmed
    {"newvilmsw1", &banim_newvilm_sword_modes_bin, &banim_newvilm_sword_script_o, &banim_newvilm_sword_oam_bin, &banim_newvilm_sword_oam_bin, &banim_newvilm_sword_agbpal}, // 0x16F vilm sword
    {"newvilmun1", &banim_newvilm_unarmed_modes_bin, &banim_newvilm_unarmed_script_o, &banim_newvilm_unarmed_oam_bin, &banim_newvilm_unarmed_oam_bin, &banim_newvilm_unarmed_agbpal}, // 0x170 vilm unarmed
    {"newlegksw1", &banim_newlegk_sword_modes_bin, &banim_newlegk_sword_script_o, &banim_newlegk_sword_oam_bin, &banim_newlegk_sword_oam_bin, &banim_newlegk_sword_agbpal}, // 0x171 legk sword
    {"newlegkln1", &banim_newlegk_lance_modes_bin, &banim_newlegk_lance_script_o, &banim_newlegk_lance_oam_bin, &banim_newlegk_lance_oam_bin, &banim_newlegk_lance_agbpal}, // 0x172 legk lance
    {"newlegkax1", &banim_newlegk_axe_modes_bin, &banim_newlegk_axe_script_o, &banim_newlegk_axe_oam_bin, &banim_newlegk_axe_oam_bin, &banim_newlegk_axe_agbpal}, // 0x173 legk axe
    {"newlegkhx1", &banim_newlegk_handaxe_modes_bin, &banim_newlegk_handaxe_script_o, &banim_newlegk_handaxe_oam_bin, &banim_newlegk_handaxe_oam_bin, &banim_newlegk_handaxe_agbpal}, // 0x174 legk handaxe
    {"newlegkmg1", &banim_newlegk_magic_modes_bin, &banim_newlegk_magic_script_o, &banim_newlegk_magic_oam_bin, &banim_newlegk_magic_oam_bin, &banim_newlegk_magic_agbpal}, // 0x175 legk magic
    {"newlegkun1", &banim_newlegk_unarmed_modes_bin, &banim_newlegk_unarmed_script_o, &banim_newlegk_unarmed_oam_bin, &banim_newlegk_unarmed_oam_bin, &banim_newlegk_unarmed_agbpal}, // 0x176 legk unarmed
    {"newonicax1", &banim_newonic_axe_modes_bin, &banim_newonic_axe_script_o, &banim_newonic_axe_oam_bin, &banim_newonic_axe_oam_bin, &banim_newonic_axe_agbpal}, // 0x177 onic axe
    {"newonichx1", &banim_newonic_handaxe_modes_bin, &banim_newonic_handaxe_script_o, &banim_newonic_handaxe_oam_bin, &banim_newonic_handaxe_oam_bin, &banim_newonic_handaxe_agbpal}, // 0x178 onic handaxe
    {"newonicmg1", &banim_newonic_magic_modes_bin, &banim_newonic_magic_script_o, &banim_newonic_magic_oam_bin, &banim_newonic_magic_oam_bin, &banim_newonic_magic_agbpal}, // 0x179 onic magic
    {"newelfnmg1", &banim_newelfn_magic_modes_bin, &banim_newelfn_magic_script_o, &banim_newelfn_magic_oam_bin, &banim_newelfn_magic_oam_bin, &banim_newelfn_magic_agbpal}, // 0x17A elfn magic
    {"newelfnrf1", &banim_newelfn_refresh_modes_bin, &banim_newelfn_refresh_script_o, &banim_newelfn_refresh_oam_bin, &banim_newelfn_refresh_oam_bin, &banim_newelfn_refresh_agbpal}, // 0x17B elfn refresh
    {"newmmarax1", &banim_newmmar_axe_modes_bin, &banim_newmmar_axe_script_o, &banim_newmmar_axe_oam_bin, &banim_newmmar_axe_oam_bin, &banim_newmmar_axe_agbpal}, // 0x17C mmar axe
    {"newmmarhx1", &banim_newmmar_handaxe_modes_bin, &banim_newmmar_handaxe_script_o, &banim_newmmar_handaxe_oam_bin, &banim_newmmar_handaxe_oam_bin, &banim_newmmar_handaxe_agbpal}, // 0x17D mmar handaxe
    {"newmmarbw1", &banim_newmmar_bow_modes_bin, &banim_newmmar_bow_script_o, &banim_newmmar_bow_oam_bin, &banim_newmmar_bow_oam_bin, &banim_newmmar_bow_agbpal}, // 0x17E mmar bow
    {"newmmarun1", &banim_newmmar_unarmed_modes_bin, &banim_newmmar_unarmed_script_o, &banim_newmmar_unarmed_oam_bin, &banim_newmmar_unarmed_oam_bin, &banim_newmmar_unarmed_agbpal}, // 0x17F mmar unarmed
    {"newmechbw1", &banim_newmech_bow_modes_bin, &banim_newmech_bow_script_o, &banim_newmech_bow_oam_bin, &banim_newmech_bow_oam_bin, &banim_newmech_bow_agbpal}, // 0x180 mech bow
    {"newmechun1", &banim_newmech_unarmed_modes_bin, &banim_newmech_unarmed_script_o, &banim_newmech_unarmed_oam_bin, &banim_newmech_unarmed_oam_bin, &banim_newmech_unarmed_agbpal}, // 0x181 mech unarmed
    {"newdragln1", &banim_newdrag_lance_modes_bin, &banim_newdrag_lance_script_o, &banim_newdrag_lance_oam_bin, &banim_newdrag_lance_oam_bin, &banim_newdrag_lance_agbpal}, // 0x182 drag lance
    {"newdragun1", &banim_newdrag_unarmed_modes_bin, &banim_newdrag_unarmed_script_o, &banim_newdrag_unarmed_oam_bin, &banim_newdrag_unarmed_oam_bin, &banim_newdrag_unarmed_agbpal}, // 0x183 drag unarmed
    {"newlancln1", &banim_newlanc_lance_modes_bin, &banim_newlanc_lance_script_o, &banim_newlanc_lance_oam_bin, &banim_newlanc_lance_oam_bin, &banim_newlanc_lance_agbpal}, // 0x184 lanc lance
    {"newlancun1", &banim_newlanc_unarmed_modes_bin, &banim_newlanc_unarmed_script_o, &banim_newlanc_unarmed_oam_bin, &banim_newlanc_unarmed_oam_bin, &banim_newlanc_unarmed_agbpal}, // 0x185 lanc unarmed
    {"newmiltln1", &banim_newmilt_lance_modes_bin, &banim_newmilt_lance_script_o, &banim_newmilt_lance_oam_bin, &banim_newmilt_lance_oam_bin, &banim_newmilt_lance_agbpal}, // 0x186 milt lance
    {"newmiltun1", &banim_newmilt_unarmed_modes_bin, &banim_newmilt_unarmed_script_o, &banim_newmilt_unarmed_oam_bin, &banim_newmilt_unarmed_oam_bin, &banim_newmilt_unarmed_agbpal}, // 0x187 milt unarmed
    {"newsentsw1", &banim_newsent_sword_modes_bin, &banim_newsent_sword_script_o, &banim_newsent_sword_oam_bin, &banim_newsent_sword_oam_bin, &banim_newsent_sword_agbpal}, // 0x188 sent sword
    {"newsentln1", &banim_newsent_lance_modes_bin, &banim_newsent_lance_script_o, &banim_newsent_lance_oam_bin, &banim_newsent_lance_oam_bin, &banim_newsent_lance_agbpal}, // 0x189 sent lance
    {"newsentax1", &banim_newsent_axe_modes_bin, &banim_newsent_axe_script_o, &banim_newsent_axe_oam_bin, &banim_newsent_axe_oam_bin, &banim_newsent_axe_agbpal}, // 0x18A sent axe
    {"newsenthx1", &banim_newsent_handaxe_modes_bin, &banim_newsent_handaxe_script_o, &banim_newsent_handaxe_oam_bin, &banim_newsent_handaxe_oam_bin, &banim_newsent_handaxe_agbpal}, // 0x18B sent handaxe
    {"newsentun1", &banim_newsent_unarmed_modes_bin, &banim_newsent_unarmed_script_o, &banim_newsent_unarmed_oam_bin, &banim_newsent_unarmed_oam_bin, &banim_newsent_unarmed_agbpal}, // 0x18C sent unarmed
    {"newt1lnsw1", &banim_newt1ln_sword_modes_bin, &banim_newt1ln_sword_script_o, &banim_newt1ln_sword_oam_bin, &banim_newt1ln_sword_oam_bin, &banim_newt1ln_sword_agbpal}, // 0x18D t1ln sword
    {"newt1lnln1", &banim_newt1ln_lance_modes_bin, &banim_newt1ln_lance_script_o, &banim_newt1ln_lance_oam_bin, &banim_newt1ln_lance_oam_bin, &banim_newt1ln_lance_agbpal}, // 0x18E t1ln lance
    {"newt1lnun1", &banim_newt1ln_unarmed_modes_bin, &banim_newt1ln_unarmed_script_o, &banim_newt1ln_unarmed_oam_bin, &banim_newt1ln_unarmed_oam_bin, &banim_newt1ln_unarmed_agbpal}, // 0x18F t1ln unarmed
    {"newgladsw1", &banim_newglad_sword_modes_bin, &banim_newglad_sword_script_o, &banim_newglad_sword_oam_bin, &banim_newglad_sword_oam_bin, &banim_newglad_sword_agbpal}, // 0x190 glad sword
    {"newgladax1", &banim_newglad_axe_modes_bin, &banim_newglad_axe_script_o, &banim_newglad_axe_oam_bin, &banim_newglad_axe_oam_bin, &banim_newglad_axe_agbpal}, // 0x191 glad axe
    {"newgladhx1", &banim_newglad_handaxe_modes_bin, &banim_newglad_handaxe_script_o, &banim_newglad_handaxe_oam_bin, &banim_newglad_handaxe_oam_bin, &banim_newglad_handaxe_agbpal}, // 0x192 glad handaxe
    {"newgladun1", &banim_newglad_unarmed_modes_bin, &banim_newglad_unarmed_script_o, &banim_newglad_unarmed_oam_bin, &banim_newglad_unarmed_oam_bin, &banim_newglad_unarmed_agbpal}, // 0x193 glad unarmed
    {"newhbrgax1", &banim_newhbrg_axe_modes_bin, &banim_newhbrg_axe_script_o, &banim_newhbrg_axe_oam_bin, &banim_newhbrg_axe_oam_bin, &banim_newhbrg_axe_agbpal}, // 0x194 hbrg axe
    {"newhsldln1", &banim_newhsld_lance_modes_bin, &banim_newhsld_lance_script_o, &banim_newhsld_lance_oam_bin, &banim_newhsld_lance_oam_bin, &banim_newhsld_lance_agbpal}, // 0x195 hsld lance
    {"newhuntbw1", &banim_newhunt_bow_modes_bin, &banim_newhunt_bow_script_o, &banim_newhunt_bow_oam_bin, &banim_newhunt_bow_oam_bin, &banim_newhunt_bow_agbpal}, // 0x196 hunt bow
    {"newhuntun1", &banim_newhunt_unarmed_modes_bin, &banim_newhunt_unarmed_script_o, &banim_newhunt_unarmed_oam_bin, &banim_newhunt_unarmed_oam_bin, &banim_newhunt_unarmed_agbpal}, // 0x197 hunt unarmed
    {"newannaln1", &banim_newanna_lance_modes_bin, &banim_newanna_lance_script_o, &banim_newanna_lance_oam_bin, &banim_newanna_lance_oam_bin, &banim_newanna_lance_agbpal}, // 0x198 anna lance
    {"newannabw1", &banim_newanna_bow_modes_bin, &banim_newanna_bow_script_o, &banim_newanna_bow_oam_bin, &banim_newanna_bow_oam_bin, &banim_newanna_bow_agbpal}, // 0x199 anna bow
    {"newannast1", &banim_newanna_staff_modes_bin, &banim_newanna_staff_script_o, &banim_newanna_staff_oam_bin, &banim_newanna_staff_oam_bin, &banim_newanna_staff_agbpal}, // 0x19A anna staff
    {"newsandmo1", &banim_newsand_monster_modes_bin, &banim_newsand_monster_script_o, &banim_newsand_monster_oam_bin, &banim_newsand_monster_oam_bin, &banim_newsand_monster_agbpal}, // 0x19B sand monster
    {"newcswdsw1", &banim_newcswd_sword_modes_bin, &banim_newcswd_sword_script_o, &banim_newcswd_sword_oam_bin, &banim_newcswd_sword_oam_bin, &banim_newcswd_sword_agbpal}, // 0x19C cswd sword
    {"newtomemg1", &banim_newtome_magic_modes_bin, &banim_newtome_magic_script_o, &banim_newtome_magic_oam_bin, &banim_newtome_magic_oam_bin, &banim_newtome_magic_agbpal}, // 0x19D tome magic
    {"newmimcmg1", &banim_newmimc_magic_modes_bin, &banim_newmimc_magic_script_o, &banim_newmimc_magic_oam_bin, &banim_newmimc_magic_oam_bin, &banim_newmimc_magic_agbpal}, // 0x19E mimc magic
    {"newmosqmo1", &banim_newmosq_monster_modes_bin, &banim_newmosq_monster_script_o, &banim_newmosq_monster_oam_bin, &banim_newmosq_monster_oam_bin, &banim_newmosq_monster_agbpal}, // 0x19F mosq monster
    {"newphntax1", &banim_newphnt_axe_modes_bin, &banim_newphnt_axe_script_o, &banim_newphnt_axe_oam_bin, &banim_newphnt_axe_oam_bin, &banim_newphnt_axe_agbpal}, // 0x1A0 phnt axe
    {"newphnthx1", &banim_newphnt_handaxe_modes_bin, &banim_newphnt_handaxe_script_o, &banim_newphnt_handaxe_oam_bin, &banim_newphnt_handaxe_oam_bin, &banim_newphnt_handaxe_agbpal}, // 0x1A1 phnt handaxe
    {"newphntun1", &banim_newphnt_unarmed_modes_bin, &banim_newphnt_unarmed_script_o, &banim_newphnt_unarmed_oam_bin, &banim_newphnt_unarmed_oam_bin, &banim_newphnt_unarmed_agbpal}, // 0x1A2 phnt unarmed
    {"newslimst1", &banim_newslim_staff_modes_bin, &banim_newslim_staff_script_o, &banim_newslim_staff_oam_bin, &banim_newslim_staff_oam_bin, &banim_newslim_staff_agbpal}, // 0x1A3 slim staff
    {"newslimmg1", &banim_newslim_magic_modes_bin, &banim_newslim_magic_script_o, &banim_newslim_magic_oam_bin, &banim_newslim_magic_oam_bin, &banim_newslim_magic_agbpal}, // 0x1A4 slim magic
    {"newwbrdln1", &banim_newwbrd_lance_modes_bin, &banim_newwbrd_lance_script_o, &banim_newwbrd_lance_oam_bin, &banim_newwbrd_lance_oam_bin, &banim_newwbrd_lance_agbpal}, // 0x1A5 wbrd lance
    {"newwbrdbw1", &banim_newwbrd_bow_modes_bin, &banim_newwbrd_bow_script_o, &banim_newwbrd_bow_oam_bin, &banim_newwbrd_bow_oam_bin, &banim_newwbrd_bow_agbpal}, // 0x1A6 wbrd bow
    {"newwbrdun1", &banim_newwbrd_unarmed_modes_bin, &banim_newwbrd_unarmed_script_o, &banim_newwbrd_unarmed_oam_bin, &banim_newwbrd_unarmed_oam_bin, &banim_newwbrd_unarmed_agbpal}, // 0x1A7 wbrd unarmed
    {"newadvnbw1", &banim_newadvn_bow_modes_bin, &banim_newadvn_bow_script_o, &banim_newadvn_bow_oam_bin, &banim_newadvn_bow_oam_bin, &banim_newadvn_bow_agbpal}, // 0x1A8 advn bow
    {"newadvnst1", &banim_newadvn_staff_modes_bin, &banim_newadvn_staff_script_o, &banim_newadvn_staff_oam_bin, &banim_newadvn_staff_oam_bin, &banim_newadvn_staff_agbpal}, // 0x1A9 advn staff
    {"newadvnun1", &banim_newadvn_unarmed_modes_bin, &banim_newadvn_unarmed_script_o, &banim_newadvn_unarmed_oam_bin, &banim_newadvn_unarmed_oam_bin, &banim_newadvn_unarmed_agbpal}, // 0x1AA advn unarmed
    {"newlynluun1", &banim_newlynlun_unarmed_modes_bin, &banim_newlynlun_unarmed_script_o, &banim_newlynlun_unarmed_oam_bin, &banim_newlynlun_unarmed_oam_bin, &banim_newlynlun_unarmed_agbpal}, // 0x1AB lynlun unarmed
    {"newlynglsw1", &banim_newlyngl_sword_modes_bin, &banim_newlyngl_sword_script_o, &banim_newlyngl_sword_oam_bin, &banim_newlyngl_sword_oam_bin, &banim_newlyngl_sword_agbpal}, // 0x1AC lyngl sword
    {"newlynglun1", &banim_newlyngl_unarmed_modes_bin, &banim_newlyngl_unarmed_script_o, &banim_newlyngl_unarmed_oam_bin, &banim_newlyngl_unarmed_oam_bin, &banim_newlyngl_unarmed_agbpal}, // 0x1AD lyngl unarmed
    {"neweldrmg1", &banim_newelder_magic_modes_bin, &banim_newelder_magic_script_o, &banim_newelder_magic_oam_bin, &banim_newelder_magic_oam_bin, &banim_newelder_magic_agbpal}, // 0x1AE elder magic
    {"neweldrst1", &banim_newelder_staff_modes_bin, &banim_newelder_staff_script_o, &banim_newelder_staff_oam_bin, &banim_newelder_staff_oam_bin, &banim_newelder_staff_agbpal}, // 0x1AF elder staff
    {"neweldrun1", &banim_newelder_unarmed_modes_bin, &banim_newelder_unarmed_script_o, &banim_newelder_unarmed_oam_bin, &banim_newelder_unarmed_oam_bin, &banim_newelder_unarmed_agbpal}, // 0x1B0 elder unarmed
    {"newarbmln1", &banim_newarblm_lance_modes_bin, &banim_newarblm_lance_script_o, &banim_newarblm_lance_oam_bin, &banim_newarblm_lance_oam_bin, &banim_newarblm_lance_agbpal}, // 0x1B1 arblm lance
    {"newarbmbw1", &banim_newarblm_bow_modes_bin, &banim_newarblm_bow_script_o, &banim_newarblm_bow_oam_bin, &banim_newarblm_bow_oam_bin, &banim_newarblm_bow_agbpal}, // 0x1B2 arblm bow
    {"newarbmun1", &banim_newarblm_unarmed_modes_bin, &banim_newarblm_unarmed_script_o, &banim_newarblm_unarmed_oam_bin, &banim_newarblm_unarmed_oam_bin, &banim_newarblm_unarmed_agbpal}, // 0x1B3 arblm unarmed
    {"newarbfln1", &banim_newarblf_lance_modes_bin, &banim_newarblf_lance_script_o, &banim_newarblf_lance_oam_bin, &banim_newarblf_lance_oam_bin, &banim_newarblf_lance_agbpal}, // 0x1B4 arblf lance
    {"newarbfbw1", &banim_newarblf_bow_modes_bin, &banim_newarblf_bow_script_o, &banim_newarblf_bow_oam_bin, &banim_newarblf_bow_oam_bin, &banim_newarblf_bow_agbpal}, // 0x1B5 arblf bow
    {"newarbfun1", &banim_newarblf_unarmed_modes_bin, &banim_newarblf_unarmed_script_o, &banim_newarblf_unarmed_oam_bin, &banim_newarblf_unarmed_oam_bin, &banim_newarblf_unarmed_agbpal}, // 0x1B6 arblf unarmed
    {"newfbkntln1", &banim_newfbknt_lance_modes_bin, &banim_newfbknt_lance_script_o, &banim_newfbknt_lance_oam_bin, &banim_newfbknt_lance_oam_bin, &banim_newfbknt_lance_agbpal}, // 0x1B7 fbknt lance
    {"newfbkntun1", &banim_newfbknt_unarmed_modes_bin, &banim_newfbknt_unarmed_script_o, &banim_newfbknt_unarmed_oam_bin, &banim_newfbknt_unarmed_oam_bin, &banim_newfbknt_unarmed_agbpal}, // 0x1B8 fbknt unarmed
    {"newgrifmsw1", &banim_newgrifm_sword_modes_bin, &banim_newgrifm_sword_script_o, &banim_newgrifm_sword_oam_bin, &banim_newgrifm_sword_oam_bin, &banim_newgrifm_sword_agbpal}, // 0x1B9 grifm sword
    {"newgrifmax1", &banim_newgrifm_axe_modes_bin, &banim_newgrifm_axe_script_o, &banim_newgrifm_axe_oam_bin, &banim_newgrifm_axe_oam_bin, &banim_newgrifm_axe_agbpal}, // 0x1BA grifm axe
    {"newgrifmhx1", &banim_newgrifm_handaxe_modes_bin, &banim_newgrifm_handaxe_script_o, &banim_newgrifm_handaxe_oam_bin, &banim_newgrifm_handaxe_oam_bin, &banim_newgrifm_handaxe_agbpal}, // 0x1BB grifm handaxe
    {"newgrifmun1", &banim_newgrifm_unarmed_modes_bin, &banim_newgrifm_unarmed_script_o, &banim_newgrifm_unarmed_oam_bin, &banim_newgrifm_unarmed_oam_bin, &banim_newgrifm_unarmed_agbpal}, // 0x1BC grifm unarmed
    {"newasagemg1", &banim_newasage_magic_modes_bin, &banim_newasage_magic_script_o, &banim_newasage_magic_oam_bin, &banim_newasage_magic_oam_bin, &banim_newasage_magic_agbpal}, // 0x1BD asage magic
    {"newasagest1", &banim_newasage_staff_modes_bin, &banim_newasage_staff_script_o, &banim_newasage_staff_oam_bin, &banim_newasage_staff_oam_bin, &banim_newasage_staff_agbpal}, // 0x1BE asage staff
    {"newmalqax1", &banim_newmalq_axe_modes_bin, &banim_newmalq_axe_script_o, &banim_newmalq_axe_oam_bin, &banim_newmalq_axe_oam_bin, &banim_newmalq_axe_agbpal}, // 0x1BF malq axe
    {"newmalqhx1", &banim_newmalq_handaxe_modes_bin, &banim_newmalq_handaxe_script_o, &banim_newmalq_handaxe_oam_bin, &banim_newmalq_handaxe_oam_bin, &banim_newmalq_handaxe_agbpal}, // 0x1C0 malq handaxe
    {"newmalqmg1", &banim_newmalq_magic_modes_bin, &banim_newmalq_magic_script_o, &banim_newmalq_magic_oam_bin, &banim_newmalq_magic_oam_bin, &banim_newmalq_magic_agbpal}, // 0x1C1 malq magic
    {"newserapsw1", &banim_newserap_sword_modes_bin, &banim_newserap_sword_script_o, &banim_newserap_sword_oam_bin, &banim_newserap_sword_oam_bin, &banim_newserap_sword_agbpal}, // 0x1C2 serap sword
    {"newserapln1", &banim_newserap_lance_modes_bin, &banim_newserap_lance_script_o, &banim_newserap_lance_oam_bin, &banim_newserap_lance_oam_bin, &banim_newserap_lance_agbpal}, // 0x1C3 serap lance
    {"newserapmg1", &banim_newserap_magic_modes_bin, &banim_newserap_magic_script_o, &banim_newserap_magic_oam_bin, &banim_newserap_magic_oam_bin, &banim_newserap_magic_agbpal}, // 0x1C4 serap magic
    {"newserapst1", &banim_newserap_staff_modes_bin, &banim_newserap_staff_script_o, &banim_newserap_staff_oam_bin, &banim_newserap_staff_oam_bin, &banim_newserap_staff_agbpal}, // 0x1C5 serap staff
    {"newserapun1", &banim_newserap_unarmed_modes_bin, &banim_newserap_unarmed_script_o, &banim_newserap_unarmed_oam_bin, &banim_newserap_unarmed_oam_bin, &banim_newserap_unarmed_agbpal}, // 0x1C6 serap unarmed
    {"newexecsw1", &banim_newexec_sword_modes_bin, &banim_newexec_sword_script_o, &banim_newexec_sword_oam_bin, &banim_newexec_sword_oam_bin, &banim_newexec_sword_agbpal}, // 0x1C7 exec sword
    {"newexecmg1", &banim_newexec_magic_modes_bin, &banim_newexec_magic_script_o, &banim_newexec_magic_oam_bin, &banim_newexec_magic_oam_bin, &banim_newexec_magic_agbpal}, // 0x1C8 exec magic
    {"newexecun1", &banim_newexec_unarmed_modes_bin, &banim_newexec_unarmed_script_o, &banim_newexec_unarmed_oam_bin, &banim_newexec_unarmed_oam_bin, &banim_newexec_unarmed_agbpal}, // 0x1C9 exec unarmed
};
__attribute__((section(".data.banim_array_len")))
long long banim_number = sizeof(banim_data) / sizeof(banim_data[0]);
