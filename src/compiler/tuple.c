#ifndef TUPLE_C
#define TUPLE_C

// #include <stdlib.h>
// #include <stdio.h>
// #include <inttypes.h>
// #include <stdarg.h>

// #include "tuple.h"
// #include "utilities.h"
// #include "metaparser.h"


// /**
//  * Create a new qtuple for the srnglr_Q vector
//  */
// qtuple* new_qtuple(gss_idx v_idx, uint64_t state_idx)
// {
//     qtuple* t = malloc(sizeof(qtuple));
//     *t = (qtuple){.v_idx=v_idx, .state_idx=state_idx};
//     return t;
// }


// /**
//  * Create a new qtuple wrapped in an object.
//  */
// obj* new_qtuple_obj(qtuple* t)
// {
//     obj* T = malloc(sizeof(obj));
//     *T = (obj){.type=QTuple_t, .data=t};
//     return T;
// }


// /**
//  * Print out the qtuple.
//  */
// void qtuple_str(qtuple* t)
// {
//     printf("{v_idx: "); gss_idx_str(&t->v_idx); printf(", state_idx: %"PRIu64"}", t->state_idx);
// }


// /**
//  * Print the internal representation of the qtuple.
//  */
// void qtuple_repr(qtuple* t) { printf("qtuple"); qtuple_str(t);}


// /**
//  * Free the allocated memory for the qtuple.
//  */
// void qtuple_free(qtuple* t) { free(t); }


// // /**
// //  * Determine if two qtuples are equal.
// //  */
// // bool qtuple_equals(qtuple* left, qtuple* right)
// // {
// //     return gss_idx_equals(&left->v_idx, &right->v_idx) && left->state_idx == right->state_idx;
// // }


// // /**
// //  * get a hash of the elements in the qtuple.
// //  */
// // uint64_t qtuple_hash(qtuple* t)
// // {
// //     uint64_t seq[] = {t->v_idx.nodes_idx, t->v_idx.node_idx, t->state_idx};
// //     return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
// // }


// /**
//  * Create a new rtuple for the srnglr_R vector
//  */
// rtuple* new_rtuple(gss_idx v_idx, uint64_t head_idx, uint64_t body_idx, uint64_t length, uint64_t nullable_idx, uint64_t y_idx)
// {
//     //build the tuple
//     rtuple* t = malloc(sizeof(rtuple));
//     *t = (rtuple){
//         .v_idx=v_idx,
//         .head_idx=head_idx,
//         .body_idx=body_idx,
//         .length=length,
//         .nullable_idx=nullable_idx,
//         .y_idx=y_idx
//     };
//     return t;
// }

// /**
//  * Create a new rtuple wrapped in an object.
//  */
// obj* new_rtuple_obj(rtuple* t)
// {
//     obj* T = malloc(sizeof(obj));
//     *T = (obj){.type=RTuple_t, .data=t};
//     return T;
// }


// /**
//  * Print out the rtuple.
//  */
// void rtuple_str(rtuple* t)
// {
//     printf("{v_idx: "); gss_idx_str(&t->v_idx);
//     printf(", ");
//     obj_str(metaparser_get_symbol(t->head_idx));
//     printf(": %"PRIu64", m: %"PRIu64", f: %"PRIu64", y_idx: %"PRIu64"}", t->body_idx, t->length, t->nullable_idx, t->y_idx);
// }


// /**
//  * Print the internal representation of the rtuple.
//  */
// void rtuple_repr(rtuple* t) { printf("rtuple"); rtuple_str(t); }


// /**
//  * Free the allocated memory for the rtuple.
//  */
// void rtuple_free(rtuple* t) { free(t); }


// // /**
// //  * Determine if two rtuples are equal.
// //  */
// // bool rtuple_equals(rtuple* left, rtuple* right)
// // {
// //     return gss_idx_equals(&left->v_idx, &right->v_idx) 
// //         && left->head_idx == right->head_idx
// //         && left->body_idx == right->body_idx
// //         && left->length == right->length
// //         && left->nullable_idx == right->nullable_idx
// //         && left->y_idx == right->nullable_idx;
// // }


// // /**
// //  * get a hash of the elements in the tuple.
// //  */
// // uint64_t rtuple_hash(rtuple* t)
// // {
// //     uint64_t seq[] = {t->v_idx.nodes_idx, t->v_idx.node_idx, t->head_idx, t->body_idx, t->length, t->nullable_idx, t->y_idx};
// //     return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
// // }


#endif