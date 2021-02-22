#ifndef SET_C
#define SET_C

#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <stdbool.h>
#include <string.h>

#include "utilities.h"
#include "object.h"
#include "set.h"

#define DEFAULT_SET_CAPACITY 8
#define MAX_LOAD 2 / 3

//constant to assign to hashes that are 0, so that the lfsr algorithm doesn't get stuck at 0
#define NONZERO_HASH 0xDEADBEEF

//representation for an empty item in the set indices table.
//since we only have pure ints, we say the max value (which probably won't be used) is EMPTY
//also allows us to initialize the indices array using memset with -1
#define EMPTY SIZE_MAX

// Implementation of Set is basically identical to dictionary's implementation


set* new_set()
{
    set* s_ptr = malloc(sizeof(set));
    set s = {
        .size = 0,                                                  //initial elements in the set (i.e. none)
        .icapacity = DEFAULT_SET_CAPACITY,                          //initial capacity of the indices table
        .ecapacity = DEFAULT_SET_CAPACITY,                          //initial capacity of the entries vector
        .indices = malloc(DEFAULT_SET_CAPACITY * sizeof(size_t)),   //pointer to the indices table
        .entries = calloc(DEFAULT_SET_CAPACITY, sizeof(set_entry))  //pointer to the entries vector
    };
    memset(s.indices, UCHAR_MAX, s.icapacity * sizeof(size_t));     //set every byte to 255, which expands `EMPTY` for every size_t in the array
    *s_ptr = s;
    return s_ptr;
}

/**
    Create a new set wrapped in an obj. points to s if it isn't null, else a new set
*/
obj* new_set_obj(set* s)
{
    obj* S = malloc(sizeof(obj));
    S->type = Set_t;
    S->size = 0; //size needs to be determined on a per call basis
    set** s_ptr = malloc(sizeof(set*));
    *s_ptr = s != NULL ? s : new_set();
    S->data = (void*)s_ptr;
    return S;
}

/**
    returns the number of elements in the set
 */
size_t set_size(set* s) 
{ 
    return s->size; 
}

/**
    returns the capacity of the indices table in a set
*/
size_t set_indices_capacity(set* s)
{
    return s->icapacity;
}

/**
    returns the capacity of the entries vector in a set
*/
size_t set_entries_capacity(set* s)
{
    return s->ecapacity;
}

bool set_resize_indices(set* s, size_t new_size)
{
    //check if the new set is large enough for all the elements in the old set
    if (s->size > new_size * MAX_LOAD) 
    {
        printf("ERROR: set indices resize failed. new capacity is too small for elements of set\n");
        return false;
    }

    size_t* new_indices = malloc(new_size * sizeof(size_t));
    if (new_indices == NULL)
    {
        printf("ERROR: memory allocation for resized set indices failed\n");
        return false;
    }
    free(s->indices);           //free the old array of indices
    s->indices = new_indices;   //store the new array of indices into the set
    s->icapacity = new_size;
    memset(s->indices, -1, s->icapacity * sizeof(size_t));          //set all items to show as "empty"

    //for each item in entries, insert it's index into the new indices
    for (size_t i = 0; i < s->size; i++)
    {
        //TODO->if/when we add ability to remove items from a set, this should skip over those
        uint64_t hash = obj_hash(s->entries[i].item);
        uint64_t address = set_find_empty_address(s, hash);
        s->indices[address] = i;
    }
    return true;
}

bool set_resize_entries(set* s, size_t new_size)
{
    if (s->size > new_size)
    {
        printf("ERROR: set entries resize failed. new capacity too small for elements of set\n");
        return false;
    }

    set_entry* new_entries = malloc(new_size * sizeof(set_entry));
    if (new_entries == NULL)
    {
        printf("ERROR: memory allocation for resized set entries failed\n");
        return false;
    }

    memcpy(new_entries, s->entries, s->size * sizeof(set_entry));
    free(s->entries);
    s->entries = new_entries;
    s->ecapacity = new_size;
    return true;
}

uint64_t set_find_empty_address(set* s, uint64_t hash)
{
    //guarantee that the starting offset is non-zero, as the lfsr will get stuck if given 0
    uint64_t offset = hash != 0 ? hash : NONZERO_HASH;
    while (s->indices[(hash + offset) % s->icapacity] != EMPTY)
    {
        offset = lfsr64_next(offset);
    }
    return (hash + offset) % s->icapacity;
}

bool set_add(set* s, obj* item)
{
    //check if this object is already in the set. No need to insert if already there
    if (set_contains(s, item))
    {
        return true;
    }

    //check if the set indices & entries tables needs to be resized. for now, return failure for too many entries;
    if (s->size >= s->icapacity * MAX_LOAD) 
    {
        if (!set_resize_indices(s, s->icapacity * 2)) //if resize fails, return false
        {
            return false;
        }
    }
    if (s->size >= s->ecapacity)
    {
        if (!set_resize_entries(s, s->ecapacity * 2))
        {
            return false;
        }
    }

    //construct a set_entry to be inserted
    uint64_t hash = obj_hash(item);
    set_entry e = (set_entry){.hash=hash, .item=item};

    //get an empty address, and insert the new item
    uint64_t address = set_find_empty_address(s, hash);
    size_t index = s->size;                             //index of entry in list of entries is end of the list
    s->indices[address] = index;                        //set the item at this address in indices to be index
    s->entries[index] = e;                              //set the next entry (i.e. at index) in entries to be our new entry
    s->size++;
    return true;
}


