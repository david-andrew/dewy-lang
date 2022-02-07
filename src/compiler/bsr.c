#ifndef BSR_C
#define BSR_C

#include <inttypes.h>
#include <stdio.h>

#include "bsr.h"
#include "metaparser.h"
#include "parser.h"
#include "ustring.h"
#include "utilities.h"

/**
 * Create a new BSR head containing a production substring
 */
bsr_head* new_str_bsr_head(slice* substring, uint64_t i, uint64_t k)
{
    bsr_head* b = malloc(sizeof(bsr_head));
    *b = new_str_bsr_head_struct(substring, i, k);
    return b;
}

/**
 * Return the struct for a BSR head containing a production substring
 */
inline bsr_head new_str_bsr_head_struct(slice* substring, uint64_t i, uint64_t k)
{
    return (bsr_head){.type = str_bsr, .substring = *substring, .i = i, .k = k};
}

/**
 * Create a new BSR head containing a whole production
 */
bsr_head* new_prod_bsr(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t k)
{
    bsr_head* b = malloc(sizeof(bsr_head));
    *b = new_prod_bsr_head_struct(head_idx, production_idx, i, k);
    return b;
}

/**
 * Return the struct for a BSR head containing a whole production
 */
bsr_head new_prod_bsr_head_struct(uint64_t head_idx, uint64_t production_idx, uint64_t i, uint64_t k)
{
    return (bsr_head){.type = prod_bsr, .head_idx = head_idx, .production_idx = production_idx, .i = i, .k = k};
}

/**
 * Return a new copy of a BSR head
 */
bsr_head* bsr_head_copy(bsr_head* b)
{
    bsr_head* b_copy = malloc(sizeof(bsr_head));
    *b_copy = *b;
    return b_copy;
}

/**
 * Return a BSR head wrapped in a new object
 */
obj* new_bsr_head_obj(bsr_head* b) { return new_obj(BSRHead_t, b); }

/**
 * Check if two BSR heads are equal
 */
bool bsr_head_equals(bsr_head* left, bsr_head* right)
{
    if (left->type != right->type) return false;
    if (left->i != right->i || left->k != right->k) return false;
    if (left->type == str_bsr) return slice_equals(&left->substring, &right->substring);
    else
        return left->head_idx == right->head_idx && left->production_idx == right->production_idx;
}

/**
 * Compute the hash of a BSR head
 */
uint64_t bsr_head_hash(bsr_head* b) { return b->type == str_bsr ? bsr_head_str_hash(b) : bsr_head_slot_hash(b); }

/**
 * Compute the hash of a str BSR head
 */
