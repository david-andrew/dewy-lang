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
        int strlen = crf_cluster_node_strlen(cluster_node);
        set* children_indices = children_indices_obj.data;
        printf(set_size(children_indices) > 0 ? " -> " : "\n");
        for (size_t j = 0; j < set_size(children_indices); j++)
        {
            uint64_t* child_idx = set_get_at_index(children_indices, j)->data;
            crf_label_node* child_node = set_get_at_index(CRF->label_nodes, *child_idx)->data;
            if (j > 0)
                for (int k = 0; k < strlen + 8; k++)
                    putchar(' '); // 8 extra spaces for tab in front and space of the arrow
            crf_label_node_str(child_node);
            printf("\n");
        }
    }
    printf("]\n");
}

/**
 * Insert a cluster node into the call return forest.
 * Creates a copy of the node passed in
 */
uint64_t crf_add_cluster_node(crf* CRF, crf_cluster_node* node)
{
    size_t node_idx = dict_get_entries_index(CRF->cluster_nodes, &(obj){.type = CRFClusterNode_t, .data = node});
    obj k, v;
    if (!dict_get_at_index(CRF->cluster_nodes, node_idx, &k, &v))
    {
        // create a new entry for this node
        node_idx = dict_set(CRF->cluster_nodes, obj_copy(&(obj){CRFClusterNode_t, node}), new_set_obj(NULL));
    }
    return node_idx;
}

/**
 * Insert a label node into the call return forest.
 * Creates a copy of the node passed in
 */
uint64_t crf_add_label_node(crf* CRF, crf_label_node* node) //, uint64_t parent_idx)
{
    size_t node_idx = set_get_entries_index(CRF->label_nodes, &(obj){.type = CRFLabelNode_t, .data = node});
    obj* v = set_get_at_index(CRF->label_nodes, node_idx);
    if (v == NULL)
    {
        // create a new entry for this node
        node_idx = set_add(CRF->label_nodes, obj_copy(&(obj){CRFLabelNode_t, node}));
    }
    return node_idx;
}

/**
 * Insert an edge into the call return forest.
 */
void crf_add_edge(crf* CRF, uint64_t parent_idx, uint64_t child_idx)
{
    obj children_obj, k;
    dict_get_at_index(CRF->cluster_nodes, parent_idx, &k, &children_obj);
    set* children = children_obj.data;
    if (!set_contains(children, &(obj){.type = UInteger_t, .data = &child_idx}))
    {
        set_add(children, new_uint_obj(child_idx));
    }
}

/**
 * Create a new cluster node.
 */
crf_cluster_node* new_crf_cluster_node(uint64_t head_idx, uint64_t j)
{
    crf_cluster_node* node = malloc(sizeof(crf_cluster_node));
    *node = crf_cluster_node_struct(head_idx, j);
    return node;
}

/**
 * return a copy of the given cluster node
 */
