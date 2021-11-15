#ifndef SLICE_C
#define SLICE_C

#include <stdio.h>

#include "slice.h"
#include "utilities.h"

/**
 * Return a stack allocated slice struct.
 */
inline slice slice_struct(vect* v, size_t start, size_t stop, obj* lookahead)
{
    if (start > vect_size(v) || stop > vect_size(v))
    {
        printf("ERROR: slice indices %zu:%zu out of bounds for vect with size %zu\n", start, stop, vect_size(v));
        exit(1);
    }
    return (slice){.v = v, .start = start, .stop = stop, .lookahead = lookahead};
}

/**
 * Return a static vect view of the slice.
 * Only works for slices where lookahead=NULL
 * Returned vect should be treated as immutable,
 * and is only valid for as long as the vect inside
 * the slice is valid.
 */
inline vect slice_vect_view_struct(slice* s)
{
    if (s->lookahead != NULL)
    {
        printf("ERROR: cannot create a vect view of a slice that contains a lookahead value\n");
        exit(1);
    }
    // printf("vect view vect: "); vect_str(s->v); printf("\n");
    // vect_repr(s->v);
    // printf("capacity: %zu, head: %zu, size: %zu, start: %zu, stop: %zu\n", s->v->capacity, s->v->head, s->v->size,
    // s->start, s->stop);
    return (vect){.capacity = s->v->capacity,
                  .head = (s->v->head + s->start) % s->v->capacity,
                  .list = s->v->list,
                  .size = s->stop - s->start};
}

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
    *s = (slice){.v = v, .start = start, .stop = stop, .lookahead = lookahead};
    return s;
}

/**
 * Return a slice wrapped in object.
 */
obj* new_slice_obj(slice* s)
{
    obj* S = malloc(sizeof(obj));
    *S = (obj){.type = Slice_t, .data = s};
    return S;
}

/**
 * Get the object at position i in the slice.
 */
obj* slice_get(slice* s, size_t i)
{
    if ((s->lookahead == NULL && i < slice_size(s)) || (s->lookahead != NULL && i < slice_size(s) - 1))
    {
        // get the item from the contained vect
        return vect_get(s->v, s->start + i);
    }
    else if (s->lookahead != NULL && i == slice_size(s) - 1)
    {
        // get the "appended" lookahead item
        return s->lookahead;
    }
    else
    {
        // out of bounds error
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
    // if lookahead is included, size is 1 larger
    return s->stop - s->start + (s->lookahead != NULL);
}

/**
 * Free the slice (without touching the original data vector).
 */
void slice_free(slice* s) { free(s); }

/**
 * Print out the slice as if it were a normal vector
 */
void slice_str(slice* s)
{
    printf("[");
    for (size_t i = 0; i < slice_size(s); i++)
    {
        obj_str(slice_get(s, i));
        if (i < slice_size(s) - 1) { printf(", "); }
    }
    printf("]");
}

/**
 * Return a copy of the slice.
 * Note copy still points to same vector/lookahead as original.
 */
slice* slice_copy(slice* s) { return new_slice(s->v, s->start, s->stop, s->lookahead); }

/**
 * Return a copy of the slice as if it were a normal vector.
 */
vect* slice_copy_to_vect(slice* s)
{
    vect* copy = new_vect();
    for (size_t i = 0; i < slice_size(s); i++) { vect_append(copy, obj_copy(slice_get(s, i))); }
    return copy;
}

/**
 * Hash the components of the slice together.
 */
uint64_t slice_hash(slice* s)
{
    uint64_t* hashes = malloc(sizeof(uint64_t) * slice_size(s));
    for (size_t i = 0; i < slice_size(s); i++) { hashes[i] = obj_hash(slice_get(s, i)); }
    uint64_t hash = hash_uint_sequence(hashes, slice_size(s));
    free(hashes);
    return hash;
}

/**
 * Determine if two slices are identical.
 */
bool slice_equals(slice* left, slice* right)
{
    if (slice_size(left) != slice_size(right)) { return false; }
    for (size_t i = 0; i < slice_size(left); i++)
    {
        if (!obj_equals(slice_get(left, i), slice_get(right, i))) { return false; }
    }
    return true;
}

#endif