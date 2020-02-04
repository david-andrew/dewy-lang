#ifndef OBJECT_H
#define OBJECT_H

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

// #include "dictionary.h" //can't include because cyclic dependancy
typedef struct dict_struct dict; //declared externally

typedef enum obj_types 
{ 
    Boolean_t,
    Character_t,
    Integer_t, 
    UInteger_t,
    String_t,
    Token_t,
    Vector_t,
    Dictionary_t,
    Set_t,
    //AST_t //leaf, or, cat, star
} obj_type;


typedef struct obj_struct
{
    obj_type type;  //integer specifying what type of object.
    size_t size;    //size of the data allocated for this object
    void* data;     //data allocated for this object
} obj;


obj* new_bool(bool b);
obj* new_char(uint32_t c); //unicode characters
obj* new_int(int64_t i);
obj* new_uint(uint64_t u);
obj* new_string(char* s);
obj* new_ustr(char* s);
size_t obj_size(obj* o);
obj* obj_copy(obj* o);
obj* obj_copy_inner(obj* o, dict* refs);
void obj_print(obj* o);
uint64_t obj_hash(obj* o);
int64_t obj_compare(obj* left, obj* right);
bool obj_equals(obj* left, obj* right);
void obj_free(obj* o);
//dict_hash, dict_compare, dict_free
//set_hash, set_compare, set_free


#endif