#ifndef TUPLE_H
#define TUPLE_H

#include <stdint.h>

#include "object.h"

typedef struct {
    size_t n;
    uint64_t* items;
} tuple;

tuple* new_tuple(size_t n, ...);
obj* new_tuple_obj(tuple* t);

void tuple_str(tuple* t);
void tuple_repr(tuple* t);
void tuple_free(tuple* t);
bool tuple_equals(tuple* left, tuple* right);
uint64_t tuple_hash(tuple* t);

#endif