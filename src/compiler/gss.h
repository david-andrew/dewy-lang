#ifndef GSS_H
#define GSS_H

#include <stdlib.h>

// #include "object.h"
#include "vector.h"
#include "set.h"


// Graph Structured Stack
typedef struct {
    vect* nodes;    //vect<set<uint64>>
    dict* edges;    //dict<gss_idx, gss_idx>
} gss;


// coordinates of state nodes in the GSS
typedef struct {
    size_t nodes_idx;
    size_t node_idx;
} gss_idx;


//GSS functions
gss* new_gss(size_t size_hint);
set* gss_get_nodes_set(gss* g, size_t nodes_idx);
uint64_t gss_get_node_state(gss* g, size_t nodes_idx, size_t node_idx);
void gss_add_node(gss* g, size_t nodes_idx, uint64_t state);
void gss_str(gss* g);
void gss_free(gss* g);

vect* gss_get_reachable(gss* g, gss_idx* root_idx, size_t length);

//GSS edge functions
gss_idx* new_gss_idx(size_t nodes_idx, size_t node_idx);
gss_idx* gss_idx_copy(gss_idx* i);
obj* new_gss_idx_obj(gss_idx* i);
void gss_idx_free(gss_idx* i); 
uint64_t gss_idx_hash(gss_idx* i);
bool gss_idx_equals(gss_idx* left, gss_idx* right);
void gss_idx_str(gss_idx* i);



#endif