#ifndef GSS_H
#define GSS_H

#include <stdlib.h>

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

typedef struct {
    gss_idx parent;
    gss_idx child;
} gss_edge;


//GSS functions
gss* new_gss(size_t size_hint);
set* gss_get_nodes_set(gss* g, size_t nodes_idx);
uint64_t gss_get_node_state(gss* g, size_t nodes_idx, size_t node_idx);
gss_idx* gss_get_node_with_label(gss* g, size_t nodes_idx, uint64_t state_idx);
bool gss_does_edge_exist(gss* g, gss_idx* parent, gss_idx* child);
vect* gss_get_reachable(gss* g, gss_idx* root_idx, size_t length);
vect* gss_get_all_paths(gss* g, gss_idx* root_idx, size_t length);
void gss_get_all_paths_inner(gss* g, size_t length, vect* stack, vect* paths);
gss_idx* gss_add_node(gss* g, size_t nodes_idx, uint64_t state);
void gss_add_edge(gss* g, gss_idx* parent, gss_idx* child);
void gss_str(gss* g);
void gss_free(gss* g);


//GSS idx/edge functions
gss_idx gss_idx_struct(size_t nodes_idx, size_t node_idx);
gss_idx* new_gss_idx(size_t nodes_idx, size_t node_idx);
gss_idx* gss_idx_copy(gss_idx* i);
obj* new_gss_idx_obj(gss_idx* i);
void gss_idx_free(gss_idx* i); 
uint64_t gss_idx_hash(gss_idx* i);
bool gss_idx_equals(gss_idx* left, gss_idx* right);
void gss_idx_str(gss_idx* i);
gss_edge gss_edge_struct(gss_idx parent, gss_idx child);
gss_edge* new_gss_edge(gss_idx parent, gss_idx child);
obj* new_gss_edge_obj(gss_edge* e);
void gss_edge_free(gss_edge* e); 
uint64_t gss_edge_hash(gss_edge* e);
bool gss_edge_equals(gss_edge* left, gss_edge* right);
void gss_edge_str(gss_edge* e);


#endif