#ifndef OBJECT_H
#define OBJECT_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

//// Object structs and typedefs ////

/** 
    Enum for each of the different types object types that exist
*/
typedef enum 
{ 
    Boolean_t,
    Character_t,
    CharSet_t,
    Integer_t, 
    UInteger_t,
    String_t,
    UnicodeString_t,
    MetaToken_t,
    Vector_t,
    Dictionary_t,
    Set_t,
    ASTCat_t,
    ASTOr_t,
    ASTStar_t,
    ASTLeaf_t,
} obj_type;

/**
    Struct/type declaration for generic objects
*/
typedef struct
{
    obj_type type;  //integer specifying what type of object.
    size_t size;    //size of the data allocated for this object
    void* data;     //data allocated for this object
} obj;

// forward declare so we can use dict here
typedef struct dict_struct dict;

//// Object Init Functions ////

obj* new_bool(bool b);
bool* new_bool_ptr(bool b);     //lighter weight than obj* of bool
obj* new_char(uint32_t c);
obj* new_int(int64_t i);
obj* new_uint(uint64_t u);
obj* new_string(char* s);       //new string object, from an allocated string
obj* new_unicode_string(uint32_t* s);
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