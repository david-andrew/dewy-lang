#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
metaast* metaparser_build_metaast(vect* body_tokens);
vect* metaparser_create_body(obj* head, metaast* body_ast);
uint32_t metaparser_extract_char_from_token(metatoken* t);
int get_next_real_metatoken(vect* tokens, int i);
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i);
bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type);
int metaparser_find_matching_pair(vect* tokens, metatoken_type left, metatoken_type right, size_t start_idx);

metaast* parse_meta_eps(vect* tokens);
metaast* parse_meta_char(vect* tokens);
metaast* parse_meta_string(vect* tokens);
metaast* parse_meta_charset(vect* tokens);
metaast* parse_meta_anyset(vect* tokens);
metaast* parse_meta_hex(vect* tokens);
metaast* parse_meta_identifier(vect* tokens);
metaast* parse_meta_star(vect* tokens);
metaast* parse_meta_plus(vect* tokens);
metaast* parse_meta_option(vect* tokens);
metaast* parse_meta_count(vect* tokens);
metaast* parse_meta_compliment(vect* tokens);
metaast* parse_meta_cat(vect* tokens);
metaast* parse_meta_or(vect* tokens);
metaast* parse_meta_group(vect* tokens);
metaast* parse_meta_capture(vect* tokens);
metaast* parse_meta_greaterthan(vect* tokens);
metaast* parse_meta_lessthan(vect* tokens);
metaast* parse_meta_reject(vect* tokens);
metaast* parse_meta_nofollow(vect* tokens);

size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);




#endif