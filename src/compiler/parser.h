#ifndef PARSER_H
#define PARSER_H

//Binary Subtree Representation (BSR) Clustered Nonterminal Parser (CNP), as described in /resources/gll/derivation_representation_using_binary_subtree_sets.pdf

#include <stdint.h>

//top level functions used by the main program
void initialize_parser();
void parse(uint32_t* src);
void release_parser();


//internal helper functions for running the parser
void generate_labels();

#endif