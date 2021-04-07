#ifndef OBJECT_C
#define OBJECT_C

#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "object.h"
#include "tuple.h"
#include "utilities.h"
#include "ustring.h"
#include "vector.h"
#include "dictionary.h"
#include "set.h"
#include "metatoken.h"
#include "charset.h"
#include "metaitem.h"
#include "gotokey.h"
#include "reduction.h"
#include "gss.h"
#include "srnglr.h"


/**
 * Functions to create lightweight pointers to primitive types.
 * Lighter weight than using obj*, so can be used if necessary.
 */
#define new_primitive(fname, dtype)         \
dtype* fname(dtype p)                       \
{                                           \
    dtype* p_ptr = malloc(sizeof(dtype));   \
    *p_ptr = p;                             \
    return p_ptr;                           \
}
new_primitive(new_bool, bool)
new_primitive(new_char, uint32_t)
new_primitive(new_int, int64_t)
new_primitive(new_uint, uint64_t)
// new_primitive(new_pointer, void*)

/**
 * Object wrapped versions of a primitive.
 */
#define new_primitive_obj(fname, dtype, dtype_t)    \
obj* fname##_obj(dtype p)                           \
{                                                   \
    obj* P = malloc(sizeof(obj));                   \
    *P = (obj){.type=dtype_t, .data=fname(p)};      \
    return P;                                       \
}
new_primitive_obj(new_bool, bool, Boolean_t)
new_primitive_obj(new_char, uint32_t, Character_t)
new_primitive_obj(new_int, int64_t, Integer_t)
new_primitive_obj(new_uint, uint64_t, UInteger_t)


/**
 *  Create a new string object, from an allocated string
 *
 *  @param s a HEAP-ALLOCATED pointer to a string. free() will be called on this string at the end of its life
 *  @return an obj* containing our string
 */
obj* new_string_obj(char* s)
{
    obj* S = malloc(sizeof(obj));
    *S = (obj){.type=String_t, .data=s};
    return S;
}


/**
 * Create a new string object by copying the given string.
 * Useful for turning const char[] strings into string objects
 */
obj* new_string_obj_copy(char* s)
{
    return new_string_obj(clone(s));
}


/**
 * Recursive deep copy of an object.
 * refs dict is used to ensure all objects are duplicated only once
 */
obj* obj_copy(obj* o)
{
    dict* refs = new_dict();
    obj* copy = obj_copy_with_refs(o, refs);
    
    //free the refs dictionary without touching any of the references
    dict_free_table_only(refs);
    return copy;
}

/**
 * Inner recursive deep copy of an object.
 * Takes in a refs dict containing objects that have already been copied.
 */
obj* obj_copy_with_refs(obj* o, dict* refs)
{
    if (o == NULL) { return NULL; }
    
    obj* copy;

    //check if we already copied this object (e.g. cyclical references)
    if ((copy = dict_get(refs, o))) { return copy; }
    
    //construct the copy object
    copy = malloc(sizeof(obj));
    copy->type = o->type;

    //save into refs original->copy.
    //copy is still incomplete, but this lets us handle cycles
    dict_set(refs, o, copy);
    switch (o->type)
    {
        case Boolean_t: //copy boolean
        {
            copy->data = new_bool(*(bool*)o->data);
            break;
        }
        case Character_t: //copy a unicode character
        {
            copy->data = new_char(*(uint32_t*)o->data);
            break;
        }
        case Integer_t: //copy int64
        {
            copy->data = new_int(*(int64_t*)o->data);
            break;
        }
        case UInteger_t: //copy uint64
        {
            copy->data = new_uint(*(uint64_t*)o->data);
            break;
        }
        case String_t: //copy string
        {
            copy->data = clone((char*)o->data);
            break;
        }
        case UnicodeString_t: //copy unicode string
        {
            copy->data = ustring_clone((uint32_t*)o->data);
            break;
        }
        case MetaToken_t:
        {
            copy->data = metatoken_copy((metatoken*)o->data);
            break;
        }
        case Push_t:
        {
            copy->data = new_uint(*(uint64_t*)o->data);
            break;
        }
        case Reduction_t:
        {
            reduction* r = o->data;
            copy->data = new_reduction(r->head_idx, r->length);
            break;
        }
        case Accept_t:
        {
            copy->data = NULL;
            break;
        }
        // case MetaSymbol_t:{ break; }
        case Vector_t: 
        {
            copy->data = vect_copy_with_refs((vect*)o->data, refs);
            break;
        }
        // case Dictionary_t: //TODO->set up dict copy that uses refs
        // {
        //     copy->data = dict_copy_with_refs((dict*)o->data, refs);
        //     break;
        // }
        // case Set_t: //TODO->set up set copy that uses refs
        // {
        //     copy->data = set_copy_with_refs((set*)o->data, refs);
        // }
        default: 
        {
            printf("WARNING, obj_copy() is not implemented for object of type \"%d\"\n", o->type); 
            copy->data = NULL;
            break;
        }
    }

    return copy;
}


