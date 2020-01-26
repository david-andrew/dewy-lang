#ifndef VECTOR_C
#define VECTOR_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.c"
#include "object.c"

#define DEFAULT_VECT_CAPACITY 8

//ArrayList Implemented as an ArrayDeque
typedef struct vect_struct 
{
    size_t head;
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
bool vect_prepend(vect* v, obj* item);
//bool vect_multi_append(vect* v, vect* items);
//bool vect_multi_prepend(vect* v, vect* items);
bool vect_push(vect* v, obj* item);
obj* vect_pop(vect* v);
obj* vect_peek(vect* v);

bool vect_enqueue(vect* v, obj* item);
obj* vect_dequeue(vect* v);

bool vect_set(vect* v, obj* item, size_t index);
bool vect_contains(vect* v, obj* item);
bool vect_find(vect* v, obj* item, size_t* index);
obj* vect_get(vect* v, size_t index);
obj* vect_remove(vect* v, size_t index);
void vect_delete(vect* v, size_t index);
void vect_reset(vect* v);
void vect_free(vect* v);
void vect_repr(vect* v);
void vect_str(vect* v);


vect* new_vect()
{
    vect* v_ptr = malloc(sizeof(vect));
    vect v = {0, 0, DEFAULT_VECT_CAPACITY, calloc(DEFAULT_VECT_CAPACITY, sizeof(obj*))};
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
    if (new_size < v->size)
    {
        printf("ERROR: resize failed. new size is not large enough to accomodate elements in vector\n");
        return false;
    }

    obj** new_list = calloc(new_size, sizeof(obj));
    if (new_list == NULL) //calloc failed 
    {
        printf("ERROR: resize failed. calloc returned NULL\n");
        return false;
    }

    //copy all elements from the old list into the new list
    for (int i = 0; i < v->size; i++)
    {
        new_list[i] = vect_get(v, i);//v->list[(v->head + i) % v->capacity];
    }

    //update vector information
    free(v->list);
    v->list = new_list;
    v->capacity = new_size;
    v->head = 0;
    return true;

}



//TODO->reimplement to use memmove instead of a for loop, as that will be faster.
//it's more complicated to implement though...
//current implementation: http://opendatastructures.org/ods-java/2_4_ArrayDeque_Fast_Deque_O.html

//BUGS
//prepending and appending work fine. inserting in the middle causes problems
//presumable off-by-one errors that occur during shift left or shift right
bool vect_insert(vect* v, obj* item, size_t index)
{
    // printf("INSERTING at index %zu. size=%zu, capacity=%zu\n", index, v->size, v->capacity);
    
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

    //move elements to make room for the insertion
    if (index < v->size / 2) 
    {
        v->head = v->head == 0 ? v->capacity - 1 : v->head - 1; //adjust the location of the head index left
        for (int i = 0; i < (int)index; i++) //move elements to the right of the insertion point
        {
            v->list[(v->head + i) % v->capacity] = v->list[(v->head + i + 1) % v->capacity];
        }
    }
    else
    {
        for (int i = (int)v->size - 1; i >= (int)index; i--) //move elements to the left of the insertion point
        {
            v->list[(v->head + i + 1) % v->capacity] = v->list[(v->head + i) % v->capacity];
        }
    }

    //assign the item to the newly free index
    v->list[(v->head + index) % v->capacity] = item;
    v->size++;
    return true;
}



bool vect_append(vect* v, obj* item)
{
    return vect_insert(v, item, v->size);
}

bool vect_prepend(vect* v, obj* item)
{
    return vect_insert(v, item, 0);
}

bool vect_push(vect* v, obj* item) 
{
    return vect_append(v, item);
}

obj* vect_pop(vect* v) 
{
    return v->size > 0 ? vect_remove(v, v->size - 1) : NULL;
}

obj* vect_peek(vect* v)
{
    return v->size > 0 ? vect_get(v, v->size - 1) : NULL;
}

// bool vect_enqueue(vect* v, obj* item)
// {
//     return vect_prepend(v, item);
// }

// obj* vect_dequeue(vect* v)
// {
//     return v->size > 0 ? vect_remove(v, v->size - 1) : NULL;
// }

bool vect_enqueue(vect* v, obj* item)
{
    return vect_append(v, item);
}

obj* vect_dequeue(vect* v)
{
    return v->size > 0 ? vect_remove(v, 0) : NULL;
}



bool vect_set(vect* v, obj* item, size_t index)
{
    if (index >= v->size)
    {
        printf("ERROR: cannot set index=%zu in vector of size=%zu\n", index, v->size);
        return false;
    }
    v->list[(v->head + index) % v->capacity] = item;
    return true;
}

bool vect_contains(vect* v, obj* item)
{
    size_t index;
    return vect_find(v, item, &index);
}

bool vect_find(vect* v, obj* item, size_t* index)
{
    for (int i = 0; i < v->size; i++)
    {
        if (obj_equals(vect_get(v, i), item))
        {
            *index = i;
            return true;
        }
    }
    return false;
}

obj* vect_get(vect* v, size_t index)
{
    if (index >= v->size)
    {
        printf("ERROR: attempted to access index=%zu for vector of size=%zu\n", index, v->size);
        return NULL;
    }
    return v->list[(v->head + index) % v->capacity];
}

obj* vect_remove(vect* v, size_t index)
{
    if (index >= v->size) 
    {
        printf("ERROR: cannot remove element at index=%zu for vector of size=%zu\n", index, v->size);
        return NULL;
    }
    obj* item = vect_get(v, index);
    if (index < v->size / 2)
    {
        for (int i = index; i > 0; i--)
        {
            v->list[(v->head + i) % v->capacity] = v->list[(v->head + i - 1) % v->capacity];
        }
        v->list[v->head] = NULL;
        v->head = (v->head + 1) % v->capacity;
    }
    else
    {
        for (int i = index; i < (int)v->size - 1; i++)
        {
            v->list[(v->head + i) % v->capacity] = v->list[(v->head + i + 1) % v->capacity];
        }
        v->list[(v->head + v->size - 1) % v->capacity] = NULL;
    }
    v->size--;
    // if (v->size < 4 * v->capacity) { vect_resize(v, v->size/2); }

    return item;
}

//remove and free an element from the vector
void vect_delete(vect* v, size_t index)
{
    obj* item = vect_remove(v, index);
    if (item != NULL) 
    {
        obj_free(item);
    }
}

void vect_reset(vect* v)
{
    //free the contents of the vector
    for (int i = 0; i < v->size; i++)
    {
        obj_free(vect_get(v, i));
    }
    free(v->list);
    v->size = 0;
    v->capacity = DEFAULT_VECT_CAPACITY;
    v->list = calloc(DEFAULT_VECT_CAPACITY, sizeof(obj));
}

void vect_free(vect* v)
{
    for (int i = 0; i < v->size; i++)
    {
        obj_free(vect_get(v, i));
    }
    free(v->list);
    free(v);
}


void vect_repr(vect* v)
{
    printf("Vector\n");
    for (int i = 0; i < v->capacity; i++) 
    {
        printf("@%d: ", i); fflush(stdout); obj_print(v->list[i]); printf("%s\n", (v->head == i ? "    (HEAD)" : ""));
    }
}


void vect_str(vect* v)
{
    printf("[");
    for (int i = 0; i < v->size; i++)
    {
        if (i != 0) { printf(", "); }
        obj_print(vect_get(v, i));
    }
    printf("]\n");
}












#endif