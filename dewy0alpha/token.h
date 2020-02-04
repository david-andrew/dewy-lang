#ifndef TOKEN_H
#define TOKEN_H

#include "object.h"

//possible token types
typedef enum token_types
{
    hashtag,
    meta_string,
    meta_comma,
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
} token_type;

//individual tokens that appear in a meta rule
typedef struct tokens
{
    token_type type;
    char* content;
} token;

obj* new_token(token_type type, char* content);
void token_str(token* t);
void token_free(token* t);

#endif