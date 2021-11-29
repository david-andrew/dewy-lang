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
    else
    {
        printf("type: prod_bsr, head_idx: %" PRIu64 ", production_idx: %" PRIu64, b->head_idx, b->production_idx);
    }
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
        obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = &head});
        if (j_set_obj != NULL)
        {
            set* j_set = j_set_obj->data;
            for (size_t k = 0; k < set_size(j_set); k++)
            {
                // printf(!first ? ", " : "");
                // first = false;
                uint64_t* j = set_get_at_index(j_set, k)->data;
                bsr_tree_str_inner(Y, I, &head, *j, 0);

                // for now skip all alternative j splits
                break; // TODO->remove this!!!
                // basically want a function for determining if a node is a packed node, which would count the number of
                // different j and j-sets via these two for loops (for prod in productions, for j in j-sets)
            }
        }
    }
}

void indent_str(uint64_t i, const char* str)
{
    for (size_t j = 0; j < i; j++) fputs(str, stdout);
}

const char indent[] = "  ";

/**
 * Helper function for printing out a bsr forest
 */
void bsr_tree_str_inner(dict* Y, uint32_t* I, bsr_head* head, uint64_t j, uint64_t level)
{
    // print the given head at the current indentation level
    indent_str(level, indent);
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
        bsr_tree_str_inner_substr(Y, I, &left_substring, head->i, j, level + 1);
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
 * Helper function for printing out a BSR tree, given a left split substring. substring is expected to have length > 1
 */
void bsr_tree_str_inner_substr(dict* Y, uint32_t* I, slice* substring, uint64_t i, uint64_t k, uint64_t level)
{
    // create a substring BSR head
    bsr_head head = new_str_bsr_head_struct(substring, i, k);
    obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = &head});
    if (j_set_obj != NULL)
    {
        for (size_t j_idx = 0; j_idx < set_size(j_set_obj->data); j_idx++)
        {
            // print out the BSR head
            uint64_t* j = set_get_at_index(j_set_obj->data, j_idx)->data;
            bsr_tree_str_inner(Y, I, &head, *j, level);

            // for now skip all alternative j splits
            break; // TODO->remove this!!!
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
        indent_str(level, indent);
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
            obj* j_set_obj = dict_get(Y, &(obj){.type = BSRHead_t, .data = &head});
            if (j_set_obj != NULL)
            {
                for (size_t j_idx = 0; j_idx < set_size(j_set_obj->data); j_idx++)
                {
                    // print out the BSR head
                    uint64_t* j = set_get_at_index(j_set_obj->data, j_idx)->data;
                    bsr_tree_str_inner(Y, I, &head, *j, level);

                    // for now skip all alternative j splits
                    break; // TODO->remove this!!!
                }
            }
        }
    }
}

/**
 * helper function for printing out a leaf node in the bsr forest
 */
// void bsr_tree_str_leaf(charset* terminal, uint64_t j, uint64_t level) {}

// /**
//  * Get the left and right children of a given BSR node. Results are stored in the pointers left and right.
//  * left or right may be set to NULL if no child is found.
//  */
// void bsr_get_children(dict* Y, bsr_head* head, uint64_t j, bsr_head** left, bsr_head** right)
// {
//     if (head->type == prod_bsr)
//     {
//         vect* body = metaparser_get_production_body(head->head_idx, head->production_idx);
//         if (vect_size(body) == 0)
//         {
//             *left = NULL;
//             *right = NULL;
//             return;
//         }
//         else if (vect_size(body) == 1)
//         {
//             uint64_t* symbol_idx = vect_get(body, 0)->data;
//             *right = NULL;

//             // TODO. could be multiple children, one for each production body of the symbol_idx.
//             // consider some method for either returning all children, or specifying which child to grab...

//             return;
//         }

//         // general case

//         // get the left child
//         slice left_substring = (slice){.v = body, .start = 0, .stop = vect_size(body) - 1, .lookahead = NULL},
//               right_substring = (slice){.v = body, .start = 0, .stop = vect_size(body) - 1, .lookahead = NULL};
//         if (slice_size(&left_substring) > 1) {}

//         // create left and right substrings of body, split at j
//     }
//     else
//     {
//         //
//     }
// }

#endif