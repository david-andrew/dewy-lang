#ifndef GOTOKEY_H
#define GOTOKEY_H

#include <stdint.h>

#include "object.h"

typedef struct {
    uint64_t state_idx;
    uint64_t symbol_idx;
} gotokey;

gotokey* new_gotokey(uint64_t state_idx, uint64_t symbol_idx);
obj* new_gotokey_obj(gotokey* k);
void gotokey_str(gotokey* k);
void gotokey_repr(gotokey* k);
bool gotokey_equals(gotokey* left, gotokey* right);
uint64_t gotokey_hash(gotokey* k);
void gotokey_free(gotokey* k);

#endif