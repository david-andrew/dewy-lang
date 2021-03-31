#ifndef SRNGLR_C
#define SRNGLR_C

#include "srnglr.h"
#include "slice.h"
#include "fset.h"
#include "metaparser.h"


/*
def first_of_symbol(X)
    if X is terminal 
        return {X}
    else
        result = {}
        for each production body of X = Y1 Y2 ... Yk, (k can be 0)
            add first_of_string(p.body) to result
        return result

def first_of_string(string = X1 X2 ... Xn)
    result = {}
    for i in 1:n
        Xi = string[i]
        fXi = first(Xi)
        add fXi - {ϵ} to result
        if ϵ not in fXi
            break
        if i == n and ϵ in fXi
            add ϵ to result

    if size(string) == 0
        add ϵ to result
    
    return result
*/

/**
 * Compute the first set for the given individual symbol.
 */
fset* srnglr_first_of_symbol(uint64_t symbol_idx)
{
    //set to hold result
    fset* result = new_fset();
    
    if (metaparser_is_symbol_terminal(symbol_idx))
    {
        fset_add(result, new_uint_obj(symbol_idx));
        result->nullable = false;
        return result;
    }
    else //handle non-terminal identifier
    {
        //get all production bodies for this non-terminal
        set* bodies = metaparser_get_production_bodies(symbol_idx);
        if (bodies == NULL)
        {
            //Error, but return nullable empty set so that the parser doesn't get stuck...
            //TODO->convert to a critical error that crashes the parser...but need to free allocated memory...
            exit(1);
        }

        //for each production body
        for (size_t i = 0; i < set_size(bodies); i++)
        {
            vect* body = bodies->entries[i].item->data;
            slice string = (slice){.v=body, .start=0, .stop=vect_size(body)}; //stack allocate to minimize short lived heap objects
            fset* first_i = srnglr_first_of_string(&string);
            fset_union_into(result, first_i, true); //handles freeing first_i. also merge nullable
        }
    }

    return result;
}


/**
 * Compute the first set for the given string of symbols.
 */
fset* srnglr_first_of_string(slice* string)
{
    fset* result = new_fset();

    if (slice_size(string) == 0)
    {
        //empty string is nullable
        result->nullable = true;
    }
    else
    {
        //handle each symbol in the string, until a non-nullable symbol is reached
        for (size_t i = 0; i < slice_size(string); i++)
        {
            uint64_t* symbol_idx = slice_get(string, i)->data;
            fset* first_i = srnglr_first_of_symbol(*symbol_idx);
            bool nullable = first_i->nullable;
            fset_union_into(result, first_i, false); //merge first of symbol into result. Don't merge nullable
            if (i == slice_size(string) - 1 && nullable)
            {
                result->nullable = true;
            }

            //only continue to next symbol if this symbol was nullable
            if (!nullable){ break; }
        }
    }

    return result;
}


#endif