#ifndef VECTOR_C
#define VECTOR_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.h"
#include "object.h"
#include "dictionary.h"
#include "vector.h"

#define DEFAULT_VECT_CAPACITY 8

//ArrayList Implemented as an ArrayDeque. see: http://opendatastructures.org/ods-java/2_4_ArrayDeque_Fast_Deque_O.html



/**
 * Create a new vector with the default amount of capacity (8)
 */
vect* new_vect()
{
    return new_vect_with_capacity(DEFAULT_VECT_CAPACITY);
}


/**
 * Create a new vector with the amount of capacity specified.
 */
//TODO->perhaps we should ensure that the init_capacity is a power of 2?
vect* new_vect_with_capacity(size_t init_capacity)
{
    vect* v = malloc(sizeof(vect));
    *v = (vect){
        .head = 0, 
        .size = 0, 
        .capacity = init_capacity, 
        .list = calloc(init_capacity, sizeof(obj*))
    };
    return v;
}


/**
 * Create a vector object. points to v if it isn't null, else points to a new vect
 */
obj* new_vect_obj(vect* v)
{
    if (v == NULL) v = new_vect();
    obj* V = malloc(sizeof(obj));
    *V = (obj){.type=Vector_t, .data=v};
    return V;
}


/**
 * Get the number of elements in the vector.
 */
size_t vect_size(vect* v)
{
    return v->size;
}


/**
 * Get the amount of space the vector has allocated 
 * for new elements, before it needs to be resized.
 */
size_t vect_capacity(vect* v)
{
    return v->capacity;
}


/**
 * Reallocate the vector so that it has the new specified amount of capacity.
 */
void vect_resize(vect* v, size_t new_size)
{
    if (new_size < v->size)
    {
        printf("ERROR: resize failed. new size is not large enough to accomodate elements in vector\n");
        exit(1);
    }

    obj** new_list = calloc(new_size, sizeof(obj*));
    if (new_list == NULL) //calloc failed 
    {
        printf("ERROR: resize failed. calloc returned NULL\n");
        exit(1);
    }

    //copy all elements from the old list into the new list
    for (int i = 0; i < v->size; i++)
    {
        new_list[i] = vect_get(v, i);
    }

    //update vector information
    free(v->list);
    v->list = new_list;
    v->capacity = new_size;
    v->head = 0;
}



/**
 * Insert an element into the vector at the specified index.
 */
