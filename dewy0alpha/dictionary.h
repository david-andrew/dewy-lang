#ifndef DICTIONARY_H
#define DICTIONARY_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#include "object.h"

#define DEFAULT_DICT_CAPACITY 8
#define MAX_LOAD 2 / 3

//representation for an empty value in the dict indices table.
//since we only have pure ints, we say the max value (which probably won't be used) is EMPTY
#define EMPTY SIZE_MAX

//constant to assign to hashes that are 0, so that the lfsr algorithm doesn't get stuck at 0
#define NONZERO_HASH 0xDEADBEEF


//structure for (hash,key,value) tuples, i.e. a single entry in a dictionary
typedef struct dict_entry_struct 
{
    uint64_t hash;
    obj* key;
    obj* value;
} dict_entry;

//structure for dictionary object. preferred to pass dict* rather than dict
typedef struct dict_struct
{
    size_t size;
    size_t icapacity;
    size_t ecapacity;
    size_t* indices;
    dict_entry* entries;
} dict;


dict* new_dict();
obj* new_dict_obj();
size_t dict_size(dict* d);
size_t dict_indices_capacity(dict* d);
size_t dict_entries_capacity(dict* d);
bool dict_resize_indices(dict* d, size_t new_size);
bool dict_resize_entries(dict* d, size_t new_size);
uint64_t dict_find_empty_address(dict*, uint64_t hash);
bool dict_set(dict* d, obj* key, obj* value);
bool dict_contains(dict* d, obj* key);
obj* dict_get(dict* d, obj* key);
void dict_reset(dict* d);
void dict_free(dict* d);
void dict_free_table_only(dict* d);
void dict_repr(dict* d);
void dict_str(dict* d);


#endif