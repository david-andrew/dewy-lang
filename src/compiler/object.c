#ifndef OBJECT_C
#define OBJECT_C

#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "object.h"
#include "utilities.h"
#include "vector.h"
#include "dictionary.h"
#include "set.h"
#include "metatoken.h"
#include "mast.h"


obj* new_bool(bool b)
{
    obj* B = malloc(sizeof(obj));
    B->type = Boolean_t;
    B->size = sizeof(bool);
    bool* b_ptr = malloc(sizeof(bool));
    *b_ptr = b;
    B->data = (void*)b_ptr;
    return B;
}

/**
    create a new pointer to a bool. lighter weight than an obj*
*/
bool* new_bool_ptr(bool b)
{
    bool* b_ptr = malloc(sizeof(bool));
    *b_ptr = b;
    return b_ptr;
}

obj* new_char(uint32_t c)
{
    obj* C = malloc(sizeof(obj));
    C->type = Character_t;
    C->size = sizeof(uint32_t);
    uint32_t* c_ptr = malloc(sizeof(uint32_t));
    *c_ptr = c;
    C->data = (void*)c_ptr;
    return C;
}

obj* new_int(int64_t i)
{
    obj* I = malloc(sizeof(obj));
    I->type = Integer_t;
    I->size = sizeof(int64_t);
    int64_t* i_ptr = malloc(sizeof(int64_t)); 
    *i_ptr = i;
    I->data = (void*)i_ptr;
    return I;
}

obj* new_uint(uint64_t u)
{
    obj* U = malloc(sizeof(obj));
    U->type = UInteger_t;
    U->size = sizeof(uint64_t);
    uint64_t* u_ptr = malloc(sizeof(uint64_t));
    *u_ptr = u;
    U->data = (void*)u_ptr;
    return U;
}


/*
    Create a new string object, from an allocated string

    @param char* s: a HEAP-ALLOCATED pointer to a string. free() will be called on this string at the end of its life
    @return obj* S: an object containing our string
*/
obj* new_string(char* s)
{
    obj* S = malloc(sizeof(obj));
    S->type = String_t;
    S->size = strlen(s);
    char** s_ptr = malloc(sizeof(char*));
    *s_ptr = s;
    S->data = (void*)s_ptr;
    return S;
}

obj* new_unicode_string(uint32_t* s)
{
    obj* S = malloc(sizeof(obj));
    S->type = UnicodeString_t;
    S->size = unicode_strlen(s);
    uint32_t** s_ptr = malloc(sizeof(uint32_t*));
    *s_ptr = s;
    S->data = (void*)s_ptr;
    return S;
}

/*
    Create a new string object from a non-allocated string
*/
obj* new_ustr(char* s)
{
    return new_string(clone(s));
}


/*
    get the current size of the object's data
*/
size_t obj_size(obj* o)
{
    if (o == NULL) { return 0; }
    switch (o->type)
    {
        case Boolean_t: return o->size;
        case Character_t: return o->size;
        case Integer_t: return o->size;
        case UInteger_t: return o->size;
        case String_t: return o->size;
        case MetaToken_t: return o->size; //TBD if token should be sized this way
        case Vector_t: return vect_size(*(vect**)o->data);
        case Dictionary_t: return dict_size(*(dict**)o->data);
        case Set_t: return set_size(*(set**)o->data);
        default: 
        {
            printf("WARNING obj_size() is not implemented for object of type \"%d\"\n", o->type);
            return 0;
        }
    }
}

//recursive deep copy of an object
//TODO->swap over to maintining a dictionary of pointers so that the deep copy can handle cyclical objects
//dict points from old pointer to new pointer, and if an istance is requested to be copied that already exists, simply substitute the existing pointer
obj* obj_copy(obj* o)
{
    dict* refs = new_dict();
    obj* copy = obj_copy_inner(o, refs);
    
    //free the refs dictionary without touching any of the references
    dict_free_table_only(refs);
    return copy;
}

