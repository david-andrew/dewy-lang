#ifndef SRNGLR_H
#define SRNGLR_H

// #include <stdlib.h>
// #include <stdint.h>

#include "set.h"
#include "fset.h"
#include "slice.h"

set* srnglr_closure(set* kernel);
set* srnglr_goto(set* itemset, uint64_t symbol_idx);
set* srnglr_generate_grammar_itemsets();

fset* srnglr_first_of_symbol(uint64_t symbol_idx);
fset* srnglr_first_of_string(slice* string);





#endif