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



#endif