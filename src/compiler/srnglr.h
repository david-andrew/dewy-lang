#ifndef SRNGLR_H
#define SRNGLR_H

// #include <stdlib.h>
// #include <stdint.h>

#include "set.h"
#include "fset.h"
#include "slice.h"

obj* new_push_obj(uint64_t p);
void push_str(uint64_t p);
void push_repr(uint64_t p);

obj* new_accept_obj();
void accept_str();
void accept_repr();

fset* srnglr_first_of_symbol(uint64_t symbol_idx);
fset* srnglr_first_of_string(slice* string);

set* srnglr_closure(set* kernel);
set* srnglr_goto(set* itemset, uint64_t symbol_idx);
set* srnglr_generate_grammar_itemsets();





#endif