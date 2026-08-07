#ifndef GUARD_GLOBAL_H
#define GUARD_GLOBAL_H

#include <limits.h>

#if UCHAR_MAX != 0xFF
#error "host test requires 8-bit bytes"
#endif

#if UINT_MAX != 0xFFFFFFFFu
#error "host test requires a 32-bit unsigned int"
#endif

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#include "expansion_config.h"

#endif /* GUARD_GLOBAL_H */
