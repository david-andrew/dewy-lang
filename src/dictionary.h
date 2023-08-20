#ifndef DICTIONARY_H
#define DICTIONARY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "object.h"

/**
    Struct/type declaration for (hash,key,value) tuples, i.e. a single entry in a dictionary
*/
typedef struct
{
    uint64_t hash;
    obj* key;
    obj* value;
} dict_entry;

/**
    Struct/type declaration for dictionary
*/
typedef struct dict_struct // struct needs a name so it can be forward declared in object.h
{
    size_t size;
    // size_t deleted;
    size_t icapacity;
    size_t ecapacity;
    size_t* indices;
    dict_entry* entries;
} dict;

dict* new_dict();
obj* new_dict_obj(dict* d);
size_t dict_size(dict* d);
size_t dict_indices_capacity(dict* d);
size_t dict_entries_capacity(dict* d);
void dict_resize_indices(dict* d, size_t new_size);
void dict_resize_entries(dict* d, size_t new_size);
size_t dict_get_indices_probe(dict* d, obj* key);
size_t dict_get_entries_index(dict* d, obj* key);
size_t dict_set(dict* d, obj* key, obj* value);
bool dict_get_at_index(dict* d, size_t i, obj* key, obj* value);
bool dict_contains(dict* d, obj* key);
bool dict_contains_uint_key(dict* d, uint64_t u);
obj* dict_get(dict* d, obj* key);
obj* dict_get_uint_key(dict* d, uint64_t u);
obj* dict_get_codepoint_key(dict* d, uint32_t c);
void dict_set_codepoint_key(dict* d, uint32_t c, obj* value);
obj* dict_get_hashtag_key(dict* d, obj* hashtag_obj);
// void dict_delete(dict* d, obj* key);
// void dict_refresh(dict* d); //clear all deleted spaces and reinsert all elements
void dict_reset(dict* d);
void dict_free(dict* d);
void dict_free_elements_only(dict* d);
void dict_free_keys_only(dict* d);
void dict_free_values_only(dict* d);
void dict_free_table_only(dict* d);
void dict_repr(dict* d);
void dict_str(dict* d);

#endif