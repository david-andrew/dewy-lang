#ifndef CRF_C
#define CRF_C

#include <inttypes.h>
#include <stdio.h>

#include "crf.h"
#include "metaparser.h"
#include "parser.h"
#include "utilities.h"

// Call Return Forest

/**
 * Create a new call return forest.
 */
crf* new_crf()
{
    crf* CRF = malloc(sizeof(crf));
    *CRF = (crf){
        .cluster_nodes = new_set(),
        .label_nodes = new_set(),
        .edges = new_set(),
    };
    return CRF;
}

/**
 * Free a call return forest.
 */
void crf_free(crf* CRF)
{
    set_free(CRF->cluster_nodes);
    set_free(CRF->label_nodes);
    set_free(CRF->edges);
    free(CRF);
}

/**
 * Print out the string representation of a CRF
 */
void crf_str(crf* CRF)
{
    printf("CRF: [\n");
    for (size_t i = 0; i < set_size(CRF->edges); i++)
    {
        crf_edge* edge = set_get_at_index(CRF->edges, i)->data;
        crf_cluster_node* cluster_node = set_get_at_index(CRF->cluster_nodes, edge->cluster_node_idx)->data;
        crf_label_node* label_node = set_get_at_index(CRF->label_nodes, edge->label_node_idx)->data;
        printf("    ");
        crf_cluster_node_str(cluster_node);
        printf(" -> ");
        crf_label_node_str(label_node);
        printf("\n");
    }
    printf("]\n");
}

/**
 * Create a new cluster node.
 */
crf_cluster_node* crf_new_cluster_node(uint64_t head_idx, uint64_t j)
{
    crf_cluster_node* node = malloc(sizeof(crf_cluster_node));
    *node = crf_cluster_node_struct(head_idx, j);
    return node;
}

/**
 * Return a stack allocated struct for a cluster node.
 */
inline crf_cluster_node crf_cluster_node_struct(uint64_t head_idx, uint64_t j)
{
    return (crf_cluster_node){
        .head_idx = head_idx,
        .j = j,
    };
}

/**
 * Return an object wrapped cluster node.
 */
obj* crf_cluster_node_obj(crf_cluster_node* node)
{
    obj* N = malloc(sizeof(obj));
    *N = obj_struct(CRFClusterNode_t, node);
    return N;
}

/**
 * return the hash value of a cluster node.
 */
uint64_t crf_cluster_node_hash(crf_cluster_node* node)
{
    uint64_t seq[] = {node->head_idx, node->j};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Determine if two cluster nodes are equal.
 */
bool crf_cluster_node_equals(crf_cluster_node* left, crf_cluster_node* right)
{
    return left->head_idx == right->head_idx && left->j == right->j;
}

/**
 * Free an allocated cluster node.
 */
void free_crf_cluster_node(crf_cluster_node* node) { free(node); }

/**
 * Print out the string representation of a cluster node.
 */
void crf_cluster_node_str(crf_cluster_node* node)
{
    obj* symbol = metaparser_get_symbol(node->head_idx);
    printf("(");
    obj_str(symbol);
    printf(", %" PRIu64 ")", node->j);
}

/**
 * Print out the internal representation of the cluster node.
 */
void crf_cluster_node_repr(crf_cluster_node* node)
{
    printf("(head_idx: %" PRIu64 ", j: %" PRIu64 ")", node->head_idx, node->j);
}

/**
 * Create a new label node.
 */
crf_label_node* crf_new_label_node(slot label, uint64_t j)
{
    crf_label_node* node = malloc(sizeof(crf_label_node));
    *node = crf_label_node_struct(label, j);
    return node;
}

/**
 * Return a stack allocated struct for a label node.
 */
crf_label_node crf_label_node_struct(slot label, uint64_t j)
{
    return (crf_label_node){
        .label = label,
        .j = j,
    };
}

/**
 * Return an object wrapped label node.
 */
obj* crf_label_node_obj(crf_label_node* node)
{
    obj* N = malloc(sizeof(obj));
    *N = obj_struct(CRFLabelNode_t, node);
    return N;
}

/**
 * Determine if two label nodes are equal.
 */
bool crf_label_node_equals(crf_label_node* left, crf_label_node* right)
{
    return left->label.head_idx == right->label.head_idx && left->label.production_idx == right->label.production_idx &&
           left->label.dot == right->label.dot && left->j == right->j;
}

/**
 * return the hash value of a label node.
 */
uint64_t crf_label_node_hash(crf_label_node* node)
{
    uint64_t seq[] = {node->label.head_idx, node->label.production_idx, node->label.dot, node->j};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Free an allocated label node.
 */
void free_crf_label_node(crf_label_node* node) { free(node); }

/**
 * Print out the string representation of a label node.
 */
void crf_label_node_str(crf_label_node* node)
{
    printf("(");
    slot_str(&node->label);
    printf(", %" PRIu64 ")", node->j);
}

/**
 * Print out the internal representation of the label node.
 */
void crf_label_node_repr(crf_label_node* node)
{
    printf("(label: ");
    slot_repr(&node->label);
    printf(", j: %" PRIu64 ")", node->j);
}

/**
 * Create a new edge.
 */
crf_edge* crf_new_edge(uint64_t cluster_node_idx, uint64_t label_node_idx)
{
    crf_edge* edge = malloc(sizeof(crf_edge));
    *edge = crf_edge_struct(cluster_node_idx, label_node_idx);
    return edge;
}

/**
 * Return a stack allocated struct for an edge.
 */
crf_edge crf_edge_struct(uint64_t cluster_node_idx, uint64_t label_node_idx)
{
    return (crf_edge){
        .cluster_node_idx = cluster_node_idx,
        .label_node_idx = label_node_idx,
    };
}

/**
 * Return an object wrapped edge.
 */
obj* crf_edge_obj(crf_edge* edge)
{
    obj* E = malloc(sizeof(obj));
    *E = obj_struct(CRFEdge_t, edge);
    return E;
}

/**
 * Determine if two edges are equal.
 */
bool crf_edge_equals(crf_edge* left, crf_edge* right)
{
    return left->cluster_node_idx == right->cluster_node_idx && left->label_node_idx == right->label_node_idx;
}

/**
 * return the hash value of an edge.
 */
uint64_t crf_edge_hash(crf_edge* edge)
{
    uint64_t seq[] = {edge->cluster_node_idx, edge->label_node_idx};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Free an allocated edge.
 */
void free_crf_edge(crf_edge* edge) { free(edge); }

/**
 * Print out the string representation of an edge.
 */
void crf_edge_str(crf_edge* edge)
{
    printf("(%" PRIu64 " -> %" PRIu64 ")", edge->cluster_node_idx, edge->label_node_idx);
}

/**
 * Print out the internal representation of the edge.
 */
void crf_edge_repr(crf_edge* edge)
{
    printf("(cluster_node_idx: %" PRIu64 ", label_node_idx: %" PRIu64 ")", edge->cluster_node_idx,
           edge->label_node_idx);
}

#endif
