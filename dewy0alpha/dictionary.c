#ifndef DICTIONARY_C
#define DICTIONARY_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.c"
#include "object.c"

#define DEFAULT_DICT_CAPACITY 8
#define MAX_LOAD 2 / 3
// #define MAX_LOAD 99 / 100

typedef struct dict_entry_struct 
{
    uint64_t hash;
    obj* key;
    obj* value;
} dict_entry;

typedef struct dict_struct 
{
    size_t size;
    size_t capacity;
    dict_entry* table;
} dict;


dict* new_dict();
obj* new_dict_obj();
size_t dict_size(dict* d);
size_t dict_obj_size(void* d);
size_t dict_capacity(dict* d);
bool dict_set(dict* d, obj* key, obj* value);
bool dict_resize(dict* d, size_t new_size);
bool dict_contains(dict* d, obj* key);
obj* dict_get(dict* d, obj* key);
void dict_reset(dict* d);
void dict_free(dict* d);
void dict_repr(dict* d);
void dict_str(dict* d);



dict* new_dict()
{
    dict* d_ptr = malloc(sizeof(dict));
    dict d = {0, DEFAULT_DICT_CAPACITY, calloc(DEFAULT_DICT_CAPACITY, sizeof(dict_entry))};
    *d_ptr = d;
    return d_ptr;
}

obj* new_dict_obj()
{
    obj* D = malloc(sizeof(obj));
    D->type = 5;
    D->size = 0; //size needs to be determined on a per call basis
    dict* d = new_dict();
    D->data = (void*)d;
    return D;
}

size_t dict_size(dict* d)
{
    return d->size;
}

size_t dict_capacity(dict* d)
{
    return d->capacity;
}

bool dict_resize(dict* d, size_t new_size)
{
    //check if the new dictionary is large enough for all the elements in the old dictionary
    if (d->size > new_size * MAX_LOAD) 
    {
        printf("ERROR: resize failed. new capacity is too small for elements of dict\n");
        return false;
    }
        
    //create a new dictionary to construct the resized version in
    dict raw_new_dict_struct = {0, new_size, calloc(new_size, sizeof(dict_entry))};
    dict* new_dict = &raw_new_dict_struct;

    if (new_dict->table == NULL) 
    {
        printf("ERROR: memory allocation for resized dict failed");
        return false;
    }

    //insert all of the elements from the old dictionary into the new dictionary
    for (int i = 0; i < d->capacity; i++) 
    {
        dict_entry e = d->table[i];
        if (e.hash != 0 || e.key != NULL) //if this isn't an empty slot, insert into the new dictionary
        {
            dict_set(new_dict, e.key, e.value);
        }
    }

    //replace the old table with the new one, and update the size and capacity.
    free(d->table);
    d->size = new_dict->size;
    d->capacity = new_dict->capacity;
    d->table = new_dict->table;

    return true;
}

bool dict_set(dict* d, obj* key, obj* value)
{
    //check if the dict needs to be resized. for now, return failure for too many entries;
    if (d->size >= d->capacity * MAX_LOAD) 
    {
        if (!dict_resize(d, d->capacity * 2)) //if resize fails, return false
        {
            return false;
        }

    }

    uint64_t hash = obj_hash(key);
    dict_entry e = {hash, key, value};
    size_t address = hash % d->capacity;
    size_t offset = 0;
    
    //look for open address. 
    srand(hash);
    while (true)
    {
        dict_entry candidate = d->table[(address + offset) % d->capacity];
        if (candidate.hash == 0 && candidate.key == NULL)                           //check if slot is free
        {
            d->table[(address + offset) % d->capacity] = e;
            d->size++;
            break;
        }
        else if (candidate.hash == e.hash && obj_equals(candidate.key, e.key))      //entry exists
        {
            d->table[(address + offset) % d->capacity] = e;                         //overwrite the existing entry
            break;
        }
        else                                                                        //probe to the next slot in the sequence
        {
            offset = rand();
        }
    }
    return true;
}

bool dict_contains(dict* d, obj* key)
{
    //check if the dictionary has the specified key
    return dict_get(d, key) != NULL;
}

obj* dict_get(dict* d, obj* key)
{
    //get the object at the specified key value
    uint64_t hash = obj_hash(key);
    size_t address = hash % d->capacity;
    size_t offset = 0;
    srand(hash);

    while (true) 
    {
        dict_entry candidate = d->table[(address + offset) % d->capacity];

        if (candidate.hash == hash && obj_equals(candidate.key, key)) //check for match
        {
            return candidate.value;
        } 
        else if (candidate.hash == 0 && candidate.key == NULL) //check empty
        {
            return NULL;
        }
        else //update offset of random probe
        {
            offset = rand();
        }
    }
}

void dict_reset(dict* d)
{
    //free the contents of the dictionary
    for (int i = 0; i < d->capacity; i++) 
    {
        dict_entry e = d->table[i];
        if (e.hash != 0 && e.key != NULL)
        {
            obj_free(e.key);
            obj_free(e.value);
        }
    }
    free(d->table);

    //reset all parameters as if new dictionary
    d->table = calloc(DEFAULT_DICT_CAPACITY, sizeof(dict_entry));
    d->size = 0;
    d->capacity = DEFAULT_DICT_CAPACITY;
}

void dict_free(dict* d)
{
    //free all keys and values in the dictionary
    for (int i = 0; i < d->capacity; i++) 
    {
        dict_entry e = d->table[i];
        if (e.hash != 0 && e.key != NULL) //if this isn't an empty slot, insert into the new dictionary
        {
            obj_free(e.key);
            obj_free(e.value);
        }
    }

    //free memory of table
    free(d->table);
    free(d);
}

void dict_repr(dict* d) 
{
    //print out all elements in the dictionary
    // printf("dictionary:\n");
    for (int i = 0; i < d->capacity; i++)
    {
        dict_entry e = d->table[i];
        printf("@%d: {%lu, ", i, e.hash); obj_print(e.key); printf(", "); obj_print(e.value); printf("}\n");
    }
    // printf("\n");

}

void dict_str(dict* d)
{
    printf("[");
    int items = 0;
    for(int i = 0; i < d->capacity; i++)
    {
        dict_entry e = d->table[i];
        if (e.hash != 0 || e.key != NULL)
        {
            if (items++ != 0) { printf(", "); }
            obj_print(e.key); printf("-> "); obj_print(e.value);
        }
    }
    printf("]\n");
}


#endif