void obj_str(obj* o)
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
        case CharSet_t: charset_str(o->data); break;
        case Integer_t: printf("%ld", *(int64_t*)o->data); break;
        case UInteger_t: printf("%lu", *(uint64_t*)o->data); break;
        case UIntNTuple_t: tuple_str(o->data); break;
        case String_t: printf("%s", o->data); break;
        case UnicodeString_t: ustring_str(o->data); break;
        case MetaToken_t: metatoken_repr(o->data); break;
        case MetaItem_t: metaitem_str(o->data); break;
        case FSet_t: fset_str(o->data); break;
        case GotoKey_t: gotokey_str(o->data); break;
        case Push_t: push_str(*(uint64_t*)o->data); break;
        case Reduction_t: reduction_str(o->data); break;
        case Accept_t: accept_str(); break;
        case GSSEdge_t: gss_edge_str(o->data); break;
        case Vector_t: vect_str(o->data); break;
        case Dictionary_t: dict_str(o->data); break;
        case Set_t: set_str(o->data); break;
        default: printf("WARNING: obj_str() is not implemented for object of type \"%d\"\n", o->type); break;
    }
}


/**
 * Return the width of the given object when printed out to stdout.
 * Counts unicode characters as 1 unit instead of utf-8 characters.
 */
int obj_strlen(obj* o)
{
    if (o == NULL) { return strlen("NULL"); }

    switch (o->type)
    {
        case UnicodeString_t: return ustring_len(o->data);
        case CharSet_t: return charset_strlen(o->data);
    
        default:
            printf("WARNING: obj_strlen() is not implementede for object of type \"%d\"\n", o->type); exit(1);
    }
}





