#ifndef METAITEM_H
#define METAITEM_H

#include <stdint.h>

#include "object.h"
#include "set.h"


typedef struct {
    uint64_t head_idx;          //key metaparser_productions
    uint64_t production_idx;    //index metaparser_productions[head_idx]
    uint64_t position;          //location of dot in item
} metaitem;


metaitem* new_metaitem(uint64_t head_idx, uint64_t production_idx, uint64_t position);
obj* new_metaitem_obj(metaitem* i);
bool metaitem_is_accept(metaitem* i);
void metaitem_str(metaitem* item);
void metaitem_repr(metaitem* i);
void metaitem_free(metaitem* i);
uint64_t metaitem_hash(metaitem* i);
bool metaitem_equals(metaitem* left, metaitem* right);



#endif