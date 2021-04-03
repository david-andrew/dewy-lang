#ifndef FSET_C
#define FSET_C

#include <stdlib.h>

#include "fset.h"


/**
 * Create a new empty fset (i.e. first/follow set).
 */
fset* new_fset()
{
    fset* s = malloc(sizeof(fset));
    *s = (fset){.nullable=false, .terminals=new_set()};
    return s;
}


/**
 * Create a new fset wrapped in obj.
 * If s is null, an empty set is created.
 */
obj* new_fset_obj(fset* s)
{
    if (s == NULL) { s = new_fset(); }
    obj* S = malloc(sizeof(obj));
    *S = (obj){.type=FSet_t, .data=s};
    return S;
}


/**
 * Add the object to the fset.
 */
void fset_add(fset* s, obj* o)
{
    set_add(s->terminals, o);
}


/**
 * Merge right into left, and free left set. 
 * If do_nullable is true, also merges nullable 
 * from both sets (i.e. nullable = left->nullable || right->nullable)
 */
void fset_union_into(fset* left, fset* right, bool do_nullable)
{
    //insert each item of right into left
    for (size_t i = 0; i < set_size(right->terminals); i++)
    {
        obj* item = right->terminals->entries[i].item;
        if (!set_contains(left->terminals, item)) //TODO->can remove check, may cause fragmentation though...
        {
            set_add(left->terminals, obj_copy(item));
        }
    }
    
    //merge ϵ from each set, if specified
    if (do_nullable)
    {
        left->nullable = left->nullable || right->nullable;
    }

    //free right set
    fset_free(right);
}


/**
 * Free an allocated fset object.
 */
void fset_free(fset* s)
{
    set_free(s->terminals);
    free(s);
}


/**
 * Return a copy of the fset.
 */
fset* fset_copy(fset* s)
{
    fset* copy = malloc(sizeof(fset));
    copy->terminals = set_copy(s->terminals);
    copy->nullable = s->nullable;
    return copy;
}



#endif