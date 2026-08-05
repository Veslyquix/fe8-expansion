#ifndef GUARD_GAME_LOCALIZATION_HOST_GLOBAL_H
#define GUARD_GAME_LOCALIZATION_HOST_GLOBAL_H

#include <stddef.h>
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#ifndef SECTION
#define SECTION(name) __attribute__((section(name)))
#endif

#endif /* GUARD_GAME_LOCALIZATION_HOST_GLOBAL_H */