uint64_t bsr_head_str_hash(bsr_head* b)
{
    uint64_t seq[] = {b->type, slice_hash(&b->substring), b->i, b->k};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Compute the hash of a slot BSR head
 */
uint64_t bsr_head_slot_hash(bsr_head* b)
{
    uint64_t seq[] = {b->type, b->head_idx, b->production_idx, b->i, b->k};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Free a BSR head
 */
void bsr_head_free(bsr_head* b) { free(b); }

/**
 * Print out the BSR head
 */
void bsr_head_str(bsr_head* b)
{

    printf("(");
    if (b->type == prod_bsr) { metaparser_production_str(b->head_idx, b->production_idx); }
    else
    {
        if (slice_size(&b->substring) == 0) printf("ϵ");
        for (size_t i = 0; i < slice_size(&b->substring); i++)
        {
            if (i > 0) printf(" ");
            uint64_t* symbol_idx = slice_get(&b->substring, i)->data;
            obj_str(metaparser_get_symbol(*symbol_idx));
        }
    }
    printf(", %" PRIu64 ", j, %" PRIu64 ")", b->i, b->k);
}

/**
 * Print out the whole BSR node, given the head and the value j
 */
void bsr_str(bsr_head* b, uint64_t j)
{
    //(X ::= α, i, j, k) for type prod_bsr
    //(α, i, j, k) for type str_bsr
    printf("(");
    if (b->type == prod_bsr) { metaparser_production_str(b->head_idx, b->production_idx); }
    else
    {
        if (slice_size(&b->substring) == 0) printf("ϵ");
        for (size_t i = 0; i < slice_size(&b->substring); i++)
        {
            if (i > 0) printf(" ");
            uint64_t* symbol_idx = slice_get(&b->substring, i)->data;
            obj_str(metaparser_get_symbol(*symbol_idx));
        }
    }
    printf(", %" PRIu64 ", %" PRIu64 ", %" PRIu64 ")", b->i, j, b->k);
}

/**
 * Print out the internal representation of a BSR head
 */
void bsr_head_repr(bsr_head* b)
{
    printf("(");
    if (b->type == str_bsr)
    {
        printf("type: str_bsr, substring: ");
        slice_str(&b->substring);
    }
    else { printf("type: prod_bsr, head_idx: %" PRIu64 ", production_idx: %" PRIu64, b->head_idx, b->production_idx); }
    printf(", i: %" PRIu64 ", k: %" PRIu64 ")", b->i, b->k);
}

/**
 * Print out a BSR forest, starting from the root with the given head_idx
 */
void bsr_tree_str(dict* Y, uint32_t* I, uint64_t start_idx, uint64_t length)
{
    // get the production bodies of the start symbol
    size_t num_bodies = metaparser_get_num_production_bodies(start_idx);
    for (size_t i = 0; i < num_bodies; i++)
    {
        // get the j-set associated with the body
        bsr_head head = new_prod_bsr_head_struct(start_idx, i, 0, length);
        bsr_tree_str_inner_head(Y, I, &head, 0);
    }
}

/**
 * Helper function for printing out a bsr forest
 */
void bsr_tree_str_inner(dict* Y, uint32_t* I, bsr_head* head, uint64_t j, uint64_t level)
{
    // print the given head at the current indentation level
    put_tabs(level);
    bsr_str(head, j);
    printf("\n");

    // split for printing left and right children. If production body is empty, then there are no children
    slice body;
    if (head->type == prod_bsr)
    {
        vect* prod_body = metaparser_get_production_body(head->head_idx, head->production_idx);
        body = slice_struct(prod_body, 0, vect_size(prod_body));
    }
    else // type == str_bsr
    {
        body = head->substring;
    }
    if (slice_size(&body) == 0) return;

    // handle left branch of the tree
    slice left_substring = slice_slice_struct(&body, 0, slice_size(&body) - 1);
    if (slice_size(&left_substring) > 1)
    {
        // do a full substring print of the left child
        // bsr_tree_str_inner_substr(Y, I, &left_substring, head->i, j, level + 1);
        bsr_head left_head = new_str_bsr_head_struct(&left_substring, head->i, j);
        bsr_tree_str_inner_head(Y, I, &left_head, level + 1);
    }
    else if (slice_size(&left_substring) == 1)
    {
        // print the left child as a single symbol
        uint64_t* left_symbol_idx = slice_get(&left_substring, 0)->data;
        bsr_tree_str_inner_symbol(Y, I, *left_symbol_idx, head->i, j, level + 1);
    }
    // otherwise nothing to print for left child

    // handle right branch of the tree
    uint64_t* right_symbol_idx = slice_get(&body, slice_size(&body) - 1)->data;
    bsr_tree_str_inner_symbol(Y, I, *right_symbol_idx, j, head->k, level + 1);
}

/**
 * Helper function for printing out a BSR tree.
 * Search the BSR dict for the given head, and any assocaited j-sets, and print at the given level.
 */
void bsr_tree_str_inner_head(dict* Y, uint32_t* I, bsr_head* head, uint64_t level)
{
    obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = head});
    if (j_set_obj != NULL)
    {
        set* j_set = j_set_obj->data;
        for (size_t k = 0; k < set_size(j_set); k++)
        {
            uint64_t* j = set_get_at_index(j_set, k)->data;
            bsr_tree_str_inner(Y, I, head, *j, level);
        }
    }
}

/**
 * Helper function for printing out a BSR tree, given a left or right split symbol
 */
