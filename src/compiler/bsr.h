#ifndef BSR_H
#define BSR_H

#include "slice.h"

typedef enum
{
    bsr_substring,
    bsr_production
} bsr_type;

typedef struct
{
    bsr_type type;
    union
    {
        struct
        {
            uint64_t head_idx;
            uint64_t production_idx;
        };
        slice substring;
    };
    uint64_t i;
    uint64_t j;
    uint64_t k;
} bsr;

#endif