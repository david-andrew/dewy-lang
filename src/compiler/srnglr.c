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


/**
 * 
 */
set* srnglr_closure(set* kernel)
{
    set* closure = set_copy(kernel);

    size_t prev_num_items;
    do 
    {
        prev_num_items = set_size(closure);
        /*
        for (each item [A->α•Bβ, a] in closure)
        {
            for (each production B->γ in metaparser_productions) //i.e each production with head B
            {
                for (each terminal b in FIRST(βa))
                {
                    add [B->•γ] to closure
                }
            }
        } 
        */
    } while (prev_num_items < set_size(closure));

    return closure;
}


/**
 * 
 */
set* srnglr_goto(set* itemset, uint64_t symbol_idx)
{
    set* gotoset = new_set();
    /*
    for (each item [A->α•Xβ, a] in itemset) where X is metaparser_symbols[symbol_idx]
    {
        add item [A->αX•β, a] to gotoset
    }
    */
    return gotoset;
}


/**
 * 
 */
set* srnglr_generate_grammar_itemsets()
{
    set* itemsets = new_set();

    size_t prev_num_itemsets;
    do 
    {
        prev_num_itemsets = set_size(itemsets);
        /*
        for (each set of items I in itemsets)
        {
            for (each grammar symbol X in metaparser_symbols)
            {
                if (GOTO(I, X) is not empty, and not in itemsets) //can skip second check since set ensures duplicates are not added
                {
                    add GOTO(I, X) to itemsets
                }
            }
        }
        */
    }
    while (prev_num_itemsets < set_size(itemsets));

    return itemsets;
}



#endif