#ifndef DICTIONARY_H
#define DICTIONARY_H

#include "types.h"

//representation for an empty value in the dict indices table.
//since we only have pure ints, we say the max value (which probably won't be used) is EMPTY
#define EMPTY SIZE_MAX

dict* new_dict();
obj* new_dict_obj(dict* d);
size_t dict_size(dict* d);
size_t dict_indices_capacity(dict* d);
size_t dict_entries_capacity(dict* d);
bool dict_resize_indices(dict* d, size_t new_size);
bool dict_resize_entries(dict* d, size_t new_size);
uint64_t dict_find_empty_address(dict*, uint64_t hash);
bool dict_set(dict* d, obj* key, obj* value);
bool dict_contains(dict* d, obj* key);
obj* dict_get(dict* d, obj* key);
obj* dict_get_uint_key(dict* d, uint64_t u);
obj* dict_get_codepoint_key(dict* d, uint32_t c);
bool dict_set_codepoint_key(dict* d, uint32_t c, obj* value);
obj* dict_get_hashtag_key(dict* d, obj* hashtag_obj);
void dict_reset(dict* d);
void dict_free(dict* d);
void dict_free_elements_only(dict* d);
void dict_free_table_only(dict* d);
void dict_repr(dict* d);
void dict_str(dict* d);


#endif