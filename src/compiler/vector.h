#ifndef VECTOR_H
#define VECTOR_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "object.h"
#include "dictionary.h"

/**
    Struct/type declaration for 1D lists of objects. Implemented as an ArrayDeque. 
    see: http://opendatastructures.org/ods-java/2_4_ArrayDeque_Fast_Deque_O.html
*/
typedef struct
{
    size_t head;
    size_t size;
    size_t capacity;
    obj** list;
} vect;


vect* new_vect();
obj* new_vect_obj(vect* v);
size_t vect_size(vect* v);
size_t vect_capacity(vect* v);
bool vect_resize(vect* v, size_t new_size);
bool vect_insert(vect* v, obj* item, size_t index);
//bool vect_multi_insert(vect* v, vect* items, size_t index);
bool vect_append(vect* v, obj* item);
bool vect_prepend(vect* v, obj* item);
//bool vect_multi_append(vect* v, vect* items);
//bool vect_multi_prepend(vect* v, vect* items);
bool vect_push(vect* v, obj* item);
obj* vect_pop(vect* v);
obj* vect_peek(vect* v);

bool vect_enqueue(vect* v, obj* item);
obj* vect_dequeue(vect* v);

bool vect_set(vect* v, obj* item, size_t index);
bool vect_contains(vect* v, obj* item);
bool vect_find(vect* v, obj* item, size_t* index);
obj* vect_get(vect* v, size_t index);
obj* vect_remove(vect* v, size_t index);
void vect_delete(vect* v, size_t index);
void vect_reset(vect* v);
vect* vect_copy(vect* src, vect* dest);
vect* vect_copy_with_refs(vect* v, dict* refs);
void vect_free(vect* v);
void vect_free_list_only(vect* v);
int64_t vect_compare(vect* left, vect* right);
uint64_t vect_hash(vect* v);
void vect_repr(vect* v);
void vect_str(vect* v);

#endif