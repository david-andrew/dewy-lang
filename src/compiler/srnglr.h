#ifndef SRNGLR_H
#define SRNGLR_H

#include "set.h"
#include "fset.h"
#include "slice.h"

//simple objects used by srnglr
obj* new_push_obj(uint64_t p);
void push_str(uint64_t p);
void push_repr(uint64_t p);

obj* new_accept_obj();
void accept_str();
void accept_repr();


//srnglr functions
void initialize_srnglr();
void release_srnglr();

fset* srnglr_first_of_symbol(uint64_t symbol_idx);
fset* srnglr_first_of_string(slice* string);

set* srnglr_closure(set* kernel);
set* srnglr_goto(set* itemset, uint64_t symbol_idx);
set* srnglr_generate_grammar_itemsets();

dict* srnglr_get_table();
void srnglr_insert_push(uint64_t state_idx, uint64_t symbol_idx, uint64_t goto_idx);




#endif