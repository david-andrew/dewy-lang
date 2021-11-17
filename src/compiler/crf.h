#ifndef CRF_H
#define CRF_H

#include <stdint.h>

#include "dictionary.h"
#include "slice.h"
#include "slot.h"

typedef enum
{
    crf_head,
    crf_label
} crf_node_type;

// Call Return Forest data structure used by CNP parsing algorithm
typedef struct
{
    crf_node_type type; // whether the node is type (X ::= α•β, j) or (X, j)
    union
    {
        slot label;
        uint64_t head_idx;
    };
    uint64_t j;
} crf_node; // binary subtree representation

typedef struct
{
    dict* forest; // map from node to vector containing indices of children
} crf;

crf* new_crf();
void crf_free(crf* CRF);

#endif