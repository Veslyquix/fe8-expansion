#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "eventscript.h"
#include "EAstdlib.h"
#include "constants/characters.h"
#include "constants/classes.h"

CONST_DATA EventScr EventScr_WM_FadeCommon[] = {
    WmEvtFadeInDark(60) // WM_SATURATE_COLORS
    WM_SHOWTEXTWINDOW(40, 0x0001)
    WM_WAITFORTEXT
    WmEvtWaitFadeInDark // ENOSUPP in EAstdlib
    ENDA
};

#if !FE8_CUSTOM_CAMPAIGN
#include "events/vanilla/prologue-wm.h"
#include "events/vanilla/ch1-wm.h"
#endif
#include "events/vanilla/ch2-wm.h"
#include "events/vanilla/ch3-wm.h"
#include "events/vanilla/ch4-wm.h"
#include "events/vanilla/ch5-wm.h"
#include "events/vanilla/ch6-wm.h"
#include "events/vanilla/ch7-wm.h"
#include "events/vanilla/ch8-wm.h"
#include "events/vanilla/messed-eventscr-wm.h"