void bsr_tree_str_inner_symbol(dict* Y, uint32_t* I, uint64_t symbol_idx, uint64_t i, uint64_t k, uint64_t level)
{
    // check if the symbol is terminal or nonterminal
    obj* symbol = metaparser_get_symbol(symbol_idx);
    if (symbol->type == CharSet_t)
    {
        // print out the terminal at the location
        put_tabs(level);
        // printf("\"");
        put_unicode(I[i]); // TODO->maybe print the charset with the input character
        // printf(" from ");
        // charset_str(symbol->data);
        printf("\n");
    }
    else
    {
        // find the BSR associated with this symbol
        set* bodies = metaparser_get_production_bodies(symbol_idx);
        for (size_t prod_idx = 0; prod_idx < set_size(bodies); prod_idx++)
        {
            // check if there is a BSR head associated with this production
            bsr_head head = new_prod_bsr_head_struct(symbol_idx, prod_idx, i, k);
            bsr_tree_str_inner_head(Y, I, &head, level);
        }
    }
}

/**
 * Check if the root BSR has multiple splits, indicating that it is ambiguous.
 * if production_idx and j are not NULL, then return the production and j value for non-ambiguous split
 */
bool bsr_root_has_multiple_splits(dict* Y, uint64_t head_idx, uint64_t length, uint64_t* production_idx, uint64_t* j)
{
    // keep track of the number of splits encountered
    uint64_t num_splits = 0;

    // iterate over each possible production_idx for the given head
    set* bodies = metaparser_get_production_bodies(head_idx);
    for (size_t prod_idx = 0; prod_idx < set_size(bodies); prod_idx++)
    {
        // check if there is a BSR head associated with this production
        bsr_head head = new_prod_bsr_head_struct(head_idx, prod_idx, 0, length);
        obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = &head});
        if (j_set_obj != NULL)
        {
            set* j_set = j_set_obj->data;
            num_splits += set_size(j_set);
            if (num_splits == 1)
            {
                if (production_idx != NULL) *production_idx = prod_idx;
                if (j != NULL) *j = *(uint64_t*)set_get_at_index(j_set, 0)->data;
            }
        }
    }

    // return true if there is more than one split
    return num_splits > 1;
}

/**
 * Get the production, and j split for the root of the BSR. Attempt to disambiguate according to filters (and future
 * disambiguation steps, e.g. type checking, etc.),
 * returns whether a split was successfully found. False indicates either ambiguous, or no split found.
 */
bool bsr_get_root_split(dict* Y, uint64_t head_idx, uint64_t length, uint64_t* production_idx, uint64_t* j)
{
    // have we found a split yet
    bool first = true;

    // in case we need to disambiguate any production bodies. (Possibly NULL)
    dict* precedence_table = metaparser_get_precedence_table(head_idx);

    // iterate over each possible production_idx for the given head
    set* bodies = metaparser_get_production_bodies(head_idx);
    for (uint64_t next_production_idx = 0; next_production_idx < set_size(bodies); next_production_idx++)
    {
        // check if there is a BSR head associated with this production
        bsr_head head = new_prod_bsr_head_struct(head_idx, next_production_idx, 0, length);
        obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = &head});
        if (j_set_obj == NULL) continue;
        set* j_set = j_set_obj->data;
        for (uint64_t j_idx = 0; j_idx < set_size(j_set); j_idx++)
        {
            uint64_t next_j = *(uint64_t*)set_get_at_index(j_set, j_idx)->data;
            if (first)
            {
                *production_idx = next_production_idx;
                *j = next_j;
                first = false;
            }
            else
            {
                // check the precedence filter for the current split vs the new split
                if (*production_idx != next_production_idx && precedence_table != NULL)
                {
                    uint64_t cur_rank = *(uint64_t*)dict_get_uint_key(precedence_table, *production_idx)->data;
                    uint64_t next_rank = *(uint64_t*)dict_get_uint_key(precedence_table, next_production_idx)->data;

                    // new split replaces current split. select rule with least precedence rank
                    if (next_rank < cur_rank)
                    {
                        *production_idx = next_production_idx;
                        *j = next_j;
                        continue;
                    }
                    // old split beats new candidate split
                    else if (next_rank > cur_rank)
                        continue;
                }

                // TODO->add more disambiguation steps here (e.g. type checking disambiguation, etc.)
                // if (disambiguation_step(...))
                // {
                //     // select the new split
                //     // continue;
                // }

                // failed to disambiguate
                printf("DEBUG: failed to disambiguate %lu from %lu\n", *production_idx, next_production_idx);
                return false;
            }
        }
    }

    // return whether a split was successfully found
    return !first;
}

/**
 * Check if the given BSR head has multiple j splits, indicating that it is ambiguous
 * if j is not NULL, then return the j value for non-ambiguous split
 */
