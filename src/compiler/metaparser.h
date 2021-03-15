#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
// #include "set.h"

/**
 * Productions are #head = #body
 * -> head set
 * -> body set
 * -> production join table
 * 
 * 
 * sequencing:
 * - collect a rule together
 * - convert all charset expressions to a single charset
 * - split out all or's from the rule
 * 
 * 
 * 
 * Higher level sequencing
 * -> compute all item sets from all rules
 * -> compute rnglr table
 * ---> closure + goto + first
 * 
 * 
 * 
 * 
 * interface Item {
 *   head::UInt64,
 *   body::UInt64,
 *   position::UInt64,
 *   lookahead::charset
 * }
 */


obj* metaparser_get_anonymous_rule_head();
void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
vect* metaparser_create_body(obj* head, vect* body_tokens);
int metaparser_get_split_idx(vect* rule_body_tokens);
vect* metaparser_parse_single_body(obj* head, vect* body_tokens);
vect* metaparser_merge_left_right_body(obj* head, vect* left_body, vect* right_body, metatoken* delimiter);
bool metaparser_is_body_charset(vect* body);
vect* parse_meta_eps(obj* head, vect* body_tokens);
vect* parse_meta_char(obj* head, vect* body_tokens);
vect* parse_meta_string(obj* head, vect* body_tokens);
vect* parse_meta_charset(obj* head, vect* body_tokens);
vect* parse_meta_anyset(obj* head, vect* body_tokens);
vect* parse_meta_hex(obj* head, vect* body_tokens);
vect* parse_meta_star(obj* head, vect* body_tokens);
vect* parse_meta_plus(obj* head, vect* body_tokens);
vect* parse_meta_option(obj* head, vect* body_tokens);
vect* parse_meta_count(obj* head, vect* body_tokens);
vect* parse_meta_compliment(obj* head, vect* body_tokens);
vect* parse_meta_cat(obj* head, vect* body_tokens);
int get_next_real_metatoken(vect* tokens, int i);
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i);
bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type);
size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);




#endif