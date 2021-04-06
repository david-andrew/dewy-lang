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
        .edges = new_set()
    };
    return g;
}


/**
 * Print out a string representation of the GSS.
 */
void gss_str(gss* g)
{
    printf("GSS Nodes:\n");
    vect_str(g->nodes);
    printf("\nGSS Edges:\n");
    set_str(g->edges);
    printf("\n");
}


/**
 * Free the GSS's allocated memory. 
 */
void gss_free(gss* g)
{
    vect_free(g->nodes);
    set_free(g->edges);
    free(g);
}


/**
 * Print out a string representation of the GSS node index.
 */
void gss_idx_str(gss_idx* i)
{
    printf("(%zu, %zu)", i->nodes_idx, i->node_idx);
}


/**
 * Return a GSS edge structure.
 */
gss_edge* new_gss_edge(gss_idx parent, gss_idx child)
{
    gss_edge* e = malloc(sizeof(gss_edge));
    *e = (gss_edge){.parent=parent, .child=child};
    return e;
}


/**
 * Return a GSS edge wrapped in an object.
 */
obj* new_gss_edge_obj(gss_edge* e)
{
    obj* E = malloc(sizeof(obj));
    *E = (obj){.type=GSSEdge_t, .data=e};
    return E;
}


/**
 * Free the GSS edge structure.
 */
void gss_edge_free(gss_edge* e)
{
    free(e);
}


/**
 * Hash the data contained in the gss edge
 */
uint64_t gss_edge_hash(gss_edge* e)
{
    uint64_t data[] = {e->parent.nodes_idx, e->parent.node_idx, e->child.nodes_idx, e->child.node_idx};
    return hash_uint_sequence(data, sizeof(data) / sizeof(uint64_t));
}


/**
 * Determine if two GSS edges are equal.
 */
bool gss_edge_equals(gss_edge* left, gss_edge* right)
{
    return left->parent.nodes_idx == right->parent.nodes_idx
        && left->parent.node_idx == right->parent.node_idx
        && left->child.nodes_idx == right->child.nodes_idx
        && left->child.node_idx == right->child.node_idx;
}


/**
 * Print out a string representation of the GSS edge.
 */
void gss_edge_str(gss_edge* e)
{
    printf("["); gss_idx_str(&e->parent); printf(" -> "); gss_idx_str(&e->child); printf("]");
}


#endif