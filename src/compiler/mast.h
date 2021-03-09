#ifndef MAST_H
#define MAST_H

// #include <stdint.h>
// #include <stdbool.h>
#include <stddef.h>

#include "object.h"
#include "charset.h"


/**
 * Nonterminal Set
 * -> list of all production left hand sides (set so we can easily check for existence)
 * -> index in set's underlying array can be used to refer to a terminal more succinctly
*/
/**
 * Body Set
 * -> list of all rule strings i.e. production right hand sides (set so we can easily check for existence)
 * -> rule strings will probably be vectors of charsets and or nonterminal strings (or perhaps ints for the nonterminal's index in the nonterminal set)
 */
/**
 * Production Junction Table
 * -> indicate which nonterminals map to which body strings. many to many map
 * -> TBD how to handle exlusions/rejects, since that would probably be here. perhaps there will be a reject table too?
 */

// typedef enum {
//     mast_epsilon,
//     // mast_codepoint,
//     mast_charset,
//     mast_count, 
//     // mast{count::int, repeat::bool}
//     // count exactly is mast{count=N, repeat=false}
//     // star is mast{count=1, repeat=true} | \e
//     // plus is mast{count=1, repeat=true}
//     // range is mast{lower, true} - mast{upper+1, true}
//     // option is #expr | \e
//     mast_or,
//     mast_cat, //or mast_string
//     mast_reference,


// } mast_type;

// typedef struct
// {
//     void* body; //either a mast** or a mast_leaf*
//     size_t size;
// } mast;

// typedef struct
// {
//     charset class;
// } mast_leaf;

#endif