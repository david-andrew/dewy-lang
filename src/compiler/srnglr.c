#ifndef SRNGLR_C
#define SRNGLR_C

#include <stdio.h>

#include "srnglr.h"
#include "slice.h"
#include "fset.h"
#include "metaparser.h"
#include "metaitem.h"
#include "slice.h"


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
            vect* body = metaparser_get_production_body(symbol_idx, i);
            slice string = (slice){ //stack allocate to minimize short lived heap objects
                .v=body, 
                .start=0, 
                .stop=vect_size(body), 
                .lookahead=NULL
            };
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
 * Compute the itemset closure for the given kernel.
 * Note that kernel will be modified by this algorithm
 * Uses the following algorithm (Dragon book page 261):
 * 
 * CLOSURE(kernel) {
 *     closure = copy of kernel
 *     do {
 *         for (each item [A->α•Bβ, a] in closure) {
 *             for (each production B->γ in metaparser_productions) { //i.e each production with head B
 *                 for (each terminal b in FIRST(βa)) {
 *                     add [B->•γ, b] to closure
 *                 }
 *             }
 *         }
 *     } while new items were added to closure
 * }
 */

set* srnglr_closure(set* kernel)
{
    //set to hold the closure of the kernel
    set* closure = kernel;

    //loop until no new items were added to closure
    while (true)
    {
        //record the size of the closure set, so we know if we added any items
        size_t prev_num_items = set_size(closure);

        //for each item in closure
        for (size_t i = 0; i < set_size(closure); i++)
        {
            //get the item and the next symbol.
            metaitem* item = closure->entries[i].item->data;
            vect* item_body = metaparser_get_production_body(item->head_idx, item->production_idx);
            if (item_body == NULL) { continue; }
            if (item->position >= vect_size(item_body)) { continue; }
            uint64_t* symbol_idx = vect_get(item_body, item->position)->data;
            
            //only need to expand non-terminals
            if (!metaparser_is_symbol_terminal(*symbol_idx))
            {
                //get the lookahead symbols for this item
                obj cur_lookahead = (obj){.type=UInteger_t, .data=&item->lookahead_idx};
                slice remaining = (slice){
                    .v = item_body,
                    .start = item->position + 1,
                    .stop = vect_size(item_body),
                    .lookahead = &cur_lookahead
                };
                fset* lookaheads = srnglr_first_of_string(&remaining);
                
                //add new items for each body, for each lookahead
                set* bodies = metaparser_get_production_bodies(*symbol_idx);
                for (uint64_t production_idx = 0; production_idx < set_size(bodies); production_idx++)
                {
                    for (size_t k = 0; k < set_size(lookaheads->terminals); k++)
                    {
                        uint64_t* lookahead = lookaheads->terminals->entries[k].item->data;
                        metaitem* new = new_metaitem(*symbol_idx, production_idx, 0, *lookahead);
                        set_add(closure, new_metaitem_obj(new));
                    }
                }

                //done with this first set of lookaheads
                fset_free(lookaheads);
            }
        }

        //closure is complete if no new items were added
        if (prev_num_items == set_size(closure)) { break; }
    }

    return closure;
}


/**
 * Compute the itemset goto for the given symbol.
 * Uses the following algorithm (Dragon book page 261):
 * 
 * GOTO(itemset, X) {
 *     gotoset = {}
 *     for (each item [A->α•Xβ, a] in itemset) { //i.e. X is next symbol
 *         add item [A->αX•β, a] to gotoset
 *     }
 *     return gotoset
 * }
 */
set* srnglr_goto(set* itemset, uint64_t symbol_idx)
{
    set* gotoset = new_set();

    for (size_t i = 0; i < set_size(itemset); i++)
    {
        //get the item and the next symbol.
        metaitem* item = itemset->entries[i].item->data;
        vect* item_body = metaparser_get_production_body(item->head_idx, item->production_idx);
        if (item_body == NULL) { continue; }
        if (item->position >= vect_size(item_body)) { continue; }
        uint64_t* next_symbol_idx = vect_get(item_body, item->position)->data;

        //this item's next symbol is the goto symbol, so add to gotoset with position+1
        if (*next_symbol_idx == symbol_idx)
        {
            metaitem* new = new_metaitem(item->head_idx, item->production_idx, item->position + 1, item->lookahead_idx);
            set_add(gotoset, new_metaitem_obj(new));
        }
    }

    return srnglr_closure(gotoset);
}


/**
 * Generate all itemesets for the current grammar.
 * start_idx is the index of the head of the augmented grammar start rule.
 * The production for the start rule should have only 1 body containing the user set start rule for the grammar.
 * 
 * itemsets = closure({[S'->•S, $]})
 * do {
 *     for (each set of items I in itemsets) {
 *         for (each grammar symbol X in metaparser_symbols) {
 *             if (GOTO(I, X) is not empty, and not in itemsets) { //can skip second check since set ensures duplicates are not added
 *                 add GOTO(I, X) to itemsets
 *             }
 *         }
 *     }
 * } while no new itemsets were added
 */
set* srnglr_generate_grammar_itemsets()
{
    //get the symbol for the augmented start rule from the grammar
    uint64_t start_idx = metaparser_get_start_symbol_idx();

    //create the first itemset by taking closure on the start rule
    set* kernel = new_set();
    metaitem* start_item = new_metaitem(start_idx, 0, 0, metaparser_get_endmarker_symbol_idx());
    set_add(kernel, new_metaitem_obj(start_item));
    set* start_set = srnglr_closure(kernel);

    set* itemsets = new_set();
    set_add(itemsets, new_set_obj(start_set));

    set* symbols = metaparser_get_symbols();

    while (true)
    {
        size_t prev_num_itemsets = set_size(itemsets);
        
        //loop through each itemset in the set of itemsets
        for (size_t i = 0; i < set_size(itemsets); i++)
        {
            //current itemset
            set* itemset = itemsets->entries[i].item->data;
            
            //loop through each symbol in the grammar
            for (uint64_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
            {
                set* gotoset = srnglr_goto(itemset, symbol_idx);
                if (set_size(gotoset) > 0)
                {
                    //set add handles duplicates
                    set_add(itemsets, new_set_obj(gotoset));
                }
                else
                {
                    //don't use empty itemsets
                    set_free(gotoset);
                }
            }
        }

        //itemsets is complete if no new itemsets were added
        if (prev_num_itemsets == set_size(itemsets)) { break; }
    }

    return itemsets;
}



#endif