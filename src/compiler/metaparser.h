#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
void print_grammar_tables();
bool metaparser_is_valid_rule(vect* tokens);
obj* metaparser_get_rule_head(vect* tokens);
vect* metaparser_get_rule_body(vect* tokens);
obj* metaparser_insert_rule_ast(obj* head, metaast* body_ast);
obj* metaparser_get_symbol_or_anonymous(obj* parent_head, metaast_type parent_type, metaast* ast);

bool metaparser_insert_rule_sentences(obj* head, vect* body);

size_t metaparser_add_symbol(obj* symbol);
obj* metaparser_get_symbol(size_t i);
size_t metaparser_add_body(vect* body);
vect* metaparser_get_body(size_t i);
void metaparser_add_production(size_t head_idx, size_t body_idx);

#endif