/**
    get the index in the entries array of the given item, or EMPTY if not found
*/
size_t set_get_index(set* s, obj* item)
{
    uint64_t hash = obj_hash(item);
    size_t offset = hash != 0 ? hash : NONZERO_HASH;

    while (true)
    {
        //current index to look at in the entries table
        size_t i = s->indices[(hash + offset) % s->icapacity];

        //check if slot is free, meaning no object to return
        if (i == EMPTY)            
        {
            return EMPTY;
        }
        else
        {
            //get the object currently in the non-free slot
            set_entry candidate = s->entries[i];
            
            //if candidate has same hash and item as what we are looking for, return true
            if (candidate.hash == hash && obj_equals(candidate.item, item))
            {
                return true;
            }
        }

        //probe to the next slot in the sequence
        offset = lfsr64_next(offset);
    }
}

/**
    check if the set contains the specified item. 
*/
bool set_contains(set* s, obj* item)
{
    uint64_t hash = obj_hash(item);
    size_t offset = hash != 0 ? hash : NONZERO_HASH;

    while (true)
    {
        //check if slot is free, meaning no object to return
        if (s->indices[(hash + offset) % s->icapacity] == EMPTY)            
        {
            return false;
        }
        else
        {
            //get the object currently in the non-free slot
            set_entry candidate = s->entries[s->indices[(hash + offset) % s->icapacity]];
            
            //if candidate has same hash and item as what we are looking for, return true
            if (candidate.hash == hash && obj_equals(candidate.item, item))
            {
                return true;
            }
        }

        //probe to the next slot in the sequence
        offset = lfsr64_next(offset);
    }
}

set* set_copy(set* s)
{
    set* copy = new_set();
    for (int i = 0; i < set_size(s); i++)
    {
        set_entry e = s->entries[i];
        set_add(copy, e.item); //TODO->deep copy? alsmost certainly need to fix?
    }
    return copy;
}

set* set_union(set* a, set* b)
{
    set* u = new_set();

    //This part could be replaced with `S = set_copy(A);` but would need to modify to do deep copy
    for (int i = 0; i < set_size(a); i++)
    {
        set_entry e = a->entries[i];
        set_add(u, obj_copy(e.item)); //add a copy of the element to the union set
    }
    for (int i = 0; i < set_size(b); i++)
    {
        set_entry e = b->entries[i];
        if (!set_contains(u, e.item)) //only add an element if it wasn't in the first list (so that we don't try to add duplicates)
        {
            set_add(u, obj_copy(e.item));
        }
    }

    return u;
}

/**
    convenience method for reassigning a variable with the result of a union
    set* A will be freed. union(A, B) will be returned
*/
set* set_union_equals(set* a, set* b)
{
    set* u = set_union(a, b);
    set_free(a);
    return u;
}

set* set_intersect(set* a, set* b)
{
    set* x = new_set();
    for (int i = 0; i < set_size(a); i++)
    {
        set_entry e = a->entries[i];
        if (set_contains(b, e.item)) //only if both A and B have the item
        {
            set_add(x, obj_copy(e.item));
        }
    }
    return x;
}

bool set_equals(set* a, set* b)
{
    //check if sizes are different
    if (set_size(a) != set_size(b)) return false;

    //check if each element in A is in B. Since sizes are the same, and sets don't have duplicates, this will indicate equality
    for (int i = 0; i < set_size(a); i++)
    {
        set_entry e = a->entries[i];
        if (!set_contains(b, e.item))
        {
            return false;
        }
    }
    return true;
}

/**
    Create a hash representing the given set object.

    NOT secure. simply adds all hashes together for the set's objects
*/
uint64_t set_hash(set* s)
{
    uint64_t hash = hash_uint(Set_t); //hash the type identifier for a set. this ensures it's not 0 if set is empty
    for (int i = 0; i < set_size(s); i++)
    {
        set_entry e = s->entries[i];
        hash += obj_hash(e.item);
    }
    return hash;
}

void set_reset(set* s)
{
    set_free_elements_only(s);
    free(s->indices);
    free(s->entries);

    //reset all parameters as if new set
    s->indices = malloc(DEFAULT_SET_CAPACITY * sizeof(size_t));     //pointer to the indices table
    s->entries = calloc(DEFAULT_SET_CAPACITY, sizeof(set_entry));   //pointer to the entries vector
    memset(s->indices, -1, s->icapacity * sizeof(size_t));          //set all items to show as "empty"
    s->size = 0;                                                    //number of items in the set
    s->icapacity = DEFAULT_SET_CAPACITY;                            //capacity of the indices table
    s->ecapacity = DEFAULT_SET_CAPACITY;                            //capacity of the entries vector
}

void set_free(set* s)
{
    set_free_elements_only(s);
    set_free_table_only(s);
}

void set_free_elements_only(set* s)
{
    for (int i = 0; i < s->size; i++)
    {
        set_entry e = s->entries[i];
        obj_free(e.item);
    }
}

void set_free_table_only(set* s)
{
    //free the set + indices table and entry vector.
    //this is mainly used when you want all elements that were stored in the set to remain alive
    free(s->indices);
    free(s->entries);
    free(s);
}

void set_repr(set* s)
{
    //print out all elements in the set indices table and entries vector
    printf("set:\nindices = [");
    for (int i = 0; i < s->icapacity; i++)
    {
        if (i != 0) printf(", ");
        if (s->indices[i] == EMPTY) printf("None");
        else printf("%zu", s->indices[i]);
    }
    printf("]\nentries = [");
    for (int i = 0; i < s->size; i++)
    {
        if (i != 0) printf(",\n           ");
        set_entry e = s->entries[i];
        printf("[%lu, ", e.hash);
        obj_print(e.item);
        printf("]");
    }
    printf("]\n");
}

void set_str(set* s)
{
    printf("{");
    for (int i = 0; i < set_size(s); i++)
    {
        set_entry e = s->entries[i];
        if (i != 0) printf(", ");
        obj_print(e.item);
    }
    printf("}");
}


#endif