bool bsr_head_has_multiple_splits(dict* Y, bsr_head* head, uint64_t* j)
{
    obj* j_set_obj = dict_get(Y, &(obj){BSRHead_t, head});
    if (j_set_obj == NULL)
    {
        // this probably shouldn't ever happen
        printf("WARNING: encountered non-existent J-set for bsr head: ");
        bsr_head_str(head);
        printf("\n");
        return false;
    }

    set* j_set = j_set_obj->data;
    if (set_size(j_set) == 1 && j != NULL) *j = *(uint64_t*)set_get_at_index(j_set, 0)->data;
    return set_size(j_set) > 1;
}

/**
 * Check if a whole BSR tree is ambiguous, starting from the root.
 */
bool bsr_has_ambiguities(dict* Y, uint64_t head_idx, uint64_t length, uint64_t* production_idx)
{
    uint64_t j;
    bool ambiguous = bsr_root_has_multiple_splits(Y, head_idx, length, production_idx, &j);

    if (ambiguous) { return true; }

    bsr_head head = new_prod_bsr_head_struct(head_idx, *production_idx, 0, length);
    return bsr_tree_is_ambiguous(Y, &head, j);
}

/**
 * recursively check BSR nodes for ambiguities
 */
bool bsr_tree_is_ambiguous(dict* Y, bsr_head* head, uint64_t j)
{
    // first check if any of the children have multiple splits, and then recursively check each child with this
    // function

    printf("TODO->need to handle recursive check for ambiguity in BSR tree\n");
    return false;

    // split for getting left and right children. If production body is empty, then there are no children
    slice body;
    if (head->type == prod_bsr)
    {
        vect* prod_body = metaparser_get_production_body(head->head_idx, head->production_idx);
        body = slice_struct(prod_body, 0, vect_size(prod_body));
    }
    else // type == str_bsr
    {
        body = head->substring;
    }
    if (slice_size(&body) == 0) return false;

    // handle left branch of the tree
    slice left_substring = slice_slice_struct(&body, 0, slice_size(&body) - 1);
    if (slice_size(&left_substring) > 1)
    {
        // do a full substring print of the left child
    }
}

// /**
//  * Check if the given BSR node is ambiguous (i.e. it or any of its children contain multiple j-sets)
//  */
// bool bsr_is_node_ambiguous(dict* Y, bsr_head* head, uint64_t j)
// {
//     // split for getting left and right children. If production body is empty, then there are no children
//     slice body;
//     if (head->type == prod_bsr)
//     {
//         vect* prod_body = metaparser_get_production_body(head->head_idx, head->production_idx);
//         body = slice_struct(prod_body, 0, vect_size(prod_body));
//     }
//     else // type == str_bsr
//     {
//         body = head->substring;
//     }
//     if (slice_size(&body) == 0) return;

//     // handle left branch of the tree
//     slice left_substring = slice_slice_struct(&body, 0, slice_size(&body) - 1);
//     if (slice_size(&left_substring) > 1)
//     {
//         // do a full substring print of the left child
//         bsr_head left_head = new_str_bsr_head_struct(&left_substring, head->i, j);
//         ///////////////////////////////////////////////RIGHT HERE///////////////////
//         // bsr_tree_str_inner_head(Y, I, &left_head, level + 1);
//     }
//     else if (slice_size(&left_substring) == 1)
//     {
//         // print the left child as a single symbol
//         uint64_t* left_symbol_idx = slice_get(&left_substring, 0)->data;
//         bsr_tree_str_inner_symbol(Y, I, *left_symbol_idx, head->i, j, level + 1);
//     }
//     // otherwise nothing to print for left child

//     // handle right branch of the tree
//     uint64_t* right_symbol_idx = slice_get(&body, slice_size(&body) - 1)->data;
//     bsr_tree_str_inner_symbol(Y, I, *right_symbol_idx, j, head->k, level + 1);

//     // // check if the head is ambiguous
//     // obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = head});
//     // if (j_set_obj != NULL)
//     // {
//     //     set* j_set = j_set_obj->data;
//     //     if (set_size(j_set) > 1) return true;
//     // }

