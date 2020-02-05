#ifndef DICTIONARY_C
#define DICTIONARY_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

#include "utilities.c"
#include "object.c"

#define DEFAULT_DICT_CAPACITY 8
#define MAX_LOAD 2 / 3

//representation for an empty value in the dict indices table.
//since we only have pure ints, we say the max value (which probably won't be used) is EMPTY
#define EMPTY SIZE_MAX

//constant to assign to hashes that are 0, so that the lfsr algorithm doesn't get stuck at 0
#define NONZERO_HASH 0xDEADBEEF


//Implementation of dictionary based on python's implementaion
//https://stackoverflow.com/questions/327311/how-are-pythons-built-in-dictionaries-implemented
//https://mail.python.org/pipermail/python-dev/2012-December/123028.html


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

/*
    create an empty dictionary
*/
dict* new_dict()
{
    dict* d_ptr = malloc(sizeof(dict));
    dict d = {
        .size = 0,                                                      //initial elements in the dictionary (i.e. none)
        .icapacity = DEFAULT_DICT_CAPACITY,                             //initial capacity of the indices table
        .ecapacity = DEFAULT_DICT_CAPACITY,                             //initial capacity of the entries vector
        .indices = malloc(DEFAULT_DICT_CAPACITY * sizeof(size_t)),      //pointer to the indices table
        .entries = calloc(DEFAULT_DICT_CAPACITY, sizeof(dict_entry))    //pointer to the entries vector
    };
    memset(d.indices, -1, d.icapacity * sizeof(size_t));                //set all values to show as "empty"
    *d_ptr = d;
    return d_ptr;
}

/**
    creates a new dict* wrapped in an object
*/
obj* new_dict_obj()
{
    obj* D = malloc(sizeof(obj));
    D->type = Dictionary_t;
    D->size = 0; //size needs to be determined on a per call basis
    dict** d_ptr = malloc(sizeof(dict*));
    *d_ptr = new_dict();
    D->data = (void*)d_ptr;
    return D;
}

/**
    returns the number of elements in a dictionary
*/
size_t dict_size(dict* d)
{
    return d->size;
}

/**
    returns the capacity of the indices table in a dictionary
*/
size_t dict_indices_capacity(dict* d)
{
    return d->icapacity;
}

/**
    returns the capacity of the entries vector in a dictionary
*/
size_t dict_entries_capacity(dict* d)
{
    return d->ecapacity;
}

bool dict_resize_indices(dict* d, size_t new_size)
{
    //check if the new dictionary is large enough for all the elements in the old dictionary
    if (d->size > new_size * MAX_LOAD) 
    {
        printf("ERROR: dict indices resize failed. new capacity is too small for elements of dict\n");
        return false;
    }

    size_t* new_indices = malloc(new_size * sizeof(size_t));
    if (new_indices == NULL)
    {
        printf("ERROR: memory allocation for resized dict indices failed\n");
        return false;
    }
    free(d->indices);           //free the old array of indices
    d->indices = new_indices;   //store the new array of indices into the dict
    d->icapacity = new_size;
    memset(d->indices, -1, d->icapacity * sizeof(size_t));          //set all values to show as "empty"

    //for each item in entries, insert it's index into the new indices
    for (size_t i = 0; i < d->size; i++)
    {
        //TODO->if/when we add ability to remove values from a dicitonary, this should skip over those
        uint64_t hash = obj_hash(d->entries[i].key);
        uint64_t address = dict_find_empty_address(d, hash);
        d->indices[address] = i;
    }
    return true;
}

bool dict_resize_entries(dict* d, size_t new_size)
{
    if (d->size > new_size)
    {
        printf("ERROR: dict entries resize failed. new capacity too small for elements of dict\n");
        return false;
    }

    dict_entry* new_entries = malloc(new_size * sizeof(dict_entry));
    if (new_entries == NULL)
    {
        printf("ERROR: memory allocation for resized dict entries failed\n");
        return false;
    }

    memcpy(new_entries, d->entries, d->size * sizeof(dict_entry));
    free(d->entries);
    d->entries = new_entries;
    d->ecapacity = new_size;
    return true;
}

uint64_t dict_find_empty_address(dict* d, uint64_t hash)
{
    //guarantee that the starting offset is non-zero, as the lfsr will get stuck if given 0
    uint64_t offset = hash != 0 ? hash : NONZERO_HASH;
    while (d->indices[(hash + offset) % d->icapacity] != EMPTY)
    {
        offset = lfsr64_next(offset);
    }
    return (hash + offset) % d->icapacity;
}


