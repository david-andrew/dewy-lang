#ifndef OBJECT_C
#define OBJECT_C

#include <stdbool.h>
#include "utilities.c"

// typedef enum obj_types { Integer, UInteger } Type; //TODO->replace with this type

/*
    Struct for Objects. 

    Type indicates what type of object:
    0 - Integer
    1 - Unsigned Integer

    TBD types:
    # - vect
    # - dict
    # - set
    # - tokens
    # - string


*/
typedef struct obj_struct
{
    int type;       //integer specifying what type of object.
    size_t size;    //size of the data allocated for this object
    void* data;     //data allocated for this object
} obj;

obj* new_int(int64_t i);
obj* new_uint(uint64_t u);
//These should probably go in their specific implementation file
//obj* new_vect();
//obj* new_dict();
//obj* new_set();
//obj* new_string();
//obj* new_token(); //already implemented?
obj* obj_copy(obj* o);
void obj_print(obj* o);
uint64_t obj_hash(obj* o);
int64_t obj_compare(obj* left, obj* right);
bool obj_equals(obj* left, obj* right);

//forward declaration for defined in other files.
//implementation in compile_tools.c
// typedef struct meta_tokens meta_token;
// typedef enum token_types token_type;
// obj* new_token(token_type type, char* content);
typedef struct tokens token;
void token_str(token* t);

obj* new_int(int64_t i)
{
    obj* I = malloc(sizeof(obj));
    I->type = 0;
    I->size = sizeof(int64_t);
    int64_t* i_ptr = malloc(sizeof(int64_t)); 
    *i_ptr = i;
    I->data = (void*)i_ptr;
    return I;
}

obj* new_uint(uint64_t u)
{
    obj* U = malloc(sizeof(obj));
    U->type = 1;
    U->size = sizeof(uint64_t);
    uint64_t* u_ptr = malloc(sizeof(uint64_t));
    *u_ptr = u;
    U->data = (void*)u_ptr;
    return U;
}

//recursive deep copy of an object
//TODO->look into maintining a dictionary of pointers so that the deep copy can handle cyclical objects
obj* obj_copy(obj* o)
{
    obj* copy = malloc(sizeof(obj));
    copy->type = o->type;
    copy->size = o->size;
    switch (o->type)
    {
        case 0: //copy int64
        {
            int64_t* copy_ptr = malloc(sizeof(int64_t));
            *copy_ptr = *((int64_t*)o->data);
            copy->data = (void*)copy_ptr;
            break;
        }
        case 1: //copy uint64
        {
            uint64_t* copy_ptr = malloc(sizeof(uint64_t));
            *copy_ptr = *((uint64_t*)o->data);
            copy->data = (void*)copy_ptr;
            break;
        }
        //TODO->other data types copy procedure. 
        //dict, set, and vect should all call obj_copy() on each of their elements, thus performing a deep copy
    }

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
        case 0: printf("%ld", *((int64_t*)o->data)); break;
        case 1: printf("%lu", *((uint64_t*)o->data)); break;
        //other cases
        //...
        case 5: token_str((token*)o->data); break;
        default: printf("WARNING: object of type \"%d\" hasn't been implemented\n", o->type); break;
    }
}


//DO NOT USE - WILL CAUSE MEMORY LEAKS IF NOT CAREFUL
// char* tostr(Object* obj)
// {
//     switch (obj->type)
//     {
//         case 0:
//         {
//             char* buffer = malloc(sizeof(char)*21); // maximum int is 20 characters long: 18,446,744,073,709,551,615
//             sprintf(buffer, "%ld", *((int64_t*)obj->data));
//             return buffer;
//         } break;

//         default:
//         { 
//             return "Unknown Type";
//         } break;
//     }
// }



// uint64_t meta_token_hash(obj* o);//forward declare
uint64_t obj_hash(obj* o) 
{
    switch (o->type)
    {
        case 0: return hash_int(*((int64_t*)o->data));
        case 1: return hash_uint(*((uint64_t*)o->data));
        //other cases
        //...
        // case 5: return meta_token_hash(o);
        default: printf("WARNING: object of type \"%d\" hasn't been implemented\n", o->type); return 0;
    }
}

int64_t obj_compare(obj* left, obj* right)
{
    //TODO->check these.
    //handle case where either or both are null
    if (left == NULL && right == NULL) { return 0; } //both null means both equal
    else if (left == NULL) { return -1; } //left only null means left comes first
    else if (right == NULL) { return 1; } //right only null means right comes first
    
    switch (left->type) //undefined behavior if left and right aren't the same type
    {
        case 0: return *((int64_t*)left->data) - *((int64_t*)right->data);
        case 1: return *((uint64_t*)left->data) - *((uint64_t*)right->data);
        //other cases
        //...
        default: printf("WARNING: object of type \"%d\" hasn't been implemented\n", left->type); return 0;
    }
}

bool obj_equals(obj* left, obj* right)
{
    return obj_compare(left, right) == 0;
}


void obj_free(obj* o)
{
    //TBD any object specific freeing that needs to happen. e.g. vects/dicts/sets need to call their specific version of free
    free(o->data);
    free(o);
}

#endif