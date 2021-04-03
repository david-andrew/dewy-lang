#ifndef FSET_H
#define FSET_H

#include "object.h"
#include "set.h"

typedef struct {
    set* terminals;
    bool nullable; //instead of representing ϵ as an obj, keep a separate boolean
} fset;


fset* new_fset();
obj* new_fset_obj(fset* s);
void fset_add(fset* s, obj* o);
// fset* fset_union(fset* left, fset* right);
void fset_union_into(fset* left, fset* right, bool do_nullable); //merge right into left, frees right, handles nullable
void fset_free(fset* s);
fset* fset_copy(fset* s);



#endif