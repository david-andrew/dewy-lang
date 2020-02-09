#ifndef SET_C
#define SET_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.c"
#include "object.c"
#include "dictionary.c"

typedef struct set_struct
{
    dict* d; //a set is just a wrapper around a dict
} set;

set* new_set();
obj* new_set_obj();
obj* set_obj_wrap(set* s);
size_t set_size(set* S);
// size_t set_capacity(set* S);
bool set_add(set* S, obj* item);
// bool set_remove(set* s, obj* item);
bool set_contains(set* S, obj* item);
set* set_copy(set* S);
set* set_union(set* A, set* B);
set* set_intersect(set* A, set* B);
bool set_equals(set* A, set* B);
void set_reset(set* S);
void set_free(set* S);
void set_repr(set* S);
void set_str(set* S);


set* new_set()
{
    set* S = malloc(sizeof(set));
    S->d = new_dict(); //create the wrapped dictionary
    return S;
}

obj* new_set_obj()
{
    obj* S = malloc(sizeof(obj));
    S->type = Set_t;
    S->size = 0; //size needs to be determined on a per call basis
    set** s_ptr = malloc(sizeof(set*));
    *s_ptr = new_set();
    S->data = (void*)s_ptr;
    return S;
}

/**
    Wrap a set* inside of an obj*
*/
obj* set_obj_wrap(set* s)
{
    obj* S = malloc(sizeof(obj));
    S->type = Set_t;
    S->size = 0;
    set** s_ptr = malloc(sizeof(set*));
    *s_ptr = s;
    S->data = (void*)s_ptr;
    return S;
}

size_t set_size(set* S) 
{ 
    return dict_size(S->d); 
}

// size_t set_capacity(set* S) 
// { 
//     return dict_capacity(S->d); 
// }

bool set_add(set* S, obj* item)
{
    return dict_set(S->d, item, NULL); //to store an item, use the item as the key
}

bool set_contains(set* S, obj* item)
{
    return dict_contains(S->d, item);
}

set* set_copy(set* S)
{
    set* copy = new_set();
    for (int i = 0; i < set_size(S); i++)
    {
        dict_entry e = S->d->entries[i];
        set_add(copy, e.key);
    }
    return copy;
}

set* set_union(set* A, set* B)
{
    set* S = new_set();

    //This part could be replaced with `S = set_copy(A);`
    for (int i = 0; i < set_size(A); i++)
    {
        dict_entry e = A->d->entries[i];
        set_add(S, obj_copy(e.key)); //add a copy of the element to the union set
    }
    for (int i = 0; i < set_size(B); i++)
    {
        dict_entry e = B->d->entries[i];        
        if (!set_contains(S, e.key)) //only add an element if it wasn't in the first list (so that we don't try to add duplicates)
        {
            set_add(S, obj_copy(e.key));
        }
    }

    return S;
}

set* set_intersect(set* A, set* B)
{
    set* S = new_set();
    for (int i = 0; i < set_size(A); i++)
    {
        dict_entry e = A->d->entries[i];
        if (set_contains(B, e.key)) //only if both A and B have the item
        {
            set_add(S, obj_copy(e.key));
        }
    }
    return S;
}

bool set_equals(set* A, set* B)
{
    //check if sizes are different
    if (set_size(A) != set_size(B)) return false;

    //check if each element in A is in B. Since sizes are the same, and sets don't have duplicates, this will indicate equality
    for (int i = 0; i < set_size(A); i++)
    {
        dict_entry e = A->d->entries[i];
        if (!set_contains(B, e.key))
        {
            return false;
        }
    }
    return true;
}

void set_reset(set* S)
{
    dict_reset(S->d);
}

void set_free(set* S)
{
    dict_free(S->d);
}

void set_repr(set* S)
{
    dict* d = S->d;
    //print out all elements in the set (dictionary) indices table and entries vector
    printf("set:\nindices = [");
    for (int i = 0; i < d->icapacity; i++)
    {
        if (i != 0) printf(", ");
        if (d->indices[i] == EMPTY) printf("None");
        else printf("%zu", d->indices[i]);
    }
    printf("]\nentries = [");
    for (int i = 0; i < d->size; i++)
    {
        if (i != 0) printf(",\n           ");
        dict_entry e = d->entries[i];
        printf("[%lu, ", e.hash);
        obj_print(e.key);
        printf("]");
    }
    printf("]\n");}

void set_str(set* S)
{
    printf("{");
    for (int i = 0; i < set_size(S); i++)
    {
        dict_entry e = S->d->entries[i];
        if (i != 0) printf(", ");
        obj_print(e.key);
    }
    printf("}");
}


#endif