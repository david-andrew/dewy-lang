#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"


//function pointer type for token scan functions
typedef metaast* (*metaparse_fn)(vect* tokens);
#define metaparse_fn_len(A) sizeof(A) / sizeof(metaparse_fn)


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
metaast* parse_meta_expr(vect* tokens);
metaast* parse_meta_expr_restricted(vect* tokens, metaparse_fn skip);
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