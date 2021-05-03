#ifndef SRNGLR_C
#define SRNGLR_C

#include <stdio.h>
#include <inttypes.h>
#include <string.h>

#include "tuple.h"
#include "dictionary.h"
#include "srnglr.h"
#include "ustring.h"
#include "slice.h"
#include "fset.h"
#include "metaparser.h"
#include "metaitem.h"
#include "slice.h"
#include "gotokey.h"
#include "reduction.h"
#include "gss.h"
#include "sppf.h"

/**
 * Global data structures for storing the srnglr item sets and parse table
 * itemsets holds all itemsets (i.e. tables states) generated from the grammar.
 * table maps from GotoKey_t to sets containing Push_t, Reduction_t, or Accept_t.
 * symbol_firsts maps (implicitly) from symbol_idx's to corresponding first sets.
 */
set* srnglr_itemsets;
dict* srnglr_table;
vect* srnglr_symbol_firsts;

//vectors used during SRNGLR parsing
vect* srnglr_R;
vect* srnglr_Q;

gss* GSS;
sppf* SPPF;

//copy of the input source being read by the parser.
uint32_t* srnglr_input_source;

/**
 * Initialize global srnglr data structures.
 */
void initialize_srnglr(size_t input_size)
{
    srnglr_itemsets = new_set();
    srnglr_table = new_dict();
    srnglr_symbol_firsts = new_vect();

    srnglr_R = new_vect();
    srnglr_Q = new_vect();

    GSS = new_gss(input_size);
    SPPF = new_sppf();
}


/**
 * Free global srnglr data structures.
 */
void release_srnglr()
{
    set_free(srnglr_itemsets);
    dict_free(srnglr_table);
    vect_free(srnglr_symbol_firsts);

    vect_free(srnglr_R);
    vect_free(srnglr_Q);

    gss_free(GSS); 
    sppf_free(SPPF);
}


/**
 * Create a new object representing a push action.
 */
obj* new_push_obj(uint64_t p)
{
    obj* P = malloc(sizeof(obj));
    *P = (obj){.type=Push_t, .data=new_uint(p)};
    return P;
}


/**
 * Print out a string representing the push action.
 */
void push_str(uint64_t p)
{
    printf("P%"PRIu64, p);
}


/**
 * Return the printed width of the push action.
 */
int push_strlen(uint64_t p)
{
    return snprintf("", 0, "P%"PRIu64, p);
}


/**
 * Print out the internal representation of the push action.
 */
void push_repr(uint64_t p)
{
    printf("Push{%"PRIu64"}", p);
}


/**
 * Create a new accept action wrapped object.
 */
obj* new_accept_obj()
{
    obj* A = malloc(sizeof(obj));
    *A = (obj){.type=Accept_t, .data=NULL};
    return A;
}


/**
void srnglr_print_gss();
 * Print out a string representing the accept action.
 */
void accept_str()
{
    printf("ACCEPT");
}


/**
 * Return the printed width of the accept action.
 */
int accept_strlen()
{
    return strlen("ACCEPT");
}


/**
 * print out a more verbose representation of the accept action.
 */
void accept_repr()
{
    printf("accept{}");
}


/**
 * Return a copy of the pointer to the current input source text.
 * May be used by other components to get characters from the text.
 */
uint32_t* srnglr_get_input_source()
{
    return srnglr_input_source;
}


/**
 * Compute all first sets for each symbol in the grammar.
 * Additionally for any nullable symbols, create epsilon nodes for them
 * in the SPPF
 */
