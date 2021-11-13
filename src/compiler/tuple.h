#ifndef TUPLE_H
#define TUPLE_H

// #include <stdint.h>

// #include "object.h"
// #include "gss.h"

// typedef struct {
//     gss_idx v_idx;          //GSS node to apply shift to
//     uint64_t state_idx;     //label of new GSS node to create as parent of v
// } qtuple;

// typedef struct {
//     gss_idx v_idx;          //GSS node to apply reduction to
//     uint64_t head_idx;      //lefthand side of the reduction rule
//     uint64_t body_idx;      //righthand side of the reduction rule
//     uint64_t length;        //length of the reduction being performed
//     uint64_t nullable_idx;  //nullable SPPF node representing any right nullable terms in the reduction
//     uint64_t y_idx;         //SPPF node that labels the first edge in the reduction path in the GSS
// } rtuple;

// qtuple* new_qtuple(gss_idx v_idx, uint64_t state_idx);
// obj* new_qtuple_obj(qtuple* t);
// void qtuple_str(qtuple* t);
// void qtuple_repr(qtuple* t);
// void qtuple_free(qtuple* t);
// bool qtuple_equals(qtuple* left, qtuple* right);
// uint64_t qtuple_hash(qtuple* t);

// rtuple* new_rtuple(gss_idx v_idx, uint64_t head_idx, uint64_t body_idx, uint64_t length, uint64_t nullable_idx, uint64_t y_idx);
// obj* new_rtuple_obj(rtuple* t);
// void rtuple_str(rtuple* t);
// void rtuple_repr(rtuple* t);
// void rtuple_free(rtuple* t);
// bool rtuple_equals(rtuple* left, rtuple* right);
// uint64_t rtuple_hash(rtuple* t);

#endif