//     // // check if the left or right child is ambiguous
//     // slice body;
//     // if (head->type == prod_bsr)
//     // {
//     //     vect* prod_body = metaparser_get_production_body(head->head_idx, head->production_idx);
//     //     body = slice_struct(prod_body, 0, vect_size(prod_body));
//     // }
//     // else // type == str_bsr
//     // {
//     //     body = head->substring;
//     // }
//     // if (slice_size(&body) == 0) return false;

//     // // handle left branch of the tree
//     // slice left_substring = slice_slice_struct(&body, 0, slice_size(&body) - 1);
//     // if (slice_size(&left_substring) > 1)
//     // {
//     //     // do a full substring print of the left child
//     //     // bsr_tree_str_inner_substr(Y, I, &left_substring, head->i, j, level + 1);
//     //     bsr_head left_head = new_str_bsr_head_struct(&left_substring, head->i, head->j);
//     //     if (bsr_is_node_ambiguous(Y, &left_head)) return true;
//     // }
//     // else if (slice_size(&left_substring) == 1)
//     // {
//     //     // print the left child as a single symbol
//     //     uint64_t* left_symbol_idx = slice_get(&left_substring, 0)->data;
//     //     bsr_head left_head = new_symbol_bsr_head_struct(*left_symbol_idx, head->i, head->j);
//     //     if (bsr_is_node_ambiguous(Y, &left_head)) return true;

//     //     // otherwise nothing to print for left child

//     //     // handle right branch of the tree
//     //     uint64_t* right_symbol_idx = slice_get(&body, slice_size(&body) - 1)->data;
//     //     bsr_head right_head = new_symbol_bsr_head_struct(*right_symbol_idx, head->j, head->k);
//     //     if (bsr_is_node_ambiguous(Y, &right_head)) return true;

//     //     // otherwise nothing to print for right child
//     // }
// }

// // TODO->need an extra function for splitting out children productions from a given BSR node.
// // this function should call it, passing in root_head
// /**
//  * Check if an entire BSR tree starting from the start symbol contains any ambiguous nodes
//  */
// bool bsr_is_tree_ambiguous(dict* Y, uint64_t start_idx, uint64_t length)
// {
//     // get the production bodies of the start symbol
//     size_t num_bodies = metaparser_get_num_production_bodies(start_idx);

//     // check if there are multiple root BSR nodes
//     uint64_t root_bsr_count = 0;
//     bsr_head root_bsr_head;
//     obj* root_j_set_obj;
//     for (size_t i = 0; i < num_bodies; i++)
//     {
//         // get the j-set associated with the body
//         bsr_head head = new_prod_bsr_head_struct(start_idx, i, 0, length);
//         obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = &head});
//         if (j_set_obj != NULL)
//         {
//             // update count
//             root_bsr_count++;

//             // save parameters in case there was only one root BSR node
//             root_j_set_obj = j_set_obj;
//             root_bsr_head = head;
//         }
//     }
//     if (root_bsr_count > 1) return true;

//     // check if the root BSR node is ambiguous
//     set* root_j_set = root_j_set_obj->data;
//     if (set_size(root_j_set) > 1) return true;

//     // check if any children of the root BSR node are ambiguous
//     for (size_t i = 0; i < set_size(root_j_set); i++)
//     {
//         uint64_t* j = set_get_at_index(root_j_set, i)->data;
//         if (bsr_is_node_ambiguous(Y, &root_bsr_head)) return true;
//     }

//     return false;

//     // obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = head});
//     // if (j_set_obj != NULL)
//     // {
//     //     set* j_set = j_set_obj->data;
//     //     for (size_t k = 0; k < set_size(j_set); k++)
//     //     {
//     //         uint64_t* j = set_get_at_index(j_set, k)->data;
//     //         bsr_tree_str_inner(Y, I, head, *j, level);

//     //         // for now skip all alternative j splits
//     //         // break; // TODO->remove this!!!
//     //         // basically want a function for determining if a node is a packed node, which would count the
//     number of
//     //         // different j and j-sets via these two for loops (for prod in productions, for j in j-sets)
//     //     }
//     // }

//     // get the j-set associated with the body
//     // bsr_head head = new_prod_bsr_head_struct(start_idx, i, 0, length);
//     // bsr_tree_str_inner_head(Y, I, &head, 0);

//     // set* j_set = j_set_obj->data;
//     // if (set_size(j_set) > 1) root_bsr_count++;
// }

#endif