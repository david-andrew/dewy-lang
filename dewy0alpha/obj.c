#ifndef OBJ_C
#define OBJ_C

#include <stdbool.h>
#include "utilities.c"

// typedef enum obj_types { Integer, UInteger } Type; //TODO->replace with this type

/*
    Struct for Objects. 

    Type indicates what type of object:
    0 - Integer
    1 - Unsigned Integer
    2 - TBD string
    3 - TBD vect
    4 - TBD dict
    5 - TBD EBNF_token
    ...

*/
typedef struct obj_struct
{
    int type;       //integer specifying what type of object.
    size_t size;    //size of the data allocated for this object
    void* data;     //data allocated for this object
} obj;

obj* new_int(int64_t i);
obj* new_uint(uint64_t u);
void obj_print(obj* o);
uint64_t obj_hash(obj* o);
int64_t obj_compare(obj* left, obj* right);
bool obj_equals(obj* left, obj* right);


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



uint64_t obj_hash(obj* o) 
{
    switch (o->type)
    {
        case 0: return hash_int(*((int64_t*)o->data));
        case 1: return hash_uint(*((uint64_t*)o->data));
        //other cases
        //...
        default: printf("WARNING: object of type \"%d\" hasn't been implemented\n", o->type); return 0;
    }
}

int64_t obj_compare(obj* left, obj* right)
{
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
    //TBD any object specific freeing that needs to happen
    free(o->data);
    free(o);
}

#endif