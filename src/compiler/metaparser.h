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


void initialize_metaparser();
void release_metaparser();
bool parse_next_meta_rule(vect* tokens);
obj* metaparser_create_body(vect* body_tokens);
bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type);
int get_next_real_metatoken(vect* tokens, int i);
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i);
size_t metaparser_add_head(obj* head);
obj* metaparser_get_head(size_t i);
size_t metaparser_add_body(obj* body);
vect* metaparser_get_body(size_t i);
void metaparser_join(size_t head_idx, size_t body_idx);




#endif