#ifndef SRNGLR_H
#define SRNGLR_H

#include "set.h"
#include "fset.h"
#include "slice.h"

//simple objects used by srnglr
obj* new_push_obj(uint64_t p);
void push_str(uint64_t p);
int push_strlen(uint64_t p);
void push_repr(uint64_t p);

obj* new_accept_obj();
void accept_str();
int accept_strlen();
void accept_repr();


//srnglr functions
void initialize_srnglr(size_t input_size);
void release_srnglr();

uint32_t* srnglr_get_input_source();

void srnglr_compute_symbol_firsts();
size_t srnglr_count_firsts_size();

fset* srnglr_first_of_symbol(uint64_t symbol_idx);
fset* srnglr_first_of_string(slice* string);

set* srnglr_closure(set* kernel);
set* srnglr_goto(set* itemset, uint64_t symbol_idx);
void srnglr_generate_grammar_itemsets();

set* srnglr_get_itemsets();
dict* srnglr_get_table();
set* srnglr_get_table_actions(uint64_t state_idx, uint64_t symbol_idx);
uint64_t* srnglr_get_table_push(uint64_t state_idx, uint64_t symbol_idx);
set* srnglr_get_merged_table_actions(uint64_t state_idx, uint32_t c);
void srnglr_insert_push(uint64_t state_idx, uint64_t symbol_idx, uint64_t goto_idx);
void srnglr_insert_reduction(uint64_t state_idx, uint64_t symbol_idx, uint64_t head_idx, uint64_t length, uint64_t nullable_idx);
void srnglr_insert_accept(uint64_t state_idx, uint64_t symbol_idx);
bool srnglr_is_accepting_state(uint64_t state_idx);

bool srnglr_parser(uint32_t* src);
void srnglr_reducer(size_t i, uint32_t* src);
void srnglr_shifter(size_t i, uint32_t* src);


//print functions
void srnglr_print_itemsets();
void srnglr_print_firsts();
void srnglr_print_table();
void srnglr_print_gss();
void srnglr_print_sppf();




#endif