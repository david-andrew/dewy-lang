#ifndef METATOKEN_H
#define METATOKEN_H

#include "object.h"
#include "vector.h"

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

int metatoken_get_next_real_token(vect* tokens, int i);
int metatoken_get_next_token_of_type(vect* tokens, metatoken_type type, int i);
bool metatoken_is_token_i_of_type(vect* tokens, int i, metatoken_type type);

metatoken_type metatoken_get_matching_pair_type(metatoken_type left);
uint32_t metatoken_extract_char_from_token(metatoken* t);
bool metatoken_is_type_bin_op(metatoken_type type);

void metatoken_str(metatoken* t);
void metatoken_repr(metatoken* t);
void metatoken_free(metatoken* t);

#endif