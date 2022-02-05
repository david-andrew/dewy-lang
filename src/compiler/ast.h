#ifndef AST_H
#define AST_H

#include <stdbool.h>
#include <stdint.h>

#include "dictionary.h"

typedef enum
{
    undefined_ast,
    terminal_ast,
    nonterminal_ast
} ast_type;

typedef struct
{
    ast_type type;
    union
    {
        struct
        {
            uint64_t head_idx;
            // TBD if we also need the production index...
            uint64_t length;
            ast_node* children;
        };
        uint32_t terminal;
    };
} ast_node;

// ast_node ast_nonterminal_node_struct(uint64_t head_idx);
// ast_node ast_terminal_node_struct(uint32_t codepoint);
ast_node* new_terminal_ast_node(uint32_t terminal);
ast_node* new_nonterminal_ast_node(uint64_t head_idx);
void ast_node_free(ast_node* node, bool root);
void ast_node_allocate_children(ast_node* node, uint64_t num_children);
void ast_node_str(ast_node* node);
void ast_node_str_inner(ast_node* node, uint64_t depth);

// bool bsr_has_ambiguities(dict* Y, uint64_t head_idx, uint64_t length
ast_node* ast_from_root(dict* Y, uint64_t head_idx, uint64_t length);

#endif