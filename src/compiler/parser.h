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
void allocate_parser();
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

// first/follow set functions
size_t parser_count_fsets_size(vect* fsets);
void parser_compute_symbol_firsts();
void parser_compute_symbol_follows();
vect* parser_get_symbol_firsts();
vect* parser_get_symbol_follows();
fset* parser_first_of_symbol(uint64_t symbol_idx);
fset* parser_first_of_string(slice* string);
fset* parser_follow_of_symbol(uint64_t symbol_idx);
void parser_print_body_slice(slice* body);
void parser_print_body(vect* body);

#endif