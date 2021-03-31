#ifndef SLICE_C
#define SLICE_C

#include <stdio.h>

#include "slice.h"


/**
 * Return a new slice object for viewing a subset of a vector.
 */
slice* new_slice(vect* v, size_t start, size_t stop)
{
    if (start >= vect_size(v) || stop >= vect_size(v))
    {
        printf("ERROR: slice indices %zu:%zu out of bounds for vect with size %zu", start, stop, vect_size(v));
        exit(1);
    }
    slice* s = malloc(sizeof(slice));
    *s = (slice){.v=v, .start=start, .stop=stop};
    return s;
}


/**
 * Get the object at position i in the slice.
 */
obj* slice_get(slice* s, size_t i)
{
    return vect_get(s->v, s->start+i);
}


/**
 * Return the number of elements in the slice.
 */
size_t slice_size(slice* s)
{
    return s->stop - s->start + 1;
}


/**
 * Free the slice (without touching the original data vector).
 */
void slice_free(slice* s)
{
    free(s);
}



#endif