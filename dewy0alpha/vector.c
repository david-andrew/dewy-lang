#ifndef VECTOR_C
#define VECTOR_C


#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
// #include <string.h>

#define DEFAULT_CAPACITY 10

typedef struct dynamic_array_struct
{
    void* data;
    size_t width;
    size_t capacity;
    size_t length;
} vector;



//predeclare all functions
//Standard vector functions
vector* new_vector(size_t data_width);
size_t vector_length(vector* v);
size_t vector_capacity(vector* v);
size_t vector_width(vector* v);
bool vector_resize(vector* v, size_t new_capacity);
bool vector_append(vector* v, void* item);
bool vector_set(vector* v, void* item, size_t index);
void* vector_get(vector* v, size_t index);
void vector_clear(vector* v);
bool vector_contains(vector* v, void* item);
bool vector_is_empty(vector* v);
bool vector_remove(vector* v, size_t index);

//integer vector functions
vector* new_int_vector();
bool vector_append_int(vector* v, int i);
bool vector_set_int(vector* v, int i, size_t index);
int vector_get_int(vector* v, size_t index);
bool vector_contains_int(vector* v, int i);
void vector_print_int(vector* v);
void* itemize_int(int i);



//EBNF Token vector functions -> acutally implement them in the compile_tools.c file


//other vectors if need be? -> should also be implemented in their own files as well


//create a new vector
vector* new_vector(size_t data_width) 
{
    vector* v_ptr = malloc(sizeof(vector));
    vector v;
    v.data = malloc(data_width * DEFAULT_CAPACITY);
    v.width = data_width;
    v.capacity = DEFAULT_CAPACITY;
    v.length = 0;
    *v_ptr = v;
    return v_ptr;
}
//new other types of vectors
//all other functions ought to be agnostic to the vector type

//return a pointer to the element at the index. If out of bounds, return null
// void* vector_get(vector* v, size_t index)
// {    
//     return index < v->length ? v->data + v->width * index : NULL;
// }

//get the number of elements in the vector
size_t vector_length(vector* v)
{
    return v->length;
}

size_t vector_capacity(vector* v)
{
    return v->capacity;
}

size_t vector_width(vector* v)
{
    return v->width;
}

//
bool vector_resize(vector* v, size_t new_capacity)
{
    void* new_data = realloc(v->data, v->width * new_capacity);
    if (new_data)
    {
        v->data = new_data;
        v->capacity = new_capacity;
        if (v->length > new_capacity) { v->length = new_capacity; } //if shrunk to less than original length, data is truncated
        return true;
    }
    else
    {
        return false;
    }
}

bool vector_append(vector* v, void* item)
{
    if (v->length == v->capacity) 
    { 
        if (!vector_resize(v, v->capacity * 2))
            {
                return false;
            } 
    }

    memcpy(v->data + v->width * v->length, item, v->width);
    v->length++;
    return true;
}

// bool vector_set(vector* v, void* item, size_t index){}

void* vector_get(vector* v, size_t index)
{
    if (index >= v->length)
    {
        return NULL;
    }
    void* item = malloc(v->width);
    memcpy(item, v->data + index * v->width, v->width);
    return item;
}

void vector_clear(vector* v) 
{ 
    v->length = 0; 
}
void vector_free(vector* v)
{
    for (int i = 0; i < v->length; i++)
    {
        free(*((void**)(v->data + v->width * i)));
    }
    v->length = 0;
}
// bool vector_contains(vector* v, void* item){}
bool vector_is_empty(vector* v) { return v->length == 0; }
// bool vector_remove(vector* v, size_t index){}




/////// INTEGER VECTOR OPERATIONS /////////
vector* new_int_vector() 
{
    return new_vector(sizeof(int));
}
bool vector_append_int(vector* v, int i)
{
    return vector_append(v, itemize_int(i));
}

// bool vector_set_int(vector* v, int i, size_t index){}
// int vector_get_int(vector* v, size_t index){}
// bool vector_contains_int(vector* v, int i){}


void vector_print_int(vector* v)
{
    printf("[");
    if (v->length >= 1) 
    {
        printf("%d", *((int*)vector_get(v, 0))); //print the first element only without a comma
    } 
    for (int i = 1 ; i < v->length; i++)
    {
        printf(", %d", *((int*)vector_get(v, i)));
    }
    printf("]\n");
}

void* itemize_int(int i)
{
    int* i_ptr = malloc(sizeof(int));
    *i_ptr = i;
    return (void*) i_ptr;
}

#endif