crf_cluster_node* crf_cluster_node_copy(crf_cluster_node* node)
{
    return new_crf_cluster_node(node->head_idx, node->j);
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
obj* new_crf_cluster_node_obj(crf_cluster_node* node) { return new_obj(CRFClusterNode_t, node); }

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
 * Return the length of the string representation of a cluster node.
 */
int crf_cluster_node_strlen(crf_cluster_node* node)
{
    int length = 4; // for both parenthesis, the comma, and the space
    length += obj_strlen(metaparser_get_symbol(node->head_idx));
    length += snprintf(NULL, 0, "%" PRIu64, node->j);
    return length;
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
crf_label_node* new_crf_label_node(slot* label, uint64_t j)
{
    crf_label_node* node = malloc(sizeof(crf_label_node));
    *node = crf_label_node_struct(label, j);
    return node;
}

/**
 * return a copy of the given label node.
 */
crf_label_node* crf_label_node_copy(crf_label_node* node) { return new_crf_label_node(&node->label, node->j); }

/**
 * Return a stack allocated struct for a label node.
 */
inline crf_label_node crf_label_node_struct(slot* label, uint64_t j)
{
    return (crf_label_node){
        .label = *label,
        .j = j,
    };
}

/**
 * Return an object wrapped label node.
 */
obj* new_crf_label_node_obj(crf_label_node* node) { return new_obj(CRFLabelNode_t, node); }

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
    printf("(L: ");
    slot_repr(&node->label);
    printf(", j: %" PRIu64 ")", node->j);
}

/**
 * Create a new crf action tuple.
 */
crf_action_head* new_crf_action_head(uint64_t head_idx, uint64_t k)
{
    crf_action_head* action = malloc(sizeof(crf_action_head));
    *action = crf_action_head_struct(head_idx, k);
    return action;
}

/**
 * return a copy of the given crf action.
 */
crf_action_head* crf_action_head_copy(crf_action_head* node) { return new_crf_action_head(node->head_idx, node->k); }

/**
 * return a crf action struct
 */
inline crf_action_head crf_action_head_struct(uint64_t head_idx, uint64_t k)
{
    return (crf_action_head){
        .head_idx = head_idx,
        .k = k,
    };
}

/**
 * return an object wrapped crf action.
 */
obj* new_crf_action_head_obj(crf_action_head* action) { return new_obj(CRFActionHead_t, action); }

/**
 * Determine if two crf actions are equal.
 */
bool crf_action_head_equals(crf_action_head* left, crf_action_head* right)
{
    return left->head_idx == right->head_idx && left->k == right->k;
}

/**
 * return the hash value of a crf action.
 */
uint64_t crf_action_head_hash(crf_action_head* action)
{
    uint64_t seq[] = {action->head_idx, action->k};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}

/**
 * Free an allocated crf action.
 */
void crf_action_head_free(crf_action_head* action) { free(action); }

/**
 * Print out the string representation of a crf action.
 */
void crf_action_head_str(crf_action_head* action)
{
    printf("(");
    obj_str(metaparser_get_symbol(action->head_idx));
    printf(", %" PRIu64, action->k);
}

/**
 * Print out the internal representation of the crf action.
 */
void crf_action_head_repr(crf_action_head* action)
{
    printf("(head_idx: %" PRIu64 ", k: %" PRIu64 ")", action->head_idx, action->k);
}

/**
 * Check if an action is in the given action "set" (represented as a dict)
 */
bool crf_action_in_P(dict* P, crf_action_head* action, uint64_t j)
{
    // check if (X, k) is in P
    obj* j_set_obj = dict_get(P, &(obj){.type = CRFActionHead_t, .data = action});
    if (j_set_obj == NULL) return false;

    // check if j is in the set returned by P[(X, k)]
    set* j_set = j_set_obj->data;
    return set_contains(j_set, &(obj){.type = UInteger_t, .data = &j});
}

/**
 * Insert a new crf action into the given action "set" (represented as a dict)
 */
void crf_add_action_to_P(dict* P, crf_action_head* action, uint64_t j)
{
    // check if (X, k) is in P
    obj* j_set_obj = dict_get(P, &(obj){.type = CRFActionHead_t, .data = action});
    set* j_set;
    if (j_set_obj == NULL)
    {
        j_set = new_set();
        dict_set(P, obj_copy(&(obj){.type = CRFActionHead_t, .data = action}), new_set_obj(j_set));
    }
    else
    {
        j_set = j_set_obj->data;
    }

    // if j is not in the child set, add it
    if (!set_contains(j_set, &(obj){.type = UInteger_t, .data = &j})) { set_add(j_set, new_uint_obj(j)); }
}

/**
 * Print out the string representation of a crf action set.
 */
void crf_action_P_str(dict* P)
{
    printf("{");
    for (size_t i = 0; i < dict_size(P); i++)
    {
        // crf_action_head* action =
        obj k, v;
        dict_get_at_index(P, i, &k, &v);
        crf_action_head* action = k.data;
        set* j_set = v.data;
        for (size_t k = 0; k < set_size(j_set); k++)
        {

            crf_action_head_str(action);
            uint64_t* j = set_get_at_index(j_set, k)->data;
            printf(", %" PRIu64 ")", *j);
            if (i < dict_size(P) - 1 || k < set_size(j_set) - 1) printf(", ");
        }
    }
    printf("}");
}

#endif
