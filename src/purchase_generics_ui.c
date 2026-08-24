#include "global.h"

#if FE8_PURCHASE_GENERICS 

asm(
    ".section .rodata\n"
    ".balign 4\n"
    ".global Tsa_PurchaseGenericPortraitBox\n"
    "Tsa_PurchaseGenericPortraitBox:\n"
    ".incbin \"graphics/purchase_generics/BlueBoxPortrait.dmp\"\n"
    ".balign 4\n"
    ".global Tsa_PurchaseGenericCostBox\n"
    "Tsa_PurchaseGenericCostBox:\n"
    ".incbin \"graphics/purchase_generics/ACostBox.dmp\"\n"
    ".balign 4\n"
    ".global Tsa_PurchaseGenericItemBox\n"
    "Tsa_PurchaseGenericItemBox:\n"
    ".incbin \"graphics/purchase_generics/AnItemBox.dmp\"\n"
    ".balign 4\n"
    ".global Tsa_PurchaseGenericBottomStats\n"
    "Tsa_PurchaseGenericBottomStats:\n"
    ".incbin \"graphics/purchase_generics/ClassBlueBoxBottom.dmp\"\n"
    ".balign 4\n"
    ".global Tsa_PurchaseGenericTopStats\n"
    "Tsa_PurchaseGenericTopStats:\n"
    ".incbin \"graphics/purchase_generics/ClassBlueBoxTop.dmp\"\n"
    ".balign 4\n"
    ".text\n"
);

#endif
