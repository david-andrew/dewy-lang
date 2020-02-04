#ifndef SCANNER_H
#define SCANNER_H

#include <stdbool.h>

#include "object.h"
#include "vector.h"
#include "token.h"

typedef enum scanner_states 
{
    scan_root,
    scan_meta_rule,
    scan_meta_func,
    scan_peek,
} scanner_state;

obj* scan(char** src);
obj* match_hashtag(char** src);
obj* match_meta_string(char** src);
obj* match_meta_comma(char** src);
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
void remove_token_type(vect* v, token_type type);

#endif