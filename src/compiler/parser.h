#ifndef PARSER_H
#define PARSER_H

// Binary Subtree Representation (BSR) Clustered Nonterminal Parser (CNP), as described in
// /resources/gll/derivation_representation_using_binary_subtree_sets.pdf

#include <stdbool.h>
#include <stdint.h>

#include "object.h"
#include "slot.h"

// top level functions used by the main program
void initialize_parser();
void release_parser();
void parse(uint32_t* src);

// internal helper functions for running the parser
void generate_labels();

bool test_select(uint32_t c, uint64_t head, uint64_t body);
void bsrAdd(slot* slot, uint64_t i, uint64_t k, uint64_t j);
void call(slot* slot, uint64_t i, uint64_t j);
void rtn(uint64_t head, uint64_t k, uint64_t j);

#endif