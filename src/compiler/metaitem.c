#ifndef METAITEM_C
#define METAITEM_C

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

#include "metaitem.h"
#include "metaparser.h"


/**
 * Create a new metaitem.
 */
metaitem* new_metaitem(uint64_t head_idx, uint64_t production_idx, uint64_t position, uint64_t lookahead_idx)
{
    metaitem* i = malloc(sizeof(metaitem));
    *i = (metaitem){
        .head_idx=head_idx,
        .production_idx=production_idx,
        .position=position,
        .lookahead_idx=lookahead_idx
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
 * Print out a string displaying the metaitem.
 */
void metaitem_str(metaitem* item)
{
    obj* head = metaparser_get_symbol(item->head_idx);
    vect* body = metaparser_get_production_body(item->head_idx, item->production_idx);
    obj* lookahead = metaparser_get_symbol(item->lookahead_idx);

    printf("["); obj_print(head); printf(" = ");
    for (size_t i = 0; i <= vect_size(body); i++)
    {
        if (i == item->position) { printf("•"); }
        if (i == vect_size(body)) { break; };
        uint64_t* symbol_idx = vect_get(body, i)->data;
        obj* symbol = metaparser_get_symbol(*symbol_idx);
        obj_print(symbol);
        if (i < vect_size(body) - 1) { printf(" "); }
    }
    printf(", "); obj_print(lookahead); printf("]");
}


/**
 * Print out the internal representation of a metaitem.
 */
void metaitem_repr(metaitem* i)
{
    printf("metaitem{head_idx: %"PRIu64", production_idx: %"PRIu64", position: %"PRIu64", lookahead_idx: %"PRIu64"}", i->head_idx, i->production_idx, i->position, i->lookahead_idx);
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
    uint64_t hash = 14695981039346656037lu;
    uint64_t components[] = {item->head_idx, item->production_idx, item->position, item->lookahead_idx};
    
    //loop through each of the 4 uint64_t's in the metaitem
    for (size_t i = 0; i < 4; i++)
    {
        //reinterpret the uint64_t as 8 bytes
        uint64_t component = components[i];
        uint8_t* bytes = (uint8_t*)&component;

        //hash combine byte into the hash
        for (int j = 7; j >= 0; j--)
        {
            hash ^= bytes[j];
            hash *= 1099511628211;
        }
    }
    return hash;
}


/**
 * Determine whether two metaitems are equal.
 */
bool metaitem_equals(metaitem* left, metaitem* right)
{
    return left->head_idx == right->head_idx 
        && left->production_idx == right->production_idx
        && left->position == right->position
        && left->lookahead_idx == right->lookahead_idx; 
}






#endif