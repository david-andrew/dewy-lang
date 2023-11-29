#ifndef SET_H
#define SET_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "object.h"

//struct for each row of the set object. Mirrors dictionary, but with just value instead of key+value
typedef struct
{
    uint64_t hash;
    obj* item;
} set_entry;

//struct for the set object
typedef struct
{
    size_t size;
    size_t icapacity;
    size_t ecapacity;
    size_t* indices;
    set_entry* entries;
} set;

set* new_set();
obj* new_set_obj(set* s);
// obj* set_obj_wrap(set* s);
size_t set_size(set* s);
size_t set_indices_capacity(set* s);
size_t set_entries_capacity(set* s);
void set_resize_indices(set* s, size_t new_size);
void set_resize_entries(set* s, size_t new_size);
size_t set_get_indices_probe(set* s, obj* item);
size_t set_get_entries_index(set* s, obj* item);
bool set_is_index_empty(size_t index);
void set_add(set* s, obj* item);
size_t set_add_return_index(set* s, obj* item);
obj* set_get_at_index(set* s, size_t i);
// bool set_remove(set* s, obj* item);
bool set_contains(set* s, obj* item);
set* set_copy(set* s);
set* set_union(set* a, set* b);
void set_union_into(set* a, set* b);
set* set_union_equals(set* a, set* b);
set* set_intersect(set* a, set* b);
bool set_equals(set* a, set* b);
uint64_t set_hash(set* s);
void set_reset(set* s);
void set_free(set* s);
void set_free_elements_only(set* s);
void set_free_table_only(set* s);
void set_repr(set* s);
void set_str(set* s);

#endif