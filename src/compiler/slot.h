#ifndef SLOT_H
#define SLOT_H

#include <stdint.h>

#include "object.h"

typedef struct
{
    uint64_t head_idx;       // key metaparser_productions
    uint64_t production_idx; // index metaparser_productions[head_idx]
    uint64_t position;       // location of dot in item
} slot;

slot* new_slot(uint64_t head_idx, uint64_t production_idx, uint64_t position);
obj* new_slot_obj(slot* i);
bool slot_is_accept(slot* i);
void slot_str(slot* item);
void slot_repr(slot* i);
void slot_free(slot* i);
uint64_t slot_hash(slot* i);
bool slot_equals(slot* left, slot* right);

#endif