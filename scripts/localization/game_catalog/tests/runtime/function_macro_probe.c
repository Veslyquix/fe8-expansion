#include "functions.h"

extern char gBufPrep[0x2000];

char *ProbeLocalBuffer(void)
{
    char local[32];

    return GetStringFromIndexInBuffer(0, local);
}

char *ProbePrepBuffer(void)
{
    return GetStringFromIndexInBuffer(0, gBufPrep);
}
