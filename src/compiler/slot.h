#ifndef SLOT_H
#define SLOT_H

#include <stdint.h>

#include "object.h"

typedef struct
{
    uint64_t head_idx;       // key metaparser_productions
    uint64_t production_idx; // index metaparser_productions[head_idx]
    uint64_t dot;            // location of dot in item
} slot;

// process descriptors from the parsing process
typedef struct
{
    slot L;
    uint64_t k;
    uint64_t j;
} desc;

slot slot_struct(uint64_t head_idx, uint64_t production_idx, uint64_t dot);
slot* new_slot(uint64_t head_idx, uint64_t production_idx, uint64_t dot);
obj* new_slot_obj(slot* s);
bool slot_is_accept(slot* s);
void slot_str(slot* s);
void slot_repr(slot* s);
void slot_free(slot* s);
slot* slot_copy(slot* s);
uint64_t slot_hash(slot* s);
bool slot_equals(slot* left, slot* right);

desc desc_struct(slot* L, uint64_t k, uint64_t j);
desc* new_desc(slot* L, uint64_t k, uint64_t j);
obj* new_desc_obj(desc* d);
void desc_str(desc* d);
void desc_repr(desc* d);
void desc_free(desc* d);
desc* desc_copy(desc* d);
uint64_t desc_hash(desc* d);
bool desc_equals(desc* left, desc* right);

#endif