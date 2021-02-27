#ifndef SCANNER_H
#define SCANNER_H

#include "object.h"
// #include "dictionary.h"
#include "vector.h"
#include "metatoken.h"

typedef enum 
{
    scan_root,
    scan_meta_rule,
    scan_meta_func,
    scan_peek,
} scanner_state;


//forward declare functions for meta parsing
obj* scan(char** src);
obj* match_hashtag(char** src);
obj* match_meta_char(char** src);
obj* match_meta_string(char** src);
obj* match_meta_hex_number(char** src);
obj* match_meta_escape(char** src);
obj* match_meta_charsetchar(char** src);
obj* match_meta_any(char** src);
obj* match_meta_epsilon(char** src);
obj* match_meta_ampersand(char** src);
obj* match_meta_star(char** src);
obj* match_meta_plus(char** src);
obj* match_meta_question_mark(char** src);
obj* match_meta_tilde(char** src);
obj* match_meta_semicolon(char** src);
obj* match_meta_vertical_bar(char** src);
obj* match_meta_minus(char** src);
obj* match_meta_equals_sign(char** src);
obj* match_meta_left_parenthesis(char** src);
obj* match_meta_right_parenthesis(char** src);
obj* match_meta_left_bracket(char** src);
obj* match_meta_right_bracket(char** src);
obj* match_meta_left_brace(char** src);
obj* match_meta_right_brace(char** src);
obj* match_whitespace(char** src);
obj* match_line_comment(char** src);
obj* match_block_comment(char** src);
bool peek_char(char** src, char c);
void remove_token_type(vect* v, metatoken_type type);

#endif