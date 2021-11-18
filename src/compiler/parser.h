#ifndef PARSER_H
#define PARSER_H

// Binary Subtree Representation (BSR) Clustered Nonterminal Parser (CNP), as described in
// /resources/gll/derivation_representation_using_binary_subtree_sets.pdf

#include <stdbool.h>
#include <stdint.h>

#include "bsr.h"
#include "crf.h"
#include "object.h"
#include "slice.h"
#include "slot.h"
#include "vector.h"

typedef struct
{
    set* P;      // set<crf_action>: set of CRF return actions represented as triples (X, k, j)
    set* Y;      // set<bsr>: set of BSRs (X ::= μ, i, k, j) and (μ, i, k, j)
    vect* R;     // vect<(slot, k, j)>: list of pending descriptors to handle.
    set* U;      // set<(slot, k, j)>: set of all descriptors constructed so far.
    crf* CRF;    // Call Return Forest
    uint32_t* I; // input source (null terminated)
    uint64_t m;  // length of the input
    uint64_t cI; // current input index
    uint64_t cU; // TBD
} parser_context;

// top level functions used by the main program
void allocate_parser();
void initialize_parser();
void release_parser();
parser_context* new_parser_context(uint32_t* src, uint64_t len);
void parser_context_free(parser_context* con);
bool parser_parse(parser_context* con, bool whole);

// internal helper functions for running the parser
void parser_generate_labels();
vect* parser_get_labels();
void parser_handle_label(slot* label, parser_context* con);
void parser_print_label(slot* label);

// CNP support functions
void parser_nonterminal_add(uint64_t head_idx, uint64_t j, parser_context* con);
bool parser_test_select(uint32_t c, uint64_t head_idx, slice* string);
void parser_descriptor_add(slot* L, uint64_t k, uint64_t j, parser_context* con);
void parser_return(uint64_t head_idx, uint64_t k, uint64_t j, parser_context* con);
void parser_call(slot* slot, uint64_t i, uint64_t j, parser_context* con);
void parser_bsr_add(slot* slot, uint64_t i, uint64_t k, uint64_t j, parser_context* con);

// first/follow set functions
size_t parser_count_fsets_size(vect* fsets);
void parser_compute_symbol_firsts();
void parser_compute_symbol_follows();
vect* parser_get_symbol_firsts();
vect* parser_get_symbol_follows();
fset* parser_first_of_symbol(uint64_t symbol_idx);
fset* parser_first_of_string(slice* string);
fset* parser_memo_first_of_string(slice* string);
fset* parser_follow_of_symbol(uint64_t symbol_idx);
void parser_print_body_slice(slice* body);
void parser_print_body(vect* body);

#endif