#ifndef PARRAY_H
#define PARRAY_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "object.h"

//primitive array. used for any primitive data type instead of obj
//same algorithm/structure as name##_arrayor.c


#define parray_header(type, name)                                           \
                                                                            \
typedef struct                                                              \
{                                                                           \
    size_t head;                                                            \
    size_t size;                                                            \
    size_t capacity;                                                        \
    type* list;                                                             \
} name##_array;                                                             \
                                                                            \
                                                                            \
name##_array* new_##name##_array();                                         \
name##_array* new_##name##_array_with_capacity(size_t size_hint);           \
obj* new_##name##_array_obj(name##_array* v);                               \
size_t name##_array_size(name##_array* v);                                  \
size_t name##_array_capacity(name##_array* v);                              \
void name##_array_resize(name##_array* v, size_t new_size);                 \
void name##_array_insert(name##_array* v, type item, size_t index);         \
void name##_array_append(name##_array* v, type item);                       \
void name##_array_prepend(name##_array* v, type item);                      \
void name##_array_push(name##_array* v, type item);                         \
type name##_array_pop(name##_array* v);                                     \
type name##_array_peek(name##_array* v);                                    \
void name##_array_enqueue(name##_array* v, type item);                      \
type name##_array_dequeue(name##_array* v);                                 \
void name##_array_set(name##_array* v, type item, size_t index);            \
name##_array* name##_array_merge(name##_array* left, name##_array* right);  \
bool name##_array_contains(name##_array* v, type item);                     \
bool name##_array_find(name##_array* v, type item, size_t* index);          \
type name##_array_get(name##_array* v, size_t index);                       \
type name##_array_remove(name##_array* v, size_t index);                    \
name##_array* name##_array_copy(name##_array* v);                           \
void name##_array_free(name##_array* v);                                    \
int64_t name##_array_compare(name##_array* left, name##_array* right);      \
bool name##_array_equals(name##_array* left, name##_array* right);          \
uint64_t name##_array_hash(name##_array* v);                                \
void name##_array_repr(name##_array* v);                                    \
void name##_array_str(name##_array* v);                                     \


//Declare primitive type headers
parray_header(uint64_t, uint64)
parray_header(bool, bool)
parray_header(int64_t, int64)
parray_header(double, double)
// parray_header(void*, ptr)

#endif