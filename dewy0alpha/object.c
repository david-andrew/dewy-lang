#ifndef OBJECT_C
#define OBJECT_C

#include <stdbool.h>
#include "utilities.c"


//TODO->name the method each WARNING occurs in

// typedef enum obj_types { Integer, UInteger } Type; //TODO->replace with this type

/*
    Struct for Objects. 

    Type indicates what type of object:
    0 - Integer
    1 - Unsigned Integer
    2 - String
    3 - Token
    4 - Vector
    5 - Dictionary
    6 - Set

    TBD types:
    # - AST?


*/
typedef struct obj_struct
{
    int type;       //integer specifying what type of object.
    size_t size;    //size of the data allocated for this object
    void* data;     //data allocated for this object
} obj;

obj* new_int(int64_t i);
obj* new_uint(uint64_t u);
obj* new_string(char* s);
obj* new_ustr(char* s);
//These should probably go in their specific implementation file
//obj* new_vect();
//obj* new_dict();
//obj* new_set();
//obj* new_token();
size_t obj_size(obj* o);
obj* obj_copy(obj* o);
void obj_print(obj* o);
uint64_t obj_hash(obj* o);
int64_t obj_compare(obj* left, obj* right);
bool obj_equals(obj* left, obj* right);

////// FORWARD DECLARATIONS ////////

//forward declare token type + methods used here
typedef struct tokens token;
void token_str(token* t);
void token_free(token* t);

//forward declare vect type + methods used here
typedef struct vect_struct vect;
size_t vect_size(vect* v);
uint64_t vect_hash(vect* v); 
int64_t vect_compare(vect* left, vect* right); 
void vect_free(vect* v);
void vect_str(vect* v);
// vect_copy

//forward declare dict type + methods used here
typedef struct dict_struct dict;
size_t dict_size(dict* d);

//forward declare set type + methods used here
typedef struct set_struct set;
size_t set_size(set* S);

//dict_hash, dict_compare, dict_free
//set_hash, set_compare, set_free

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


/*
    Create a new string object, from an allocated string

    @param char* s: a HEAP-ALLOCATED pointer to a string. free() will be called on this string at the end of its life
    @return obj* S: an object containing our string
*/
obj* new_string(char* s)
{
    obj* S = malloc(sizeof(obj));
    S->type = 2;
    S->size = strlen(s);
    S->data = (void*)s;
    return S;
}

/*
    Create a new string object from a non-allocated string
*/
obj* new_ustr(char* s)
{
    return new_string(clone(s));
}


/*
    get the current size of the object's data
*/
size_t obj_size(obj* o)
{
    if (o == NULL) { return 0; }
    switch (o->type)
    {
        case 0: return o->size;
        case 1: return o->size;
        case 2: return o->size;
        case 3: return o->size; //TBD if token should be sized this way
        case 4: return vect_size((vect*)o->data);
        case 5: return dict_size((dict*)o->data);
        case 6: return set_size((set*)o->data);
        default: 
        {
            printf("WARNING obj_size() is not implemented for object of type \"%d\"\n", o->type);
            return 0;
        }
    }
}

//recursive deep copy of an object
//TODO->look into maintining a dictionary of pointers so that the deep copy can handle cyclical objects
obj* obj_copy(obj* o)
{
    if (o == NULL) { return NULL; }
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
        case 2: //copy string
        {
            char** copy_ptr = malloc(o->size + sizeof(char));
            strcpy(*((char**)o->data), *copy_ptr);
            copy->data = (void*)copy_ptr;
            break;
        }
        //TODO->other data types copy procedure. 
        //dict, set, and vect should all call obj_copy() on each of their elements, thus performing a deep copy
    
        default: printf("WARNING, obj_copy() is not implemented for object of type \"%d\"\n", o->type); break;
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
        case 2: printf("%s", *((char**)o->data));
        case 3: token_str((token*)o->data); break;
        case 4: vect_str((vect*)o->data);
        // case 5: dict_str((dict*)o->data);
        // case 6: set_str((set*)o->data);
        default: printf("WARNING: obj_print() is not implemented for object of type \"%d\"\n", o->type); break;
    }
}




// uint64_t meta_token_hash(obj* o);//forward declare
uint64_t obj_hash(obj* o) 
{
    if (o == NULL) { return 0; }
    switch (o->type)
    {
        case 0: return hash_int(*((int64_t*)o->data));
        case 1: return hash_uint(*((uint64_t*)o->data));
        case 2: return fnv1a(*((char**)o->data));
        // case 3: return meta_token_hash(o);
        case 4: return vect_hash((vect*)o->data);
        // case 5: return dict_hash((dict*)o->data);
        // case 6: return set_hash((set*)o->data);
        default: printf("WARNING: obj_hash() is not implemented for object of type \"%d\"\n", o->type); return 0;
    }
}

int64_t obj_compare(obj* left, obj* right)
{
    //TODO->check these.
    //handle case where either or both are null
    if (left == NULL && right == NULL) { return 0; } //both null means both equal
    else if (left == NULL) { return -1; } //left only null means left comes first
    else if (right == NULL) { return 1; } //right only null means right comes first
    
    //if the objects are of different type, order by type value
    if (left->type != right->type)
    {
        return left->type - right->type;
    }

    switch (left->type)
    {
        case 0: return *((int64_t*)left->data) - *((int64_t*)right->data);
        case 1: return *((uint64_t*)left->data) - *((uint64_t*)right->data);
        case 2: return strcmp(*((char**)left->data), *((char**)right->data));
        // case 3: return token_compare((token*)left->data, (token*)right->data);
        case 4: return vect_compare((vect*)left->data, (vect*)right->data);
        // case 5: return dict_compare((dict*)left->data, (dict*)right->data);
        // case 6: return set_compare((set*)left->data, (set*)right->data);
        default: printf("WARNING: obj_compare() is not implemented for object of type \"%d\"\n", left->type); return 0;
    }
}

bool obj_equals(obj* left, obj* right)
{
    return obj_compare(left, right) == 0;
}

void obj_free(obj* o)
{
    if (o != NULL)
    {
        //TODO->any object specific freeing that needs to happen. e.g. vects/dicts/sets need to call their specific version of free
        //handle freeing of o->data
        switch (o->type)
        {
            case 0: free(o->data); break;  //free uint pointer
            case 1: free(o->data); break;  //free int pointer
            case 2: free(o->data); break;  //free the string
            case 3: token_free((token*)o->data); break; 
            case 4: vect_free((vect*)o->data);
            // case 5: dict_free((dict*)o->data);
            // case 6: set_free((set*)o->data);
            default: printf("WARNING: obj_free() is not implemented for object of type \"%d\"\n", o->type); break;
        }

        free(o);
    }
}

#endif