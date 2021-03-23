#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
bool metaparser_is_valid_rule(vect* tokens);
obj* metaparser_get_rule_head(vect* tokens);
vect* metaparser_get_rule_body(vect* tokens);
obj* metaparser_insert_rule_ast(obj* head, metaast* body_ast);
obj* metaparser_get_symbol_or_anonymous(metaast* ast);

bool metaparser_insert_rule_sentences(obj* head, vect* body);

size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);

obj* new_epsilon_obj();


#endif