#ifndef AST_C
#define AST_C

// #include <stdlib.h>
#include <stdio.h>

#include "ast.h"
#include "bsr.h"
#include "metaparser.h"
#include "ustring.h"

/**
 * Create a new AST node representing a terminal character (i.e. a leaf node)
 */
ast_node* new_char_ast_node(uint32_t term)
{
    ast_node* node = malloc(sizeof(ast_node));
    *node = new_char_ast_node_struct(term);
    return node;
}

/**
 * Create a struct for an AST node representing a terminal character
 */
inline ast_node new_char_ast_node_struct(uint32_t term) { return (ast_node){.type = char_ast, .term = term}; }

/**
 * Create a new AST node representing a non-terminal character (i.e. an inner node with children)
 */
ast_node* new_inner_ast_node(uint64_t head_idx, uint64_t production_idx)
{
    ast_node* node = malloc(sizeof(ast_node));
    *node = (ast_node){
        .type = inner_ast,
        .head_idx = head_idx,
        .production_idx = production_idx,
        .length = 0,
        .children = NULL,
    };
    return node;
}

/**
 * Recursively free an AST node and its children. If root is true, then the pointer to the node itself is also
 * freed. False is for nodes that are children of other nodes (i.e. they don't own their own space).
 */
void ast_node_free(ast_node* node, bool root)
{
    if (node->type == inner_ast && node->children != NULL)
    {
        for (uint64_t i = 0; i < node->length; i++) { ast_node_free(&node->children[i], false); }
        free(node->children);
    }
    else if (node->type == str_ast && node->string != NULL)
    {
        free(node->string);
    }
    if (root) { free(node); }
}

/**
 * Allocate space for the specified number of children in the given node.
 */
void ast_node_allocate_children(ast_node* node, uint64_t num_children)
{
    // error if the node already has children
    if (node->children != NULL)
    {
        printf("ERROR: Cannot allocate children to a node that already has children");
        exit(1);
    }

    // allocate space for the children
    node->children = malloc(sizeof(ast_node) * num_children);
    node->length = num_children;

    // initialize the children to undefined_ast
    for (uint64_t i = 0; i < num_children; i++) { node->children[i] = (ast_node){.type = undefined_ast}; }
}

/**
 * Attempt to construct a full AST from the given BSR. When ambiguities are encountered, attempt to resolve them by
 * using ambiguity resolution (e.g. filters from the grammer, as well as post parse disambiguation, e.g. type info).
 */
ast_node* ast_from_root(dict* Y, uint32_t* I, uint64_t head_idx, uint64_t length)
{
    // first, attempt to get the start BSR node (applying disambiguation rules if possible)
    uint64_t j, production_idx;
    if (!bsr_get_root_split(Y, head_idx, length, &production_idx, &j)) { return NULL; }

    // create the root of the AST
    ast_node* root = new_inner_ast_node(head_idx, production_idx);

    // recursively construct the AST
    bool success = ast_attach_children(root, 0, j, length, Y, I);

    // if the construction failed, free the root and return NULL
    if (!success)
    {
        ast_node_free(root, true);
        return NULL;
    }

    // reduce the AST
    ast_reduce(root);

    return root;
}

/**
 * Recursively attach children to the given AST node, constructed from the given BSR forest.
 */
bool ast_attach_children(ast_node* node, uint64_t i, uint64_t j, uint64_t k, dict* Y, uint32_t* I)
{
    // get the production string for the current node
    vect* body = metaparser_get_production_body(node->head_idx, node->production_idx);

    // number of children of the AST node is the length of the production body
    uint64_t num_children = vect_size(body);

    // allocate space for the children
    ast_node_allocate_children(node, num_children);

    // substring to keep track of progress in the traversal of the bsr for this production
    slice string = slice_struct(body, 0, num_children);

    // save i, j, k for later passes?
    uint64_t saved_i = i;
    uint64_t saved_j = j;
    uint64_t saved_k = k;
    while (slice_size(&string) > 0)
    {
        // split the last element off from the string
        printf("slice size: %lu\n", slice_size(&string));
        obj* right = slice_get(&string, slice_size(&string) - 1);
        string = slice_struct(body, 0, slice_size(&string) - 1);
        // printf("splitting string: ");
        // slice_str(&string);
        // printf(" | ");
        // obj_str(right);
        // printf("\n");

        // determine if the right symbol is a terminal or non-terminal
        uint64_t* symbol_idx = right->data;
        obj* symbol = metaparser_get_symbol(*symbol_idx);
        if (symbol->type == CharSet_t)
        {
            // terminal
            node->children[slice_size(&string)] = new_char_ast_node_struct(I[k - 1]);
        }
        else
        {
            // nonterminal
            printf("TODO: handle nonterminal symbols\n");
            // find the bsr associated with the symbol
            set* bodies = metaparser_get_production_bodies(*symbol_idx);
            for (uint64_t prod_idx = 0; prod_idx < set_size(bodies); prod_idx++)
            {
                bsr_head head = new_prod_bsr_head_struct(*symbol_idx, prod_idx, i, k);
            }
        }
        // printf("right symbol: ");
        // obj_str(symbol);
        // printf("\n");

        // create the empty AST node for the right object
        // ast_node* child = ast_from_right(right, j, k, Y, I);

        // compute the next i, j, k values for the next item
        if (slice_size(&string) > 0)
        {
            // get the next bsr node
            bsr_head visitor = new_str_bsr_head_struct(&string, i, j);
            printf("TODO: computing next i, j, k\n");
            exit(1);
        }
    }

    // start slotting child nodes into the children array, from the end since BSRs go from end to start
    // if there is an ambiguity, then return false. If there is no ambiguity, then recursively call this function,
    // and return the result of the recursive call.
    // TODO: eventually should probably just iterate over all possible splits, and disambiguate when there's
    // multiple

    //
    // checking each symbol in the production for ambiguities, fill in each of the children

    // continue this process recursively

    // printf("TODO: implement attach_children\n");
    return true;
}

/**
 * Recursively reduce the given AST by combining term/char nodes into string nodes according to grammar's capture rules
 */
void ast_reduce(ast_node* node)
{
    // TODO
}

/**
 * Recursively print out the given AST
 */
void ast_node_str(ast_node* node) { ast_node_str_inner(node, 0); }

/**
 * Helper function for printing out the given AST. Depth specifies how many indents to print before the node itself.
 */
void ast_node_str_inner(ast_node* node, uint64_t depth)
{
    // print the number of tabs before the node
    uint64_t tabsize = 2;
    for (uint64_t i = 0; i < depth * tabsize; i++) { fputc(' ', stdout); }

    // print the node itself
    switch (node->type)
    {
        case undefined_ast: printf("undefined\n"); break;
        case char_ast:
            put_unicode(node->term);
            fputc('\n', stdout);
            break;
        case str_ast:
            ustring_str(node->string);
            fputc('\n', stdout);
            break;
        case inner_ast:
            // print the production name and body
            metaparser_production_str(node->head_idx, node->production_idx);
            fputc('\n', stdout);
            for (uint64_t i = 0; i < node->length; i++) { ast_node_str_inner(&node->children[i], depth + 1); }
            break;
    }
}

#endif