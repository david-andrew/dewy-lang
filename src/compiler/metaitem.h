#ifndef METAITEM_H
#define METAITEM_H

#include <stdlib.h>
#include <stdint.h>

typedef struct {
    size_t head_idx;
    size_t body_idx;
    uint64_t position;
    size_t lookahead_idx;
} metaitem;


#endif