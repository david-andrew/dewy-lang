#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
vect* metaparser_create_body(obj* head, metaast* body_ast);

size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);




#endif