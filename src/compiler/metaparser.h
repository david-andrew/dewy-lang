#ifndef METAPARSER_H
#define METAPARSER_H

#include "vector.h"
#include "metaast.h"

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
metaast* metaparser_build_metaast(vect* body_tokens);
vect* metaparser_create_body(obj* head, metaast* body_ast);
int metaparser_get_split_idx(vect* rule_body_tokens);
vect* metaparser_parse_single_body(obj* head, vect* body_tokens);
vect* metaparser_merge_left_right_body(obj* head, vect* left_body, vect* right_body, metatoken* delimiter);
bool metaparser_is_body_charset(vect* body);
metaast* parse_meta_eps(vect* tokens);
metaast* parse_meta_char(vect* tokens);
metaast* parse_meta_string(vect* tokens);
metaast* parse_meta_charset(vect* tokens);
metaast* parse_meta_anyset(vect* tokens);
metaast* parse_meta_hex(vect* tokens);
metaast* parse_meta_star(vect* tokens);
metaast* parse_meta_plus(vect* tokens);
metaast* parse_meta_option(vect* tokens);
metaast* parse_meta_count(vect* tokens);
metaast* parse_meta_compliment(vect* tokens);
metaast* parse_meta_cat(vect* tokens);
int get_next_real_metatoken(vect* tokens, int i);
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i);
bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type);
size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);




#endif