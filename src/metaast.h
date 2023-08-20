#ifndef METAAST_H
#define METAAST_H

#include <stdint.h>

#include "charset.h"
#include "metatoken.h"
#include "object.h"
#include "set.h"
#include "vector.h"

// used to represent the initial metasyntax read in by the parser
// the metaast is then converted to the proper CFG production form, containing only strings of symbols

/*
Node struct map:

    NULL (i.e. empty node)
    - metaast_eps

    metaast_string_node
    - metaast_string
    - metaast_identifier

    metaast_charset_node
    - metaast_charset
    (don't have their own type name since identical in function to charset)
    // metaast_anyset
    // metaast_char
    // metaast_hex

    metaast_repeat_node
    - metaast_star
    - metaast_plus
    - metaast_count

    metaast_unary_op_node
    - metaast_option
    - metaast_compliment
    - metaast_capture

    metaast_binary_op_node
    - metaast_or
    - metaast_greaterthan
    - metaast_reject
    - metaast_nofollow
    - metaast_intersect

    metaast_sequence_node
    - metaast_cat
*/

typedef enum
{
    // general expression node types
    metaast_eps,
    metaast_capture,
    metaast_string,
    metaast_caseless,
    metaast_star,
    metaast_plus,
    metaast_option,
    metaast_count,
    metaast_cat,
    metaast_or, // or on sets is union
    metaast_greaterthan,
    metaast_reject, // reject on sets is diff
    metaast_nofollow,
    metaast_identifier,

    // set specific node types
    metaast_charset, // covers char, hex, charset, and anyset
    metaast_compliment,
    metaast_intersect,
} metaast_type;

// forward declare so we can reference inside the struct itself
typedef struct metaast_struct metaast;

// \e uses this directly with node=NULL
typedef struct metaast_struct
{
    metaast_type type;
    union
    {
        uint32_t* string; // "strings", #identifiers
        struct
        {
            uint64_t count;
            metaast* inner;
        } repeat; // A*, A+, (A)5
        struct
        {
            metaast* inner;
        } unary; // A?, A~
        struct
        {
            size_t size;
            metaast** elements;
        } sequence; // A B C D
        struct
        {
            metaast* left;
            metaast* right;
        } binary;    // A | B,  C > D,  E < F,  G - H,  I / J,  K & L
        charset* cs; // [a-zA-Z],  'A',  \X65,  \U
    } node;
} metaast;

// function pointer type for token scan functions
typedef metaast* (*metaast_parse_fn)(vect* tokens);
#define metaast_parse_fn_len(A) sizeof(A) / sizeof(metaast_parse_fn)

// create meta-ast objects
// metaast* new_metaast(metaast_type type, void* node);
metaast* new_metaast_null_node(metaast_type type);
metaast* new_metaast_string_node(metaast_type type, uint32_t* string);
metaast* new_metaast_repeat_node(metaast_type type, uint64_t count, metaast* inner);
metaast* new_metaast_unary_op_node(metaast_type type, metaast* inner);
metaast* new_metaast_sequence_node(metaast_type type, size_t size, metaast** elements);
metaast* new_metaast_binary_op_node(metaast_type type, metaast* left, metaast* right);
metaast* new_metaast_charset_node(metaast_type type, charset* cs);
obj* new_metaast_obj(metaast* ast);

// construct nodes from input tokens
metaast* metaast_parse_expr(vect* tokens);
void metaast_parse_error();
metaast* metaast_parse_expr_restricted(vect* tokens, metaast_parse_fn skip);
metaast* metaast_parse_eps(vect* tokens);
metaast* metaast_parse_char(vect* tokens);
metaast* metaast_parse_caseless_char(vect* tokens);
metaast* metaast_parse_string(vect* tokens);
metaast* metaast_parse_caseless_string(vect* tokens);
metaast* metaast_parse_charset(vect* tokens);
metaast* metaast_parse_anyset(vect* tokens);
metaast* metaast_parse_hex(vect* tokens);
metaast* metaast_parse_identifier(vect* tokens);
metaast* metaast_parse_star(vect* tokens);
metaast* metaast_parse_plus(vect* tokens);
metaast* metaast_parse_capture(vect* tokens);
metaast* metaast_parse_option(vect* tokens);
metaast* metaast_parse_count(vect* tokens);
metaast* metaast_parse_compliment(vect* tokens);
metaast* metaast_parse_cat(vect* tokens);
metaast* metaast_parse_or(vect* tokens);
metaast* metaast_parse_group(vect* tokens);
metaast* metaast_parse_greaterthan(vect* tokens);
metaast* metaast_parse_reject(vect* tokens);
metaast* metaast_parse_nofollow(vect* tokens);
metaast* metaast_parse_intersect(vect* tokens);
metaast* metaast_parse_binary_op(vect* tokens, metatoken_type optype);

// parsing helper functions
int metaast_find_matching_pair(vect* tokens, metatoken_type left, size_t start_idx);
bool metaast_is_type_single_unit(metaast_type type);
int metaast_scan_to_end_of_unit(vect* tokens, size_t start_idx);
metaast_type metaast_get_token_ast_type(metatoken_type type);
uint64_t metaast_get_type_precedence_level(metaast_type type);

// free meta-ast objects
void metaast_free(metaast* ast);
void metaast_free_with_refs(metaast* ast, set* refs);

// constant folding contents of meta-ast
bool metaast_fold_constant(metaast** ast_ptr);
bool metaast_fold_charsets(metaast** ast_ptr);
bool metaast_fold_strings(metaast** ast_ptr);

void metaast_str(metaast* ast);
void metaast_str_inner(metaast* ast, metaast_type parent);
bool metaast_str_inner_check_needs_parenthesis(metaast_type parent, metaast_type inner);
void metaast_repr(metaast* ast);
void metaast_repr_inner(metaast* ast, int level);

bool metaast_equals(metaast* left, metaast* right);
uint64_t metaast_hash(metaast* ast);
uint64_t metaast_hash_sequence_getval(void* seq, size_t i);

#endif