bool dict_set(dict* d, obj* key, obj* value)
{
    //check if the dict indices & entries tables needs to be resized. for now, return failure for too many entries;
    if (d->size >= d->icapacity * MAX_LOAD) 
    {
        if (!dict_resize_indices(d, d->icapacity * 2)) //if resize fails, return false
        {
            return false;
        }
    }
    if (d->size >= d->ecapacity)
    {
        if (!dict_resize_entries(d, d->ecapacity * 2))
        {
            return false;
        }
    }

    //construct a dict_entry to be inserted
    uint64_t hash = obj_hash(key);
    dict_entry e = (dict_entry){.hash=hash, .key=key, .value=value};

    size_t offset = hash != 0 ? hash : NONZERO_HASH;                                //ensure we start with a non-zero offset
    while (true)
    {
        if (d->indices[(hash + offset) % d->icapacity] == EMPTY)                    //check if slot is free
        {
            size_t index = d->size;                                                 //index of entry in list of entries is end of the list
            d->indices[(hash + offset) % d->icapacity] = index;                     //set the value at this address in indices to be index
            d->entries[index] = e;                                                  //set the next entry (i.e. at index) in entries to be our new entry
            d->size++;
            break;
        }
        else
        {
            //get the object currently in the non-free slot
            dict_entry candidate = d->entries[d->indices[(hash + offset) % d->icapacity]];
            
            if (candidate.hash == e.hash && obj_equals(candidate.key, e.key))       //if candidate has same hash and key as what is currently in the dictionary
            {
                size_t index = d->indices[(hash + offset) % d->icapacity];          //get the index of the item to overwrite in the entries vector
                d->entries[index] = e;                                              //overwrite the existing entry
                break;
            }
            else                                                                    //else probe to the next slot in the sequence
            {
                offset = lfsr64_next(offset);
            }
        }
    }

    return true;
}




bool dict_contains(dict* d, obj* key)
{
    //check if the dictionary has the specified key
    return dict_get(d, key) != NULL;
}


//TODO->I think this has a bug where a full dictionary will cause an infinite loop if the key is not in the dictionary.
//basically it should be guaranteed that dictionaries will never be full!
obj* dict_get(dict* d, obj* key)
{
    uint64_t hash = obj_hash(key);
    size_t offset = hash != 0 ? hash : NONZERO_HASH;

    while (true)
    {
        //check if slot is free, meaning no object to return
        if (d->indices[(hash + offset) % d->icapacity] == EMPTY)            
        {
            return NULL;
        }
        else
        {
            //get the object currently in the non-free slot
            dict_entry candidate = d->entries[d->indices[(hash + offset) % d->icapacity]];
            
            //if candidate has same hash and key as what we are looking for, return its value object
            if (candidate.hash == hash && obj_equals(candidate.key, key))
            {
                return candidate.value;
            }
            else //probe to the next slot in the sequence                                                          
            {
                offset = lfsr64_next(offset);
            }
        }
    }
}


void dict_reset(dict* d)
{
    for (int i = 0; i < d->size; i++)
    {
        dict_entry e = d->entries[i];
        if (e.key != e.value) //only if key and value are different object, free both
        {
            obj_free(e.key); 
        }
        obj_free(e.value);
    }
    free(d->indices);
    free(d->entries);

    //reset all parameters as if new dictionary
    d->indices = malloc(DEFAULT_DICT_CAPACITY * sizeof(size_t));    //pointer to the indices table
    d->entries = calloc(DEFAULT_DICT_CAPACITY, sizeof(dict_entry)); //pointer to the entries vector
    memset(d->indices, -1, d->icapacity * sizeof(size_t));          //set all values to show as "empty"
    d->size = 0;                                                    //number of values in the dict
    d->icapacity = DEFAULT_DICT_CAPACITY;                           //capacity of the indices table
    d->ecapacity = DEFAULT_DICT_CAPACITY;                           //capacity of the entries vector
}


void dict_free(dict* d)
{
    for (int i = 0; i < d->size; i++)
    {
        dict_entry e = d->entries[i];
        if (e.key != e.value) //only if key and value are different object, free both
        {
            obj_free(e.key); 
        }
        obj_free(e.value);
    }
    free(d->indices);
    free(d->entries);
    free(d);
}

void dict_free_table_only(dict* d)
{
    //free memory of indices table and entry vectory.
    //this is mainly used when you want all elements that were stored in the dictionary to remain alive
    free(d->indices);
    free(d->entries);
    free(d);
}


void dict_repr(dict* d)
{
    //print out all elements in the dictionary indices table and entries vector
    printf("dictionary:\nindices = [");
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
        printf(", ");
        obj_print(e.value);
        printf("]");
    }
    printf("]\n");
}


void dict_str(dict* d)
{
    printf("[");
    for (int i = 0; i < d->size; i++)
    {
        if (i != 0) printf(", ");
        obj_print(d->entries[i].key);
        printf(" -> ");
        obj_print(d->entries[i].value);
    }
    printf("]");
}



#endif