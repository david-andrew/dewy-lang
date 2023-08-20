#ifndef FSET_C
#define FSET_C

#include <stdio.h>
#include <stdlib.h>

#include "charset.h"
#include "fset.h"
#include "metaparser.h"

/**
 * Create a new empty fset (i.e. first/follow set).
 */
fset* new_fset()
{
    fset* s = malloc(sizeof(fset));
    *s = (fset){.special = false, .terminals = new_charset()};
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
 * Count the total size number of characters contained in the fset.
 */
uint64_t fset_size(fset* s) { return charset_length(s->terminals) + s->special; }

/**
 * Add the charset range to the fset. charset is not modified by this function.
 */
void fset_add(fset* s, charset* cs) { charset_union_into(s->terminals, cs, false); }

/**
 * Set the special value for the fset.
 * For first sets, true means the set contains ϵ
 * For follow sets, true means the set contains $
 */
void fset_set_special(fset* s, bool special) { s->special = special; }

/**
 * Merge right into left, and free right set if free_right is true.
 * If do_nullable is true, also merges nullable from both sets
 *   i.e. nullable = left->nullable || right->nullable
 */
void fset_union_into(fset* left, fset* right, bool do_nullable, bool free_right)
{
    // merge the terminals charset from right into left
    charset_union_into(left->terminals, right->terminals, false);

    // merge ϵ from each set, if specified
    if (do_nullable) { left->special = left->special || right->special; }

    // free right set if specified
    if (free_right) { fset_free(right); }
}

/**
 * Free an allocated fset object.
 */
void fset_free(fset* s)
{
    charset_free(s->terminals);
    free(s);
}

/**
 * Return a copy of the fset.
 */
fset* fset_copy(fset* s)
{
    fset* copy = malloc(sizeof(fset));
    copy->terminals = charset_clone(s->terminals);
    copy->special = s->special;
    return copy;
}

/**
 * Print out a string representation of the fset. Generic version, prints both ϵ/$ for special fsets.
 */
void fset_str(fset* s)
{
    printf("{");
    charset_str_inner(s->terminals);
    if (s->special) { printf(charset_size(s->terminals) > 0 ? ", ϵ/$" : "ϵ/$"); }
    printf("}");
}

/**
 * Print out the string representation of a first set (i.e. special fsets are printed with ϵ).
 */
void fset_first_str(fset* s)
{
    printf("{");
    charset_str_inner(s->terminals);
    if (s->special) { printf(charset_size(s->terminals) > 0 ? ", ϵ" : "ϵ"); }
    printf("}");
}

/**
 * Print out the string representation of a follow set (i.e. special fsets are printed with $).
 */
void fset_follow_str(fset* s)
{
    printf("{");
    charset_str_inner(s->terminals);
    if (s->special) { printf(charset_size(s->terminals) > 0 ? ", $" : "$"); }
    printf("}");
}

/**
 * determine if the fset contains the given unicode character (interprets c = 0 as ϵ or $)
 */
bool fset_contains_c(fset* s, uint32_t c)
{
    if (c == 0) { return s->special; }
    return charset_contains_c(s->terminals, c);
}

#endif