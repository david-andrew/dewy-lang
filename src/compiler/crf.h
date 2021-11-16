#ifndef CRF_H
#define CRF_H

#include <stdint.h>

#include "dictionary.h"
#include "slice.h"

// Call Return Forest data structure used by CNP parsing algorithm
typedef struct
{
    uint64_t head_idx; // value of (uint64_t) -1 indicates no head
    uint64_t substring_idx;

    uint64_t i;
} bsr; // binary subtree representation

typedef struct
{
    dict* forest; // map from node to vector containing indices of children
} crf;

#endif