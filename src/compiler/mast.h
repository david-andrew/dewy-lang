#ifndef MAST_H
#define MAST_H

#include "types.h"

node_ast* new_node_ast(uint32_t c);
unary_ast* new_unary_ast(obj* body);
binary_ast* new_binary_ast(obj* left, obj* right);
obj* new_ast_leaf_obj(uint32_t c);
obj* new_ast_star_obj(obj* body);
obj* new_ast_or_obj(obj* left, obj* right);
obj* new_ast_cat_obj(obj* left, obj* right);
void ast_repr(obj* root);
void ast_repr_inner(obj* node, int indent);
void ast_str(obj* node);
bool ast_nullable(obj* node);
set* ast_firstpos(obj* node);
set* ast_lastpos(obj* node);
set* ast_get_followpos(obj* node);
void ast_set_followpos(obj* node, set* followpos);
void ast_compute_followpos(obj* root, vect* nodes_list, dict* id_to_node);
void ast_compute_followpos_cat(obj* cat_node, dict* id_to_node);
void ast_compute_followpos_star(obj* star_node, dict* id_to_node);
vect* ast_get_nodes_list(obj* node, vect* nodes);
dict* ast_get_ids_to_nodes(vect* nodes_list);
obj* ast_copy(obj* node);
void ast_uniqueify_ids(vect* nodes_list);
void ast_generate_trans_table(obj* root, set** ret_accepting_states, dict** ret_trans_table);
obj* ast_get_transition_key(uint64_t id, uint32_t codepoint);
void ast_print_trans_table(dict* trans_table);
dict* ast_get_symbol_to_ids(set* S, dict* id_to_node);

#endif