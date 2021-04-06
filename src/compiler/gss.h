#ifndef GSS_H
#define GSS_H

#include <stdlib.h>

// #include "object.h"
#include "vector.h"
#include "set.h"


// Graph Structured Stack
typedef struct {
    vect* nodes;
    set* edges;
} gss;


// coordinates of state nodes in the GSS
typedef struct {
    size_t nodes_idx;
    size_t node_idx;
} gss_idx;


// edges in the GSS
typedef struct {
    gss_idx parent;
    gss_idx child;
} gss_edge;


//GSS functions
gss* new_gss(size_t size_hint);
void gss_str(gss* g);
void gss_free(gss* g);

//GSS node functions?
//TBD if we need any special methods for gss_idx, or they only live in gss_edge
//gss_idx* new_gss_idx(size_t nodes_idx, size_t node_idx);
void gss_idx_str(gss_idx* i);

//GSS edge functions
gss_edge* new_gss_edge(gss_idx parent, gss_idx child);
obj* new_gss_edge_obj(gss_edge* e);
void gss_edge_free(gss_edge* e); 
uint64_t gss_edge_hash(gss_edge* e);
bool gss_edge_equals(gss_edge* left, gss_edge* right);
void gss_edge_str(gss_edge* e);



#endif