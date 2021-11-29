#ifndef BSR_C
#define BSR_C

#include <inttypes.h>
#include <stdio.h>

#include "bsr.h"
#include "metaparser.h"
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
void bsr_tree_str(dict* Y, uint64_t start_idx, uint64_t length)
{
    // printf("RESULTS BSRs:\n");
    // printf("{");
    // bool first = true;

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
                bsr_tree_str_inner(&head, *j, 0);
            }
        }
    }
    // printf("}\n\n");
}

void indent_str(uint64_t i, const char* str)
{
    for (size_t j = 0; j < i; j++) puts(str);
}

/**
 * Helper function for printing out a bsr forest
 */
void bsr_tree_str_inner(bsr_head* head, uint64_t j, uint64_t level)
{
    const char indent[] = "  ";

    // print indentation for the current level
    indent_str(level, indent);

    // print the given head
    bsr_str(head, j);
    printf("\n");

    if (head->type == prod_bsr)
    {
        // print the production body left and right strings
        indent_str(level, indent);
        metaparser_production_str(head->head_idx, head->production_idx);
        printf("\n");

        vect* body = metaparser_get_production_body(head->head_idx, head->production_idx);

        indent_str(level, indent);
        metaparser_body_str(body);
        printf("\n");

        if (vect_size(body) == 0) { return; }

        // get the left split of the body
        slice left_substring = slice_struct(body, 0, vect_size(body) - 1);
    }

    // print the children of the given head
    // TODO
}

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