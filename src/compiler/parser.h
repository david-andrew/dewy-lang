#ifndef PARSER_H
#define PARSER_H

// Binary Subtree Representation (BSR) Clustered Nonterminal Parser (CNP), as described in
// /resources/gll/derivation_representation_using_binary_subtree_sets.pdf

#include <stdbool.h>
#include <stdint.h>

#include "object.h"
#include "slice.h"
#include "slot.h"
#include "vector.h"

// top level functions used by the main program
void initialize_parser();
void release_parser();
void parse(uint32_t* src);

// internal helper functions for running the parser
void parser_generate_labels();
vect* parser_get_labels();
void parser_handle_label(slot* label);
void parser_print_label(slot* label);

// CNP support functions
void parser_nt_add(uint64_t head_idx, uint64_t j);
bool parser_test_select(uint32_t c, uint64_t head_idx, slice* string);
void parser_dsc_add(slot* slot, uint64_t k, uint64_t j);
void parser_return(uint64_t head_idx, uint64_t k, uint64_t j);
void parser_call(slot* slot, uint64_t i, uint64_t j);
void parser_bsr_add(slot* slot, uint64_t i, uint64_t k, uint64_t j);

#endif