//TODO->reimplement to use memmove instead of a for loop, as that will be faster.
//it's more complicated to implement though...
//current implementation: http://opendatastructures.org/ods-java/2_4_ArrayDeque_Fast_Deque_O.html
//BUGS
//prepending and appending work fine. inserting in the middle causes problems
//presumable off-by-one errors that occur during shift left or shift right
void vect_insert(vect* v, obj* item, size_t index)
{    
    if (index > v->size)
    {
        printf("ERROR: cannot insert at index=%zu for vector of size=%zu\n", index, v->size);
        exit(1);
    }
    if (v->size == v->capacity)
    {
        vect_resize(v, v->capacity * 2);
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
}


/**
 * Add an element to the end of the vect.
 */
void vect_append(vect* v, obj* item)
{
    vect_insert(v, item, v->size);
}


/**
 * Add an element to the front of the vect.
 */
void vect_prepend(vect* v, obj* item)
{
    vect_insert(v, item, 0);
}


/**
 * Add an element to the end of the vect (i.e. top of the stack).
 */
void vect_push(vect* v, obj* item) 
{
    vect_append(v, item);
}


/**
 * Remove the last element of the vect (i.e. top of the stack) and return it.
 */
obj* vect_pop(vect* v) 
{
    return v->size > 0 ? vect_remove(v, v->size - 1) : NULL;
}


/**
 * Return the last element in the vect (i.e. top of the stack) without modifying the vect.
 */
obj* vect_peek(vect* v)
{
    return v->size > 0 ? vect_get(v, v->size - 1) : NULL;
}


/**
 * Add an element to the end of the vect (i.e. end of the queue).
 */
void vect_enqueue(vect* v, obj* item)
{
    vect_append(v, item);
}


/**
 * Remove the first element of the vect (i.e. start of the queue), and return it.
 */
obj* vect_dequeue(vect* v)
{
    return v->size > 0 ? vect_remove(v, 0) : NULL;
}


//TODO->should probably free the current item at the index
void vect_set(vect* v, obj* item, size_t index)
{
    if (index >= v->size)
    {
        printf("ERROR: cannot set index=%zu in vector of size=%zu\n", index, v->size);
        exit(1);
    }
    v->list[(v->head + index) % v->capacity] = item;
}


/**
 * Merge two vectors while freeing the input left/right inputs.
 */
vect* vect_merge(vect* left, vect* right)
{
    //vect to hold merge result
    vect* merge = new_vect();
    
    //resize merge if not big enough to hold all data. ensure size is power of 2
    size_t min_size = vect_size(left) + vect_size(right);
    if (merge->capacity < min_size)
    {
        size_t size = DEFAULT_VECT_CAPACITY;
        while (size < min_size) { size *= 2; }
        vect_resize(merge, size);
    }
    
    // pull items in order from each vector into the merge vector
    while (vect_size(left) > 0) { vect_enqueue(merge, vect_dequeue(left)); }
    while (vect_size(right) > 0) { vect_enqueue(merge, vect_dequeue(right)); }
    
    //free empty left/right vectors
    vect_free(left);
    vect_free(right);

    return merge;
}


/**
 * Merge two vectors without modifying the input left/right inputs
 */
vect* vect_merge_copy(vect* left, vect* right)
{
    //vect to hold merge result
    vect* merge = new_vect();
    
    //resize merge if not big enough to hold all data. ensure size is power of 2
    size_t min_size = vect_size(left) + vect_size(right);
    if (merge->capacity < min_size)
    {
        size_t size = DEFAULT_VECT_CAPACITY;
        while (size < min_size) { size *= 2; }
        vect_resize(merge, size);
    }
    
    // pull items in order from each vector into the merge vector. copy items so that left/right not modified
    for (size_t i = 0; i < vect_size(left); i++) { vect_enqueue(merge, obj_copy(vect_get(left, i))); }
    for (size_t i = 0; i < vect_size(right); i++) { vect_enqueue(merge, obj_copy(vect_get(right, i))); }
    
    return merge;
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

    return item;
}


/**
 * remove and free an element from the vector
 */
void vect_delete(vect* v, size_t index)
{
    obj_free(vect_remove(v, index));
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


vect* vect_copy(vect* v)
{
    vect* copy = new_vect();
    for (int i = 0; i < vect_size(v); i++)
    {
        vect_append(copy, obj_copy(vect_get(v, i)));
    }
    return copy;
}

vect* vect_copy_with_refs(vect* v, dict* refs)
{
    vect* copy = new_vect();
    for (int i = 0; i < vect_size(v); i++)
    {
        obj* item = vect_get(v, i);

        //if a reference doesn't yet exist for the copy, create a copy, otherwise use the existing reference
        if (!dict_contains(refs, item))
        {
            dict_set(refs, item, obj_copy_with_refs(item, refs));
        }
        vect_append(copy, dict_get(refs, item));
    }
    return copy;
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

/**
    Free the vector container without touching its objects
*/
void vect_free_list_only(vect* v)
{
    free(v->list);
    free(v);
}


int64_t vect_compare(vect* left, vect* right)
{
    //handle if either or both are null
    if (left == NULL && right == NULL) { return 0; }
    else if (left == NULL) { return -1; }
    else if (right == NULL) { return 1; }

    if (vect_size(left) != vect_size(right))
    {
        return vect_size(left) - vect_size(right); //smaller vectors sort earlier than larger ones
    }

    //check each element in sequence for equality. if not equal, return as compareto value
    for (int i = 0; i < vect_size(left); i++) 
    {
        int64_t result = obj_compare(vect_get(left, i), vect_get(right, i));
        if (result) { return result; }
    }

    //all objects were equal, so return 0, indicating left equals right
    return 0;
}


/**
 * Hash the sequence of elements in the vector.
 */
uint64_t vect_hash(vect* v)
{
    //get a list of hashes for each element in the vector
    uint64_t* hashes = malloc(sizeof(uint64_t) * vect_size(v));
    for (size_t i = 0; i < vect_size(v); i++)
    {
        hashes[i] = obj_hash(vect_get(v, i));
    }

    //hash the sequence together
    uint64_t hash = hash_uint_sequence(hashes, vect_size(v));
    free(hashes);
    return hash;
}


void vect_repr(vect* v)
{
    printf("Vector\n");
    for (int i = 0; i < v->capacity; i++) 
    {
        printf("@%d: ", i); fflush(stdout); obj_str(v->list[i]); printf("%s\n", (v->head == i ? "    (HEAD)" : ""));
    }
}


void vect_str(vect* v)
{
    printf("[");
    for (int i = 0; i < v->size; i++)
    {
        if (i != 0) { printf(", "); }
        obj_str(vect_get(v, i));
    }
    printf("]");
}












#endif