uint64_t obj_hash(obj* o) 
{
    if (o == NULL) { return 0; }
    switch (o->type)
    {
        case Boolean_t: return hash_bool(*(bool*)o->data);
        case Character_t: return hash_uint(*(uint32_t*)o->data);
        case CharSet_t: return charset_hash(o->data);
        case Integer_t: return hash_int(*(int64_t*)o->data);
        case UInteger_t: return hash_uint(*(uint64_t*)o->data);
        case UIntNTuple_t: return tuple_hash(o->data);
        case String_t: return fnv1a(o->data);
        case UnicodeString_t: return ustring_hash(o->data);
        // case MetaToken_t: return metatoken_hash((metatoken*)o->data);
        case MetaItem_t: return metaitem_hash(o->data);
        case Slice_t: return slice_hash(o->data);
        // case FSet_t: return fset_hash(o->data);
        case GotoKey_t: return gotokey_hash(o->data);
        case Push_t: return hash_uint(*(uint64_t*)o->data);
        case Reduction_t: return reduction_hash(o->data);
        case Accept_t: return hash_uint(0);
        case GSSEdge_t: return gss_edge_hash(o->data);
        case Vector_t: return vect_hash(o->data);
        // case Dictionary_t: return dict_hash(o->data);
        case Set_t: return set_hash(o->data);
        default: printf("WARNING: obj_hash() is not implemented for object of type \"%d\"\n", o->type); obj_str(o); exit(1);
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
        // case CharSet_t: return charset_compare((charset*)left->data, (charset*)right->data);
        case Integer_t: return *(int64_t*)left->data - *(int64_t*)right->data;
        case UInteger_t: return *(uint64_t*)left->data - *(uint64_t*)right->data;
        case String_t: return strcmp((char*)left->data, (char*)right->data);
        case UnicodeString_t: return ustring_cmp((uint32_t*)left->data, (uint32_t*)right->data);
        // case MetaToken_t: return metatoken_compare((metatoken*)left->data, (metatoken*)right->data);
        case Vector_t: return vect_compare((vect*)left->data, (vect*)right->data);
        // case Dictionary_t: return dict_compare((dict*)left->data, (dict*)right->data);
        // case Set_t: return set_compare((set*)left->data, (set*)right->data);
        default: printf("WARNING: obj_compare() is not implemented for object of type \"%d\"\n", left->type); exit(1);
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
        case UIntNTuple_t: return tuple_equals(left->data, right->data);
        // case Dictionary_t: return dict_equals((dict*)left->data, (dict*)right->data);
        case Set_t: return set_equals((set*)left->data, (set*)right->data);
        case CharSet_t: return charset_equals(left->data, right->data);
        case MetaItem_t: return metaitem_equals(left->data, right->data);
        case Slice_t: return slice_equals(left->data, right->data);
        //case FSet_t: return fset_equals(left->data, right->data);
        case GotoKey_t: return gotokey_equals(left->data, right->data);
        case Push_t: return *(uint64_t*)left->data == *(uint64_t*)right->data;
        case Reduction_t: return reduction_equals(left->data, right->data);
        case Accept_t: return true; //accepts have no internal data
        case GSSEdge_t: return gss_edge_equals(left->data, right->data);
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
            //Simple objects with no nested data can be freed with free(o->data)
            case Boolean_t:
            case Character_t:
            case Integer_t:
            case UInteger_t:
            case String_t:
            case UnicodeString_t:
            case Push_t:
                free(o->data); 
                break;

            //Objects with nested datastructures must free their inner contents first
            case UIntNTuple_t: tuple_free(o->data); break;
            case MetaToken_t: metatoken_free((metatoken*)o->data); break; 
            case Vector_t: vect_free((vect*)o->data); break;
            case Dictionary_t: dict_free((dict*)o->data); break;
            case Set_t: set_free((set*)o->data); break;
            case CharSet_t: charset_free((charset*)o->data); break;
            case MetaItem_t: metaitem_free((metaitem*)o->data); break;
            case Slice_t: slice_free(o->data); break;
            case FSet_t: fset_free(o->data); break;
            case GotoKey_t: gotokey_free(o->data); break;
            case Reduction_t: reduction_free(o->data); break;
            case GSSEdge_t: gss_edge_free(o->data);

            //objects with no internal data
            case Accept_t: break;

            default: 
                printf("WARNING: obj_free() is not implemented for object of type \"%d\""
                "\ncontents: ", o->type); obj_str(o); printf("\n");
                exit(1);
        }
        free(o);
    }
}

/**
 * Get the void* data from inside an obj*, and free the obj* container.
 * If the object does not match the specified type, throw an error.
 */
void* obj_free_keep_inner(obj* o, obj_type type)
{
    if (o->type == type)
    {
        void* data = o->data;
        free(o);
        return data;
    }
    else
    {
        printf("ERROR: attempted to obj_free_keep_inner() on an incorrect type:\n");
        obj_str(o);
        printf("Expected type {%d}\n", type);
        exit(1);
    }
}

#endif