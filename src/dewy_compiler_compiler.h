#ifndef DEWY_COMPILER_COMPILER_H
#define DEWY_COMPILER_COMPILER_H

#include <stdint.h>

#include "vector.h"
#include "metaast.h"
#include "set.h"


bool run_compiler_compiler(char* source, bool verbose, bool scanner, bool ast, bool parser, bool grammar, bool table);
bool run_compiler(uint32_t* source, bool compile, bool forest);
void print_scanner(vect* tokens, bool verbose);
void print_ast(uint64_t head_idx, metaast* body_ast, bool verbose);
void print_parser(bool verbose);
void print_grammar();
void print_table();
void print_compiler();

#endif