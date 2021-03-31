#ifndef SLICE_H
#define SLICE_H

#include <stdlib.h>

#include "vector.h"


//view a slice of a vector
typedef struct {
    vect* v;
    size_t start;   //index of first element in slice
    size_t stop;    //index - 1 of last element in slice. essentially python slice rules
    obj* lookahead;
} slice;

slice* new_slice(vect* v, size_t start, size_t stop, obj* lookahead);
obj* slice_get(slice* s, size_t i);
size_t slice_size(slice* s);
void slice_free(slice* s); //doesn't touch v's data

#endif