#ifndef METATOKEN_H
#define METATOKEN_H

#include "object.h"

/**
 * Enum/type declaration for each possible token type for reading syntax rules
 */
typedef enum
{
    hashtag,
    meta_char,
    meta_single_quote,
    meta_double_quote,
    meta_hex_number,
    meta_dec_number,
    meta_escape,
    meta_charset_char,
    meta_anyset,
    meta_epsilon,
    meta_ampersand,
    meta_star,
    meta_plus,
    meta_question_mark,
    meta_tilde,
    meta_semicolon,
    meta_vertical_bar,
    meta_minus,
    meta_forward_slash,
    meta_greater_than,
    meta_less_than,
    meta_equals_sign,
    meta_left_parenthesis,
    meta_right_parenthesis,
    meta_left_bracket,
    meta_right_bracket,
    meta_left_brace,
    meta_right_brace,
    whitespace,
    comment,
} metatoken_type;

/**
 * Struct/type declaration for tokens for lexer/parser
 */
typedef struct
{
    metatoken_type type;
    uint32_t* content;
} metatoken;


metatoken* new_metatoken(metatoken_type type, uint32_t* content);
obj* new_metatoken_obj(metatoken_type type, uint32_t* content);
metatoken* metatoken_copy(metatoken* t);
void metatoken_str(metatoken* t);
void metatoken_repr(metatoken* t);
void metatoken_free(metatoken* t);

#endif