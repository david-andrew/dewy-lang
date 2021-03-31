#ifndef DEWY_COMPILER_COMPILER_H
#define DEWY_COMPILER_COMPILER_H

#include <stdint.h>

#include "vector.h"
#include "metaast.h"
#include "set.h"


void run_compiler(char* source, bool verbose, bool scanner, bool ast, bool parser, bool grammar, bool table);
void print_scanner(vect* tokens, bool verbose);
void print_ast(uint64_t head_idx, metaast* body_ast, bool verbose);
void print_parser();
void print_grammar(set* itemsets);
void print_table();

#endif