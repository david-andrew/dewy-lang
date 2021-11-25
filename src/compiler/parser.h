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
    dict* P;            // dict<(X, k), set<j>> where (X, k, j) is a crf_action
    dict* Y;            // dict<bsr_head, set<j>>: BSRs (X ::= μ, i, j, k) and (μ, i, j, k)
    vect* R;            // vect<(slot, k, j)>: list of pending descriptors to handle.
    set* U;             // set<(slot, k, j)>: set of all descriptors constructed so far.
    crf* CRF;           // Call Return Forest
    uint32_t* I;        // input source (null terminated)
    uint64_t m;         // length of the input
    uint64_t cI;        // current input index (right extent so far, of rule being parsed)
    uint64_t cU;        // current left extent of rule being parsed
    uint64_t start_idx; // index of the start symbol
    bool whole;         // if true, require parse to consume the whole input
    bool sub;           // indicates if the parse needs to track BSR inputs, or just match for success
    bool success;       // indicates if the parse succeeded
} parser_context;

// top level functions used by the main program
void allocate_parser();
void initialize_parser();
void release_parser();
parser_context parser_context_struct(uint32_t* src, uint64_t len, uint64_t start_idx, bool whole, bool sub);
void release_parser_context(parser_context* con);
bool parser_parse(parser_context* con);

// internal helper functions for running the parser
void parser_generate_labels();
vect* parser_get_labels();
void parser_handle_label(slot* label, parser_context* con);
void parser_print_label(slot* label);
bool parser_rule_passes_filters(uint64_t head_idx, parser_context* con);
void parser_apply_precedence_filters(parser_context* con);

// CNP support functions
void parser_nonterminal_add(uint64_t head_idx, uint64_t j, parser_context* con);
bool parser_test_select(uint32_t c, uint64_t head_idx, slice* string);
void parser_descriptor_add(slot* L, uint64_t k, uint64_t j, parser_context* con);
void parser_return(uint64_t head_idx, uint64_t k, uint64_t j, parser_context* con);
void parser_call(slot* L, uint64_t i, uint64_t j, parser_context* con);
void parser_bsr_add(slot* L, uint64_t i, uint64_t k, uint64_t j, parser_context* con);
void parser_bsr_add_helper(bsr_head* b, uint64_t j, parser_context* con);

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