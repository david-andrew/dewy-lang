#ifndef SLICE_C
#define SLICE_C

#include <stdio.h>

#include "slice.h"


/**
 * Return a new slice object for viewing a subset of a vector.
 * Lookahead is an optional terminal index object that will be treated as 
 * appended to the end of the slice. if lookahead is null, it is ignored.
 */
slice* new_slice(vect* v, size_t start, size_t stop, obj* lookahead)
{
    if (start > vect_size(v) || stop > vect_size(v))
    {
        printf("ERROR: slice indices %zu:%zu out of bounds for vect with size %zu\n", start, stop, vect_size(v));
        exit(1);
    }
    slice* s = malloc(sizeof(slice));
    *s = (slice){.v=v, .start=start, .stop=stop, .lookahead=lookahead};
    return s;
}


/**
 * Get the object at position i in the slice.
 */
obj* slice_get(slice* s, size_t i)
{
    if ((s->lookahead == NULL && i < slice_size(s)) || (s->lookahead != NULL && i < slice_size(s) - 1))
    {
        //get the item from the contained vect
        return vect_get(s->v, s->start+i);
    }
    else if (s->lookahead != NULL && i == slice_size(s))
    {
        //get the "appended" lookahead item
        return s->lookahead;
    }
    else
    {
        //out of bounds error
        printf("ERROR: attempted to get item at %zu of slice with size %zu\n", i, slice_size(s));
        exit(1);
    }
}


/**
 * Return the number of elements in the slice.
 * Under python slice rules, if stop=start, then slice size is 0.
 * If lookahead is not NULL, then size is 1 larger than vector slice size.
 */
size_t slice_size(slice* s)
{
    //if lookahead is included, size is 1 larger
    return s->stop - s->start + (s->lookahead != NULL);
}


/**
 * Free the slice (without touching the original data vector).
 */
void slice_free(slice* s)
{
    free(s);
}



#endif