void srnglr_compute_symbol_firsts()
{
    //ensure that the endmarker symbol has been added to the metaparser. TODO->move this into the intialization of the metaparser?
    metaparser_get_endmarker_symbol_idx();
    
    //ensure the sppf has the root epsilon defined
    sppf_add_root_epsilon(SPPF);

    //create empty fsets for each symbol in the grammar
    set* symbols = metaparser_get_symbols();
    for (size_t i = 0; i < set_size(symbols); i++)
    {
        vect_append(srnglr_symbol_firsts, new_fset_obj(NULL));
    }

    //compute firsts for all terminal symbols, since the fset is just the symbol itself.
    for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
    {
        if (!metaparser_is_symbol_terminal(symbol_idx)) { continue; }
        fset* symbol_fset = vect_get(srnglr_symbol_firsts, symbol_idx)->data;
        fset_add(symbol_fset, new_uint_obj(symbol_idx));
        symbol_fset->nullable = false;
    }

    //compute first for all non-terminal symbols. update each set until no new changes occur
    size_t count;
    do
    {
        //keep track of if any sets got larger (i.e. by adding new terminals to any fset's)
        count = srnglr_count_firsts_size();

        //for each non-terminal symbol
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (metaparser_is_symbol_terminal(symbol_idx)) { continue; }

            fset* symbol_fset = vect_get(srnglr_symbol_firsts, symbol_idx)->data;            
            set* bodies = metaparser_get_production_bodies(symbol_idx);
            for (size_t production_idx = 0; production_idx < set_size(bodies); production_idx++)
            {
                vect* body = metaparser_get_production_body(symbol_idx, production_idx);
                
                //for each element in body, get its fset, and merge into this one. stop if non-nullable
                for (size_t i = 0; i < vect_size(body); i++)
                {
                    uint64_t* body_symbol_idx = vect_get(body, i)->data;
                    fset* body_symbol_fset = vect_get(srnglr_symbol_firsts, *body_symbol_idx)->data;
                    fset_union_into(symbol_fset, fset_copy(body_symbol_fset), true);
                    if (!body_symbol_fset->nullable) { break; }
                }

                //epsilon strings add epsilon to fset
                if (vect_size(body) == 0)
                {
                    symbol_fset->nullable = true;
                }
            }
        }
    }
    while(count < srnglr_count_firsts_size());

    //add all nullable non-terminals as nodes to the SPPF
    for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
    {
        if (metaparser_is_symbol_terminal(symbol_idx)) { continue; }

        fset* symbol_fset = vect_get(srnglr_symbol_firsts, symbol_idx)->data;
        if (symbol_fset->nullable)
        {
            //add the nullable symbol to the SPPF
            sppf_add_nullable_symbol_node(SPPF, symbol_idx);
        }
    }
}


/**
 * Helper function to count the total number of elements in all first sets 
 */
