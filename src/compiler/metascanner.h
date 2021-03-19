#ifndef METASCANNER_H
#define METASCANNER_H

#include "object.h"
#include "vector.h"
#include "metatoken.h"

typedef enum 
{
    scan_root,
    scan_meta_rule,
    scan_charset_body,
    scan_single_quote_string_body,
    scan_double_quote_string_body,
    scan_metafunc_body,
    scan_peek,
} metascanner_state;


//forward declare functions for meta parsing
void initialize_metascanner();
void release_metascanner();
metascanner_state peek_metascanner_state();
void push_metascanner_state(metascanner_state state);
metascanner_state pop_metascanner_state();

//helper functions
bool is_identifier_char(char c);
bool is_identifier_symbol_char(char c);
bool is_alpha_char(char c);
bool is_dec_digit(char c);
bool is_alphanum_char(char c);
bool is_upper_hex_letter(char c);
bool is_lower_hex_letter(char c);
bool is_hex_digit(char c);
bool is_hex_escape(char c);
bool is_whitespace_char(char c);
bool is_charset_char(uint32_t c);

//token matching functions
obj* scan(char** src);
obj* match_hashtag(char** src);
obj* match_meta_single_quote(char** src);
obj* match_meta_single_quote_char(char** src);
obj* match_meta_double_quote(char** src);
obj* match_meta_double_quote_char(char** src);
obj* match_meta_hex_number(char** src);
obj* match_meta_dec_number(char** src);
obj* match_meta_anyset(char** src);
obj* match_meta_escape(char** src);
obj* match_meta_charset_char(char** src);
obj* match_meta_epsilon(char** src);
obj* match_meta_ampersand(char** src);
obj* match_meta_star(char** src);
obj* match_meta_plus(char** src);
obj* match_meta_question_mark(char** src);
obj* match_meta_tilde(char** src);
obj* match_meta_semicolon(char** src);
obj* match_meta_vertical_bar(char** src);
obj* match_meta_minus(char** src);
obj* match_meta_forward_slash(char** src);
obj* match_meta_greater_than(char** src);
obj* match_meta_less_than(char** src);
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


void remove_token_type(vect* v, metatoken_type type);
uint32_t get_peek_char(char** src);

#endif