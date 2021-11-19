#ifndef BSR_H
#define BSR_H

#include "slice.h"

typedef enum
{
    prod_bsr,
    str_bsr
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

bsr* new_str_bsr(slice* substring, uint64_t i, uint64_t j, uint64_t k);
bsr new_str_bsr_struct(slice* substring, uint64_t i, uint64_t j, uint64_t k);
bsr* new_prod_bsr(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t j, uint64_t k);
bsr new_prod_bsr_struct(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t j, uint64_t k);
bsr* bsr_copy(bsr* b);
obj* new_bsr_obj(bsr* b);
bool bsr_equals(bsr* left, bsr* right);
uint64_t bsr_hash(bsr* b);
uint64_t bsr_str_hash(bsr* b);
uint64_t bsr_slot_hash(bsr* b);
void bsr_free(bsr* b);
void bsr_str(bsr* b);
void bsr_repr(bsr* b);

#endif