obj* obj_copy_inner(obj* o, dict* refs)
{
    if (o == NULL) { return NULL; }
    
    obj* copy;

    //check if we already copied this object (i.e. cyclical references
    if ((copy = dict_get(refs, o))) { return copy; }
    
    //construct the copy object
    copy = malloc(sizeof(obj));
    copy->type = o->type;
    copy->size = o->size;
    switch (o->type)
    {
        case Boolean_t: //copy boolean
        {
            bool* copy_ptr = malloc(sizeof(bool));
            *copy_ptr = *(bool*)o->data;
            copy->data = (void*)copy_ptr;
            break;
        }
        case Character_t: //copy a unicode character
        {
            uint32_t* copy_ptr = malloc(sizeof(uint32_t));
            *copy_ptr = *(uint32_t*)o->data;
            copy->data = (void*)copy_ptr;
            break;
        }
        case Integer_t: //copy int64
        {
            int64_t* copy_ptr = malloc(sizeof(int64_t));
            *copy_ptr = *(int64_t*)o->data;
            copy->data = (void*)copy_ptr;
            break;
        }
        case UInteger_t: //copy uint64
        {
            uint64_t* copy_ptr = malloc(sizeof(uint64_t));
            *copy_ptr = *(uint64_t*)o->data;
            copy->data = (void*)copy_ptr;
            break;
        }
        case String_t: //copy string
        {
            char** copy_ptr = malloc(sizeof(char*));
            *copy_ptr = clone(*(char**)o->data);
            copy->data = (void*)copy_ptr;
            break;
        }
        // case MetaToken_t:
        // {
        //     copy->data = (void*)token_obj_copy((token*)o->data, refs);
        //     break;

        // }
        case Vector_t: 
        {
            vect** copy_ptr = malloc(sizeof(vect*));
            *copy_ptr = vect_copy_with_refs(*(vect**)o->data, refs);
            copy->data = (void*)copy_ptr;
            break;
        }
        // case Dictionary_t: //TODO->set up dict copy that uses refs
        // {
        //     copy->data = (void*)dict_obj_copy((dict*)o->data, refs);
        //     break;
        // }
        // case Set_t: //TODO->set up set copy that uses refs
        // {
        //     copy->data = (void*)set_obj_copy((set*)o->data, refs);
        // }
        default: 
        {
            printf("WARNING, obj_copy() is not implemented for object of type \"%d\"\n", o->type); 
            copy->data = NULL;
            break;
        }
    }

    //save a copy of this object's reference into refs, and return the object
    dict_set(refs, o, copy);
    return copy;
}


void obj_print(obj* o)
{
    if (o == NULL) 
    { 
        printf("NULL");
        return;
    }
    switch (o->type)
    {
        case Boolean_t: printf(*(bool*)o->data ? "true" : "false"); break;
        case Character_t: unicode_str(*(uint32_t*)o->data); break;
        case Integer_t: printf("%ld", *(int64_t*)o->data); break;
        case UInteger_t: printf("%lu", *(uint64_t*)o->data); break;
        case String_t: printf("%s", *(char**)o->data); break;
        case MetaToken_t: metatoken_str((metatoken*)o->data); break;
        case Vector_t: vect_str(*(vect**)o->data); break;
        case Dictionary_t: dict_str(*(dict**)o->data); break;
        case Set_t: set_str(*(set**)o->data); break;
        case ASTLeaf_t:
        case ASTStar_t:
        case ASTOr_t:
        case ASTCat_t: ast_str(o); break;
        default: printf("WARNING: obj_print() is not implemented for object of type \"%d\"\n", o->type); break;
    }
}




