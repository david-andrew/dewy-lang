#ifndef SLICE_H
#define SLICE_H

#include <stdlib.h>

#include "vector.h"

// #include "vector.h"

//view a slice of a vector
typedef struct {
    vect* v;
    size_t start;
    size_t stop;
} slice;

slice* new_slice(vect* v, size_t start, size_t stop);
obj* slice_get(slice* s, size_t i);
size_t slice_size(slice* s);
void slice_free(slice* s); //doesn't touch v's data

#endif