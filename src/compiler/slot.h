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

slot slot_struct(uint64_t head_idx, uint64_t production_idx, uint64_t position);
slot* new_slot(uint64_t head_idx, uint64_t production_idx, uint64_t position);
obj* new_slot_obj(slot* s);
bool slot_is_accept(slot* s);
void slot_str(slot* s);
void slot_repr(slot* s);
void slot_free(slot* s);
slot* slot_copy(slot* s);
uint64_t slot_hash(slot* s);
bool slot_equals(slot* left, slot* right);

#endif