// uint64_t meta_token_hash(obj* o);//forward declare
uint64_t obj_hash(obj* o) 
{
    if (o == NULL) { return 0; }
    switch (o->type)
    {
        case Boolean_t: return hash_bool(*(bool*)o->data);
        case Character_t: return hash_uint(*(uint32_t*)o->data);
        case Integer_t: return hash_int(*(int64_t*)o->data);
        case UInteger_t: return hash_uint(*(uint64_t*)o->data);
        case String_t: return fnv1a(*(char**)o->data);
        // case MetaToken_t: return meta_token_hash(o);
        case Vector_t: return vect_hash(*(vect**)o->data);
        // case Dictionary_t: return dict_hash((dict*)o->data);
        case Set_t: return set_hash(*(set**)o->data);
        default: printf("WARNING: obj_hash() is not implemented for object of type \"%d\"\n", o->type); return 0;
    }
}

int64_t obj_compare(obj* left, obj* right)
{
    //TODO->check these.
    //handle case where either or both are null
    if (left == NULL && right == NULL) { return 0; } //both null means both equal
    else if (left == NULL) { return -1; } //left only null means left comes first
    else if (right == NULL) { return 1; } //right only null means right comes first
    
    //if the objects are of different type, order by type value
    if (left->type != right->type)
    {
        return left->type - right->type;
    }

    switch (left->type)
    {
        case Boolean_t: return *(bool*)left->data - *(bool*)right->data;    //this works because bool is a macro for int
        case Character_t: return *(uint32_t*)left->data - *(uint32_t*)right->data;
        case Integer_t: return *(int64_t*)left->data - *(int64_t*)right->data;
        case UInteger_t: return *(uint64_t*)left->data - *(uint64_t*)right->data;
        case String_t: return strcmp(*(char**)left->data, *(char**)right->data);
        // case MetaToken_t: return token_compare((token*)left->data, (token*)right->data);
        case Vector_t: return vect_compare(*(vect**)left->data, *(vect**)right->data);
        // case Dictionary_t: return dict_compare((dict*)left->data, (dict*)right->data);
        // case Set_t: return set_compare((set*)left->data, (set*)right->data);
        default: printf("WARNING: obj_compare() is not implemented for object of type \"%d\"\n", left->type); return 0;
    }
}

bool obj_equals(obj* left, obj* right)
{
    //handle case where either or both are null
    if (left == NULL && right == NULL) { return true; }         //both null means both equal
    else if (left == NULL || right == NULL) { return false; }   //left or right only null means not equal
    
    //if the objects are of different type, then not equal
    if (left->type != right->type) { return false; }

    switch (left->type)
    {
        // case Dictionary_t: return dict_equals(*(dict**)left->data, *(dict**)right->data);
        case Set_t: return set_equals(*(set**)left->data, *(set**)right->data);
        default: return obj_compare(left, right) == 0;
    }

    //TODO->make this call equals directly for sets/dictionaries, as compare will be inefficient
    
}

void obj_free(obj* o)
{
    if (o != NULL)
    {
        //TODO->any object specific freeing that needs to happen. e.g. vects/dicts/sets need to call their specific version of free
        //handle freeing of o->data
        switch (o->type)
        {
            case Boolean_t: free(o->data); break;   //free boolean pointer
            case Character_t: free(o->data); break; //free character (uint32)
            case Integer_t: free(o->data); break;   //free uint pointer
            case UInteger_t: free(o->data); break;  //free int pointer
            case String_t:                          //free the string
            {
                free(*(char**)o->data);
                free(o->data);
                break;
            }
            case MetaToken_t: metatoken_free((metatoken*)o->data); break; 
            case Vector_t: 
            {
                vect_free(*(vect**)o->data); 
                free(o->data);
                break;
            }
            case Dictionary_t:
            { 
                dict_free(*(dict**)o->data); 
                break;
            }
            case Set_t:
            {
                set_free(*(set**)o->data); 
                break;
            }
            default: printf("WARNING: obj_free() is not implemented for object of type \"%d\"\n", o->type); break;
        }
        free(o);
    }
}

#endif