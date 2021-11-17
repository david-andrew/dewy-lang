#ifndef CRF_C
#define CRF_C

#include "crf.h"

// Call Return Forest

/**
 * Create a new call return forest.
 */
crf* new_crf()
{
    crf* CRF = malloc(sizeof(crf));
    *CRF = (crf){.forest = new_dict()};
    return CRF;
}

/**
 * Free a call return forest.
 */
void crf_free(crf* CRF)
{
    dict_free(CRF->forest);
    free(CRF);
}

#endif
