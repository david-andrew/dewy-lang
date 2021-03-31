#ifndef METAITEM_H
#define METAITEM_H

#include <stdint.h>

#include "object.h"
#include "set.h"


typedef struct {
    uint64_t head_idx;          //key metaparser_productions
    uint64_t production_idx;    //index metaparser_productions[head_idx]
    uint64_t position;          //location of dot in item
    uint64_t lookahead_idx;     //index metaparser_symbols
} metaitem;


metaitem* new_metaitem(uint64_t head_idx, uint64_t body_idx, uint64_t position, uint64_t lookahead_idx);
obj* new_metaitem_obj(metaitem* i);
void metaitem_free(metaitem* i);



#endif