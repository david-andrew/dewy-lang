#ifndef METAAST_H
#define METAAST_H

#include <stdint.h>

#include <charset.h>


//used to represent the initial metasyntax read in by the parser
//the metaast is then converted to the proper CFG production form, containing only strings of symbols

/*
Node struct map:

    NULL (i.e. empty node)
    - metaast_eps
    - metaast_anyset
    
    metaast_string_node
    - metaast_string
    - metaast_identifier

    metaast_char_node
    - metaast_char
    - metaast_hex (doesn't have it's own enum type name since identical in function to char)

    metaast_charset_node
    - metaast_charset

    metaast_repeat_node
    - metaast_star
    - metaast_plus
    - metaast_count

    metaast_unary_op_node
    - metaast_option
    - metaast_compliment

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
    // metaast_capture,     //FUTURE USE
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
    metaast_anyset,
    metaast_char,           //also includes hex literals
    metaast_charset,
    metaast_compliment,
    metaast_intersect
} metaast_types;


typedef struct {
    metaast_types type;
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
    metaast* sequence; //array of metaast
} metaast_sequence_node;


// C > D,  E < F,  G - H,  I / J,  K & L
typedef struct {
    metaast* left;
    metaast* right;
} metaast_binary_op_node;


// 'A', \X65
typedef struct {
    uint32_t c;
} metaast_char_node;


// [a-zA-Z]
typedef struct {
    charset* c;
} metaast_charset_node;


#endif