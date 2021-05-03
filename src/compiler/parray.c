#ifndef PARRAY_C
#define PARRAY_C


#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

#include "utilities.h"
#include "parray.h"

#define DEFAULT_VECT_CAPACITY 8

//ArrayList Implemented as an ArrayDeque
//see: http://opendatastructures.org/ods-java/2_4_ArrayDeque_Fast_Deque_O.html

#define parray_implementation(dtype, TypeArray_t, name, format, hashcast)                                                   \
name##_array* new_##name##_array() { return new_##name##_array_with_capacity(DEFAULT_VECT_CAPACITY); }                      \
name##_array* new_##name##_array_with_capacity(size_t init_capacity)                                                        \
{                                                                                                                           \
    name##_array* v = malloc(sizeof(name##_array));                                                                         \
    *v = (name##_array){                                                                                                    \
        .head = 0,                                                                                                          \
        .size = 0,                                                                                                          \
        .capacity = init_capacity,                                                                                          \
        .list = calloc(init_capacity, sizeof(dtype))                                                                        \
    };                                                                                                                      \
    return v;                                                                                                               \
}                                                                                                                           \
obj* new_##name##_array_obj(name##_array* v)                                                                                \
{                                                                                                                           \
    if (v == NULL) v = new_##name##_array();                                                                                \
    obj* V = malloc(sizeof(obj));                                                                                           \
    *V = (obj){.type=TypeArray_t, .data=v};                                                                                 \
    return V;                                                                                                               \
}                                                                                                                           \
size_t name##_array_size(name##_array* v) { return v->size; }                                                               \
size_t name##_array_capacity(name##_array* v) { return v->capacity; }                                                       \
void name##_array_resize(name##_array* v, size_t new_size)                                                                  \
{                                                                                                                           \
    if (new_size < v->size)                                                                                                 \
    {                                                                                                                       \
        printf("ERROR: resize failed. new size is not large enough to accomodate elements in "#name"_array\n");             \
        exit(1);                                                                                                            \
    }                                                                                                                       \
                                                                                                                            \
    dtype* new_list = calloc(new_size, sizeof(dtype));                                                                      \
    if (new_list == NULL)                                                                                                   \
    {                                                                                                                       \
        printf("ERROR: resize failed. calloc returned NULL\n");                                                             \
        exit(1);                                                                                                            \
    }                                                                                                                       \
    for (int i = 0; i < v->size; i++)                                                                                       \
    {                                                                                                                       \
        new_list[i] = name##_array_get(v, i);                                                                               \
    }                                                                                                                       \
    free(v->list);                                                                                                          \
    v->list = new_list;                                                                                                     \
    v->capacity = new_size;                                                                                                 \
    v->head = 0;                                                                                                            \
}                                                                                                                           \
void name##_array_insert(name##_array* v, dtype item, size_t index)                                                         \
{                                                                                                                           \
    if (index > v->size)                                                                                                    \
    {                                                                                                                       \
        printf("ERROR: cannot insert at index=%zu for "#name"_array of size=%zu\n", index, v->size);                        \
        exit(1);                                                                                                            \
    }                                                                                                                       \
    if (v->size == v->capacity)                                                                                             \
    {                                                                                                                       \
        name##_array_resize(v, v->capacity * 2);                                                                            \
    }                                                                                                                       \
    if (index < v->size / 2)                                                                                                \
    {                                                                                                                       \
        v->head = v->head == 0 ? v->capacity - 1 : v->head - 1;                                                             \
        for (int i = 0; i < (int)index; i++)                                                                                \
        {                                                                                                                   \
            v->list[(v->head + i) % v->capacity] = v->list[(v->head + i + 1) % v->capacity];                                \
        }                                                                                                                   \
    }                                                                                                                       \
    else                                                                                                                    \
    {                                                                                                                       \
        for (int i = (int)v->size - 1; i >= (int)index; i--)                                                                \
        {                                                                                                                   \
            v->list[(v->head + i + 1) % v->capacity] = v->list[(v->head + i) % v->capacity];                                \
        }                                                                                                                   \
    }                                                                                                                       \
    v->list[(v->head + index) % v->capacity] = item;                                                                        \
    v->size++;                                                                                                              \
}                                                                                                                           \
void name##_array_append(name##_array* v, dtype item) { name##_array_insert(v, item, v->size); }                            \
void name##_array_prepend(name##_array* v, dtype item) { name##_array_insert(v, item, 0); }                                 \
void name##_array_push(name##_array* v, dtype item)  { name##_array_append(v, item); }                                      \
dtype name##_array_pop(name##_array* v) { return name##_array_remove(v, v->size - 1); }                                     \
dtype name##_array_peek(name##_array* v) { return name##_array_get(v, v->size - 1); }                                       \
void name##_array_enqueue(name##_array* v, dtype item) { name##_array_append(v, item); }                                    \
dtype name##_array_dequeue(name##_array* v) { return name##_array_remove(v, 0); }                                           \
void name##_array_set(name##_array* v, dtype item, size_t index)                                                            \
{                                                                                                                           \
    if (index >= v->size)                                                                                                   \
    {                                                                                                                       \
        printf("ERROR: cannot set index=%zu in "#name"_array of size=%zu\n", index, v->size);                               \
        exit(1);                                                                                                            \
    }                                                                                                                       \
    v->list[(v->head + index) % v->capacity] = item;                                                                        \
}                                                                                                                           \
name##_array* name##_array_merge(name##_array* left, name##_array* right)                                                   \
{                                                                                                                           \
    size_t min_size = name##_array_size(left) + name##_array_size(right);                                                   \
    size_t size = DEFAULT_VECT_CAPACITY;                                                                                    \
    while (size < min_size) { size *= 2; }                                                                                  \
                                                                                                                            \
    name##_array* merge = new_##name##_array_with_capacity(size);                                                           \
                                                                                                                            \
    for (size_t i = 0; i < name##_array_size(left); i++) { name##_array_enqueue(merge, name##_array_get(left, i)); }        \
    for (size_t i = 0; i < name##_array_size(right); i++) { name##_array_enqueue(merge, name##_array_get(right, i)); }      \
                                                                                                                            \
    return merge;                                                                                                           \
}                                                                                                                           \
bool name##_array_contains(name##_array* v, dtype item)                                                                     \
{                                                                                                                           \
    size_t index;                                                                                                           \
    return name##_array_find(v, item, &index);                                                                              \
}                                                                                                                           \
bool name##_array_find(name##_array* v, dtype item, size_t* index)                                                          \
{                                                                                                                           \
    for (int i = 0; i < v->size; i++)                                                                                       \
    {                                                                                                                       \
        if (name##_array_get(v, i) == item)                                                                                 \
        {                                                                                                                   \
            *index = i;                                                                                                     \
            return true;                                                                                                    \
        }                                                                                                                   \
    }                                                                                                                       \
    return false;                                                                                                           \
}                                                                                                                           \
dtype name##_array_get(name##_array* v, size_t index)                                                                       \
{                                                                                                                           \
    if (index >= v->size)                                                                                                   \
    {                                                                                                                       \
        printf("ERROR: attempted to access index=%zu for "#name"_array of size=%zu\n", index, v->size);                     \
        exit(1);                                                                                                            \
    }                                                                                                                       \
    return v->list[(v->head + index) % v->capacity];                                                                        \
}                                                                                                                           \
dtype name##_array_remove(name##_array* v, size_t index)                                                                    \
{                                                                                                                           \
    if (index >= v->size)                                                                                                   \
    {                                                                                                                       \
        printf("ERROR: cannot remove element at index=%zu for "#name"_array of size=%zu\n", index, v->size);                \
        exit(1);                                                                                                            \
    }                                                                                                                       \
    dtype item = name##_array_get(v, index);                                                                                \
    if (index < v->size / 2)                                                                                                \
    {                                                                                                                       \
        for (int i = index; i > 0; i--)                                                                                     \
        {                                                                                                                   \
            v->list[(v->head + i) % v->capacity] = v->list[(v->head + i - 1) % v->capacity];                                \
        }                                                                                                                   \
        v->list[v->head] = 0;                                                                                               \
        v->head = (v->head + 1) % v->capacity;                                                                              \
    }                                                                                                                       \
    else                                                                                                                    \
    {                                                                                                                       \
        for (int i = index; i < (int)v->size - 1; i++)                                                                      \
        {                                                                                                                   \
            v->list[(v->head + i) % v->capacity] = v->list[(v->head + i + 1) % v->capacity];                                \
        }                                                                                                                   \
        v->list[(v->head + v->size - 1) % v->capacity] = 0;                                                                 \
    }                                                                                                                       \
    v->size--;                                                                                                              \
                                                                                                                            \
    return item;                                                                                                            \
}                                                                                                                           \
name##_array* name##_array_copy(name##_array* v)                                                                            \
{                                                                                                                           \
    name##_array* copy = new_##name##_array_with_capacity(v->capacity);                                                     \
    for (int i = 0; i < name##_array_size(v); i++)                                                                          \
    {                                                                                                                       \
        name##_array_append(copy, name##_array_get(v, i));                                                                  \
    }                                                                                                                       \
    return copy;                                                                                                            \
}                                                                                                                           \
void name##_array_free(name##_array* v)                                                                                     \
{                                                                                                                           \
    free(v->list);                                                                                                          \
    free(v);                                                                                                                \
}                                                                                                                           \
int64_t name##_array_compare(name##_array* left, name##_array* right)                                                       \
{                                                                                                                           \
    if (left == NULL && right == NULL) { return 0; }                                                                        \
    else if (left == NULL) { return -1; }                                                                                   \
    else if (right == NULL) { return 1; }                                                                                   \
                                                                                                                            \
    if (name##_array_size(left) != name##_array_size(right))                                                                \
    {                                                                                                                       \
        return name##_array_size(left) - name##_array_size(right);                                                          \
    }                                                                                                                       \
    for (int i = 0; i < name##_array_size(left); i++)                                                                       \
    {                                                                                                                       \
        dtype lvalue = name##_array_get(left, i);                                                                           \
        dtype rvalue = name##_array_get(right, i);                                                                          \
        int64_t result = (lvalue < rvalue) - (lvalue > rvalue);                                                             \
        if (result) { return result; }                                                                                      \
    }                                                                                                                       \
    return 0;                                                                                                               \
}                                                                                                                           \
bool name##_array_equals(name##_array* left, name##_array* right) { return name##_array_compare(left, right) == 0; }        \
uint64_t name##_array_hash_getval(void* v, size_t i) { return hashcast(name##_array_get((name##_array*)v, i)); }            \
uint64_t name##_array_hash(name##_array* v) { return hash_uint_lambda_sequence(v, name##_array_size(v), name##_array_hash_getval); }  \
void name##_array_repr(name##_array* v)                                                                                     \
{                                                                                                                           \
    printf(#name" array\n");                                                                                                \
    for (int i = 0; i < v->capacity; i++)                                                                                   \
    {                                                                                                                       \
        printf("@%d: %"format, i, v->list[i]);                                                                              \
        if (v->head == i) { printf("    (HEAD)"); }                                                                         \
        if (v->head + v->size == i) { printf("    (END)"); }                                                                \
    }                                                                                                                       \
}                                                                                                                           \
void name##_array_str(name##_array* v)                                                                                      \
{                                                                                                                           \
    printf("[");                                                                                                            \
    for (int i = 0; i < v->size; i++)                                                                                       \
    {                                                                                                                       \
        if (i != 0) { printf(", "); }                                                                                       \
        printf("%"format, name##_array_get(v, i));                                                                          \
    }                                                                                                                       \
    printf("]");                                                                                                            \
}                                                                                                                           \

//hash int/uint simply by reading off value as uint
#define uint64_hashcast(v) v
#define bool_hashcast(v) (uint64_t)v
#define int64_hashcast(v) *(uint64_t*)v

//hash doubles by shifting decimal place several spots, and then rounding to int
#define double_hashcast(v) (uint64_t) (v * 1000)

//TODO->instead of print specifier, pass a whole print function
parray_implementation(uint64_t, UInt64Array_t, uint64, PRIu64, uint64_hashcast)
parray_implementation(bool, BoolArray_t, bool, "d", bool_hashcast)
parray_implementation(int64_t, Int64Array_t, int64, PRIi64, int64_hashcast)
parray_implementation(double, DoubleArray_t, double, "f", double_hashcast)

#endif