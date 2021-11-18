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
        .cluster_nodes = new_dict(),
        .label_nodes = new_set(),
    };
    return CRF;
}

/**
 * Free a call return forest.
 */
void crf_free(crf* CRF)
{
    dict_free(CRF->cluster_nodes);
    set_free(CRF->label_nodes);
    free(CRF);
}

/**
 * Print out the string representation of a CRF
 */
void crf_str(crf* CRF)
{
    printf("CRF: [\n");
    for (size_t i = 0; i < dict_size(CRF->cluster_nodes); i++)
    {
        obj cluster_node_obj, children_indices_obj;
        dict_get_at_index(CRF->cluster_nodes, i, &cluster_node_obj, &children_indices_obj);
        crf_cluster_node* cluster_node = cluster_node_obj.data;
        printf("    ");
        crf_cluster_node_str(cluster_node);
        set* children_indices = children_indices_obj.data;
        printf(set_size(children_indices) > 0 ? " -> " : "\n");
        for (size_t j = 0; j < set_size(children_indices); j++)
        {
            uint64_t* child_idx = set_get_at_index(children_indices, j)->data;
            crf_label_node* child_node = set_get_at_index(CRF->label_nodes, *child_idx)->data;
            printf(j == 0 ? "" : "        ");
            crf_label_node_str(child_node);
            printf("\n");
        }
    }
    printf("]\n");
}

/**
 * Insert a cluster node into the call return forest.
 */
uint64_t crf_add_cluster_node(crf* CRF, crf_cluster_node* node)
{
    size_t node_idx = dict_get_entries_index(CRF->cluster_nodes, &(obj){.type = CRFClusterNode_t, .data = node});
    obj k, v;
    if (!dict_get_at_index(CRF->cluster_nodes, node_idx, &k, &v))
    {
        // create a new entry for this node
        dict_set(CRF->cluster_nodes, crf_cluster_node_obj(node), new_set_obj(NULL));
    }
    else
    {
        // free the node as it already exists
        crf_cluster_node_free(node);
    }
    return node_idx;
}

uint64_t crf_add_label_node(crf* CRF, crf_label_node* node, uint64_t parent_idx);

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
void crf_cluster_node_free(crf_cluster_node* node) { free(node); }

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
void crf_label_node_free(crf_label_node* node) { free(node); }

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

#endif
