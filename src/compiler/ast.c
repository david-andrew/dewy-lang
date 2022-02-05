#ifndef AST_C
#define AST_C

// #include <stdlib.h>

#include "ast.h"
#include "bsr.h"

/**
 * Create a new AST node representing a terminal character (i.e. a leaf node)
 */
ast_node* new_terminal_ast_node(uint32_t terminal)
{
    ast_node* node = malloc(sizeof(ast_node));
    *node = (ast_node){.type = terminal_ast, .terminal = terminal};
    return node;
}

/**
 * Create a new AST node representing a non-terminal character (i.e. an inner node with children)
 */
ast_node* new_nonterminal_ast_node(uint64_t head_idx)
{
    ast_node* node = malloc(sizeof(ast_node));
    *node = (ast_node){.type = nonterminal_ast, .head_idx = head_idx, .length = 0, .children = NULL};
    return node;
}

/**
 * Recursively free an AST node and its children. If root is true, then the pointer to the node itself is also
 * freed. False is for nodes that are children of other nodes (i.e. they don't own their own space).
 */
void ast_node_free(ast_node* node, bool root)
{
    if (node->type == nonterminal_ast && node->children != NULL)
    {
        for (uint64_t i = 0; i < node->length; i++) { ast_node_free(&node->children[i], false); }
        free(node->children);
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
ast_node* ast_from_root(dict* Y, uint64_t head_idx, uint64_t length)
{
    // first check if the root node is unambiguous
    uint64_t j, production_idx;
    bool ambiguous = bsr_root_has_multiple_splits(Y, head_idx, length, &production_idx, &j);

    if (ambiguous) { return NULL; }

    // create the root of the AST
    ast_node* root = new_nonterminal_ast_node(head_idx);

    // create space for the children of the root
    // ast_node_allocate_children(root, <length of the production>);

    // checking each symbol in the production for ambiguities, fill in each of the children

    // continue this process recursively

    return root;

    // bsr_head head = new_prod_bsr_head_struct(head_idx, *production_idx, 0, length);
    // return bsr_tree_is_ambiguous(Y, &head, j);
}

#endif