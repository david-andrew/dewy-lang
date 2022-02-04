#ifndef BSR_H
#define BSR_H

#include <stdbool.h>

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
    uint64_t i; // left extent
    // uint64_t j; // binary right split point. stored separately for ease of lookup
    uint64_t k; // right extent
} bsr_head;

// BSR nodes are represented in the dict Y as follows:
// Y[(X ::= μ, i, k)] = {j} and Y[(μ, i, k)] = {j}
// i.e. (X ::= μ, i, k)/(μ, i, k) is a key in Y and the value is a set of j1, j2, ..., jn,
// making actions (X ::= μ, i, j1, k), (X ::= μ, i, j2, k), ... (X ::= μ, i, jn k)
// or (μ, i, j1, k), (μ, i, j2, k), ... (μ, i, jn, k), depending on the type of head
// this allows easy lookup of BSRs by (X ::= μ, i, k) and (μ, i, k)

// convenience for storing bsr nodes (prod type only)
typedef struct
{
    uint64_t head_idx;
    uint64_t production_idx;
    uint64_t i; // left extent
    uint64_t j; // binary right split point
    uint64_t k; // right extent
} bsr;

bsr_head* new_str_bsr_head(slice* substring, uint64_t i, uint64_t k);
bsr_head new_str_bsr_head_struct(slice* substring, uint64_t i, uint64_t k);
bsr_head* new_prod_bsr_head(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t k);
bsr_head new_prod_bsr_head_struct(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t k);
bsr_head* bsr_head_copy(bsr_head* b);
obj* new_bsr_head_obj(bsr_head* b);
bool bsr_head_equals(bsr_head* left, bsr_head* right);
uint64_t bsr_head_hash(bsr_head* b);
uint64_t bsr_head_str_hash(bsr_head* b);
uint64_t bsr_head_slot_hash(bsr_head* b);
void bsr_head_free(bsr_head* b);
void bsr_head_str(bsr_head* b);
void bsr_str(bsr_head* b, uint64_t j);
void bsr_head_repr(bsr_head* b);
void bsr_tree_str(dict* Y, uint32_t* I, uint64_t start_idx, uint64_t length);
void bsr_tree_str_inner(dict* Y, uint32_t* I, bsr_head* head, uint64_t j, uint64_t level);
void bsr_tree_str_inner_head(dict* Y, uint32_t* I, bsr_head* head, uint64_t level);
void bsr_tree_str_inner_substr(dict* Y, uint32_t* I, slice* substring, uint64_t i, uint64_t k, uint64_t level);
void bsr_tree_str_inner_symbol(dict* Y, uint32_t* I, uint64_t symbol_idx, uint64_t i, uint64_t k, uint64_t level);
// void bsr_tree_str_leaf(charset* terminal, uint64_t j, uint64_t level);
// void bsr_get_children(dict* Y, bsr_head* head, uint64_t j, bsr_head** left, bsr_head** right);

bool bsr_root_has_multiple_splits(dict* Y, uint64_t head_idx, uint64_t length, uint64_t* production_idx, uint64_t* j);
bool bsr_head_has_multiple_splits(dict* Y, bsr_head* head, uint64_t* j);
bool bsr_has_ambiguities(dict* Y, uint64_t head_idx, uint64_t length, uint64_t* production_idx);
bool bsr_tree_is_ambiguous(dict* Y, bsr_head* head, uint64_t j); // recursively check any node for ambiguity
// bool bsr_children_have_multiple_splits(dict* Y, bsr_head* head, uint64_t j);

#endif