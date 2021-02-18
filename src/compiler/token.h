#ifndef TOKEN_H
#define TOKEN_H

#include "object.h"

/**
    Enum/type declaration for each possible token type for reading syntax rules
*/
typedef enum token_types
{
    hashtag,
    meta_string,
    meta_hex_number,
    meta_comma,
    meta_semicolon,
    meta_vertical_bar,
    // meta_minus,
    meta_equals_sign,
    meta_left_parenthesis,
    meta_right_parenthesis,
    meta_left_bracket,
    meta_right_bracket,
    meta_left_brace,
    meta_right_brace,
    whitespace,
    comment,
} token_type;

/**
    Struct/type declaration for tokens for lexer/parser
*/
typedef struct tokens
{
    token_type type;
    char* content;
} token;


obj* new_token(token_type type, char* content); //TODO->replace with below versions
//token* new_token(token_type, char* content)
//obj* new_token_obj(token* t);
void token_str(token* t);
void token_free(token* t);

#endif