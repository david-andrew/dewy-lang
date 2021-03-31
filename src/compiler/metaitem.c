#ifndef METAITEM_C
#define METAITEM_C

#include <stdlib.h>

#include "metaitem.h"


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
 * Free an allocated metaitem.
 */
void metaitem_free(metaitem* i)
{
    free(i);
}




#endif