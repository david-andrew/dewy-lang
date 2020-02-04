#ifndef PARSER_H
#define PARSER_H

#include "vector.h"
#include "dictionary.h"
#include "token.h"

//TODO
// typedef struct parser_context_struct
// {
//     dict* meta_symbols;
//     dict* meta_rules;
//     //other context stuff
// } parser_context;

int get_next_real_token(vect* tokens, int i);
int get_next_token_type(vect* tokens, token_type type, int i);
void update_meta_symbols(dict* meta_symbols, vect* tokens);
void create_lex_rule(dict* meta_rules, vect* tokens);

#endif