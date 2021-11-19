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
    dict* cluster_nodes; // dict<cluster_nodes, set<children_indices>>
    set* label_nodes;    // set<label_nodes>
} crf;

typedef struct
{
    uint64_t head_idx;
    uint64_t k;
    uint64_t j;
} crf_action;

crf* new_crf();
void crf_free(crf* CRF);
void crf_str(crf* CRF);
uint64_t crf_add_cluster_node(crf* CRF, crf_cluster_node* node);
uint64_t crf_add_label_node(crf* CRF, crf_label_node* node, uint64_t parent_idx);
crf_cluster_node* new_crf_cluster_node(uint64_t head_idx, uint64_t j);
crf_cluster_node crf_cluster_node_struct(uint64_t head_idx, uint64_t j);
obj* new_crf_cluster_node_obj(crf_cluster_node* node);
bool crf_cluster_node_equals(crf_cluster_node* left, crf_cluster_node* right);
uint64_t crf_cluster_node_hash(crf_cluster_node* node);
void crf_cluster_node_free(crf_cluster_node* node);
void crf_cluster_node_str(crf_cluster_node* node);
void crf_cluster_node_repr(crf_cluster_node* node);
crf_label_node* new_crf_label_node(slot label, uint64_t j);
crf_label_node crf_label_node_struct(slot label, uint64_t j);
obj* new_crf_label_node_obj(crf_label_node* node);
bool crf_label_node_equals(crf_label_node* left, crf_label_node* right);
uint64_t crf_label_node_hash(crf_label_node* node);
void crf_label_node_free(crf_label_node* node);
void crf_label_node_str(crf_label_node* node);
void crf_label_node_repr(crf_label_node* node);
crf_action* new_crf_action(uint64_t head_idx, uint64_t k, uint64_t j);
crf_action crf_action_struct(uint64_t head_idx, uint64_t k, uint64_t j);
obj* new_crf_action_obj(crf_action* action);
bool crf_action_equals(crf_action* left, crf_action* right);
uint64_t crf_action_hash(crf_action* action);
void crf_action_free(crf_action* action);
void crf_action_str(crf_action* action);
void crf_action_repr(crf_action* action);

#endif