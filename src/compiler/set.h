#ifndef SET_H
#define SET_H

#include "types.h"

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