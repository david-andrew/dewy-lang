#ifndef BSR_C
#define BSR_C

#include <inttypes.h>
#include <stdio.h>

#include "bsr.h"
#include "metaparser.h"
#include "utilities.h"

/**
 * Create a new BSR containing a production substring
 */
bsr* new_str_bsr(slice* substring, uint64_t i, uint64_t j, uint64_t k)
{
    bsr* b = malloc(sizeof(bsr));
    *b = new_str_bsr_struct(substring, i, j, k);
    return b;
}

/**
 * Return the struct for a BSR containing a production substring
 */
inline bsr new_str_bsr_struct(slice* substring, uint64_t i, uint64_t j, uint64_t k)
{
    return (bsr){.type = str_bsr, .substring = *substring, .i = i, .j = j, .k = k};
}

/**
 * Create a new BSR containing a whole production
 */
bsr* new_prod_bsr(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t j, uint64_t k)
{
    bsr* b = malloc(sizeof(bsr));
    *b = new_prod_bsr_struct(head_idx, production_idx, i, j, k);
    return b;
}

/**
 * Return the struct for a BSR containing a whole production
 */
bsr new_prod_bsr_struct(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t j, uint64_t k)
{
    return (bsr){.type = prod_bsr, .head_idx = head_idx, .production_idx = production_idx, .i = i, .j = j, .k = k};
}

/**
 * Return a new copy of a BSR
 */
bsr* bsr_copy(bsr* b)
{
    bsr* b_copy = malloc(sizeof(bsr));
    *b_copy = *b;
    return b_copy;
}

/**
 * Return a BSR wrapped in a new object
 */
obj* new_bsr_obj(bsr* b) { return new_obj(BSR_t, b); }

/**
 * Check if two BSRs are equal
 */
bool bsr_equals(bsr* left, bsr* right)
{
    if (left->type != right->type) return false;
    if (left->i != right->i || left->j != right->j || left->k != right->k) return false;
    if (left->type == str_bsr) return slice_equals(&left->substring, &right->substring);
    else
        return left->head_idx == right->head_idx && left->production_idx == right->production_idx;
}

/**
 * Compute the hash of a BSR
 */
uint64_t bsr_hash(bsr* bsr) { return bsr->type == str_bsr ? bsr_str_hash(bsr) : bsr_slot_hash(bsr); }

/**
 * Compute the hash of a str BSR
 */
uint64_t bsr_str_hash(bsr* b)
{
    uint64_t seq[] = {b->type, slice_hash(&b->substring), b->i, b->j, b->k};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Compute the hash of a slot BSR
 */
uint64_t bsr_slot_hash(bsr* b)
{
    uint64_t seq[] = {b->type, b->head_idx, b->production_idx, b->i, b->j, b->k};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Free a BSR
 */
void bsr_free(bsr* b) { free(b); }

/**
 * Print out the BSR
 */
void bsr_str(bsr* b)
{
    //(X ::= α, i, k, j) for type prod_bsr
    //(α, i, k, j) for type str_bsr
    printf("(");
    if (b->type == str_bsr) { metaparser_production_str(b->head_idx, b->production_idx); }
    else
    {
        for (size_t i = 0; i < slice_size(&b->substring); i++)
        {
            if (i > 0) printf(" ");
            uint64_t* symbol_idx = slice_get(&b->substring, i)->data;
            obj_str(metaparser_get_symbol(*symbol_idx));
        }
    }
    printf(", %" PRIu64 ", %" PRIu64 ", %" PRIu64 ")", b->i, b->j, b->k);
}

/**
 * Print out the internal representation of a BSR
 */
void bsr_repr(bsr* bsr)
{
    printf("(");
    if (bsr->type == str_bsr)
    {
        printf("type: str_bsr, substring: ");
        slice_str(&bsr->substring);
    }
    else
    {
        printf("type: prod_bsr, head_idx: %" PRIu64 ", production_idx: %" PRIu64, bsr->head_idx, bsr->production_idx);
    }
    printf(", i: %" PRIu64 ", j: %" PRIu64 ", k: %" PRIu64 ")", bsr->i, bsr->j, bsr->k);
}

#endif