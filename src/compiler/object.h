#ifndef OBJECT_H
#define OBJECT_H

#include "types.h"

//// Object Init Functions ////

obj* new_bool(bool b);
bool* new_bool_ptr(bool b);     //lighter weight than obj* of bool
obj* new_char(uint32_t c);
obj* new_int(int64_t i);
obj* new_uint(uint64_t u);
obj* new_string(char* s);       //new string object, from an allocated string
obj* new_ustr(char* s);         //new string object from a non-allocated string


//// Utility Functions ////

size_t obj_size(obj* o);
obj* obj_copy(obj* o);
obj* obj_copy_inner(obj* o, dict* refs);
void obj_print(obj* o);
uint64_t obj_hash(obj* o) ;
int64_t obj_compare(obj* left, obj* right);
bool obj_equals(obj* left, obj* right);
void obj_free(obj* o);



#endif