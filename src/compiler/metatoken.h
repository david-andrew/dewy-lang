#ifndef METATOKEN_H
#define METATOKEN_H

#include "object.h"

/**
    Enum/type declaration for each possible token type for reading syntax rules
*/
typedef enum
{
    hashtag,
    meta_char,
    meta_string,
    meta_hex_number,
    meta_escape,
    meta_charsetchar,
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
    Struct/type declaration for tokens for lexer/parser
*/
typedef struct
{
    metatoken_type type;
    // char* content;
    uint32_t* content;
} metatoken;


obj* new_metatoken(metatoken_type type, char* content); //TODO->replace with below versions
//token* new_token(token_type, char* content)
//obj* new_token_obj(token* t);
void metatoken_str(metatoken* t);
void metatoken_free(metatoken* t);

#endif