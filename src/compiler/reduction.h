#ifndef REDUCTION_H
#define REDUCTION_H

#include <stdint.h>

#include "object.h"

typedef struct {
    uint64_t head_idx;      //non-terminal to reduce
    uint64_t length;        //length of the reduction
    uint64_t nullable_idx;  //index of the nullable SPPF node for this reduction (0 if not right-nullable)
} reduction;

reduction* new_reduction(uint64_t head_idx, uint64_t length, uint64_t nullable_idx);
obj* new_reduction_obj(reduction* r);
void reduction_str(reduction* r);
int reduction_strlen(reduction* r);
void reduction_repr(reduction* r);
bool reduction_equals(reduction* left, reduction* right);
uint64_t reduction_hash(reduction* r);
void reduction_free(reduction* r);


#endif