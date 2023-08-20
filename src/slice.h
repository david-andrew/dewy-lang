#ifndef SLICE_H
#define SLICE_H

#include <stdlib.h>

#include "vector.h"

// view a slice of a vector
typedef struct
{
    vect* v;
    size_t start; // index of first element in slice
    size_t stop;  // index - 1 of last element in slice. essentially python slice rules
} slice;

slice slice_struct(vect* v, size_t start, size_t stop);
slice slice_slice_struct(slice* s, size_t start, size_t stop);
vect slice_vect_view_struct(slice* s);
slice* new_slice(vect* v, size_t start, size_t stop);
obj* new_slice_obj(slice* s);
obj* slice_get(slice* s, size_t i);
size_t slice_size(slice* s);
void slice_free(slice* s); // doesn't touch v's data
void slice_str(slice* s);
slice* slice_copy(slice* s);
vect* slice_copy_to_vect(slice* s);
uint64_t slice_hash(slice* s);
bool slice_equals(slice* left, slice* right);

#endif