#ifndef PARSER_H
#define PARSER_H

#include <stdint.h>

#include "object.h"
#include "dictionary.h"
#include "vector.h"
#include "set.h"
#include "token.h"

int get_next_real_token(vect* tokens, int i);
int get_next_token_type(vect* tokens, token_type type, int i);
int get_level_first_token_type(vect* tokens, token_type type);
int get_level_first_adjacent(vect* tokens);
void update_meta_symbols(vect* tokens, dict* meta_symbols);
void create_lex_rule(vect* tokens, dict* meta_symbols, dict* meta_tables, dict* meta_accepts);
bool dynamic_scan(char** source, dict* meta_tables, dict* meta_accepts);
char* dynamic_scan_inner(char** source, dict* table, set* accepts);
obj* get_next_state(dict* table, obj* state, uint32_t codepoint);
obj* build_ast(vect* tokens, dict* meta_symbols);
int find_closing_pair(vect* tokens, int start);
obj* build_string_ast_obj(token* t);

#endif