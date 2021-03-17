#ifndef METAAST_H
#define METAAST_H

#include <stdint.h>

#include "charset.h"


//used to represent the initial metasyntax read in by the parser
//the metaast is then converted to the proper CFG production form, containing only strings of symbols

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
    - metaast_greaterthan
    - metaast_lessthan
    - metaast_reject
    - metaast_nofollow
    - metaast_intersect

    metaast_sequence_node
    - metaast_cat
    - metaast_or
*/


typedef enum {
    //general expression node types
    metaast_eps,
    metaast_capture,
    metaast_string,
    metaast_star,
    metaast_plus,
    metaast_option,
    metaast_count,
    metaast_cat,
    metaast_or,             //or on sets is union
    metaast_greaterthan,
    metaast_lessthan,
    metaast_reject,         //reject on sets is diff
    metaast_nofollow,
    metaast_identifier,

    //set specific node types
    metaast_charset,        //covers char, hex, charset, and anyset
    metaast_compliment,
    metaast_intersect
} metaast_type;


// \e uses this directly with node=NULL
typedef struct {
    metaast_type type;
    void* node;
} metaast;


//"strings", #identifiers
typedef struct {
    uint32_t* string;
} metaast_string_node;


//A*, A+, (A)5
typedef struct {
    uint64_t count;
    metaast* inner;
} metaast_repeat_node;


//A?, A~
typedef struct {
    metaast* inner;
} metaast_unary_op_node;


//A B C D, A | B | C | D
typedef struct {
    size_t size;
    size_t capacity;
    metaast* sequence; //array of metaast
} metaast_sequence_node;


// C > D,  E < F,  G - H,  I / J,  K & L
typedef struct {
    metaast* left;
    metaast* right;
} metaast_binary_op_node;


// [a-zA-Z],  'A',  \X65,  \U
typedef struct {
    charset* c;
} metaast_charset_node;


//create meta-ast objects
metaast* new_metaast(metaast_type type, void* node);
metaast* new_metaast_null_node(metaast_type type);
metaast* new_metaast_string_node(metaast_type type, uint32_t* string);
metaast* new_metaast_repeat_node(metaast_type type, uint64_t count, metaast* inner);
metaast* new_metaast_unary_op_node(metaast_type type, metaast* inner);
metaast* new_metaast_sequence_node(metaast_type type, size_t size, size_t capacity, metaast* sequence); //sequence is array of metaast
metaast* new_metaast_binary_op_node(metaast_type type, metaast* left, metaast* right);
metaast* new_metaast_charset_node(metaast_type type, charset* c);

void metaast_sequence_append(metaast* sequence, metaast* ast);

//free meta-ast objects
void metaast_free(metaast* ast);

//constant folding contents of meta-ast
bool metaast_fold_constant(metaast* ast);
bool metaast_fold_charsets(metaast* ast);
bool metaast_fold_strings(metaast* ast);


void metaast_str(metaast* ast);
void metaast_str_inner(metaast* ast, int level);
void metaast_repr(metaast* ast);
void metaast_repr_inner(metaast* ast, int level);

#endif