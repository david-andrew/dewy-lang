#ifndef TUPLE_C
#define TUPLE_C

#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>
#include <stdarg.h>

#include "tuple.h"
#include "utilities.h"


/**
 * Create a new n-tuple given a list of the elements it should contain.
 */
tuple* new_tuple(size_t n, ...)
{   
    //set up variadic args
    va_list args;
    va_start(args, n);

    //build the tuple
    tuple* t = malloc(sizeof(tuple));
    uint64_t* items = malloc(sizeof(uint64_t) * n);
    for (size_t i = 0; i < n; i++)
    {
        items[i] = va_arg(args, uint64_t);
    }
    *t = (tuple){.n=n, .items=items};

    //close variadic args
    va_end(args);
    
    return t;
}


/**
 * Create a new tuple wrapped in an object.
 */
obj* new_tuple_obj(tuple* t)
{
    obj* T = malloc(sizeof(obj));
    *T = (obj){.type=UIntNTuple_t, .data=t};
    return T;
}


/**
 * Print out the tuple.
 */
void tuple_str(tuple* t)
{
    printf("(");
    for (size_t i = 0; i < t->n; i++)
    {
        printf("%"PRIu64, t->items[i]);
        if (t < t->n - 1) { printf(", "); }
    }
    printf(")");
}


/**
 * Print the internal representation of the tuple.
 */
void tuple_repr(tuple* t)
{
    printf("tuple{n=%zu"
    ", items=", t->n); tuple_str(t); printf("}");
}


/**
 * Free the allocated memory for the tuple.
 */
void tuple_free(tuple* t)
{
    free(t->items);
    free(t);
}


/**
 * Determine if two tuples are equal.
 */
bool tuple_equals(tuple* left, tuple* right)
{
    if (left->n != right->n) { return false; }
    for (size_t i = 0; i < left->n; i++)
    {
        if (left->items[i] != right->items[i]) { return false; }
    }
    return true;
}


/**
 * get a hash of the elements in the tuple.
 */
uint64_t tuple_hash(tuple* t)
{
    return hash_uint_sequence(t->items, t->n);
}


#endif