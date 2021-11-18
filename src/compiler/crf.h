#ifndef CRF_H
#define CRF_H

#include <stdbool.h>
#include <stdint.h>

#include "object.h"
#include "set.h"
#include "slice.h"
#include "slot.h"

// Call Return Forest data structure used by CNP parsing algorithm

typedef struct
{
    uint64_t head_idx;
    uint64_t j;
} crf_cluster_node; // nodes of the form (X, j)

typedef struct
{
    slot label;
    uint64_t j;
} crf_label_node; // nodes of the form (X ::= α•β, j)

typedef struct
{
    dict* cluster_nodes; // dict<cluster_nodes, vect<children_indices>>
    set* label_nodes;    // set<label_nodes>
} crf;

crf* new_crf();
void crf_free(crf* CRF);
void crf_str(crf* CRF);
crf_cluster_node* crf_new_cluster_node(uint64_t head_idx, uint64_t j);
crf_cluster_node crf_cluster_node_struct(uint64_t head_idx, uint64_t j);
obj* crf_cluster_node_obj(crf_cluster_node* node);
bool crf_cluster_node_equals(crf_cluster_node* left, crf_cluster_node* right);
uint64_t crf_cluster_node_hash(crf_cluster_node* node);
void crf_cluster_node_free(crf_cluster_node* node);
void crf_cluster_node_str(crf_cluster_node* node);
void crf_cluster_node_repr(crf_cluster_node* node);
crf_label_node* crf_new_label_node(slot label, uint64_t j);
crf_label_node crf_label_node_struct(slot label, uint64_t j);
obj* crf_label_node_obj(crf_label_node* node);
bool crf_label_node_equals(crf_label_node* left, crf_label_node* right);
uint64_t crf_label_node_hash(crf_label_node* node);
void crf_label_node_free(crf_label_node* node);
void crf_label_node_str(crf_label_node* node);
void crf_label_node_repr(crf_label_node* node);

#endif