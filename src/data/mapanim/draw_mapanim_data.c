#include "global.h"
#include "draw_mapanim.h"

#if FE8_DRAW_MAP_ANIMS

static const u8 ALIGNED(4) Cauterize_0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0001.dmp");
static const u16 ALIGNED(4) Cauterize_0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Cauterize_0001_pal.dmp");
static const u8 ALIGNED(4) Cauterize_0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0002.dmp");
static const u8 ALIGNED(4) Cauterize_0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0003.dmp");
static const u8 ALIGNED(4) Cauterize_0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0004.dmp");
static const u8 ALIGNED(4) Cauterize_0005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0005.dmp");
static const u8 ALIGNED(4) Cauterize_0006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0006.dmp");
static const u8 ALIGNED(4) Cauterize_0007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0007.dmp");
static const u8 ALIGNED(4) Cauterize_0008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0008.dmp");
static const u8 ALIGNED(4) Cauterize_0009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0009.dmp");
static const u8 ALIGNED(4) Cauterize_0010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0010.dmp");
static const u8 ALIGNED(4) Cauterize_0011_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0011.dmp");
static const u8 ALIGNED(4) Cauterize_0012_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0012.dmp");
static const u8 ALIGNED(4) Cauterize_0013_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0013.dmp");
static const u8 ALIGNED(4) Cauterize_0014_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0014.dmp");
static const u8 ALIGNED(4) Cauterize_0015_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0015.dmp");
static const u8 ALIGNED(4) Cauterize_0016_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0016.dmp");
static const u8 ALIGNED(4) Cauterize_0017_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0017.dmp");
static const u8 ALIGNED(4) Cauterize_0018_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0018.dmp");
static const u8 ALIGNED(4) Cauterize_0019_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0019.dmp");
static const u8 ALIGNED(4) Cauterize_0020_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0020.dmp");
static const u8 ALIGNED(4) Cauterize_0021_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0021.dmp");
static const u8 ALIGNED(4) Cauterize_0022_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0022.dmp");
static const u8 ALIGNED(4) Cauterize_0023_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0023.dmp");
static const u8 ALIGNED(4) Cauterize_0024_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0024.dmp");
static const u8 ALIGNED(4) Cauterize_0025_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0025.dmp");
static const u8 ALIGNED(4) Cauterize_0026_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0026.dmp");
static const u8 ALIGNED(4) Cauterize_0027_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0027.dmp");
static const u8 ALIGNED(4) Cauterize_0028_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0028.dmp");
static const u8 ALIGNED(4) Cauterize_0029_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0029.dmp");
static const u8 ALIGNED(4) Cauterize_0030_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0030.dmp");
static const u8 ALIGNED(4) Cauterize_0031_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0031.dmp");
static const u8 ALIGNED(4) Cauterize_0032_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Cauterize_0032.dmp");
static const u8 ALIGNED(4) Flash00_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash00.dmp");
static const u16 ALIGNED(4) Flash00_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Flash00_pal.dmp");
static const u8 ALIGNED(4) Flash01_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash01.dmp");
static const u8 ALIGNED(4) Flash02_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash02.dmp");
static const u8 ALIGNED(4) Flash03_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash03.dmp");
static const u8 ALIGNED(4) Flash04_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash04.dmp");
static const u8 ALIGNED(4) Flash05_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash05.dmp");
static const u8 ALIGNED(4) Flash06_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash06.dmp");
static const u8 ALIGNED(4) Flash07_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash07.dmp");
static const u8 ALIGNED(4) Flash08_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash08.dmp");
static const u8 ALIGNED(4) Flash09_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Flash09.dmp");
static const u8 ALIGNED(4) Freeze03_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze03.dmp");
static const u16 ALIGNED(4) Freeze03_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Freeze03_pal.dmp");
static const u8 ALIGNED(4) Freeze04_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze04.dmp");
static const u8 ALIGNED(4) Freeze05_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze05.dmp");
static const u8 ALIGNED(4) Freeze06_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze06.dmp");
static const u8 ALIGNED(4) Freeze07_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze07.dmp");
static const u8 ALIGNED(4) Freeze08_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze08.dmp");
static const u8 ALIGNED(4) Freeze09_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze09.dmp");
static const u8 ALIGNED(4) Freeze10_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze10.dmp");
static const u8 ALIGNED(4) Freeze11_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze11.dmp");
static const u8 ALIGNED(4) Freeze12_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze12.dmp");
static const u8 ALIGNED(4) Freeze13_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze13.dmp");
static const u8 ALIGNED(4) Freeze14_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze14.dmp");
static const u8 ALIGNED(4) Freeze15_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze15.dmp");
static const u8 ALIGNED(4) Freeze16_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze16.dmp");
static const u8 ALIGNED(4) Freeze17_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze17.dmp");
static const u8 ALIGNED(4) Freeze18_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze18.dmp");
static const u8 ALIGNED(4) Freeze19_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze19.dmp");
static const u8 ALIGNED(4) Freeze20_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze20.dmp");
static const u8 ALIGNED(4) Freeze21_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze21.dmp");
static const u8 ALIGNED(4) Freeze22_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze22.dmp");
static const u8 ALIGNED(4) Freeze23_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze23.dmp");
static const u8 ALIGNED(4) Freeze24_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze24.dmp");
static const u8 ALIGNED(4) Freeze25_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze25.dmp");
static const u8 ALIGNED(4) Freeze26_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze26.dmp");
static const u8 ALIGNED(4) Freeze27_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze27.dmp");
static const u8 ALIGNED(4) Freeze28_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze28.dmp");
static const u8 ALIGNED(4) Freeze29_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze29.dmp");
static const u8 ALIGNED(4) Freeze30_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze30.dmp");
static const u8 ALIGNED(4) Freeze31_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze31.dmp");
static const u8 ALIGNED(4) Freeze32_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze32.dmp");
static const u8 ALIGNED(4) Freeze33_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze33.dmp");
static const u8 ALIGNED(4) Freeze34_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze34.dmp");
static const u8 ALIGNED(4) Freeze35_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze35.dmp");
static const u8 ALIGNED(4) Freeze36_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze36.dmp");
static const u8 ALIGNED(4) Freeze37_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze37.dmp");
static const u8 ALIGNED(4) Freeze38_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze38.dmp");
static const u8 ALIGNED(4) Freeze39_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze39.dmp");
static const u8 ALIGNED(4) Freeze40_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze40.dmp");
static const u8 ALIGNED(4) Freeze41_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze41.dmp");
static const u8 ALIGNED(4) Freeze42_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze42.dmp");
static const u8 ALIGNED(4) Freeze43_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze43.dmp");
static const u8 ALIGNED(4) Freeze44_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze44.dmp");
static const u8 ALIGNED(4) Freeze45_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze45.dmp");
static const u8 ALIGNED(4) Freeze46_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze46.dmp");
static const u8 ALIGNED(4) Freeze47_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze47.dmp");
static const u8 ALIGNED(4) Freeze48_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze48.dmp");
static const u8 ALIGNED(4) Freeze49_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze49.dmp");
static const u8 ALIGNED(4) Freeze50_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze50.dmp");
static const u8 ALIGNED(4) Freeze51_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze51.dmp");
static const u8 ALIGNED(4) Freeze52_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze52.dmp");
static const u8 ALIGNED(4) Freeze53_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze53.dmp");
static const u8 ALIGNED(4) Freeze54_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze54.dmp");
static const u8 ALIGNED(4) Freeze55_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze55.dmp");
static const u8 ALIGNED(4) Freeze56_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze56.dmp");
static const u8 ALIGNED(4) Freeze57_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze57.dmp");
static const u8 ALIGNED(4) Freeze58_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze58.dmp");
static const u8 ALIGNED(4) Freeze59_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze59.dmp");
static const u8 ALIGNED(4) Freeze60_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze60.dmp");
static const u8 ALIGNED(4) Freeze61_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze61.dmp");
static const u8 ALIGNED(4) Freeze62_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze62.dmp");
static const u8 ALIGNED(4) Freeze63_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze63.dmp");
static const u8 ALIGNED(4) Freeze64_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze64.dmp");
static const u8 ALIGNED(4) Freeze65_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze65.dmp");
static const u8 ALIGNED(4) Freeze66_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze66.dmp");
static const u8 ALIGNED(4) Freeze67_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze67.dmp");
static const u8 ALIGNED(4) Freeze68_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze68.dmp");
static const u8 ALIGNED(4) Freeze69_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze69.dmp");
static const u8 ALIGNED(4) Freeze70_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze70.dmp");
static const u8 ALIGNED(4) Freeze71_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze71.dmp");
static const u8 ALIGNED(4) Freeze72_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze72.dmp");
static const u8 ALIGNED(4) Freeze73_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze73.dmp");
static const u8 ALIGNED(4) Freeze74_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze74.dmp");
static const u8 ALIGNED(4) Freeze75_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze75.dmp");
static const u8 ALIGNED(4) Freeze76_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Freeze76.dmp");
static const u8 ALIGNED(4) Healing0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0000.dmp");
static const u16 ALIGNED(4) Healing0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0000_pal.dmp");
static const u8 ALIGNED(4) Healing0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0001.dmp");
static const u16 ALIGNED(4) Healing0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0001_pal.dmp");
static const u8 ALIGNED(4) Healing0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0002.dmp");
static const u16 ALIGNED(4) Healing0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0002_pal.dmp");
static const u8 ALIGNED(4) Healing0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0003.dmp");
static const u16 ALIGNED(4) Healing0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0003_pal.dmp");
static const u8 ALIGNED(4) Healing0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0004.dmp");
static const u16 ALIGNED(4) Healing0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0004_pal.dmp");
static const u8 ALIGNED(4) Healing0005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0005.dmp");
static const u16 ALIGNED(4) Healing0005_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0005_pal.dmp");
static const u8 ALIGNED(4) Healing0006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0006.dmp");
static const u16 ALIGNED(4) Healing0006_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0006_pal.dmp");
static const u8 ALIGNED(4) Healing0007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Healing0007.dmp");
static const u16 ALIGNED(4) Healing0007_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Healing0007_pal.dmp");
static const u8 ALIGNED(4) Map_Axe_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_01.img.bin");
static const u8 ALIGNED(4) Map_Axe_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_02.img.bin");
static const u8 ALIGNED(4) Map_Axe_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_03.img.bin");
static const u8 ALIGNED(4) Map_Axe_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_04.img.bin");
static const u8 ALIGNED(4) Map_Axe_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_05.img.bin");
static const u8 ALIGNED(4) Map_Axe_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_06.img.bin");
static const u8 ALIGNED(4) Map_Axe_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/axe_07.img.bin");
static const u16 ALIGNED(4) Map_Axe_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/axe.pal.bin");
static const u8 ALIGNED(4) Map_BlankImg[] = INCBIN_U8("graphics/mapanim/draw/dmp/blank.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_01.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_10[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_10.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_11[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_11.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_12[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_12.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_13[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_13.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_14[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_14.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_02.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_03.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_04.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_05.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_06.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_07.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_08.img.bin");
static const u8 ALIGNED(4) Map_Bow_Img_9[] = INCBIN_U8("graphics/mapanim/draw/dmp/bow_09.img.bin");
static const u16 ALIGNED(4) Map_Bow_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/bow.pal.bin");
static const u8 ALIGNED(4) Map_Dark_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_01.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_10[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_10.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_11[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_11.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_12[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_12.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_13[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_13.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_02.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_03.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_04.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_05.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_06.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_07.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_08.img.bin");
static const u8 ALIGNED(4) Map_Dark_Img_9[] = INCBIN_U8("graphics/mapanim/draw/dmp/dark_09.img.bin");
static const u16 ALIGNED(4) Map_Dark_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/dark.pal.bin");
static const u8 ALIGNED(4) Map_Lance_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_01.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_10[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_10.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_02.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_03.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_04.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_05.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_06.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_07.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_08.img.bin");
static const u8 ALIGNED(4) Map_Lance_Img_9[] = INCBIN_U8("graphics/mapanim/draw/dmp/lance_09.img.bin");
static const u16 ALIGNED(4) Map_Lance_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/lance.pal.bin");
static const u8 ALIGNED(4) Map_Light_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_01.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_02.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_03.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_04.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_05.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_06.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_07.img.bin");
static const u8 ALIGNED(4) Map_Light_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/light_08.img.bin");
static const u16 ALIGNED(4) Map_Light_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/light.pal.bin");
static const u8 ALIGNED(4) Map_Magic_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_01.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_10[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_10.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_11[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_11.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_12[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_12.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_13[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_13.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_02.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_03.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_04.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_05.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_06.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_07.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_08.img.bin");
static const u8 ALIGNED(4) Map_Magic_Img_9[] = INCBIN_U8("graphics/mapanim/draw/dmp/magic_09.img.bin");
static const u16 ALIGNED(4) Map_Magic_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/magic.pal.bin");
static const u8 ALIGNED(4) Map_Monster_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_01.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_10[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_10.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_11[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_11.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_02.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_03.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_04.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_05.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_06.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_07.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_08.img.bin");
static const u8 ALIGNED(4) Map_Monster_Img_9[] = INCBIN_U8("graphics/mapanim/draw/dmp/monster_09.img.bin");
static const u16 ALIGNED(4) Map_Monster_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/monster.pal.bin");
static const u8 ALIGNED(4) Map_Sword_Img_1[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_01.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_2[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_02.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_3[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_03.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_4[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_04.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_5[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_05.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_6[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_06.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_7[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_07.img.bin");
static const u8 ALIGNED(4) Map_Sword_Img_8[] = INCBIN_U8("graphics/mapanim/draw/dmp/sword_08.img.bin");
static const u16 ALIGNED(4) Map_Sword_Pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/sword.pal.bin");
static const u8 ALIGNED(4) SaveScreenNumbers[] = INCBIN_U8("graphics/mapanim/draw/dmp/NumbersFromSaveScreen.dmp");
static const u16 ALIGNED(4) SaveScreenNumbersPal[] = INCBIN_U16("graphics/mapanim/draw/dmp/NumbersFromSaveScreen_pal.dmp");
static const u8 ALIGNED(4) Slashing000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing000.dmp");
static const u16 ALIGNED(4) Slashing000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Slashing000_pal.dmp");
static const u8 ALIGNED(4) Slashing001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing001.dmp");
static const u8 ALIGNED(4) Slashing002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing002.dmp");
static const u8 ALIGNED(4) Slashing003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing003.dmp");
static const u8 ALIGNED(4) Slashing004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing004.dmp");
static const u8 ALIGNED(4) Slashing005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing005.dmp");
static const u8 ALIGNED(4) Slashing006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing006.dmp");
static const u16 ALIGNED(4) Slashing006_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/Slashing006_pal.dmp");
static const u8 ALIGNED(4) Slashing007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing007.dmp");
static const u8 ALIGNED(4) Slashing008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing008.dmp");
static const u8 ALIGNED(4) Slashing009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing009.dmp");
static const u8 ALIGNED(4) Slashing010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing010.dmp");
static const u8 ALIGNED(4) Slashing011_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/Slashing011.dmp");
static const u8 ALIGNED(4) electric0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/electric0000.dmp");
static const u16 ALIGNED(4) electric0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/electric0000_pal.dmp");
static const u8 ALIGNED(4) electric0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/electric0001.dmp");
static const u16 ALIGNED(4) electric0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/electric0001_pal.dmp");
static const u8 ALIGNED(4) electric0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/electric0002.dmp");
static const u16 ALIGNED(4) electric0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/electric0002_pal.dmp");
static const u8 ALIGNED(4) electric0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/electric0003.dmp");
static const u16 ALIGNED(4) electric0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/electric0003_pal.dmp");
static const u8 ALIGNED(4) electric0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/electric0004.dmp");
static const u16 ALIGNED(4) electric0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/electric0004_pal.dmp");
static const u8 ALIGNED(4) electric0005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/electric0005.dmp");
static const u16 ALIGNED(4) electric0005_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/electric0005_pal.dmp");
static const u8 ALIGNED(4) feather0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0000.dmp");
static const u16 ALIGNED(4) feather0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/feather0000_pal.dmp");
static const u8 ALIGNED(4) feather0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0001.dmp");
static const u8 ALIGNED(4) feather0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0002.dmp");
static const u8 ALIGNED(4) feather0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0003.dmp");
static const u8 ALIGNED(4) feather0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0004.dmp");
static const u8 ALIGNED(4) feather0005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0005.dmp");
static const u8 ALIGNED(4) feather0006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0006.dmp");
static const u8 ALIGNED(4) feather0007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0007.dmp");
static const u8 ALIGNED(4) feather0008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0008.dmp");
static const u8 ALIGNED(4) feather0009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0009.dmp");
static const u8 ALIGNED(4) feather0010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0010.dmp");
static const u8 ALIGNED(4) feather0011_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0011.dmp");
static const u8 ALIGNED(4) feather0012_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0012.dmp");
static const u8 ALIGNED(4) feather0013_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0013.dmp");
static const u8 ALIGNED(4) feather0014_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0014.dmp");
static const u8 ALIGNED(4) feather0015_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/feather0015.dmp");
static const u8 ALIGNED(4) fire0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire0000.dmp");
static const u16 ALIGNED(4) fire0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire0000_pal.dmp");
static const u8 ALIGNED(4) fire0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire0001.dmp");
static const u16 ALIGNED(4) fire0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire0001_pal.dmp");
static const u8 ALIGNED(4) fire0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire0002.dmp");
static const u16 ALIGNED(4) fire0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire0002_pal.dmp");
static const u8 ALIGNED(4) fire0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire0003.dmp");
static const u16 ALIGNED(4) fire0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire0003_pal.dmp");
static const u8 ALIGNED(4) fire0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire0004.dmp");
static const u16 ALIGNED(4) fire0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire0004_pal.dmp");
static const u8 ALIGNED(4) fire_plume0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire_plume0000.dmp");
static const u16 ALIGNED(4) fire_plume0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire_plume0000_pal.dmp");
static const u8 ALIGNED(4) fire_plume0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire_plume0001.dmp");
static const u16 ALIGNED(4) fire_plume0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire_plume0001_pal.dmp");
static const u8 ALIGNED(4) fire_plume0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire_plume0002.dmp");
static const u16 ALIGNED(4) fire_plume0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire_plume0002_pal.dmp");
static const u8 ALIGNED(4) fire_plume0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire_plume0003.dmp");
static const u16 ALIGNED(4) fire_plume0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire_plume0003_pal.dmp");
static const u8 ALIGNED(4) fire_plume0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/fire_plume0004.dmp");
static const u16 ALIGNED(4) fire_plume0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/fire_plume0004_pal.dmp");
static const u8 ALIGNED(4) ghost0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ghost0000.dmp");
static const u16 ALIGNED(4) ghost0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ghost0000_pal.dmp");
static const u8 ALIGNED(4) ghost0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ghost0001.dmp");
static const u16 ALIGNED(4) ghost0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ghost0001_pal.dmp");
static const u8 ALIGNED(4) ghost0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ghost0002.dmp");
static const u16 ALIGNED(4) ghost0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ghost0002_pal.dmp");
static const u8 ALIGNED(4) ghost0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ghost0003.dmp");
static const u16 ALIGNED(4) ghost0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ghost0003_pal.dmp");
static const u8 ALIGNED(4) ghost0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ghost0004.dmp");
static const u16 ALIGNED(4) ghost0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ghost0004_pal.dmp");
static const u8 ALIGNED(4) gust0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0000.dmp");
static const u16 ALIGNED(4) gust0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0000_pal.dmp");
static const u8 ALIGNED(4) gust0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0001.dmp");
static const u16 ALIGNED(4) gust0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0001_pal.dmp");
static const u8 ALIGNED(4) gust0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0002.dmp");
static const u16 ALIGNED(4) gust0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0002_pal.dmp");
static const u8 ALIGNED(4) gust0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0003.dmp");
static const u16 ALIGNED(4) gust0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0003_pal.dmp");
static const u8 ALIGNED(4) gust0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0004.dmp");
static const u16 ALIGNED(4) gust0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0004_pal.dmp");
static const u8 ALIGNED(4) gust0005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0005.dmp");
static const u16 ALIGNED(4) gust0005_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0005_pal.dmp");
static const u8 ALIGNED(4) gust0006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0006.dmp");
static const u16 ALIGNED(4) gust0006_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0006_pal.dmp");
static const u8 ALIGNED(4) gust0007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0007.dmp");
static const u16 ALIGNED(4) gust0007_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0007_pal.dmp");
static const u8 ALIGNED(4) gust0008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0008.dmp");
static const u16 ALIGNED(4) gust0008_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0008_pal.dmp");
static const u8 ALIGNED(4) gust0009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/gust0009.dmp");
static const u16 ALIGNED(4) gust0009_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/gust0009_pal.dmp");
static const u8 ALIGNED(4) ice0000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ice0000.dmp");
static const u16 ALIGNED(4) ice0000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ice0000_pal.dmp");
static const u8 ALIGNED(4) ice0001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ice0001.dmp");
static const u16 ALIGNED(4) ice0001_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ice0001_pal.dmp");
static const u8 ALIGNED(4) ice0002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ice0002.dmp");
static const u16 ALIGNED(4) ice0002_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ice0002_pal.dmp");
static const u8 ALIGNED(4) ice0003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ice0003.dmp");
static const u16 ALIGNED(4) ice0003_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ice0003_pal.dmp");
static const u8 ALIGNED(4) ice0004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/ice0004.dmp");
static const u16 ALIGNED(4) ice0004_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/ice0004_pal.dmp");
static const u8 ALIGNED(4) small_break1_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_000.dmp");
static const u16 ALIGNED(4) small_break1_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_break1_000_pal.dmp");
static const u8 ALIGNED(4) small_break1_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_001.dmp");
static const u8 ALIGNED(4) small_break1_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_002.dmp");
static const u8 ALIGNED(4) small_break1_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_003.dmp");
static const u8 ALIGNED(4) small_break1_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_004.dmp");
static const u8 ALIGNED(4) small_break1_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_005.dmp");
static const u8 ALIGNED(4) small_break1_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_006.dmp");
static const u8 ALIGNED(4) small_break1_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_007.dmp");
static const u8 ALIGNED(4) small_break1_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_008.dmp");
static const u8 ALIGNED(4) small_break1_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_009.dmp");
static const u8 ALIGNED(4) small_break1_010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break1_010.dmp");
static const u8 ALIGNED(4) small_break2_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_000.dmp");
static const u16 ALIGNED(4) small_break2_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_break2_000_pal.dmp");
static const u8 ALIGNED(4) small_break2_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_001.dmp");
static const u8 ALIGNED(4) small_break2_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_002.dmp");
static const u8 ALIGNED(4) small_break2_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_003.dmp");
static const u8 ALIGNED(4) small_break2_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_004.dmp");
static const u8 ALIGNED(4) small_break2_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_005.dmp");
static const u8 ALIGNED(4) small_break2_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_006.dmp");
static const u8 ALIGNED(4) small_break2_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_007.dmp");
static const u8 ALIGNED(4) small_break2_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_008.dmp");
static const u8 ALIGNED(4) small_break2_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_009.dmp");
static const u8 ALIGNED(4) small_break2_010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_break2_010.dmp");
static const u8 ALIGNED(4) small_circle_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_000.dmp");
static const u16 ALIGNED(4) small_circle_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_circle_000_pal.dmp");
static const u8 ALIGNED(4) small_circle_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_001.dmp");
static const u8 ALIGNED(4) small_circle_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_002.dmp");
static const u8 ALIGNED(4) small_circle_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_003.dmp");
static const u8 ALIGNED(4) small_circle_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_004.dmp");
static const u8 ALIGNED(4) small_circle_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_005.dmp");
static const u8 ALIGNED(4) small_circle_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_006.dmp");
static const u8 ALIGNED(4) small_circle_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_circle_007.dmp");
static const u8 ALIGNED(4) small_hit1_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_000.dmp");
static const u16 ALIGNED(4) small_hit1_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_hit1_000_pal.dmp");
static const u8 ALIGNED(4) small_hit1_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_001.dmp");
static const u8 ALIGNED(4) small_hit1_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_002.dmp");
static const u8 ALIGNED(4) small_hit1_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_003.dmp");
static const u8 ALIGNED(4) small_hit1_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_004.dmp");
static const u8 ALIGNED(4) small_hit1_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_005.dmp");
static const u8 ALIGNED(4) small_hit1_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_006.dmp");
static const u8 ALIGNED(4) small_hit1_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_007.dmp");
static const u8 ALIGNED(4) small_hit1_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_008.dmp");
static const u8 ALIGNED(4) small_hit1_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit1_009.dmp");
static const u8 ALIGNED(4) small_hit2_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_000.dmp");
static const u16 ALIGNED(4) small_hit2_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_hit2_000_pal.dmp");
static const u8 ALIGNED(4) small_hit2_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_001.dmp");
static const u8 ALIGNED(4) small_hit2_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_002.dmp");
static const u8 ALIGNED(4) small_hit2_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_003.dmp");
static const u8 ALIGNED(4) small_hit2_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_004.dmp");
static const u8 ALIGNED(4) small_hit2_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_005.dmp");
static const u8 ALIGNED(4) small_hit2_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_006.dmp");
static const u8 ALIGNED(4) small_hit2_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_007.dmp");
static const u8 ALIGNED(4) small_hit2_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_008.dmp");
static const u8 ALIGNED(4) small_hit2_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_hit2_009.dmp");
static const u8 ALIGNED(4) small_impact1_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_000.dmp");
static const u16 ALIGNED(4) small_impact1_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_impact1_000_pal.dmp");
static const u8 ALIGNED(4) small_impact1_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_001.dmp");
static const u8 ALIGNED(4) small_impact1_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_002.dmp");
static const u8 ALIGNED(4) small_impact1_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_003.dmp");
static const u8 ALIGNED(4) small_impact1_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_004.dmp");
static const u8 ALIGNED(4) small_impact1_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_005.dmp");
static const u8 ALIGNED(4) small_impact1_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_006.dmp");
static const u8 ALIGNED(4) small_impact1_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_007.dmp");
static const u8 ALIGNED(4) small_impact1_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_008.dmp");
static const u8 ALIGNED(4) small_impact1_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_009.dmp");
static const u8 ALIGNED(4) small_impact1_010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact1_010.dmp");
static const u8 ALIGNED(4) small_impact2_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_000.dmp");
static const u16 ALIGNED(4) small_impact2_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_impact2_000_pal.dmp");
static const u8 ALIGNED(4) small_impact2_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_001.dmp");
static const u8 ALIGNED(4) small_impact2_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_002.dmp");
static const u8 ALIGNED(4) small_impact2_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_003.dmp");
static const u8 ALIGNED(4) small_impact2_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_004.dmp");
static const u8 ALIGNED(4) small_impact2_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_005.dmp");
static const u8 ALIGNED(4) small_impact2_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_006.dmp");
static const u8 ALIGNED(4) small_impact2_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_007.dmp");
static const u8 ALIGNED(4) small_impact2_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_008.dmp");
static const u8 ALIGNED(4) small_impact2_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_009.dmp");
static const u8 ALIGNED(4) small_impact2_010_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_impact2_010.dmp");
static const u8 ALIGNED(4) small_shards1_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_000.dmp");
static const u16 ALIGNED(4) small_shards1_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_shards1_000_pal.dmp");
static const u8 ALIGNED(4) small_shards1_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_001.dmp");
static const u8 ALIGNED(4) small_shards1_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_002.dmp");
static const u8 ALIGNED(4) small_shards1_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_003.dmp");
static const u8 ALIGNED(4) small_shards1_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_004.dmp");
static const u8 ALIGNED(4) small_shards1_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_005.dmp");
static const u8 ALIGNED(4) small_shards1_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_006.dmp");
static const u8 ALIGNED(4) small_shards1_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_007.dmp");
static const u8 ALIGNED(4) small_shards1_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_008.dmp");
static const u8 ALIGNED(4) small_shards1_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards1_009.dmp");
static const u8 ALIGNED(4) small_shards2_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_000.dmp");
static const u16 ALIGNED(4) small_shards2_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_shards2_000_pal.dmp");
static const u8 ALIGNED(4) small_shards2_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_001.dmp");
static const u8 ALIGNED(4) small_shards2_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_002.dmp");
static const u8 ALIGNED(4) small_shards2_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_003.dmp");
static const u8 ALIGNED(4) small_shards2_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_004.dmp");
static const u8 ALIGNED(4) small_shards2_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_005.dmp");
static const u8 ALIGNED(4) small_shards2_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_006.dmp");
static const u8 ALIGNED(4) small_shards2_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_007.dmp");
static const u8 ALIGNED(4) small_shards2_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_008.dmp");
static const u8 ALIGNED(4) small_shards2_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_shards2_009.dmp");
static const u8 ALIGNED(4) small_splash1_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_000.dmp");
static const u16 ALIGNED(4) small_splash1_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_splash1_000_pal.dmp");
static const u8 ALIGNED(4) small_splash1_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_001.dmp");
static const u8 ALIGNED(4) small_splash1_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_002.dmp");
static const u8 ALIGNED(4) small_splash1_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_003.dmp");
static const u8 ALIGNED(4) small_splash1_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_004.dmp");
static const u8 ALIGNED(4) small_splash1_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_005.dmp");
static const u8 ALIGNED(4) small_splash1_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_006.dmp");
static const u8 ALIGNED(4) small_splash1_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash1_007.dmp");
static const u8 ALIGNED(4) small_splash2_000_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_000.dmp");
static const u16 ALIGNED(4) small_splash2_000_pal[] = INCBIN_U16("graphics/mapanim/draw/dmp/small_splash2_000_pal.dmp");
static const u8 ALIGNED(4) small_splash2_001_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_001.dmp");
static const u8 ALIGNED(4) small_splash2_002_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_002.dmp");
static const u8 ALIGNED(4) small_splash2_003_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_003.dmp");
static const u8 ALIGNED(4) small_splash2_004_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_004.dmp");
static const u8 ALIGNED(4) small_splash2_005_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_005.dmp");
static const u8 ALIGNED(4) small_splash2_006_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_006.dmp");
static const u8 ALIGNED(4) small_splash2_007_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_007.dmp");
static const u8 ALIGNED(4) small_splash2_008_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_008.dmp");
static const u8 ALIGNED(4) small_splash2_009_Data[] = INCBIN_U8("graphics/mapanim/draw/dmp/small_splash2_009.dmp");

static const struct DrawMapAnimFrame Break1_Small_Anim[] = {
    { 2, 0, small_break1_000_Data, small_break1_000_pal },
    { 2, 0, small_break1_001_Data, small_break1_000_pal },
    { 2, 0, small_break1_002_Data, small_break1_000_pal },
    { 3, 0, small_break1_003_Data, small_break1_000_pal },
    { 3, 0, small_break1_004_Data, small_break1_000_pal },
    { 3, 0, small_break1_005_Data, small_break1_000_pal },
    { 3, 0, small_break1_006_Data, small_break1_000_pal },
    { 3, 0, small_break1_007_Data, small_break1_000_pal },
    { 3, 0, small_break1_008_Data, small_break1_000_pal },
    { 2, 0, small_break1_009_Data, small_break1_000_pal },
    { 2, 0, small_break1_010_Data, small_break1_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Break2_Small_Anim[] = {
    { 2, 0, small_break2_000_Data, small_break2_000_pal },
    { 2, 0, small_break2_001_Data, small_break2_000_pal },
    { 2, 0, small_break2_002_Data, small_break2_000_pal },
    { 3, 0, small_break2_003_Data, small_break2_000_pal },
    { 3, 0, small_break2_004_Data, small_break2_000_pal },
    { 3, 0, small_break2_005_Data, small_break2_000_pal },
    { 3, 0, small_break2_006_Data, small_break2_000_pal },
    { 3, 0, small_break2_007_Data, small_break2_000_pal },
    { 3, 0, small_break2_008_Data, small_break2_000_pal },
    { 2, 0, small_break2_009_Data, small_break2_000_pal },
    { 2, 0, small_break2_010_Data, small_break2_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Cauterize_Anim[] = {
    { 1, 0, Cauterize_0001_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0002_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0003_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0004_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0005_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0006_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0007_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0008_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0009_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0010_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0011_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0012_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0013_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0014_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0015_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0016_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0017_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0018_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0019_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0020_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0021_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0022_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0023_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0024_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0025_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0026_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0027_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0028_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0029_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0030_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0031_Data, Cauterize_0001_pal },
    { 1, 0, Cauterize_0032_Data, Cauterize_0001_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Circle_Small_Anim[] = {
    { 3, 0, small_circle_000_Data, small_circle_000_pal },
    { 3, 0, small_circle_001_Data, small_circle_000_pal },
    { 4, 0, small_circle_002_Data, small_circle_000_pal },
    { 4, 0, small_circle_003_Data, small_circle_000_pal },
    { 4, 0, small_circle_004_Data, small_circle_000_pal },
    { 4, 0, small_circle_005_Data, small_circle_000_pal },
    { 3, 0, small_circle_006_Data, small_circle_000_pal },
    { 3, 0, small_circle_007_Data, small_circle_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Feather_Anim[] = {
    { 1, 0, feather0000_Data, feather0000_pal },
    { 1, 0, feather0001_Data, feather0000_pal },
    { 2, 0, feather0002_Data, feather0000_pal },
    { 2, 0, feather0003_Data, feather0000_pal },
    { 2, 0, feather0004_Data, feather0000_pal },
    { 2, 0, feather0005_Data, feather0000_pal },
    { 2, 0, feather0006_Data, feather0000_pal },
    { 2, 0, feather0007_Data, feather0000_pal },
    { 2, 0, feather0008_Data, feather0000_pal },
    { 2, 0, feather0009_Data, feather0000_pal },
    { 2, 0, feather0010_Data, feather0000_pal },
    { 2, 0, feather0011_Data, feather0000_pal },
    { 2, 0, feather0012_Data, feather0000_pal },
    { 2, 0, feather0013_Data, feather0000_pal },
    { 1, 0, feather0014_Data, feather0000_pal },
    { 1, 0, feather0015_Data, feather0000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Flash_Anim[] = {
    { 2, 0, Flash00_Data, Flash00_pal },
    { 3, 0, Flash01_Data, Flash00_pal },
    { 3, 0, Flash02_Data, Flash00_pal },
    { 3, 0, Flash03_Data, Flash00_pal },
    { 3, 0, Flash04_Data, Flash00_pal },
    { 3, 0, Flash05_Data, Flash00_pal },
    { 3, 0, Flash06_Data, Flash00_pal },
    { 3, 0, Flash07_Data, Flash00_pal },
    { 3, 0, Flash08_Data, Flash00_pal },
    { 2, 0, Flash09_Data, Flash00_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Freeze_Anim[] = {
    { 1, 0, Freeze03_Data, Freeze03_pal },
    { 1, 0, Freeze04_Data, Freeze03_pal },
    { 1, 0, Freeze05_Data, Freeze03_pal },
    { 1, 0, Freeze06_Data, Freeze03_pal },
    { 1, 0, Freeze07_Data, Freeze03_pal },
    { 1, 0, Freeze08_Data, Freeze03_pal },
    { 1, 0, Freeze09_Data, Freeze03_pal },
    { 1, 0, Freeze10_Data, Freeze03_pal },
    { 1, 0, Freeze11_Data, Freeze03_pal },
    { 1, 0, Freeze12_Data, Freeze03_pal },
    { 1, 0, Freeze13_Data, Freeze03_pal },
    { 1, 0, Freeze14_Data, Freeze03_pal },
    { 1, 0, Freeze15_Data, Freeze03_pal },
    { 1, 0, Freeze16_Data, Freeze03_pal },
    { 1, 0, Freeze17_Data, Freeze03_pal },
    { 1, 0, Freeze18_Data, Freeze03_pal },
    { 1, 0, Freeze19_Data, Freeze03_pal },
    { 1, 0, Freeze20_Data, Freeze03_pal },
    { 1, 0, Freeze21_Data, Freeze03_pal },
    { 1, 0, Freeze22_Data, Freeze03_pal },
    { 1, 0, Freeze23_Data, Freeze03_pal },
    { 1, 0, Freeze24_Data, Freeze03_pal },
    { 1, 0, Freeze25_Data, Freeze03_pal },
    { 1, 0, Freeze26_Data, Freeze03_pal },
    { 1, 0, Freeze27_Data, Freeze03_pal },
    { 1, 0, Freeze28_Data, Freeze03_pal },
    { 1, 0, Freeze29_Data, Freeze03_pal },
    { 1, 0, Freeze30_Data, Freeze03_pal },
    { 1, 0, Freeze31_Data, Freeze03_pal },
    { 1, 0, Freeze32_Data, Freeze03_pal },
    { 1, 0, Freeze33_Data, Freeze03_pal },
    { 1, 0, Freeze34_Data, Freeze03_pal },
    { 1, 0, Freeze35_Data, Freeze03_pal },
    { 1, 0, Freeze36_Data, Freeze03_pal },
    { 1, 0, Freeze37_Data, Freeze03_pal },
    { 1, 0, Freeze38_Data, Freeze03_pal },
    { 1, 0, Freeze39_Data, Freeze03_pal },
    { 1, 0, Freeze40_Data, Freeze03_pal },
    { 1, 0, Freeze41_Data, Freeze03_pal },
    { 1, 0, Freeze42_Data, Freeze03_pal },
    { 1, 0, Freeze43_Data, Freeze03_pal },
    { 1, 0, Freeze44_Data, Freeze03_pal },
    { 1, 0, Freeze45_Data, Freeze03_pal },
    { 1, 0, Freeze46_Data, Freeze03_pal },
    { 1, 0, Freeze47_Data, Freeze03_pal },
    { 1, 0, Freeze48_Data, Freeze03_pal },
    { 1, 0, Freeze49_Data, Freeze03_pal },
    { 1, 0, Freeze50_Data, Freeze03_pal },
    { 1, 0, Freeze51_Data, Freeze03_pal },
    { 1, 0, Freeze52_Data, Freeze03_pal },
    { 1, 0, Freeze53_Data, Freeze03_pal },
    { 1, 0, Freeze54_Data, Freeze03_pal },
    { 1, 0, Freeze55_Data, Freeze03_pal },
    { 1, 0, Freeze56_Data, Freeze03_pal },
    { 1, 0, Freeze57_Data, Freeze03_pal },
    { 1, 0, Freeze58_Data, Freeze03_pal },
    { 1, 0, Freeze59_Data, Freeze03_pal },
    { 1, 0, Freeze60_Data, Freeze03_pal },
    { 1, 0, Freeze61_Data, Freeze03_pal },
    { 1, 0, Freeze62_Data, Freeze03_pal },
    { 1, 0, Freeze63_Data, Freeze03_pal },
    { 1, 0, Freeze64_Data, Freeze03_pal },
    { 1, 0, Freeze65_Data, Freeze03_pal },
    { 1, 0, Freeze66_Data, Freeze03_pal },
    { 1, 0, Freeze67_Data, Freeze03_pal },
    { 1, 0, Freeze68_Data, Freeze03_pal },
    { 1, 0, Freeze69_Data, Freeze03_pal },
    { 1, 0, Freeze70_Data, Freeze03_pal },
    { 1, 0, Freeze71_Data, Freeze03_pal },
    { 1, 0, Freeze72_Data, Freeze03_pal },
    { 1, 0, Freeze73_Data, Freeze03_pal },
    { 1, 0, Freeze74_Data, Freeze03_pal },
    { 1, 0, Freeze75_Data, Freeze03_pal },
    { 1, 0, Freeze76_Data, Freeze03_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Hit1_Small_Anim[] = {
    { 2, 0, small_hit1_000_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_001_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_002_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_003_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_004_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_005_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_006_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_007_Data, small_hit1_000_pal },
    { 3, 0, small_hit1_008_Data, small_hit1_000_pal },
    { 2, 0, small_hit1_009_Data, small_hit1_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Hit2_Small_Anim[] = {
    { 2, 0, small_hit2_000_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_001_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_002_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_003_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_004_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_005_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_006_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_007_Data, small_hit2_000_pal },
    { 3, 0, small_hit2_008_Data, small_hit2_000_pal },
    { 2, 0, small_hit2_009_Data, small_hit2_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Impact1_Small_Anim[] = {
    { 2, 0, small_impact1_000_Data, small_impact1_000_pal },
    { 2, 0, small_impact1_001_Data, small_impact1_000_pal },
    { 2, 0, small_impact1_002_Data, small_impact1_000_pal },
    { 3, 0, small_impact1_003_Data, small_impact1_000_pal },
    { 3, 0, small_impact1_004_Data, small_impact1_000_pal },
    { 3, 0, small_impact1_005_Data, small_impact1_000_pal },
    { 3, 0, small_impact1_006_Data, small_impact1_000_pal },
    { 3, 0, small_impact1_007_Data, small_impact1_000_pal },
    { 3, 0, small_impact1_008_Data, small_impact1_000_pal },
    { 2, 0, small_impact1_009_Data, small_impact1_000_pal },
    { 2, 0, small_impact1_010_Data, small_impact1_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Impact2_Small_Anim[] = {
    { 2, 0, small_impact2_000_Data, small_impact2_000_pal },
    { 2, 0, small_impact2_001_Data, small_impact2_000_pal },
    { 2, 0, small_impact2_002_Data, small_impact2_000_pal },
    { 3, 0, small_impact2_003_Data, small_impact2_000_pal },
    { 3, 0, small_impact2_004_Data, small_impact2_000_pal },
    { 3, 0, small_impact2_005_Data, small_impact2_000_pal },
    { 3, 0, small_impact2_006_Data, small_impact2_000_pal },
    { 3, 0, small_impact2_007_Data, small_impact2_000_pal },
    { 3, 0, small_impact2_008_Data, small_impact2_000_pal },
    { 2, 0, small_impact2_009_Data, small_impact2_000_pal },
    { 2, 0, small_impact2_010_Data, small_impact2_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Axe_FrameData[] = {
    { 2, 0, Map_Axe_Img_1, Map_Axe_Pal },
    { 2, 0, Map_Axe_Img_2, Map_Axe_Pal },
    { 2, 0, Map_Axe_Img_3, Map_Axe_Pal },
    { 2, 0, Map_Axe_Img_4, Map_Axe_Pal },
    { 2, 0, Map_Axe_Img_5, Map_Axe_Pal },
    { 2, 0, Map_Axe_Img_6, Map_Axe_Pal },
    { 2, 0, Map_Axe_Img_7, Map_Axe_Pal },
    { 14, 0, Map_BlankImg, Map_Axe_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Bow_FrameData[] = {
    { 2, 0, Map_Bow_Img_1, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_2, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_3, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_4, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_5, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_6, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_7, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_8, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_9, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_10, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_11, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_12, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_13, Map_Bow_Pal },
    { 2, 0, Map_Bow_Img_14, Map_Bow_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Dark_FrameData[] = {
    { 2, 0, Map_Dark_Img_1, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_2, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_3, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_4, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_5, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_6, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_7, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_8, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_9, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_10, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_11, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_12, Map_Dark_Pal },
    { 2, 0, Map_Dark_Img_13, Map_Dark_Pal },
    { 2, 0, Map_BlankImg, Map_Dark_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Lance_FrameData[] = {
    { 2, 0, Map_Lance_Img_1, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_2, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_3, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_4, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_5, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_6, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_7, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_8, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_9, Map_Lance_Pal },
    { 2, 0, Map_Lance_Img_10, Map_Lance_Pal },
    { 8, 0, Map_BlankImg, Map_Lance_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Light_FrameData[] = {
    { 2, 0, Map_Light_Img_1, Map_Light_Pal },
    { 2, 0, Map_Light_Img_2, Map_Light_Pal },
    { 2, 0, Map_Light_Img_3, Map_Light_Pal },
    { 2, 0, Map_Light_Img_4, Map_Light_Pal },
    { 2, 0, Map_Light_Img_5, Map_Light_Pal },
    { 2, 0, Map_Light_Img_6, Map_Light_Pal },
    { 2, 0, Map_Light_Img_7, Map_Light_Pal },
    { 2, 0, Map_Light_Img_8, Map_Light_Pal },
    { 12, 0, Map_BlankImg, Map_Light_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Magic_FrameData[] = {
    { 2, 0, Map_Magic_Img_1, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_2, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_3, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_4, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_5, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_6, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_7, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_8, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_9, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_10, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_11, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_12, Map_Magic_Pal },
    { 2, 0, Map_Magic_Img_13, Map_Magic_Pal },
    { 2, 0, Map_BlankImg, Map_Magic_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Monster_FrameData[] = {
    { 2, 0, Map_Monster_Img_1, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_2, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_3, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_4, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_5, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_6, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_7, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_8, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_9, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_10, Map_Monster_Pal },
    { 2, 0, Map_Monster_Img_11, Map_Monster_Pal },
    { 6, 0, Map_BlankImg, Map_Monster_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Map_Sword_FrameData[] = {
    { 2, 0, Map_Sword_Img_1, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_2, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_3, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_4, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_5, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_6, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_7, Map_Sword_Pal },
    { 2, 0, Map_Sword_Img_8, Map_Sword_Pal },
    { 12, 0, Map_BlankImg, Map_Sword_Pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Shards1_Small_Anim[] = {
    { 2, 0, small_shards1_000_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_001_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_002_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_003_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_004_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_005_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_006_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_007_Data, small_shards1_000_pal },
    { 3, 0, small_shards1_008_Data, small_shards1_000_pal },
    { 2, 0, small_shards1_009_Data, small_shards1_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Shards2_Small_Anim[] = {
    { 2, 0, small_shards2_000_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_001_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_002_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_003_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_004_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_005_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_006_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_007_Data, small_shards2_000_pal },
    { 3, 0, small_shards2_008_Data, small_shards2_000_pal },
    { 2, 0, small_shards2_009_Data, small_shards2_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Slashing_A_Anim[] = {
    { 4, 0, Slashing000_Data, Slashing000_pal },
    { 5, 0, Slashing001_Data, Slashing000_pal },
    { 5, 0, Slashing002_Data, Slashing000_pal },
    { 5, 0, Slashing003_Data, Slashing000_pal },
    { 5, 0, Slashing004_Data, Slashing000_pal },
    { 4, 0, Slashing005_Data, Slashing000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Slashing_B_Anim[] = {
    { 4, 0, Slashing006_Data, Slashing006_pal },
    { 5, 0, Slashing007_Data, Slashing006_pal },
    { 5, 0, Slashing008_Data, Slashing006_pal },
    { 5, 0, Slashing009_Data, Slashing006_pal },
    { 5, 0, Slashing010_Data, Slashing006_pal },
    { 4, 0, Slashing011_Data, Slashing006_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Splash1_Small_Anim[] = {
    { 3, 0, small_splash1_000_Data, small_splash1_000_pal },
    { 3, 0, small_splash1_001_Data, small_splash1_000_pal },
    { 4, 0, small_splash1_002_Data, small_splash1_000_pal },
    { 4, 0, small_splash1_003_Data, small_splash1_000_pal },
    { 4, 0, small_splash1_004_Data, small_splash1_000_pal },
    { 4, 0, small_splash1_005_Data, small_splash1_000_pal },
    { 3, 0, small_splash1_006_Data, small_splash1_000_pal },
    { 3, 0, small_splash1_007_Data, small_splash1_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame Splash2_Small_Anim[] = {
    { 2, 0, small_splash2_000_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_001_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_002_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_003_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_004_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_005_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_006_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_007_Data, small_splash2_000_pal },
    { 3, 0, small_splash2_008_Data, small_splash2_000_pal },
    { 2, 0, small_splash2_009_Data, small_splash2_000_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame electric_Anim[] = {
    { 4, 0, electric0000_Data, electric0000_pal },
    { 4, 0, electric0001_Data, electric0001_pal },
    { 4, 0, electric0000_Data, electric0000_pal },
    { 4, 0, electric0001_Data, electric0001_pal },
    { 4, 0, electric0002_Data, electric0002_pal },
    { 4, 0, electric0003_Data, electric0003_pal },
    { 4, 0, electric0002_Data, electric0002_pal },
    { 4, 0, electric0003_Data, electric0003_pal },
    { 3, 0, electric0004_Data, electric0004_pal },
    { 3, 0, electric0005_Data, electric0005_pal },
    { 3, 0, electric0004_Data, electric0004_pal },
    { 3, 0, electric0005_Data, electric0005_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame fire_Anim[] = {
    { 8, 0, fire0000_Data, fire0000_pal },
    { 8, 0, fire0001_Data, fire0001_pal },
    { 8, 0, fire0002_Data, fire0002_pal },
    { 8, 0, fire0003_Data, fire0003_pal },
    { 8, 0, fire0004_Data, fire0004_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame fire_plume_Anim[] = {
    { 8, 0, fire_plume0000_Data, fire_plume0000_pal },
    { 8, 0, fire_plume0001_Data, fire_plume0001_pal },
    { 8, 0, fire_plume0002_Data, fire_plume0002_pal },
    { 8, 0, fire_plume0003_Data, fire_plume0003_pal },
    { 8, 0, fire_plume0004_Data, fire_plume0004_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame ghost_Anim[] = {
    { 8, 0, ghost0000_Data, ghost0000_pal },
    { 8, 0, ghost0001_Data, ghost0001_pal },
    { 8, 0, ghost0002_Data, ghost0002_pal },
    { 8, 0, ghost0003_Data, ghost0003_pal },
    { 8, 0, ghost0004_Data, ghost0004_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame gust_Anim[] = {
    { 4, 0, gust0000_Data, gust0000_pal },
    { 4, 0, gust0001_Data, gust0001_pal },
    { 4, 0, gust0002_Data, gust0002_pal },
    { 4, 0, gust0003_Data, gust0003_pal },
    { 4, 0, gust0004_Data, gust0004_pal },
    { 4, 0, gust0005_Data, gust0005_pal },
    { 4, 0, gust0006_Data, gust0006_pal },
    { 4, 0, gust0007_Data, gust0007_pal },
    { 4, 0, gust0008_Data, gust0008_pal },
    { 4, 0, gust0009_Data, gust0009_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame healing_Anim[] = {
    { 5, 0, Healing0000_Data, Healing0000_pal },
    { 5, 0, Healing0001_Data, Healing0001_pal },
    { 5, 0, Healing0002_Data, Healing0002_pal },
    { 5, 0, Healing0003_Data, Healing0003_pal },
    { 5, 0, Healing0004_Data, Healing0004_pal },
    { 5, 0, Healing0005_Data, Healing0005_pal },
    { 5, 0, Healing0006_Data, Healing0006_pal },
    { 5, 0, Healing0007_Data, Healing0007_pal },
    { 0, 0, NULL, NULL },
};

static const struct DrawMapAnimFrame ice_Anim[] = {
    { 8, 0, ice0000_Data, ice0000_pal },
    { 8, 0, ice0001_Data, ice0001_pal },
    { 8, 0, ice0002_Data, ice0002_pal },
    { 8, 0, ice0003_Data, ice0003_pal },
    { 8, 0, ice0004_Data, ice0004_pal },
    { 0, 0, NULL, NULL },
};

const struct DrawMapAnimFrame * const gDrawMapAnimTable[DRAW_MAP_ANIM_COUNT] = {
    [DRAW_MAP_ANIM_NONE] = NULL,
    [DRAW_MAP_ANIM_BREAK1] = Break1_Small_Anim,
    [DRAW_MAP_ANIM_BREAK2] = Break2_Small_Anim,
    [DRAW_MAP_ANIM_CIRCLE] = Circle_Small_Anim,
    [DRAW_MAP_ANIM_HIT1] = Hit1_Small_Anim,
    [DRAW_MAP_ANIM_HIT2] = Hit2_Small_Anim,
    [DRAW_MAP_ANIM_IMPACT1] = Impact1_Small_Anim,
    [DRAW_MAP_ANIM_IMPACT2] = Impact2_Small_Anim,
    [DRAW_MAP_ANIM_SHARDS1] = Shards1_Small_Anim,
    [DRAW_MAP_ANIM_SHARDS2] = Shards2_Small_Anim,
    [DRAW_MAP_ANIM_SPLASH1] = Splash1_Small_Anim,
    [DRAW_MAP_ANIM_SPLASH2] = Splash2_Small_Anim,
    [DRAW_MAP_ANIM_THIN_SLASH] = Slashing_A_Anim,
    [DRAW_MAP_ANIM_THICK_SLASH] = Slashing_B_Anim,
    [DRAW_MAP_ANIM_FLASH] = Flash_Anim,
    [DRAW_MAP_ANIM_FREEZE] = Freeze_Anim,
    [DRAW_MAP_ANIM_FEATHER] = Feather_Anim,
    [DRAW_MAP_ANIM_CAUTERIZE] = Cauterize_Anim,
    [DRAW_MAP_ANIM_HEAL] = healing_Anim,
    [DRAW_MAP_ANIM_FIRE] = fire_Anim,
    [DRAW_MAP_ANIM_THUNDER] = electric_Anim,
    [DRAW_MAP_ANIM_ICE] = ice_Anim,
    [DRAW_MAP_ANIM_WIND] = gust_Anim,
    [DRAW_MAP_ANIM_ELFIRE] = fire_plume_Anim,
    [DRAW_MAP_ANIM_DARK] = ghost_Anim,
    [DRAW_MAP_ANIM_MAP_SWORD] = Map_Sword_FrameData,
    [DRAW_MAP_ANIM_MAP_LANCE] = Map_Lance_FrameData,
    [DRAW_MAP_ANIM_MAP_AXE] = Map_Axe_FrameData,
    [DRAW_MAP_ANIM_MAP_BOW] = Map_Bow_FrameData,
    [DRAW_MAP_ANIM_MAP_MAGIC] = Map_Magic_FrameData,
    [DRAW_MAP_ANIM_MAP_LIGHT] = Map_Light_FrameData,
    [DRAW_MAP_ANIM_MAP_DARK] = Map_Dark_FrameData,
    [DRAW_MAP_ANIM_MAP_MONSTER] = Map_Monster_FrameData,
};

const u8 * const gDrawMapAnimNumbersImg = SaveScreenNumbers;
const u16 * const gDrawMapAnimNumbersPal = SaveScreenNumbersPal;

#endif /* FE8_DRAW_MAP_ANIMS */