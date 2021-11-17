#ifndef CRF_C
#define CRF_C

#include "crf.h"

// Call Return Forest

crf* new_crf()
{
    crf* CRF = malloc(sizeof(crf));
    *CRF = (crf){.forest = new_dict()};
    return CRF;
}

void crf_free(crf* CRF)
{
    dict_free(CRF->forest);
    free(CRF);
}

#endif
