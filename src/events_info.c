#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventscript.h"
#include "EAstdlib.h"
#include "chapterdata.h"
#include "constants/event-flags.h"
#include "bmunit.h"
#include "bmtrap.h"

#if FE8_CUSTOM_CAMPAIGN
#include "events/prologue.h"
#include "events/ch1.h"
#else
#include "events/vanilla/prologue-eventinfo.h"
#include "events/vanilla/ch1-eventinfo.h"
#endif

#include "events/vanilla/ch2-eventinfo.h"

/* The excluded header above is not actually a binary-layout prefix of
 * this translation unit's .data -- the "events/prologue.h" and
 * "events/ch1.h" includes above emit Prologue/Chapter-1
 * event-list data first, ahead of Chapter 2. To let
 * build/generated/data/data_ch2_eventlists.o(.data) slot in at the exact
 * original Chapter-2 address (between the still-hand Prologue/Ch1 data
 * and this file's own Chapter 3+ data) without shifting either side,
 * everything from here to end-of-file is redirected into a distinctly
 * named section so ldscript.txt can place the generated object between
 * the two pieces of this same object file's data. See ldscript.txt and
 * docs/generated_data.md's "eventlists" section. */
#undef CONST_DATA
#define CONST_DATA SECTION(".data.ch2eventtail")

#include "events/vanilla/ch3-eventinfo.h"
#include "events/vanilla/ch4-eventinfo.h"
#include "events/vanilla/ch5-eventinfo.h"
#include "events/vanilla/ch5x-eventinfo.h"
#include "events/vanilla/ch6-eventinfo.h"
#include "events/vanilla/ch7-eventinfo.h"
#include "events/vanilla/ch8-eventinfo.h"

#include "events/vanilla/ch9a-eventinfo.h"
#include "events/vanilla/ch10a-eventinfo.h"
#include "events/vanilla/ch11a-eventinfo.h"
#include "events/vanilla/ch12a-eventinfo.h"
#include "events/vanilla/ch13a-eventinfo.h"
#include "events/vanilla/ch14a-eventinfo.h"
#include "events/vanilla/ch15a-eventinfo.h"
#include "events/vanilla/ch16a-eventinfo.h"
#include "events/vanilla/ch17a-eventinfo.h"
#include "events/vanilla/ch18a-eventinfo.h"
#include "events/vanilla/ch19a-eventinfo.h"
#include "events/vanilla/ch20a-eventinfo.h"
#include "events/vanilla/ch21a-eventinfo.h"
#include "events/vanilla/ch21xa-eventinfo.h"

#include "events/vanilla/ch9b-eventinfo.h"
#include "events/vanilla/ch10b-eventinfo.h"
#include "events/vanilla/ch11b-eventinfo.h"
#include "events/vanilla/ch12b-eventinfo.h"
#include "events/vanilla/ch13b-eventinfo.h"
#include "events/vanilla/ch14b-eventinfo.h"
#include "events/vanilla/ch15b-eventinfo.h"
#include "events/vanilla/ch16b-eventinfo.h"
#include "events/vanilla/ch17b-eventinfo.h"
#include "events/vanilla/ch18b-eventinfo.h"
#include "events/vanilla/ch19b-eventinfo.h"
#include "events/vanilla/ch20b-eventinfo.h"
#include "events/vanilla/ch21b-eventinfo.h"
#include "events/vanilla/ch21xb-eventinfo.h"

#include "events/vanilla/tower1-eventinfo.h"
#include "events/vanilla/tower2-eventinfo.h"
#include "events/vanilla/tower3-eventinfo.h"
#include "events/vanilla/tower4-eventinfo.h"
#include "events/vanilla/tower5-eventinfo.h"
#include "events/vanilla/tower6-eventinfo.h"
#include "events/vanilla/tower7-eventinfo.h"
#include "events/vanilla/tower8-eventinfo.h"

#include "events/vanilla/ruin1-eventinfo.h"
#include "events/vanilla/ruin2-eventinfo.h"
#include "events/vanilla/ruin3-eventinfo.h"
#include "events/vanilla/ruin4-eventinfo.h"
#include "events/vanilla/ruin5-eventinfo.h"
#include "events/vanilla/ruin6-eventinfo.h"
#include "events/vanilla/ruin7-eventinfo.h"
#include "events/vanilla/ruin8-eventinfo.h"
#include "events/vanilla/ruin9-eventinfo.h"
#include "events/vanilla/ruin10-eventinfo.h"

#include "events/vanilla/lordsplit-eventinfo.h"
#include "events/vanilla/MelkaenCoast-eventinfo.h"
#include "events/vanilla/chunk3B-eventinfo.h"
#include "events/vanilla/debugmap-eventinfo.h"
