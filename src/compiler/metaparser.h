#ifndef METAPARSER_H
#define METAPARSER_H

#include "fset.h"
#include "metaast.h"
#include "set.h"
#include "slice.h"
#include "vector.h"

uint64_t metaparser_get_anonymous_rule_head();
void allocate_metaparser();
void complete_metaparser();
void release_metaparser();
void metaparser_free_ast_cache();
bool parse_next_meta_rule(vect* tokens);
void metaparser_rules_repr();
void metaparser_rules_str();
void metaparser_rule_str(obj* head, vect* body);
void metaparser_body_str(vect* body);
void metaparser_production_str(uint64_t head_idx, uint64_t production_idx);
void metaparser_filter_str(obj* right);
void metaparser_precedence_table_str(dict* table, set* bodies);

bool metaparser_is_valid_rule(vect* tokens);
obj* metaparser_get_rule_head(vect* tokens);
vect* metaparser_get_rule_body(vect* tokens);
uint64_t metaparser_insert_rule_ast(uint64_t head_idx, metaast* body_ast);
uint64_t metaparser_get_symbol_or_anonymous(metaast* ast);
bool metaparser_ast_uses_parent_level(metaast_type type);
void metaparser_insert_or_inner_rule_ast(uint64_t parent_head_idx, metaast* ast);

bool metaparser_insert_rule_sentences(obj* head, vect* body);

set* metaparser_get_symbols();
set* metaparser_get_bodies();
dict* metaparser_get_productions();
uint64_t metaparser_get_eps_body_idx();
uint64_t metaparser_get_start_symbol_idx();
uint64_t metaparser_add_symbol(obj* symbol);
obj* metaparser_get_symbol(uint64_t i);
bool metaparser_is_symbol_terminal(uint64_t symbol_idx);
uint64_t metaparser_add_body(vect* body);
vect* metaparser_get_body(uint64_t i);
void metaparser_add_production(uint64_t head_idx, uint64_t body_idx);
set* metaparser_get_production_bodies(uint64_t head_idx);
size_t metaparser_get_num_production_bodies(uint64_t head_idx);
vect* metaparser_get_production_body(uint64_t head_idx, uint64_t production_idx);
void metaparser_set_start_symbol(uint64_t symbol_idx);
void metaparser_add_nofollow(uint64_t left_idx, obj* right);
obj* metaparser_get_nofollow_entry(uint64_t head_idx);
void metaparser_add_reject(uint64_t left_idx, obj* right);
obj* metaparser_get_reject_entry(uint64_t head_idx);
void metaparser_add_precedence_split(uint64_t head_idx);
dict* metaparser_get_precedence_table(uint64_t head_idx);
void metaparser_finalize_precedence_tables();
void metaparser_add_capture(uint64_t head_idx);
bool metaparser_is_capture(uint64_t head_idx);

#endif