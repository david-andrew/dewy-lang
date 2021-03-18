#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
vect* metaparser_create_body(obj* head, metaast* body_ast);
uint32_t metaparser_extract_char_from_token(metatoken* t);
int get_next_real_metatoken(vect* tokens, int i);
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i);
bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type);
metatoken_type metaparser_get_matching_pair_type(metatoken_type left);
int metaparser_find_matching_pair(vect* tokens, metatoken_type left, size_t start_idx);
int metaparser_scan_to_end_of_unit(vect* tokens, size_t start_idx);
bool metaparser_is_token_bin_op(metatoken_type type);
metaast_type metaparser_get_token_ast_type(metatoken_type type);
uint64_t metaparser_get_type_precedence_level(metaast_type type);
bool metaparser_is_type_current_precedence(vect* tokens, metaast_type type);


size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);




#endif