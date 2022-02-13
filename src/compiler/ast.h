#ifndef AST_H
#define AST_H

#include <stdbool.h>
#include <stdint.h>

#include "dictionary.h"

typedef enum
{
    undefined_ast,
    char_ast,
    str_ast,
    inner_ast
} ast_type;

typedef struct ast_node ast_node;
struct ast_node
{
    ast_type type;
    union
    {
        struct
        {
            uint64_t head_idx;
            uint64_t production_idx;
            uint64_t length; // number of children
            ast_node* children;
        };
        uint32_t term;
        uint32_t* string;
    };
};

// ast_node ast_nonterminal_node_struct(uint64_t head_idx);
// ast_node ast_terminal_node_struct(uint32_t codepoint);
ast_node* new_char_ast_node(uint32_t term);
// ast_node* new_str_ast_node(uint32_t* string);
ast_node* new_inner_ast_node(uint64_t head_idx, uint64_t production_idx);
void ast_node_free(ast_node* node, bool root);
void ast_node_allocate_children(ast_node* node, uint64_t num_children);
ast_node* ast_from_root(dict* Y, uint32_t* I, uint64_t head_idx, uint64_t length);
bool ast_attach_children(ast_node* node, uint64_t i, uint64_t j, uint64_t k, dict* Y, uint32_t* I);
void ast_reduce(ast_node* node);
void ast_node_str(ast_node* node);
void ast_node_str_inner(ast_node* node, uint64_t depth);

#endif