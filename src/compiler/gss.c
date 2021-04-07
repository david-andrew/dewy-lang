#ifndef GSS_C
#define GSS_C

#include <stdio.h>

#include "gss.h"
#include "utilities.h"


/**
 * Create a new Graph Structured Stack (GSS) structure.
 */
gss* new_gss(size_t size_hint)
{
    if (size_hint == 0) { size_hint = 8; }
    gss* g = malloc(sizeof(gss));
    *g = (gss){
        .nodes = new_vect_with_capacity(size_hint),
        .edges = new_dict()
    };
    return g;
}

/**
 * Get a specific set of nodes from the GSS.
 * Handles allocating empty sets if they do not exist yet.
 */
set* gss_get_nodes_set(gss* g, size_t nodes_idx)
{
    //create empty sets up to the requested one, if they don't exist yet.
    while (vect_size(g->nodes) <= nodes_idx)
    {
        vect_append(g->nodes, new_set_obj(NULL));
    }

    //return the requested set.
    return vect_get(g->nodes, nodes_idx)->data;
}


/**
 * Return the state label of the node at the given coordinates.
 */
uint64_t gss_get_node_state(gss* g, size_t nodes_idx, size_t node_idx)
{
    set* nodes = gss_get_nodes_set(g, nodes_idx);
    if (node_idx >= set_size(nodes))
    {
        printf("ERROR: no GSS node at index (%zu, %zu)\n", nodes_idx, node_idx);
        exit(1);
    }
    return *(uint64_t*)nodes->entries[node_idx].item->data;
}


/**
 * Insert a node into the GSS.
 */
void gss_add_node(gss* g, size_t nodes_idx, uint64_t state)
{
    set* U = gss_get_nodes_set(g, nodes_idx);
    obj* v = new_uint_obj(state);
    set_add(U, v);
}


/**
 * Print out a string representation of the GSS.
 */
void gss_str(gss* g)
{
    printf("GSS Nodes:\n");
    vect_str(g->nodes);
    printf("\nGSS Edges:\n");
    dict_str(g->edges);
    printf("\n");
}


/**
 * Free the GSS's allocated memory. 
 */
void gss_free(gss* g)
{
    vect_free(g->nodes);
    dict_free(g->edges);
    free(g);
}


/**
 * Perform a breadth first search from the root to find all nodes
 * that are the specified length away from the root.
 */
set* gss_get_reachable(gss* g, gss_idx* root, size_t length)
{
    
}


/**
 * Return a GSS index structure.
 */
gss_idx* new_gss_idx(size_t nodes_idx, size_t node_idx)
{
    gss_idx* i = malloc(sizeof(gss_idx));
    *i = (gss_idx){.nodes_idx=nodes_idx, .node_idx=node_idx};
    return i;
}


/**
 * Return a GSS index wrapped in an object.
 */
obj* new_gss_idx_obj(gss_idx* i)
{
    obj* I = malloc(sizeof(obj));
    *I = (obj){.type=GSSIndex_t, .data=i};
    return I;
}


/**
 * Free the GSS edge structure.
 */
void gss_idx_free(gss_idx* i)
{
    free(i);
}


/**
 * Hash the data contained in the gss edge
 */
uint64_t gss_idx_hash(gss_idx* i)
{
    uint64_t data[] = {i->nodes_idx, i->node_idx};
    return hash_uint_sequence(data, sizeof(data) / sizeof(uint64_t));
}


/**
 * Determine if two GSS edges are equal.
 */
bool gss_idx_equals(gss_idx* left, gss_idx* right)
{
    return left->nodes_idx == right->nodes_idx && left->node_idx == right->node_idx;
}


// /**
//  * Print out a string representation of the GSS edge.
//  */
// void gss_edge_str(gss_edge* e)
// {
//     printf("["); gss_idx_str(&e->parent); printf(" -> "); gss_idx_str(&e->child); printf("]");
// }


/**
 * Print out a string representation of the GSS node index.
 */
void gss_idx_str(gss_idx* i)
{
    printf("(%zu, %zu)", i->nodes_idx, i->node_idx);
}


#endif