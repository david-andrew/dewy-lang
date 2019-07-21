#ifndef VECT_C
#define VECT_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.c"
#include "obj.c"

#define DEFAULT_VECT_CAPACITY 8

//TODO-> look into reimplementing the vector as an array queue
//new elements can be inserted at the start or end with O(1)
//keep track of the start of the vector, and size.
//appending simply places after the last element
//prepending places befor the first element
//use modulus for out of bounds. so prepending to -1 would put the element at the location size - 1
//this way insertions would only cost when applied to the middle of the vector
//and then any insertion will only be forced to copy at most half of the elements
//as in any situation, you can choose to move the size with fewer elements to make room
//the only drawback is implementing is more complicated, and you have to be very careful about keeping track of the start/end of the vector


typedef struct vect_struct 
{
    size_t size;
    size_t capacity;
    obj** list;
} vect;


vect* new_vect();
size_t vect_size(vect* v);
size_t vect_capacity(vect* v);
bool vect_resize(vect* v, size_t new_size);
bool vect_insert(vect* v, obj* item, size_t index);
//bool vect_multi_insert(vect* v, vect* items, size_t index);
bool vect_append(vect* v, obj* item);
//bool vect_multi_append(vect* v, vect* items);
bool vect_set(vect* v, obj* item, size_t index);
bool vect_contains(vect* v, obj* item);
// size_t vect_find(vect* v, obj* item);
obj* vect_get(vect* v, size_t index);
obj* vect_remove(vect* v, size_t index);
void vect_reset(vect* v);
void vect_free(vect* v);
void vect_repr(vect* v);
void vect_str(vect* v);


vect* new_vect()
{
    vect* v_ptr = malloc(sizeof(vect));
    vect v = {0, DEFAULT_VECT_CAPACITY, malloc(DEFAULT_VECT_CAPACITY * sizeof(obj))};
    *v_ptr = v;
    return v_ptr;
}

size_t vect_size(vect* v)
{
    return v->size;
}

size_t vect_capacity(vect* v)
{
    return v->capacity;
}

bool vect_resize(vect* v, size_t new_size)
{
    if (new_size < v->size) //won't have room for all elements
    {
        printf("ERROR: resize failed. new size is not large enough to accomodate elements in vector\n");
        return false;
    }
    obj** new_list = realloc(v->list, new_size * sizeof(obj*));
    if (new_list == NULL) //realloc failed 
    {
        printf("ERROR: resize failed. realloc returned NULL\n");
        return false;
    }
    else 
    {
        v->capacity = new_size;
        v->list = new_list;
        return true;
    }
}

bool vect_insert(vect* v, obj* item, size_t index)
{
    if (index > v->size)
    {
        printf("ERROR: cannot insert at index=%zu for vector of size=%zu\n", index, v->size);
        return false;
    }
    if (v->size == v->capacity)
    {
        if (!vect_resize(v, v->capacity * 2))
        {
            return false;
        }
    }

    //compute the range of elements to shift
    size_t to_shift = v->size - index;
    if (to_shift > 0)
    {
        memmove(v->list + index + 1, v->list + index, to_shift * sizeof(obj*));
    }
    //insert the value into the newly free space
    v->list[index] = item;
    v->size++;
    return true;
}

bool vect_append(vect* v, obj* item)
{
    return vect_insert(v, item, v->size);
}


void vect_repr(vect* v)
{
    printf("Vector\n");
    for (int i = 0; i < v->size; i++) 
    {
        printf("@%d: ", i); obj_print(v->list[i]); printf("\n");
    }
}


void vect_str(vect* v)
{
    printf("[");
    for (int i = 0; i < v->size; i++)
    {
        if (i != 0) { printf(", "); }
        obj_print(v->list[i]);
    }
    printf("]\n");
}












#endif