size_t srnglr_count_firsts_size()
{
    size_t count = 0;
    for (size_t i = 0; i < vect_size(srnglr_symbol_firsts); i++)
    {
        fset* s = vect_get(srnglr_symbol_firsts, i)->data;
        count += set_size(s->terminals) + s->nullable;
    }
    return count;
}

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
            fset* first_i = vect_get(srnglr_symbol_firsts, *symbol_idx)->data;
            bool nullable = first_i->nullable;
            fset_union_into(result, fset_copy(first_i), false); //merge first of symbol into result. Don't merge nullable
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
                obj cur_lookahead = obj_struct(UInteger_t, &item->lookahead_idx);
                slice remaining = slice_struct(item_body, item->position + 1, vect_size(item_body), &cur_lookahead);
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
void srnglr_generate_grammar_itemsets()
{
    //get the symbol for the augmented start rule from the grammar
    uint64_t start_idx = metaparser_get_start_symbol_idx();

    //precompute all first sets for each grammar symbol
    srnglr_compute_symbol_firsts();

    //create the first itemset by taking closure on the start rule
    set* kernel = new_set();
    metaitem* start_item = new_metaitem(start_idx, 0, 0, metaparser_get_endmarker_symbol_idx());
    set_add(kernel, new_metaitem_obj(start_item));
    set* start_set = srnglr_closure(kernel);

    //add the first itemset to the (global) list of itemsets
    set_add(srnglr_itemsets, new_set_obj(start_set));

    set* symbols = metaparser_get_symbols();

    //Generate all itemsets + GOTO actions
    while (true)
    {
        size_t prev_num_itemsets = set_size(srnglr_itemsets);
        
        //loop through each itemset in the set of itemsets
        for (size_t itemset_idx = 0; itemset_idx < set_size(srnglr_itemsets); itemset_idx++)
        {
            //current itemset
            set* itemset = srnglr_itemsets->entries[itemset_idx].item->data;
            
            //loop through each symbol in the grammar
            for (uint64_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
            {
                set* gotoset = srnglr_goto(itemset, symbol_idx);
                if (set_size(gotoset) > 0)
                {
                    //set add handles duplicates
                    uint64_t goto_idx = set_add_return_index(srnglr_itemsets, new_set_obj(gotoset));
                    srnglr_insert_push(itemset_idx, symbol_idx, goto_idx);
                }
                else
                {
                    //don't use empty itemsets
                    set_free(gotoset);
                }
            }
        }

        //itemsets is complete if no new itemsets were added
        if (prev_num_itemsets == set_size(srnglr_itemsets)) { break; }
    }

    //insert reduction/accept actions into the table
    for (size_t state_idx = 0; state_idx < set_size(srnglr_itemsets); state_idx++)
    {
        set* itemset = srnglr_itemsets->entries[state_idx].item->data;

        //check each item in the itemset
        for (size_t j = 0; j < set_size(itemset); j++)
        {
            metaitem* item = itemset->entries[j].item->data;
            if (metaitem_is_accept(item))
            {
                //check if special head
                if (item->head_idx == metaparser_get_start_symbol_idx())
                {
                    //this is an accepting state
                    srnglr_insert_accept(state_idx, item->lookahead_idx);
                }
                else //otherwise normal reduction
                {
                    //determine the value for `f`  i.e. which nullable sentence is left in the item being reduced. 0 -> ϵ
                    uint64_t nullable_idx = 0;

                    //determine if nullable head needs to be inserted as a nullable node in the SPPF.
                    vect* body = metaparser_get_production_body(item->head_idx, item->production_idx);
                    if (item->position < vect_size(body))
                    {
                        slice requlred_part = slice_struct(body, item->position, vect_size(body), NULL);
                        nullable_idx = sppf_add_nullable_string_node(SPPF, &requlred_part);
                    }

                    
                    srnglr_insert_reduction(state_idx, item->lookahead_idx, item->head_idx, item->production_idx, item->position, nullable_idx);
                }
            }
        }
    }
}


/**
 * Return the itemsets (mainly used by external functions).
 */
set* srnglr_get_itemsets()
{
    return srnglr_itemsets;
}


/**
 * Return the parser table (mainly used by external functions).
 */
dict* srnglr_get_table()
{
    return srnglr_table;
}


/**
 * Return the action set for the given state, symbol pair in the parser table.
 * If no set exists, an empty set is created at that index, and returned.
 */
set* srnglr_get_table_actions(uint64_t state_idx, uint64_t symbol_idx)
{
    //create a static key object (for retrieving the set in the dict)
    gotokey static_key = gotokey_struct(state_idx, symbol_idx);
    obj static_key_obj = obj_struct(GotoKey_t, &static_key);

    //check if the srnglr table has a set for the given key
    if (!dict_contains(srnglr_table, &static_key_obj))
    {
        //create a new entry for this key
        gotokey* key = new_gotokey(state_idx, symbol_idx);
        dict_set(srnglr_table, new_gotokey_obj(key), new_set_obj(NULL));
    }

    //get the set at this key
    set* actions = dict_get(srnglr_table, &static_key_obj)->data;

    return actions;
}


/**
 * Return the single push action in the table cell if it exists.
 * Otherwise return NULL.
 */
uint64_t* srnglr_get_table_push(uint64_t state_idx, uint64_t symbol_idx)
{
    set* actions = srnglr_get_table_actions(state_idx, symbol_idx);
    for (size_t i = 0; i < set_size(actions); i++)
    {
        if (set_get_at_index(actions, i)->type == Push_t)
        {
            return set_get_at_index(actions, i)->data;
        }
    }
    return NULL;
}


/**
 * Get the set of all actions that corresponds to the given state and input character.
 * Since a single input character can match multiple grammar symbols, merge the action
 * sets from each cell that matches the (state, input) pair.
 */
set* srnglr_get_merged_table_actions(uint64_t state_idx, uint32_t c)
{
    //interpret null terminator as the endmarker symbol #$
    if (c == 0){ c = UNICODE_ENDMARKER_POINT; }

    //set to merge actions into
    set* actions = new_set();

    set* symbols = metaparser_get_symbols();
    for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
    {        
        //characters can only match terminals (i.e. charsets)
        if (!metaparser_is_symbol_terminal(symbol_idx)) { continue; }

        //if the character is a member of the symbol charset
        charset* terminal = metaparser_get_symbol(symbol_idx)->data;
        if (charset_contains_c(terminal, c))
        {
            //merge in the actions for this cell
            set* cell_actions = srnglr_get_table_actions(state_idx, symbol_idx);
            set_union_into(actions, set_copy(cell_actions));
        }
    }
    return actions;
}


/**
 * Add a Push_t item to the srnglr table.
 */
void srnglr_insert_push(uint64_t state_idx, uint64_t symbol_idx, uint64_t goto_idx)
{
    //get the actions set for this state, symbol pair
    set* actions = srnglr_get_table_actions(state_idx, symbol_idx);

    //insert the push action to the set
    set_add(actions, new_push_obj(goto_idx));
}


/**
 * Add a reduction action to the srnglr table.
 */
void srnglr_insert_reduction(uint64_t state_idx, uint64_t symbol_idx, uint64_t head_idx, uint64_t production_idx, uint64_t length, uint64_t nullable_idx)
{
    //get the actions set for this state, symbol pair
    set* actions = srnglr_get_table_actions(state_idx, symbol_idx);

    //create a reduction and add to the actions set.
    reduction* r = new_reduction(head_idx, production_idx, length, nullable_idx);
    set_add(actions, new_reduction_obj(r));
}


/**
 * Add an accept action to the srnglr table.
 */
void srnglr_insert_accept(uint64_t state_idx, uint64_t symbol_idx)
{
    //get the actions set for this state, symbol pair
    set* actions = srnglr_get_table_actions(state_idx, symbol_idx);

    //insert an accept action to the set
    set_add(actions, new_accept_obj());
}


/**
 * Determine if the given state is an accepting state,
 * i.e. it's lookahead is the endmarker, and it contains
 * an accept action.
 */
bool srnglr_is_accepting_state(uint64_t state_idx)
{
    uint64_t endmarker_idx = metaparser_get_endmarker_symbol_idx();
    set* actions = srnglr_get_table_actions(state_idx, endmarker_idx);
    for (size_t i = 0; i < set_size(actions); i++)
    {
        obj* action = actions->entries[i].item;
        if (action->type == Accept_t)
        {
            return true;
        }
    }
    return false;
}


/**
 * Parse an input string according to the preparsed grammar.
 * Implementation 1 is pulled directly from rnglr paper.
 * Returns whether or not the parse was successful.
 */
bool srnglr_parser(uint32_t* src)
{
    //cache a copy of the input source
    srnglr_input_source = src;
    
    //length 0 input is only a successful parse if table includes accept at state 0, with #$ lookahead
    if (src[0] == 0)
    {
        uint64_t endmarker_idx = metaparser_get_endmarker_symbol_idx();
        set* actions = srnglr_get_table_actions(0, endmarker_idx);
        for (size_t i = 0; i < set_size(actions); i++)
        {
            if (actions->entries[i].item->type == Accept_t) { return true; }
        }
        return false;
    }

    //normal parse process

    //create the start node (v0), and insert into the GSS
    gss_idx* v0_idx = gss_add_node(GSS, 0, 0);
    gss_idx_free(v0_idx); //free the unused index returned by gss_add_node()

    //initialize Q and R based on first input character.
    set* actions = srnglr_get_merged_table_actions(0, src[0]);
    for (size_t i = 0; i < set_size(actions); i++)
    {
        obj* action = actions->entries[i].item;
        if (action->type == Push_t)
        {
            //add (v0, k) to Q. v0 is represented as (0,0) i.e. (nodes_idx, node_idx)
            uint64_t k = *(uint64_t*)action->data;
            tuple* t = new_tuple(3, 0, 0, k);
            vect_enqueue(srnglr_Q, new_tuple_obj(t));
        }
        else if (action->type == Reduction_t)
        {
            //if reduction is length 0
            reduction* r = action->data;
            if (r->length == 0)
            {
                //add (v0, X:i, 0, f, ϵ) to R. v0 is represented as (0,0), i.e. (nodes_idx, node_idx), ϵ is SPPF node at index 0
                tuple* t = new_tuple(7, 0, 0, r->head_idx, r->production_idx, 0, r->nullable_idx, 0);
                vect_enqueue(srnglr_R, new_tuple_obj(t));
            }
        }
    }

    //merged table creates a new allocation that needs to be freed
    set_free(actions);

    size_t d = ustring_len(src);

    for (size_t i = 0; i <= d; i++)
    {
        if (set_size(gss_get_nodes_set(GSS, i)) == 0) { break; }
        while (vect_size(srnglr_R) > 0)
        {
            srnglr_reducer(i, src);
        }
        srnglr_shifter(i, src);
    }

    //check if an accept state is in the final set Ud
    set* Ud = gss_get_nodes_set(GSS, d);
    for (size_t i = 0; i < set_size(Ud); i++)
    {
        uint64_t* state = Ud->entries[i].item->data;
        if (srnglr_is_accepting_state(*state))
        {
            return true;
        }
    }

    return false;
}


/**
 * Reducer subroutine from rnglr parsing process
 */
void srnglr_reducer(size_t i, uint32_t* src)
{
    //remove and unpack a 5-tuple from R
    tuple* t = obj_free_keep_inner(vect_dequeue(srnglr_R), UIntNTuple_t);
    gss_idx v_idx = gss_idx_struct(t->items[0], t->items[1]);   //index of the GSS node the reduction applies to
    uint64_t head_idx = t->items[2];                            //index of the symbol being reduced
    uint64_t body_idx = t->items[3];                            //future use (SRNGLR filters?). index of the production for this reduction
    uint64_t length = t->items[4];                              //length of the reduction
    uint64_t nullable_idx = t->items[5];                        //index of the sppf node representing any right-nulled terms for this reduction
    uint64_t y_idx = t->items[6];                               //index of the sppf node for the first edge in the gss path for this reduction
    tuple_free(t);
    
    //collect a list of all reachable nodes from v
    vect* reachable = gss_get_reachable(GSS, &v_idx, length > 0 ? length - 1 : 0); //TODO->replace with next line
    vect* paths = gss_get_all_paths(GSS, &v_idx, length > 0 ? length - 1 : 0);

    for (size_t j = 0; j < vect_size(reachable); j++)
    {
        gss_idx* u_idx = vect_get(reachable, j)->data;
        uint64_t state_idx = gss_get_node_state(GSS, u_idx->nodes_idx, u_idx->node_idx);
        uint64_t* l = srnglr_get_table_push(state_idx, head_idx);
        if (l == NULL) { continue; }
        
        gss_idx* w_idx = gss_get_node_with_label(GSS, i, *l);
        if (w_idx != NULL)
        {
            if (!gss_does_edge_exist(GSS, w_idx, u_idx)) //TODO->if the edge exists, still need to add the reduciton tuple, but need to grab existing z.
            {
                gss_add_edge(GSS, w_idx, u_idx); //TODO->should probably return the SPPF node z here...
                //e.g. `sppf_node* z = gss_add_edge(GSS, SPPF, w_idx, u_idx);`
                if (length != 0)
                {
                    set* actions = srnglr_get_merged_table_actions(*l, src[i]);
                    for (size_t j = 0; j < set_size(actions); j++)
                    {
                        obj* action = set_get_at_index(actions, j);
                        if (action->type == Reduction_t)
                        {
                            reduction* r = action->data;
                            if (r->length > 0)
                            {
                                tuple* t = new_tuple(7, u_idx->nodes_idx, u_idx->node_idx, r->head_idx, r->production_idx, r->length, r->nullable_idx, /*for now skip sppf node z to add here*/0);
                                vect_append(srnglr_R, new_tuple_obj(t));
                            }
                        }
                    }
                    set_free(actions);
                }
            }
        }
        else
        {
            //create a new node, and edge from w back to u
            w_idx = gss_add_node(GSS, i, *l);
            gss_add_edge(GSS, w_idx, u_idx); //TODO->this should also generate SPPF node z
            //e.g. `sppf_node* z = gss_add_edge(GSS, SPPF, w_idx, u_idx);`
            set* actions = srnglr_get_merged_table_actions(*l, src[i]);
            for (size_t j = 0; j < set_size(actions); j++)
            {
                obj* action = set_get_at_index(actions, j);
                if (action->type == Push_t)
                {
                    uint64_t* h = action->data;
                    tuple* t = new_tuple(3, w_idx->nodes_idx, w_idx->node_idx, *h);
                    vect_append(srnglr_Q, new_tuple_obj(t));
                }
                else if (action->type == Reduction_t)
                {
                    reduction* r = action->data;
                    if (r->length == 0)
                    {
                        tuple* t = new_tuple(7, w_idx->nodes_idx, w_idx->node_idx, r->head_idx, r->production_idx, 0, r->nullable_idx, 0);
                        vect_append(srnglr_R, new_tuple_obj(t));
                    }
                    else if (length != 0)
                    {
                        tuple* t = new_tuple(7, u_idx->nodes_idx, u_idx->node_idx, r->head_idx, r->production_idx, r->length, /*z_idx would go here*/0);
                        vect_append(srnglr_R, new_tuple_obj(t));
                    }
                }
            }
            set_free(actions); 
        }
        gss_idx_free(w_idx);
    }
    vect_free(reachable); //TODO->replace with next line
    vect_free(paths);
}


/**
 * Shifter subroutien from rnglr parsing process
 */
void srnglr_shifter(size_t i, uint32_t* src)
{
    if (src[i] != 0) //i.e. we're not on the last input
    {
        vect* Qp = new_vect(); //Q' for intermediate push
        
        //create the leaf node and insert into the SPPF structure
        sppf_node* z = new_sppf_leaf_node(i);
        obj* z_obj = new_sppf_node_obj(z);
        uint64_t z_idx = set_add_return_index(SPPF->nodes, z_obj);

        while (vect_size(srnglr_Q) > 0)
        {            
            //remove and unpack a tuple from Q
            tuple* t = obj_free_keep_inner(vect_dequeue(srnglr_Q), UIntNTuple_t);
            gss_idx v_idx = gss_idx_struct(t->items[0], t->items[1]);
            uint64_t k = t->items[2];
            tuple_free(t);
            
            gss_idx* w_idx = gss_get_node_with_label(GSS, i+1, k);
            if (w_idx != NULL)
            {
                //create an edge from w to v
                gss_add_edge(GSS, w_idx, &v_idx); //TODO->need to map from edge to sppf node index
                //e.g. `gss_add_edge(GSS, w_idx, &v_idx, z_idx);`
                set* actions = srnglr_get_merged_table_actions(k, src[i+1]);
                for (size_t j = 0; j < set_size(actions); j++)
                {
                    obj* action = set_get_at_index(actions, j);
                    if (action->type == Reduction_t)
                    {
                        reduction* r = action->data;
                        if (r->length != 0)
                        {
                            tuple* t = new_tuple(7, v_idx.nodes_idx, v_idx.node_idx, r->head_idx, r->production_idx, r->length, r->nullable_idx, z_idx);
                            vect_append(srnglr_R, new_tuple_obj(t));
                        }
                    }
                }
                set_free(actions);
            }
            else
            {
                //create a node w in Ui with label k, and edge from w to v
                w_idx = gss_add_node(GSS, i+1, k);
                gss_add_edge(GSS, w_idx, &v_idx);
                // uint64_t* h = srnglr_get_table_push()
                set* actions = srnglr_get_merged_table_actions(k, src[i+1]);
                // printf("actions for (%"PRIu64", ", k); put_unicode(src[i+1]); printf("): "); set_str(actions); printf("\n");
                for (size_t j = 0; j < set_size(actions); j++)
                {
                    obj* action = set_get_at_index(actions, j);
                    if (action->type == Push_t)
                    {
                        uint64_t h = *(uint64_t*)action->data;
                        tuple* t = new_tuple(3, w_idx->nodes_idx, w_idx->node_idx, h);
                        vect_append(Qp, new_tuple_obj(t));
                    }
                    else if (action->type == Reduction_t)
                    {
                        reduction* r = action->data;
                        if (r->length != 0)
                        {
                            tuple* t = new_tuple(7, v_idx.nodes_idx, v_idx.node_idx, r->head_idx, r->production_idx, r->length, r->nullable_idx, z_idx);
                            vect_append(srnglr_R, new_tuple_obj(t));
                        }
                        else
                        {
                            tuple* t = new_tuple(7, w_idx->nodes_idx, w_idx->node_idx, r->head_idx, r->production_idx, 0, r->nullable_idx, 0);
                            vect_append(srnglr_R, new_tuple_obj(t));
                        }
                    }
                }
                set_free(actions);
            }
            gss_idx_free(w_idx);
        }
        //copy Q' into Q
        while (vect_size(Qp) > 0) { vect_append(srnglr_Q, vect_dequeue(Qp)); }
        vect_free(Qp);
    }
}


/**
 * Add_children subroutine from rnglr parsing process.
 * z should be an inner node.
 */
void srnglr_add_children(uint64_t z_idx, vect* path, uint64_t nullable_idx)
{
    if (nullable_idx != 0)
    {
        vect_append(path, new_uint_obj(nullable_idx));
    }
    obj* path_obj = new_vect_obj(path);
    uint64_t new_children_idx = set_add_return_index(SPPF->children, path_obj);
    
    obj z_idx_obj = obj_struct(UInteger_t, &z_idx);

    //get the children for this node
    obj* children = dict_get(SPPF->edges, &z_idx_obj);
    if (children->type == UInteger_t)  //non-packed node
    {
        uint64_t* children_idx = children->data;
        
        //if the child to add is not the current children index, create a packed node with both indices
        if (*children_idx != new_children_idx)
        {
            uint64_t entry_idx = dict_get_entries_index(SPPF->edges, &z_idx_obj);
            set* children_set = new_set();
            set_add(children_set, children);
            set_add(children_set, new_uint_obj(new_children_idx));
            SPPF->edges->entries[entry_idx].value = new_set_obj(children_set);
        }
    }
    else //type == Set_t //packed node
    {
        //insert the new index into the list of children lists (set handle duplicates)
        set* children_set = children->data;
        set_add(children_set, new_uint_obj(new_children_idx));
    }
}


/**
 * Print out the itemsets generated for this grammar
 */
void srnglr_print_itemsets()
{
    for (size_t i = 0; i < set_size(srnglr_itemsets); i++)
    {
        set* itemset = srnglr_itemsets->entries[i].item->data;
        printf("I%zu:\n", i);
        for (size_t j = 0; j < set_size(itemset); j++)
        {
            metaitem* item = itemset->entries[j].item->data;
            printf("  "); metaitem_str(item); printf("\n");
        }
        printf("\n");
    }
}


/**
 * Print out the first sets generated for each head in the grammar.
 */
void srnglr_print_firsts()
{
    for (size_t symbol_idx = 0; symbol_idx < vect_size(srnglr_symbol_firsts); symbol_idx++)
    {
        // if (metaparser_is_symbol_terminal(symbol_idx)) { continue; }
        obj_str(metaparser_get_symbol(symbol_idx));
        printf(" -> ");
        obj_str(vect_get(srnglr_symbol_firsts, symbol_idx));
        printf("\n");
    }
    printf("\n");
}


/**
 * Print out the srnglr table as a properly formatted table.
 */
void srnglr_print_table()
{
    set* symbols = metaparser_get_symbols();

    //compute number of rows in table. this doesn't include the header row
    size_t num_rows = set_size(srnglr_itemsets);

    //compute the number of columns in the table
    size_t num_columns = 0;
    bool* symbols_used = calloc(set_size(symbols), sizeof(bool)); //track whether we've seen a given symbol
    for (size_t i = 0; i < dict_size(srnglr_table); i++)
    {
        gotokey* key = srnglr_table->entries[i].key->data;
        
        //check if we haven't seen this symbol yet
        if (!symbols_used[key->symbol_idx])
        {
            symbols_used[key->symbol_idx] = true;
            num_columns++;
        }
    }

    //allocate grid to keep track of the print width of each cell (including headers) in the table
    uint64_t* cell_widths = calloc((num_rows + 1) * (num_columns + 1), sizeof(uint64_t));
    
    //check the widths of each column header
    {
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            obj* symbol = metaparser_get_symbol(symbol_idx);
            uint64_t width = symbol->type == CharSet_t ? charset_strlen(symbol->data) : ustring_len(symbol->data);

            //save the width into the widths matrix
            cell_widths[column_idx + 1] = width;

            column_idx++;
        }
    }

    //check the widths of each state number
    for (uint64_t state_idx = 0; state_idx < num_rows; state_idx++)
    {
        cell_widths[(num_columns + 1) * (state_idx + 1)] = snprintf("", 0, "%"PRIu64, state_idx);
    }

    //check the widths of each cell in that column
    {
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            for (size_t state_idx = 0; state_idx < set_size(srnglr_itemsets); state_idx++)
            {
                //get the set of actions for this coordinate in the table
                gotokey key = gotokey_struct(state_idx, symbol_idx);
                obj key_obj = obj_struct(GotoKey_t, &key);
                if (dict_contains(srnglr_table, &key_obj))
                {
                    set* actions = dict_get(srnglr_table, &key_obj)->data;
                    uint64_t width = 0;
                    for (size_t i = 0; i < set_size(actions); i++)
                    {
                        obj* action = actions->entries[i].item;
                        if (action->type == Push_t){ width += push_strlen(*(uint64_t*)action->data); }
                        else if (action->type == Reduction_t) { width += reduction_strlen(action->data); }
                        else if (action->type == Accept_t) { width += accept_strlen(); }
                        else { printf("ERROR: unknown action object type %u\n", action->type); }

                        if (i < set_size(actions) - 1) { width += 2; } //space for ", " between elements
                    }

                    // if (column_widths[column_idx] < width) { column_widths[column_idx] = width; }
                    cell_widths[(num_columns + 1) * (state_idx + 1) + column_idx + 1] = width;
                }
            }
            column_idx++;
        }
    }


    //using the cell widths, compute the max column widths
    uint64_t* column_widths = calloc((num_columns + 1), sizeof(uint64_t));
    for (size_t i = 0; i < num_rows + 1; i++)
    {
        for (size_t j = 0; j < num_columns + 1; j++)
        {
            if (column_widths[j] < cell_widths[(num_columns + 1) * i + j])
            {
                column_widths[j] = cell_widths[(num_columns + 1) * i + j];
            } 
        }
    }


    //print the table header
    for (int i = 0; i < column_widths[0] + 2; i++) { putchar(' '); }
    printf("│");    
    {
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            obj* symbol = metaparser_get_symbol(symbol_idx);
            putchar(' '); 
            obj_str(symbol);
            putchar(' ');

            uint64_t remaining = column_widths[1 + column_idx] - cell_widths[1 + column_idx];
            for (int i = 0; i < remaining; i++) { putchar(' '); }

            column_idx++;
        }
    }
    printf("\n");

    //print the divider row
    for (int i = 0; i < column_widths[0] + 2; i++) { printf("─"); }
    printf("┼");
    for (size_t j = 1; j < num_columns + 1; j++)
        for (int i = 0; i < column_widths[j] + 2; i++)
            printf("─"); 
    
    printf("\n");
    
    //print the body of the table    
    for (size_t state_idx = 0; state_idx < set_size(srnglr_itemsets); state_idx++)
    {
        //print out the state number
        putchar(' ');
        printf("%zu", state_idx);
        putchar(' ');
        uint64_t remaining = column_widths[0] - cell_widths[(num_columns + 1) * (state_idx + 1)];
        for (int i = 0; i < remaining; i++) { putchar(' '); }
        printf("│");

        //print out the contents of each column in this row
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            putchar(' ');

            //get the set of actions for this coordinate in the table
            gotokey key = gotokey_struct(state_idx, symbol_idx);
            obj key_obj = obj_struct(GotoKey_t, &key);
            if (dict_contains(srnglr_table, &key_obj))
            {
                set* actions = dict_get(srnglr_table, &key_obj)->data;                
                
                for (size_t i = 0; i < set_size(actions); i++)
                {
                    obj* action = actions->entries[i].item;
                    obj_str(action);
                    if (i < set_size(actions) - 1) { printf(", "); }
                }
            }

            putchar(' ');

            uint64_t remaining = column_widths[column_idx + 1] - cell_widths[(num_columns + 1) * (state_idx + 1) + column_idx + 1];
            for (int i = 0; i < remaining; i++) { putchar(' '); }

            column_idx++;
        }
        printf("\n");
    }
    printf("\n");


    free(symbols_used);
    free(cell_widths);
    free(column_widths);
}

void srnglr_print_gss()
{
    gss_str(GSS);
}

void srnglr_print_sppf()
{
    sppf_repr(SPPF);
}


#endif