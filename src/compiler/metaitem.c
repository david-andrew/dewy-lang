#ifndef METAITEM_C
#define METAITEM_C

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

#include "metaitem.h"
#include "metaparser.h"
#include "slice.h"
#include "fset.h"
// #include "srnglr.h"
#include "utilities.h"


/**
 * Create a new metaitem.
 */
metaitem* new_metaitem(uint64_t head_idx, uint64_t production_idx, uint64_t position)
{
    metaitem* i = malloc(sizeof(metaitem));
    *i = (metaitem){
        .head_idx=head_idx,
        .production_idx=production_idx,
        .position=position,
    };
    return i;
}


/**
 * Create a new metaitem obj from an existing metaitem.
 * i is expected to be non-null.
 */
obj* new_metaitem_obj(metaitem* i)
{
    obj* I = malloc(sizeof(obj));
    *I = (obj){.type=MetaItem_t, .data=i};
    return I;
}


/**
 * Returns whether the metaitem is in an accepting state,
 * i.e. if the position is at the end of the list of body symbols.
 * Additionally, an item is accepting if the remaining string is nullable.
 */
bool metaitem_is_accept(metaitem* i)
{
    // get the body for this item
    vect* body = metaparser_get_production_body(i->head_idx, i->production_idx);
    
    if (i->position == vect_size(body))
    {
        //normal accept, when position is at end of body
        return true;
    }
    else
    {
        //check if the remaining portion of the string is nullable
        slice remaining = slice_struct(body, i->position, vect_size(body), NULL);
        fset* first = metaparser_first_of_string(&remaining);
        bool nullable = first->nullable;
        fset_free(first);
        return nullable;
    }
}


/**
 * Print out a string displaying the metaitem.
 */
void metaitem_str(metaitem* item)
{
    obj* head = metaparser_get_symbol(item->head_idx);
    vect* body = metaparser_get_production_body(item->head_idx, item->production_idx);

    printf("["); obj_str(head); printf(" -> ");
    for (size_t i = 0; i <= vect_size(body); i++)
    {
        if (i == item->position) { printf("•"); }
        if (i == vect_size(body)) { break; };
        uint64_t* symbol_idx = vect_get(body, i)->data;
        obj* symbol = metaparser_get_symbol(*symbol_idx);
        obj_str(symbol);
        if (i < vect_size(body) - 1) { printf(" "); }
    }
    printf("]");
}


/**
 * Print out the internal representation of a metaitem.
 */
void metaitem_repr(metaitem* i)
{
    printf("metaitem{head_idx: %"PRIu64
        ", production_idx: %"PRIu64
        ", position: %"PRIu64"}",
        i->head_idx, 
        i->production_idx, 
        i->position
    );
}


/**
 * Free an allocated metaitem.
 */
void metaitem_free(metaitem* i)
{
    free(i);
}


/**
 * Compute the hash of the metaitem with a modified version of fnv1a.
 */
uint64_t metaitem_hash(metaitem* item)
{
    uint64_t components[] = {item->head_idx, item->production_idx, item->position};

    return hash_uint_sequence(components, sizeof(components) / sizeof(uint64_t));
}


/**
 * Determine whether two metaitems are equal.
 */
bool metaitem_equals(metaitem* left, metaitem* right)
{
    return left->head_idx == right->head_idx 
        && left->production_idx == right->production_idx
        && left->position == right->position;
}






#endif