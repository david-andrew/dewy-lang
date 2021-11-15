#ifndef FSET_C
#define FSET_C

#include <stdio.h>
#include <stdlib.h>

#include "fset.h"
#include "metaparser.h"

/**
 * Create a new empty fset (i.e. first/follow set).
 */
fset* new_fset()
{
    fset* s = malloc(sizeof(fset));
    *s = (fset){.special = false, .terminals = new_set()};
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
    *S = (obj){.type = FSet_t, .data = s};
    return S;
}

/**
 * Add the object to the fset.
 */
void fset_add(fset* s, obj* o) { set_add(s->terminals, o); }

/**
 * Merge right into left, and free right set.
 * If do_nullable is true, also merges nullable
 * from both sets (i.e. nullable = left->nullable || right->nullable)
 */
void fset_union_into(fset* left, fset* right, bool do_nullable)
{
    // insert each item of right into left
    for (size_t i = 0; i < set_size(right->terminals); i++)
    {
        obj* item = right->terminals->entries[i].item;
        if (!set_contains(left->terminals, item)) // TODO->can remove check, may cause fragmentation though...
        {
            set_add(left->terminals, obj_copy(item));
        }
    }

    // merge ϵ from each set, if specified
    if (do_nullable) { left->special = left->special || right->special; }

    // free right set
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
    copy->special = s->special;
    return copy;
}

/**
 * Print out a string representation of the fset. Generic version, prints both ϵ/$ for special fsets.
 */
void fset_str(fset* s)
{
    printf("{");
    fset_str_inner(s);
    if (s->special) { printf(set_size(s->terminals) > 0 ? ", ϵ/$" : "ϵ/$"); }
    printf("}");
}

/**
 * Print out the string representation of a first set (i.e. special fsets are printed with ϵ).
 */
void fset_first_str(fset* s)
{
    printf("{");
    fset_str_inner(s);
    if (s->special) { printf(set_size(s->terminals) > 0 ? ", ϵ" : "ϵ"); }
    printf("}");
}

/**
 * Print out the string representation of a follow set (i.e. special fsets are printed with $).
 */
void fset_follow_str(fset* s)
{
    printf("{");
    fset_str_inner(s);
    if (s->special) { printf(set_size(s->terminals) > 0 ? ", $" : "$"); }
    printf("}");
}

/**
 * Print out the list of terminals contained in the fset (not including ϵ/$)
 */
void fset_str_inner(fset* s)
{

    for (size_t i = 0; i < set_size(s->terminals); i++)
    {
        uint64_t* symbol_idx = s->terminals->entries[i].item->data;
        obj_str(metaparser_get_symbol(*symbol_idx));
        if (i < set_size(s->terminals) - 1) { printf(", "); }
    }
}

/**
 * determine if the fset contains the given unicode character (interprets c = 0 as ϵ or $)
 */
bool fset_contains_c(fset* s, uint32_t c)
{
    for (size_t i = 0; i < set_size(s->terminals); i++)
    {
        charset* symbol = set_get_at_index(s->terminals, i)->data;
        if (charset_contains_c(symbol, c) || (c == 0 && s->special)) { return true; }
    }
    return false;
}

#endif