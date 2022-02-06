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
    *node = (ast_node){.type = char_ast, .term = term};
    return node;
}

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
    else if (node->type == str_ast && node->string != NULL) { free(node->string); }
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
    // first check if the root node is unambiguous (BSR checks all possible disambiguations)
    uint64_t j, production_idx;

    // SUPER HACKY, replace with bsr_get_root_split function below!
    bool ambiguous = bsr_root_has_multiple_splits(Y, head_idx, length, &production_idx, &j);
    // bool ambiguous = bsr_get_root_split(Y, head_idx, length, &production_idx, &j);

    if (ambiguous) { return NULL; }

    // create the root of the AST
    ast_node* root = new_inner_ast_node(head_idx, production_idx);

    // create space for the children of the root
    // ast_node_allocate_children(root, <length of the production>);

    // checking each symbol in the production for ambiguities, fill in each of the children

    // continue this process recursively

    return root;

    // bsr_head head = new_prod_bsr_head_struct(head_idx, *production_idx, 0, length);
    // return bsr_tree_is_ambiguous(Y, &head, j);
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