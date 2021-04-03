#ifndef GOTOKEY_C
#define GOTOKEY_C

#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>

#include "gotokey.h"
#include "metaparser.h"
#include "utilities.h"


/**
 * Create a new GOTO key for indexing into an RNGLR parse table.
 */
gotokey* new_gotokey(uint64_t state_idx, uint64_t symbol_idx)
{
    gotokey* k = malloc(sizeof(gotokey));
    *k = (gotokey){.state_idx=state_idx, .symbol_idx=symbol_idx};
    return k;
}


/**
 * Create a new object wrapped GOTO key.
 */
obj* new_gotokey_obj(gotokey* k)
{
    obj* K = malloc(sizeof(obj));
    *K = (obj){.type=GotoKey_t, .data=k};
    return K;
}


/**
 * Print out the value contained in the GOTO key.
 */
void gotokey_str(gotokey* k)
{
    printf("(I%"PRIu64", ", k->state_idx);
    obj* symbol = metaparser_get_symbol(k->symbol_idx);
    obj_str(symbol); printf(")");
}


/**
 * Print the internal representation of the GOTO key.
 */
void gotokey_repr(gotokey* k)
{
    printf("gotokey{state_idx: %"PRIu64", symbol_idx: %"PRIu64"}", k->state_idx, k->symbol_idx);
}


/**
 * Determine if two GOTO keys are equal.
 */
bool gotokey_equals(gotokey* left, gotokey* right)
{
    return left->state_idx == right->state_idx && left->symbol_idx == right->symbol_idx;
}


/**
 * Return a hash of a gotokey.
 */
uint64_t gotokey_hash(gotokey* k)
{
    uint64_t seq[] = {k->state_idx, k->symbol_idx};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}


/**
 * Free the gotokey container.
 */
void gotokey_free(gotokey* k)
{
    free(k);
}


#endif