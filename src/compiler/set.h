#ifndef SET_H
#define SET_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "object.h"
#include "dictionary.h"

/**
    Struct/type declaration for sets. Currently just wraps dictionary. TODO->have dedicated type
*/
typedef struct set_struct
{
    dict* d; //a set is just a wrapper around a dict
} set;

set* new_set();
obj* new_set_obj(set* s);
// obj* set_obj_wrap(set* s);
size_t set_size(set* S);
// size_t set_capacity(set* S);
bool set_add(set* S, obj* item);
// bool set_remove(set* s, obj* item);
bool set_contains(set* S, obj* item);
set* set_copy(set* S);
set* set_union(set* A, set* B);
set* set_union_equals(set* A, set* B);
set* set_intersect(set* A, set* B);
bool set_equals(set* A, set* B);
uint64_t set_hash(set* S);
void set_reset(set* S);
void set_free(set* S);
void set_repr(set* S);
void set_str(set* S);

#endif